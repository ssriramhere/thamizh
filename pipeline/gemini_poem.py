"""Generate the AI layers for each Caṅkam poem with Gemini on Vertex AI.

One request per poem. The model separates the words of each line (pada
pirippu), splits each word into its parts, glosses them, and writes a literal
rendering, a translation, the poem in today's Tamil, and an explanation.

Checks before saving (a failed check is retried, up to three times):
  - each line's separated words join back to the printed line by the joining
    rules (engine.yappu.rejoin); a line that never passes is kept as printed
  - each word's parts join back to the word; a word that never passes is kept
    as one part and marked split_unverified
  - no field is empty

Usage:
  python pipeline/gemini_poem.py kuruntokai 1-401 --workers 12 --skip-existing
  python pipeline/gemini_poem.py purananuru all
Writes data/ai/<text>/<n>.json.
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

from engine.yappu import rejoin  # noqa: E402

TITLES = {"kuruntokai": "Kuṟuntokai", "purananuru": "Puṟanāṉūṟu"}
GAP = "…"

WORD = {
    "type": "OBJECT",
    "properties": {
        "surface": {"type": "STRING"},
        "parts": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "text": {"type": "STRING"}, "lemma": {"type": "STRING"}, "gloss": {"type": "STRING"}},
            "required": ["text", "lemma", "gloss"]}},
        "gloss": {"type": "STRING"},
    },
    "required": ["surface", "parts", "gloss"],
}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "lines": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "words": {"type": "ARRAY", "items": WORD}}, "required": ["words"]}},
        "literal": {"type": "STRING"},
        "translation": {"type": "STRING"},
        "modern": {"type": "STRING"},
        "explanation": {"type": "STRING"},
    },
    "required": ["lines", "literal", "translation", "modern", "explanation"],
}

INSTRUCTIONS = """You are a careful scholar of classical Tamil preparing study material for learners of every level.

Work only from the Tamil text given and the colophon details given with it (tiṇai, speaker or theme, poet). Do not quote, cite or follow any commentator or modern interpretation, and do not attribute the poem to any religious, philosophical or political school. Where a word has more than one accepted sense, choose the one that best fits this poem and say so briefly in the explanation.

Return JSON with:
- lines: one entry per printed line, in order. For each line, list its words separated (pada pirippu): each word in its full form as it would stand alone, with any joining undone (a dropped final u restored, a glide letter removed, a doubled consonant undone where it belongs to the join). The text may be printed divided by metrical feet, so a printed group can hold parts of two words. Keep every word and the word order; do not change spelling otherwise and do not modernise. Keep a gap marked … as a word "…".
  For each word give "surface" (the separated word), its parts (stem, suffixes, joined words, each in its own full form; the parts must give back the word when joined by the regular joining rules, and if you are unsure give the word as a single part), a dictionary form ("lemma") and a short English gloss for each part, and a short English gloss for the whole word.
- literal: an English rendering that follows the Tamil word order, line by line, lines separated by " / ".
- translation: a clear, natural English translation of the whole poem. Keep the poem's own images.
- modern: the poem rewritten as plain modern written Tamil prose.
- explanation: four to seven sentences for a learner: who is speaking to whom and in what situation, what the poem says, how its images carry the feeling (for an akam poem, how they belong to its landscape, its tiṇai), and the key words. No references to commentators.
"""


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def nospace(s: str) -> str:
    return nfc(s).replace(" ", "")


def line_ok(printed: str, words: list[str]) -> bool:
    if GAP in printed:
        return True     # a damaged line: not checked
    parts = [nfc(w) for w in words if nfc(w)]
    if not parts or len(parts) > 10:
        return False
    target = nospace(printed)
    joined = rejoin(parts)
    if target in joined:
        return True
    # a line may end on a doubled hard consonant that belongs to the next line,
    # or on ற் / ட் for ல் ன் / ள் ண் changed before the next line's hard consonant
    if target.endswith("்") and len(target) > 2 and target[-2] in "கசடதபற" and target[:-2] in joined:
        return True
    if target.endswith(("ற்", "ட்")):
        alts = {"ற": ("ல", "ன"), "ட": ("ள", "ண")}[target[-2]]
        return any(target[:-2] + a + "்" in joined for a in alts)
    return False


def word_ok(w: dict) -> bool:
    if nfc(w.get("surface")) == GAP:
        return True
    parts = [nfc(p.get("text")) for p in w.get("parts") or []]
    return bool(parts) and nfc(w.get("surface")) in rejoin(parts)


def context(text: str, p: dict) -> str:
    bits = [f"{TITLES[text]} {p['n']}"]
    if p.get("tinai_ta"):
        bits.append(f"tiṇai: {p['tinai_ta']}")
    if p.get("speaker_ta"):
        bits.append(f"speaker: {p['speaker_ta']}")
    if p.get("turai_ta"):
        bits.append(f"tuṟai (theme): {p['turai_ta']}")
    if p.get("poet_ta"):
        bits.append(f"poet: {p['poet_ta']}")
    if p.get("addressed_ta"):
        bits.append(f"addressed to: {p['addressed_ta']}")
    return "; ".join(bits)


def prompt_for(text: str, p: dict) -> str:
    lines = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(p["lines"]))
    return f"{context(text, p)}.\n\nThe poem, {len(p['lines'])} lines:\n{lines}\n"


def check(p: dict, data: dict) -> list[str]:
    problems = []
    got = data.get("lines") or []
    if len(got) != len(p["lines"]):
        return [f"there must be exactly {len(p['lines'])} lines, one per printed line"]
    for i, (printed, ln) in enumerate(zip(p["lines"], got)):
        ws = ln.get("words") or []
        if not line_ok(printed, [w.get("surface", "") for w in ws]):
            problems.append(f"line {i + 1}: the separated words do not join back to the printed line «{printed}»")
        for w in ws:
            if not word_ok(w):
                problems.append(f"line {i + 1}: parts of {w.get('surface')} do not join back to it")
            if not w.get("gloss"):
                problems.append(f"line {i + 1}: no gloss for {w.get('surface')}")
    for f in ("literal", "translation", "modern", "explanation"):
        if not (data.get(f) or "").strip():
            problems.append(f"empty {f}")
    return problems


def salvage(p: dict, data: dict) -> dict | None:
    """Keep what passed: lines that don't rejoin fall back to the printed groups
    with one part each; words whose split fails keep one part."""
    got = data.get("lines") or []
    if len(got) != len(p["lines"]) or any(not (data.get(f) or "").strip() for f in ("literal", "translation", "modern", "explanation")):
        return None
    for printed, ln in zip(p["lines"], got):
        ws = ln.get("words") or []
        if not line_ok(printed, [w.get("surface", "") for w in ws]):
            ln["words"] = [{"surface": g, "parts": [{"text": g, "lemma": g, "gloss": ""}], "gloss": "", "split_unverified": True}
                           for g in printed.split()]
            ln["as_printed"] = True
            continue
        for w in ws:
            if not word_ok(w):
                w["parts"] = [{"text": w["surface"], "lemma": w["surface"], "gloss": w.get("gloss", "")}]
                w["split_unverified"] = True
    return data


async def one(client, model, text, p, out, sem, stats):
    from google.genai import types
    async with sem:
        if (out / f"{p['n']}.json").exists():
            return      # done meanwhile by another run
        last, data = [], None
        for attempt in range(3):
            resp = None
            for tries in range(6):
                try:
                    resp = await client.aio.models.generate_content(
                        model=model,
                        contents=prompt_for(text, p) + (f"\nYour previous answer had these problems, fix them: {last[:12]}" if last else ""),
                        config=types.GenerateContentConfig(system_instruction=INSTRUCTIONS, response_mime_type="application/json",
                                                           response_schema=SCHEMA, temperature=0.2),
                    )
                    break
                except Exception as e:
                    msg = str(e)
                    if any(x in msg for x in ("429", "RESOURCE_EXHAUSTED", "503", "500", "timed out", "Timeout")):
                        await asyncio.sleep(min(60, 5 * 2 ** tries))
                        continue
                    last = [f"request failed: {msg[:200]}"]
                    break
            if resp is None:
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
            last = check(p, data)
            if not last or all("parts of" in x for x in last):
                break       # a word split that doesn't join is kept as one part; not worth another request
        if last and data is not None:
            data = salvage(p, data)
            if data is not None:
                stats["salvaged"] += 1
                last = []
        if last or data is None:
            stats["failed"].append({"n": p["n"], "problems": last[:3]})
            return
        data["model"] = model
        data["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{p['n']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
        stats["ok"] += 1


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", choices=sorted(TITLES))
    ap.add_argument("range")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"))
    ap.add_argument("--out")
    args = ap.parse_args()
    out = Path(args.out or ROOT / "data/ai" / args.text)
    poems = {p["n"]: p for p in json.loads((ROOT / f"data/build/{args.text}.json").read_text())}
    if args.range == "all":
        want = sorted(poems)
    else:
        want = []
        for part in args.range.split(","):
            a, _, b = part.partition("-")
            want.extend(range(int(a), int(b or a) + 1))
    todo = [n for n in want if n in poems and not (args.skip_existing and (out / f"{n}.json").exists())]

    from google import genai
    from google.genai import types as _t
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
                          http_options=_t.HttpOptions(timeout=300_000))
    stats = {"ok": 0, "failed": [], "in": 0, "out": 0, "salvaged": 0}
    sem = asyncio.Semaphore(args.workers)
    t = time.time()
    await asyncio.gather(*(one(client, args.model, args.text, poems[n], out, sem, stats) for n in todo))
    print(f"{args.text} · {args.model}: {stats['ok']} saved ({stats['salvaged']} with parts kept as printed), "
          f"{len(stats['failed'])} failed, {stats['in']:,} tokens in, {stats['out']:,} out, {time.time() - t:.0f}s")
    for f in stats["failed"]:
        print("  failed", f["n"], f["problems"])


if __name__ == "__main__":
    asyncio.run(main())
