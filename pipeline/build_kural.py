"""Build the Tirukkuṟaḷ text from several digital sources.

Each source is a separate open dataset of the 1,330 couplets. They agree
on most couplets but each carries its own typos. For every couplet we
take the reading most sources share; when the sources disagree, the meter
decides: a reading that scans as a kuṟaḷ veṇpā beats one that doesn't.
Couplets that no reading scans are listed for human review.

Only the Tamil text of the couplets is taken from the sources, along with
the division into books and chapters. No commentary or translation is used.

Usage: python pipeline/build_kural.py SRC_DIR
  SRC_DIR holds clones of the source repositories (see data/sources/README.md).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.tamil import normalize  # noqa: E402
from engine.yappu import scan_kural  # noqa: E402


def fix_au(text: str) -> str:
    """Some sources type ௌ as ெ followed by ள (கெளவை for கௌவை)."""
    return re.sub(r"ெள(?=[க-ஹ\s]|$)", "ௌ", text)


def clean(line1: str, line2: str) -> str:
    return fix_au(normalize(line1.strip() + "\n" + line2.strip()))


def load_sources(src: Path) -> dict[str, dict[int, str]]:
    out: dict[str, dict[int, str]] = {}

    d = json.loads((src / "tk/thirukkural.json").read_text())["kural"]
    out["tk120404/thirukkural"] = {k["Number"]: clean(k["Line1"], k["Line2"]) for k in d}

    con = sqlite3.connect(src / "pypi/x/thirukkural/kural.db")
    out["thirukkural (PyPI)"] = {n: clean(*(t.split("\n") + [""])[:2]) for n, t in con.execute("select no, kural_ta from kural")}

    d = json.loads((src / "nramc_thirukkural-api/public/data/canonical/kurals.ta.json").read_text())["items"]
    out["nramc/thirukkural-api"] = {k["number"]: clean(*k["lines"][:2]) for k in d}

    d = json.loads((src / "prodev717_openthirukkural/allKural.json").read_text())["allKural"]
    out["prodev717/openthirukkural"] = {k["number"]: clean(k["line1"], k["line2"]) for k in d}

    d = json.loads((src / "vijayanandrp_Thirukkural-Tamil-Dataset/data/all_kural.json").read_text())
    v = {}
    for rec in d:
        m = re.search(r"குறள் எண்:\s*(\d+)", rec)
        t = re.search(r"குறள் - (.+?)\n\s*(.+?)\n", rec)
        if m and t:
            v[int(m.group(1))] = clean(t.group(1), t.group(2))
    out["vijayanandrp/Thirukkural-Tamil-Dataset"] = v
    return out


def structure(src: Path) -> dict[int, dict]:
    con = sqlite3.connect(src / "pypi/x/thirukkural/kural.db")
    rows = con.execute("select no, paal_no, paal_ta, iyal_no, iyal_ta, adigaaram_no, adigaaram_ta from kural")
    out = {r[0]: {"paal": r[1], "paal_ta": r[2], "iyal": r[3], "iyal_ta": r[4],
                  "chapter": r[5], "chapter_ta": r[6]} for r in rows}
    # Books by chapter: 1–38 aṟam, 39–108 poruḷ, 109–133 kāmam. (One source
    # files chapter 38, ūḻ, under poruḷ; the other sources and the
    # tradition place it in aṟam.)
    books = {1: "அறத்துப்பால்", 2: "பொருட்பால்", 3: "காமத்துப்பால்"}
    for rec in out.values():
        b = 1 if rec["chapter"] <= 38 else 2 if rec["chapter"] <= 108 else 3
        rec["paal"], rec["paal_ta"] = b, books[b]
    return out


def main(src: Path) -> None:
    sources = load_sources(src)
    corrections = json.loads((ROOT / "data/corrections.json").read_text())
    struct = structure(src)
    names = list(sources)
    kurals, review, disagreements = [], [], 0
    for n in range(1, 1331):
        votes = Counter(s[n] for s in sources.values() if n in s and s[n].count("\n") == 1)
        ranked = votes.most_common()
        if len(ranked) > 1:
            disagreements += 1
        chosen, scan, how = None, None, ""
        for text, count in ranked:
            sc = scan_kural(text)
            if sc.ok:
                chosen, scan = text, sc
                how = "majority" if text == ranked[0][0] else "meter"
                break
        fix = corrections.get(str(n))
        if fix and (chosen is None or fix.get("override")):
            sc = scan_kural(fix["text"])
            if sc.ok:
                chosen, scan = normalize(fix["text"]), sc
                how = f"correction ({fix['status']})"
        if chosen is None:
            chosen = ranked[0][0]
            scan = scan_kural(chosen)
            how = "unresolved"
            review.append({"n": n, "text": chosen,
                           "readings": [{"text": t, "sources": c} for t, c in ranked],
                           "problems": [c["text"] for c in scan.checks if not c["ok"]]})
        kurals.append({"n": n, **struct[n], "text": chosen, "chosen_by": how,
                       "agree": votes[chosen], "of": sum(votes.values())})
    out = ROOT / "data/build"
    out.mkdir(parents=True, exist_ok=True)
    (out / "kural_text.json").write_text(json.dumps(kurals, ensure_ascii=False, indent=1))
    (out / "kural_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1))
    by = Counter(k["chosen_by"] for k in kurals)
    print(f"sources: {', '.join(names)}")
    print(f"couplets where sources disagree: {disagreements}")
    print("chosen:", dict(by))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
