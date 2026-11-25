"""Separate the words of each couplet (pada pirippu) with Gemini on Vertex AI.

Some digital editions print a couplet divided by metrical feet rather than
by words (தாள்சேர்ந்தார்க் கல்லால்), or join words without a space
(அன்புஈனும்). For readers and for the word glosses we want each word on its
own, in its full form (தாள் சேர்ந்தார்க்கு அல்லால்).

The model proposes the separated words for each line. The answer is kept
only if the words, re-joined by the joining rules, give back the printed line
letter for letter (spaces aside). A line that fails is retried, then kept as
printed.

Output: data/build/kural_words.json  {"<n>": {"lines": [[word, ...], [word, ...]], "model": ...}}

Usage (same environment as gemini_kural.py):
  python pipeline/gemini_words.py 1-20
  python pipeline/gemini_words.py all --skip-existing --workers 6
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.tamil import normalize  # noqa: E402
from engine.yappu import rejoin  # noqa: E402

OUT = ROOT / "data/build/kural_words.json"

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "lines": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}},
    },
    "required": ["lines"],
}

INSTRUCTIONS = """You separate the words of a Tirukkuṟaḷ couplet for learners (pada pirippu).

The couplet may be printed divided by metrical feet, or with words run together. Rewrite each line as its separate words, each word in its full form as it would stand alone, with any joining undone: a dropped final u restored (சேர்ந்தார்க் கல்லால் -> சேர்ந்தார்க்கு அல்லால்), a glide letter removed (முதல வெழுத்து -> முதல எழுத்து), a doubled consonant undone where it belongs to the join.

Separate words only; do not split a word into stem and suffix, and keep compounds that are written as one word in ordinary Tamil. Keep the original word order and every word of the line. Do not change spelling otherwise and do not modernise.

Return JSON: {"lines": [[words of line 1], [words of line 2]]}."""


def nospace(s: str) -> str:
    return unicodedata.normalize("NFC", s).replace(" ", "").strip()


def line_ok(printed: str, words: list[str]) -> bool:
    if not words:
        return False
    target = nospace(printed)
    parts = [nfc for nfc in (unicodedata.normalize("NFC", w).strip() for w in words) if nfc]
    if len(parts) > 8:
        return False
    joined = rejoin(parts)
    if target in joined:
        return True
    # a line may end on a doubled hard consonant that belongs to the next line's
    # first word (துப்பார்க்குத் / துப்பாக்கி)
    if target.endswith("\u0BCD") and len(target) > 2 and target[-2] in "கசடதபற" and target[:-2] in joined:
        return True
    return False


async def one(client, model: str, k: dict, sem: asyncio.Semaphore, stats: dict, results: dict) -> None:
    from google.genai import types
    printed = k["text"].split("\n")
    async with sem:
        feedback = ""
        best = None
        for attempt in range(3):
            resp = None
            for tries in range(6):
                try:
                    resp = await client.aio.models.generate_content(
                        model=model,
                        contents=f"Couplet {k['n']}:\n{k['text']}" + feedback,
                        config=types.GenerateContentConfig(
                            system_instruction=INSTRUCTIONS,
                            response_mime_type="application/json",
                            response_schema=SCHEMA,
                            temperature=0.1,
                        ),
                    )
                    break
                except Exception as e:
                    msg = str(e)
                    if any(c in msg for c in ("429", "RESOURCE_EXHAUSTED", "503", "500")):
                        await asyncio.sleep(min(60, 5 * 2 ** tries))
                        continue
                    break
            if resp is None:
                continue
            u = resp.usage_metadata
            if u:
                stats["in"] += u.prompt_token_count or 0
                stats["out"] += (u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
            try:
                lines = json.loads(resp.text)["lines"]
            except Exception:
                feedback = "\n\nYour previous answer was not valid JSON."
                continue
            if len(lines) != len(printed):
                feedback = f"\n\nGive exactly {len(printed)} lines."
                continue
            oks = [line_ok(p, ws) for p, ws in zip(printed, lines)]
            # keep the good lines, fall back to the printed words for the rest
            merged = [ws if ok else p.split(" ") for p, ws, ok in zip(printed, lines, oks)]
            if best is None or sum(oks) > best[1]:
                best = (merged, sum(oks))
            if all(oks):
                break
            bad = [p for p, ok in zip(printed, oks) if not ok]
            feedback = ("\n\nThese lines did not re-join to the printed text: " + json.dumps(bad, ensure_ascii=False) +
                        ". Keep every letter of the original; only undo joins.")
        if best is None:
            stats["failed"].append(k["n"])
            return
        results[str(k["n"])] = {"lines": best[0], "verified": best[1] == len(printed), "model": model}
        save(results)
        stats["ok"] += 1
        if best[1] != len(printed):
            stats["partial"] += 1


_OUT_PATH = [OUT]


def save(results: dict) -> None:
    p = _OUT_PATH[0]
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(sorted(results.items(), key=lambda x: int(x[0]))), ensure_ascii=False, indent=1))
    tmp.replace(p)


def parse_range(spec: str) -> list[int]:
    if spec == "all":
        return list(range(1, 1331))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("range")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview"))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    _OUT_PATH[0] = out

    from google import genai
    from google.genai import types as _t
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
                          http_options=_t.HttpOptions(timeout=180_000))
    kurals = {k["n"]: k for k in json.loads((ROOT / "data/build/kural_text.json").read_text())}
    results = json.loads(out.read_text()) if out.exists() else {}
    todo = [n for n in parse_range(args.range) if not (args.skip_existing and str(n) in results)]
    stats = {"ok": 0, "partial": 0, "failed": [], "in": 0, "out": 0}
    sem = asyncio.Semaphore(args.workers)
    t = time.time()
    await asyncio.gather(*(one(client, args.model, kurals[n], sem, stats, results) for n in todo))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(sorted(results.items(), key=lambda x: int(x[0]))), ensure_ascii=False, indent=1))
    print(f"model {args.model}: {stats['ok']} done ({stats['partial']} with a line kept as printed), "
          f"{len(stats['failed'])} failed, {stats['in']:,} tokens in, {stats['out']:,} out, {time.time() - t:.0f}s")
    if stats["failed"]:
        print("  failed:", stats["failed"])


if __name__ == "__main__":
    asyncio.run(main())
