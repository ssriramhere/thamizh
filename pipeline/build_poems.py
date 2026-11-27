"""Build the site's data for the Caṅkam anthologies.

    python pipeline/build_poems.py

For each text in data/build/<text>.json writes:
  web/data/<text>/index.json   one row per poem: number, first line, poet,
                               tiṇai, speaker or tuṟai (for the list page)
  web/data/<text>/<n>.json     the poem: lines, transliteration, colophon,
                               āciriyappā scan and the AI layers if present
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.akaval import scan_akaval  # noqa: E402
from engine.tamil import translit  # noqa: E402

TEXTS = {
    "kuruntokai": {"title": "Kuṟuntokai", "ta": "குறுந்தொகை", "printed_feet": True},
    "purananuru": {"title": "Puṟanāṉūṟu", "ta": "புறநானூறு", "printed_feet": False},
}
# Speakers of the akam poems, as the colophons name them.
SPEAKERS = {
    "தலைவி": "the heroine (talaivi)", "தலைமகள்": "the heroine (talaivi)", "தலைவன்": "the hero (talaivaṉ)",
    "தலைமகன்": "the hero (talaivaṉ)", "தலைன்": "the hero (talaivaṉ)", "தோழி": "her friend (tōḻi)",
    "செவிலி": "the foster-mother (cevili)", "நற்றாய்": "the mother (naṟṟāy)", "பரத்தை": "the courtesan (parattai)",
    "பாங்கன்": "the hero's companion (pāṅkaṉ)", "கண்டோர்": "onlookers (kaṇṭōr)", "பாணன்": "the bard (pāṇaṉ)",
    "அறிவர்": "the wise ones (aṟivar)", "காமக்கிழத்தி": "the concubine (kāmakkiḻatti)",
}


def speaker_en(sp: str) -> str | None:
    for k, v in SPEAKERS.items():
        if sp.startswith(k):
            return v
    return None


def gloss_sync(lines: list[str], ai_lines: list[dict]) -> list[list[list[str]]]:
    """For each printed word (in recitation order, gaps skipped), the AI words it holds,
    as [surface, gloss] pairs. Printed groups and separated words are matched by letters."""
    import difflib
    out = []
    for printed, al in zip(lines, ai_lines):
        pw = [w for w in printed.split() if w != "…"]
        aw = [w for w in al.get("words", []) if w.get("surface") and w["surface"] != "…"]
        ps, as_ = "".join(pw), "".join(w["surface"] for w in aw)
        owner = []                       # which AI word each letter of as_ belongs to
        for i, w in enumerate(aw):
            owner += [i] * len(w["surface"])
        m = {}
        for a, b, n in difflib.SequenceMatcher(None, ps, as_, autojunk=False).get_matching_blocks():
            for k in range(n):
                m[a + k] = b + k
        pos = 0
        for w in pw:
            hit = sorted({owner[m[i]] for i in range(pos, pos + len(w)) if i in m})
            pos += len(w)
            out.append([[aw[i]["surface"], aw[i].get("gloss", "")] for i in hit])
    return out


def cap(s: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in s.split())


def first_text(s: str | None) -> str:
    return (s or "").split(";")[0].strip()


def main() -> None:
    for slug, meta in TEXTS.items():
        src = ROOT / f"data/build/{slug}.json"
        if not src.exists():
            continue
        poems = json.loads(src.read_text())
        tf = ROOT / f"data/build/{slug}_timings.json"
        timings = json.loads(tf.read_text()) if tf.exists() else {}
        out = ROOT / "web/data" / slug
        out.mkdir(parents=True, exist_ok=True)
        rows, with_ai = [], 0
        for p in poems:
            scan = scan_akaval(p["lines"], meta["printed_feet"])
            ai_f = ROOT / "data/ai" / slug / f"{p['n']}.json"
            ai = json.loads(ai_f.read_text()) if ai_f.exists() else None
            if ai:
                with_ai += 1
                ai = {k: ai[k] for k in ("lines", "literal", "translation", "modern", "explanation", "model") if k in ai}
            col = {k: p.get(k) for k in ("tinai", "tinai_ta", "speaker_ta", "turai_ta", "poet_ta", "addressed_ta") if p.get(k)}
            if p.get("speaker_ta"):
                col["speaker_en"] = speaker_en(p["speaker_ta"])
            if p.get("poet_ta"):
                col["poet_tr"] = cap(translit(first_text(p["poet_ta"])))
            rec = {"text": slug, "n": p["n"], "lines": p["lines"], "tr": [translit(l) for l in p["lines"]],
                   "colophon": col, "scan": scan, "ai": ai}
            t = timings.get(str(p["n"]), {})
            nwords = sum(1 for l in p["lines"] for w in l.split() if w != "…")
            if t.get("male") and t.get("female") and len(t["male"]) == nwords == len(t["female"]):
                from timing_fix import smooth
                ws = [w for l in p["lines"] for w in l.split() if w != "…"]
                rec["timing"] = {v: smooth(ws, t[v]) for v in ("male", "female")}
                if ai and len(ai.get("lines", [])) == len(p["lines"]):
                    rec["sync"] = gloss_sync(p["lines"], ai["lines"])
            (out / f"{p['n']}.json").write_text(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
            rows.append({"n": p["n"], "first": p["lines"][0], "poet": col.get("poet_tr", ""), "tinai": p.get("tinai", ""),
                         "tinai_ta": p.get("tinai_ta", ""), "speaker": col.get("speaker_en") or translit(p.get("speaker_ta", "")) or "",
                         "turai": cap(translit(first_text(p.get("turai_ta")))) if p.get("turai_ta") else "",
                         "lines": len(p["lines"]), "meter": scan["meter"], "ai": bool(ai)})
        (out / "index.json").write_text(json.dumps({"text": slug, "title": meta["title"], "ta": meta["ta"],
                                                    "count": len(rows), "poems": rows}, ensure_ascii=False, separators=(",", ":")))
        print(f"{slug}: {len(rows)} poems, {with_ai} with AI layers")


if __name__ == "__main__":
    main()
