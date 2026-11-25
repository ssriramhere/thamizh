"""Generate the AI layers for each couplet with Gemini on Vertex AI.

For every couplet the model gets the Tamil text, its printed words and the
engine's scansion, and returns:
  - words:  each printed word split into its parts (the parts must join back
            to the printed word letter for letter), with a dictionary form and
            an English gloss for each part
  - literal:      a word-order English rendering
  - translation:  a readable English translation
  - modern:       the couplet in today's Tamil prose
  - explanation:  a short explanation for a learner

Every answer is checked before it is saved; a failed check is retried.
The meter is never asked of the model.

Setup:
  pip install google-genai
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
  export GOOGLE_CLOUD_PROJECT=your-project
  export GOOGLE_CLOUD_LOCATION=global          # or us-central1
  export GEMINI_MODEL=gemini-3.5-flash         # any Vertex Gemini model id

Usage:
  python pipeline/gemini_kural.py 1-10         # a range
  python pipeline/gemini_kural.py all --skip-existing --workers 8
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.yappu import rejoin, scan_kural  # noqa: E402

OUT = ROOT / "data/ai/kural"

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "words": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "surface": {"type": "STRING"},
                    "parts": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "text": {"type": "STRING"},
                                "lemma": {"type": "STRING"},
                                "gloss": {"type": "STRING"},
                            },
                            "required": ["text", "lemma", "gloss"],
                        },
                    },
                    "gloss": {"type": "STRING"},
                },
                "required": ["surface", "parts", "gloss"],
            },
        },
        "literal": {"type": "STRING"},
        "translation": {"type": "STRING"},
        "modern": {"type": "STRING"},
        "explanation": {"type": "STRING"},
    },
    "required": ["words", "literal", "translation", "modern", "explanation"],
}

INSTRUCTIONS = """You are a careful scholar of classical Tamil preparing study material for learners of every level.

Work only from the Tamil text given. Do not quote, cite or follow any commentator or modern interpretation, and do not attribute the couplet to any religious, philosophical or political school. Where a word has more than one accepted sense, choose the one that best fits this couplet and its chapter, and say so briefly in the explanation.

Return JSON with:
- words: one entry per printed word, in order, with "surface" exactly as printed. Split each surface into its parts (stem, suffixes, joined words), writing each part in its own full form (எழுத்தெல்லாம் -> எழுத்து + எல்லாம்). The parts must give back the surface when joined by the regular joining rules (puṇarcci); if you are unsure, give the word as a single part. For each part give its dictionary form ("lemma") and a short English gloss. Give the whole word a short English gloss too.
- literal: an English rendering that follows the Tamil word order.
- translation: a clear, natural English translation of the couplet, in one or two sentences. Keep the couplet's own images.
- modern: the couplet rewritten as plain modern written Tamil prose.
- explanation: three to five sentences for a learner: what the couplet says and how its key words carry the meaning. No references to commentators.
"""


def prompt_for(k: dict) -> str:
    scan = scan_kural(k["text"])
    words = [w for line in k["text"].split("\n") for w in line.split(" ")]
    meter = " | ".join(" ".join(f.word for f in line) for line in scan.lines)
    return (
        f"Tirukkuṟaḷ {k['n']}, chapter {k['chapter']} ({k['chapter_ta']}).\n\n"
        f"Couplet:\n{k['text']}\n\n"
        f"Printed words, in order ({len(words)}): {json.dumps(words, ensure_ascii=False)}\n\n"
        f"For reference, the metrical division into feet: {meter}\n"
    )


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def check(k: dict, data: dict) -> list[str]:
    problems = []
    words = [w for line in k["text"].split("\n") for w in line.split(" ")]
    got = data.get("words") or []
    if [nfc(w.get("surface", "")) for w in got] != [nfc(w) for w in words]:
        problems.append("words do not match the printed words")
    for w in got:
        parts = [nfc(p.get("text", "")) for p in w.get("parts") or []]
        if not parts or nfc(w.get("surface", "")) not in rejoin(parts):
            problems.append(f"parts of {w.get('surface')} do not join back to it")
        if not w.get("gloss"):
            problems.append(f"no gloss for {w.get('surface')}")
    for f in ("literal", "translation", "modern", "explanation"):
        if not (data.get(f) or "").strip():
            problems.append(f"empty {f}")
    return problems


async def one(client, model: str, k: dict, sem: asyncio.Semaphore, stats: dict) -> None:
    from google.genai import types
    async with sem:
        last = []
        for attempt in range(3):
            resp = None
            for tries in range(6):
                try:
                    resp = await client.aio.models.generate_content(
                        model=model,
                        contents=prompt_for(k) + (f"\nYour previous answer had these problems, fix them: {last}" if last else ""),
                        config=types.GenerateContentConfig(
                            system_instruction=INSTRUCTIONS,
                            response_mime_type="application/json",
                            response_schema=SCHEMA,
                            temperature=0.2,
                        ),
                    )
                    break
                except Exception as e:  # rate limits and transient errors: back off and retry
                    msg = str(e)
                    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "500" in msg:
                        await asyncio.sleep(min(60, 5 * 2 ** tries))
                        continue
                    last = [f"request failed: {msg[:200]}"]
                    break
            if resp is None:
                last = last or ["rate limited; gave up"]
                continue
            u = resp.usage_metadata
            if u:
                stats["in"] += u.prompt_token_count or 0
                stats["out"] += (u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
            try:
                data = json.loads(resp.text)
            except Exception:
                last = ["the answer was not valid JSON"]
                continue
            last = check(k, data)
            if not last:
                data["model"] = model
                data["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                OUT.mkdir(parents=True, exist_ok=True)
                (OUT / f"{k['n']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
                stats["ok"] += 1
                return
        if data_ok_but_splits(last) and isinstance(locals().get("data"), dict):
            for w in data["words"]:
                parts = [nfc(p.get("text", "")) for p in w.get("parts") or []]
                if not parts or nfc(w.get("surface", "")) not in rejoin(parts):
                    w["parts"] = [{"text": w["surface"], "lemma": w["surface"], "gloss": w["gloss"]}]
                    w["split_unverified"] = True
            if not check(k, data):
                data["model"] = model
                data["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                OUT.mkdir(parents=True, exist_ok=True)
                (OUT / f"{k['n']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
                stats["ok"] += 1
                stats["collapsed"] += 1
                return
        stats["failed"].append({"n": k["n"], "problems": last})


def data_ok_but_splits(problems: list[str]) -> bool:
    return bool(problems) and all("do not join back" in p for p in problems)


def parse_range(spec: str) -> list[int]:
    if spec == "all":
        return list(range(1, 1331))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return out


async def main() -> None:
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("range")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"))
    ap.add_argument("--out", default=str(OUT), help="output folder (default data/ai/kural)")
    args = ap.parse_args()
    OUT = Path(args.out)

    from google import genai
    client = genai.Client(vertexai=True,
                          project=os.environ["GOOGLE_CLOUD_PROJECT"],
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
    kurals = {k["n"]: k for k in json.loads((ROOT / "data/build/kural_text.json").read_text())}
    todo = [n for n in parse_range(args.range) if not (args.skip_existing and (OUT / f"{n}.json").exists())]
    stats = {"ok": 0, "failed": [], "in": 0, "out": 0, "collapsed": 0}
    sem = asyncio.Semaphore(args.workers)
    t = time.time()
    await asyncio.gather(*(one(client, args.model, kurals[n], sem, stats) for n in todo))
    print(f"model {args.model}: {stats['ok']} saved, {len(stats['failed'])} failed, "
          f"{stats['collapsed']} with a split left unverified, {stats['in']:,} tokens in, {stats['out']:,} out, {time.time() - t:.0f}s")
    for f in stats["failed"]:
        print("  failed", f["n"], f["problems"][:3])


if __name__ == "__main__":
    asyncio.run(main())
