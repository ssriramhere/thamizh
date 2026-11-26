"""Scansion for āciriyappā (akaval), the meter of the Caṅkam poems.

What is checked:
  - feet: mostly two-unit feet (iyaṟcīr); three-unit feet ending in nēr
    (veṇcīr) are allowed now and then; three-unit feet ending in nirai
    (vañcicīr) belong to vañci lines
  - lines: four feet (aḷavaṭi) as the rule; a three-foot line (cintaṭi)
    as the second-to-last line makes it nēricai āciriyappā, three-foot
    lines inside the poem make it iṇaikkuṟaḷ āciriyappā, all four-foot
    lines make it nilaimaṇṭila āciriyappā
  - linkage: āciriyattaḷai (nēr meets nēr, nirai meets nirai) should be the
    most common; the others are counted
  - ending: the poem traditionally ends on ē; ō, ī, āy, ai and eṉ also occur

Kuṟuntokai is printed with spaces at foot boundaries, so the feet are the
printed groups. Puṟanāṉūṟu is printed word by word, so its lines are joined
and cut into feet the way the Kuṟaḷ scan does it.
"""
from __future__ import annotations

from collections import Counter

from engine.tamil import letters
from engine.yappu import (Foot, _cost, _segmentations, join_words, link_name,
                          make_foot)

ENDINGS = ("ஏ", "ஓ", "ஈ", "ஐ")


def _ending(last_foot: Foot) -> str | None:
    ls = last_foot.letters
    real = [L for L in ls if L.kind != "s"]
    if not real:
        return None
    L = real[-1]
    if L.kind in ("k", "n") and L.vowel in ENDINGS:
        return L.vowel
    if L.kind == "o" and len(real) > 1:
        prev = real[-2]
        if L.consonant == "ய" and prev.vowel == "ஆ":
            return "ஆய்"
        if L.consonant == "ன" and prev.vowel == "எ":
            return "என்"
    return None


def _foot_ok(f: Foot) -> bool:
    return len(f.acai) == 2 or (len(f.acai) == 3)


def _foot_score(f: Foot) -> int:
    """Lower is better: two-unit feet are the norm."""
    n = len(f.acai)
    if n == 2:
        return 0
    if n == 3:
        return 1 if f.ending() == "kāy" else 2
    return 4


def _cut_line(stream, n_feet: int):
    best = None
    for segs, cuts in _segmentations(stream, n_feet):
        feet = [make_foot(s) for s in segs]
        score = sum(_foot_score(f) for f in feet) * 3 + _cost(cuts, stream)
        if best is None or score < best[0]:
            best = (score, feet)
    return best


def scan_akaval(lines: list[str], printed_feet: bool) -> dict:
    words = [l.split() for l in lines]
    if printed_feet:
        feet_lines = [[make_foot(letters(w)) for w in ws] for ws in words]
    else:
        streams, _ = join_words(words)
        feet_lines = []
        for st, ws in zip(streams, words):
            options = []
            for n in sorted({4, 3, 2, max(2, min(len(ws), 5))}):
                if n <= len([L for L in st.letters if L.kind not in ("o", "a")]):
                    r = _cut_line(st, n)
                    if r:
                        # prefer four feet unless the line clearly is shorter
                        options.append((r[0] + (0 if n == 4 else 4), r[1]))
            feet_lines.append(min(options, key=lambda x: x[0])[1] if options else [])
    counts = [len(fl) for fl in feet_lines]
    feet = [f for fl in feet_lines for f in fl]
    kinds = Counter("iyaṟcīr" if len(f.acai) == 2 else ("veṇcīr" if f.ending() == "kāy" else
                    ("vañcicīr" if len(f.acai) == 3 else "other")) for f in feet)
    links = Counter(link_name(a, b) for a, b in zip(feet, feet[1:]))
    end = _ending(feet[-1]) if feet else None
    n = len(counts)
    if all(c == 4 for c in counts):
        form = "nilaimaṇṭila āciriyappā"
    elif n >= 3 and counts[-2] == 3 and all(c == 4 for i, c in enumerate(counts) if i != n - 2):
        form = "nēricai āciriyappā"
    elif n >= 3 and counts[0] == 4 and counts[-1] == 4 and all(c in (2, 3, 4) for c in counts):
        form = "iṇaikkuṟaḷ āciriyappā"
    else:
        form = None
    vanci_lines = sum(1 for fl in feet_lines if len(fl) == 2 and any(len(f.acai) == 3 for f in fl))
    checks = [
        {"name": "lines", "ok": n >= 3, "detail": f"{n} lines"},
        {"name": "feet per line", "ok": counts.count(4) >= 0.5 * n and all(2 <= c <= 6 for c in counts),
         "detail": ", ".join(f"{c}×{k}" for k, c in sorted(Counter(counts).items(), reverse=True)) + " feet"},
        {"name": "foot types", "ok": kinds.get("iyaṟcīr", 0) >= 0.6 * max(1, len(feet)),
         "detail": ", ".join(f"{k} {c}" for k, c in kinds.most_common())},
        {"name": "linkage", "ok": (links.get("kalittaḷai", 0) + links.get("oṉṟiya vañcittaḷai", 0)
                                   + links.get("oṉṟā vañcittaḷai", 0)) <= 0.25 * max(1, sum(links.values())),
         "detail": ", ".join(f"{k} {c}" for k, c in links.most_common())},
        {"name": "ending", "ok": end is not None, "detail": f"ends on {end}" if end else "no usual ending"},
    ]
    ok = all(c["ok"] for c in checks)
    if ok:
        meter = form or ("āciriyappā with vañci lines" if vanci_lines else "āciriyappā")
    else:
        meter = "āciriyappā with vañci lines" if vanci_lines and checks[4]["ok"] else "not a regular āciriyappā"
    if any(c == 5 for c in counts):
        checks.append({"name": "long lines", "ok": True,
                       "detail": f"{counts.count(5)} five-foot line{'s' if counts.count(5) > 1 else ''} (neṭilaṭi)"})
    return {
        "meter": meter, "ok": ok, "checks": checks, "ending": end,
        "lines": [[{"text": f.word, "tr": f.tr, "foot": f.name,
                    "acai": [{"kind": a.kind, "text": a.text, "tr": a.tr} for a in f.acai]} for f in fl]
                  for fl in feet_lines],
    }
