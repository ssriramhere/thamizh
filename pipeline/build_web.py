"""Build the site's data files from data/build/kural_text.json.

web/data/kural/index.json        books, chapters, and the chapter of every couplet
web/data/kural/<chapter>.json    the ten couplets of one chapter: text, letters,
                                 transliteration, scansion, and any AI layers
                                 found in data/ai/kural/<n>.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.tamil import letters, translit  # noqa: E402
from engine.yappu import scan_kural  # noqa: E402

OUT = ROOT / "web/data/kural"
AI = ROOT / "data/ai/kural"
_TF = ROOT / "data/build/kural_timings.json"
TIMINGS = json.loads(_TF.read_text()) if _TF.exists() else {}   # word timings of the recitation
_WF = ROOT / "data/build/kural_words.json"
WORDS = json.loads(_WF.read_text()) if _WF.exists() else {}


def reading(k: dict) -> dict:
    """The couplet with its words separated (AI, verified by re-joining)."""
    sep = WORDS.get(str(k["n"]))
    lines = sep["lines"] if sep else [l.split(" ") for l in k["text"].split("\n")]
    return {"verified": bool(sep and sep["verified"]), "separated": bool(sep),
            "lines": [[{"ta": w, "tr": translit(w)} for w in line] for line in lines]}


def couplet(k: dict) -> dict:
    lines = k["text"].split("\n")
    scan = scan_kural(k["text"])
    rec = {
        "n": k["n"],
        "chapter": k["chapter"],
        "lines": lines,
        "tr": translit(k["text"]).split("\n"),
        "words": [[{"ta": w, "tr": translit(w), "letters": [L.as_dict() for L in letters(w)]}
                   for w in line.split(" ")] for line in lines],
        "scan": scan.as_dict(),
        "reading": reading(k),
        "source": {"chosen_by": k["chosen_by"], "agree": k["agree"], "of": k["of"]},
    }
    t = TIMINGS.get(str(k["n"]), {})
    if t.get("male") or t.get("female"):
        rec["timing"] = {v: t[v] for v in ("male", "female") if t.get(v)}
    ai = AI / f"{k['n']}.json"
    if ai.exists():
        rec["ai"] = json.loads(ai.read_text())
    return rec


def main() -> None:
    kurals = json.loads((ROOT / "data/build/kural_text.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    # Books and chapters only. The grouping of chapters into iyals differs
    # between commentators, so it is left out.
    books: dict[int, dict] = {}
    for k in kurals:
        b = books.setdefault(k["paal"], {"n": k["paal"], "ta": k["paal_ta"], "tr": translit(k["paal_ta"]), "chapters": {}})
        b["chapters"].setdefault(k["chapter"], {"n": k["chapter"], "ta": k["chapter_ta"], "tr": translit(k["chapter_ta"]),
                                                "first": k["n"], "last": k["n"]})["last"] = k["n"]
    index = {
        "count": len(kurals),
        "books": [{**b, "chapters": list(b["chapters"].values())} for b in books.values()],
        "chapter_of": {str(k["n"]): k["chapter"] for k in kurals},
    }
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")))
    by_ch: dict[int, list] = {}
    for k in kurals:
        by_ch.setdefault(k["chapter"], []).append(couplet(k))
    for ch, items in by_ch.items():
        (OUT / f"{ch}.json").write_text(json.dumps({"chapter": ch, "kurals": items}, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote index and {len(by_ch)} chapter files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
