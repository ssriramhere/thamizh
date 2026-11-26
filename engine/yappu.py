"""Yāppu: rule-based Tamil scansion.

letters (eḻuttu) -> acai (nēr / nirai) -> cīr (feet) -> taḷai (linkage)
-> toṭai (mōṉai, etukai) -> pā (meter).

Modern printings separate the words of a verse (pirittu eḻutiyatu). Meter
runs on the joined text, so the engine first re-applies the joining rules
that change the letter stream (puṇarcci), then finds the foot boundaries
that make a valid kuṟaḷ veṇpā, preferring boundaries at word breaks.

Everything here is deterministic. An AI model may explain the result,
never produce it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .tamil import HARD, PULLI, VOWELS, Letter, letters, normalize

NER, NIRAI = "nēr", "nirai"

FOOT_NAMES = {
    (NER,): "nāḷ", (NIRAI,): "malar",
    (NER, NER): "tēmā", (NIRAI, NER): "puḷimā",
    (NIRAI, NIRAI): "karuviḷam", (NER, NIRAI): "kūviḷam",
    (NER, NER, NER): "tēmāṅkāy", (NIRAI, NER, NER): "puḷimāṅkāy",
    (NIRAI, NIRAI, NER): "karuviḷaṅkāy", (NER, NIRAI, NER): "kūviḷaṅkāy",
    (NER, NER, NIRAI): "tēmāṅkaṉi", (NIRAI, NER, NIRAI): "puḷimāṅkaṉi",
    (NIRAI, NIRAI, NIRAI): "karuviḷaṅkaṉi", (NER, NIRAI, NIRAI): "kūviḷaṅkaṉi",
}

_MONAI_VOWEL_GROUPS = [set("அஆஐஔ"), set("இஈஎஏ"), set("உஊஒஓ")]
_MONAI_CONS_GROUPS = [set("சத"), set("ஞந"), set("மவ")]
_Y_GLIDE = set("இஈஐஎஏ")
_ALAPEDAI = {"ஆ": "அ", "ஈ": "இ", "ஊ": "உ", "ஏ": "எ", "ஓ": "ஒ", "ஐ": "இ", "ஔ": "உ"}
_SIGN_OF = {"அ": "", "ஆ": "ா", "இ": "ி", "ஈ": "ீ", "உ": "ு", "ஊ": "ூ", "எ": "ெ",
            "ஏ": "ே", "ஐ": "ை", "ஒ": "ொ", "ஓ": "ோ", "ஔ": "ௌ"}
_TR = {"க": "k", "ங": "ṅ", "ச": "c", "ஞ": "ñ", "ட": "ṭ", "ண": "ṇ", "த": "t", "ந": "n",
       "ப": "p", "ம": "m", "ய": "y", "ர": "r", "ல": "l", "வ": "v", "ழ": "ḻ", "ள": "ḷ",
       "ற": "ṟ", "ன": "ṉ", "ஜ": "j", "ஷ": "ṣ", "ஸ": "s", "ஹ": "h"}


# ---------------------------------------------------------------- acai

@dataclass
class Acai:
    kind: str
    letters: list[Letter]

    @property
    def text(self) -> str:
        return "".join(L.text for L in self.letters)

    @property
    def tr(self) -> str:
        return "".join(L.tr for L in self.letters)


def acai_of(ls: list[Letter]) -> list[Acai]:
    """Group letters into nēr / nirai.

    nēr   = one short or long syllable, plus any bare consonants after it
    nirai = a short syllable followed directly by a short or long one,
            plus any bare consonants after them
    """
    out: list[Acai] = []
    pending: list[Letter] = []   # silent letters, shown with the next unit
    i = 0
    while i < len(ls):
        L = ls[i]
        if L.kind == "s":
            pending.append(L)
            i += 1
            continue
        if L.kind in ("o", "a"):
            if out:
                out[-1].letters.append(L)
            else:
                out.append(Acai(NER, [L]))
            i += 1
            continue
        group = pending + [L]
        pending = []
        kind = NER
        if L.kind == "k" and i + 1 < len(ls) and ls[i + 1].kind in ("k", "n"):
            group.append(ls[i + 1])
            kind = NIRAI
            i += 2
        else:
            i += 1
        while i < len(ls) and ls[i].kind in ("o", "a"):
            group.append(ls[i])
            i += 1
        out.append(Acai(kind, group))
    if pending and out:
        out[-1].letters.extend(pending)
    return out


def split_acai(word: str) -> list[Acai]:
    return acai_of(letters(word))


# ---------------------------------------------------------------- sandhi

def _is_kurriyalukaram(word_letters: list[Letter]) -> bool:
    """Word-final u on a hard consonant, unless the word is just two short
    letters (then it is a full u, muṟṟiyalukaram)."""
    if len(word_letters) < 2:
        return False
    L = word_letters[-1]
    if not (L.kind == "k" and L.vowel == "உ" and L.consonant in HARD):
        return False
    if len(word_letters) == 2 and word_letters[0].kind == "k":
        return False
    return True


def _merge(cons: str, vowel_letter: Letter) -> Letter:
    v = vowel_letter.vowel
    text = cons + _SIGN_OF[v]
    return Letter(text, _TR[cons] + VOWELS[v][0], vowel_letter.kind, cons, v)


@dataclass
class Stream:
    """The joined letters of one line, with the word breaks that a reader
    of the printed text would expect."""
    letters: list[Letter]
    breaks: set[int]          # positions (letter index) where a word starts


def join_words(lines: list[list[str]], aytam_short: bool = False,
               written_ikaram: bool = False, u_ikaram: bool = False,
               ai_short: bool = False) -> tuple[list[Stream], list[str]]:
    """Apply the joining rules that change the letter stream.

    - kuṟṟiyalukaram before a vowel drops its u; the consonant takes the vowel
    - a bare consonant before a vowel takes the vowel (doubled after a lone
      short letter: kaṇ + il -> kaṇṇil)
    - a vowel before a vowel takes a y or v glide (no effect on meter, kept
      so the joined text reads correctly)
    Returns one stream per line and a list of notes on what was joined.
    """
    # A printed word can hold two words joined without a space
    # (தான்அமிழ்தம்). Split it before an inner vowel letter, unless that
    # vowel lengthens the long letter before it (aḷapeṭai: விடாஅ, தழீஇ).
    words = []   # (line, letters, starts_printed_word)
    for li, line in enumerate(lines):
        for w in line:
            ls = letters(w)
            start = 0
            for i in range(1, len(ls)):
                L = ls[i]
                if L.consonant or L.kind not in ("k", "n"):
                    continue
                prev = ls[i - 1]
                if prev.kind == "n" and _ALAPEDAI.get(prev.vowel) == L.vowel:
                    continue
                words.append((li, ls[start:i], start == 0))
                start = i
            words.append((li, ls[start:], start == 0))
    notes: list[str] = []
    for k in range(len(words) - 1):
        _, A, _ = words[k]
        lj, B, _ = words[k + 1]
        if u_ikaram and A and B and B[0].consonant == "ய" and _is_kurriyalukaram(A):
            # kuṟṟiyalikaram: the u becomes a short i that does not count
            cons = A[-1].consonant
            notes.append(f"{''.join(x.text for x in A)} + {''.join(x.text for x in B)}: u turns to a silent i")
            A.pop()
            B.insert(0, Letter(cons + "ி", _TR[cons] + "i", "s", cons, "இ"))
            continue
        if not A or not B or B[0].consonant or B[0].kind not in ("k", "n"):
            continue
        first = B[0]
        if _is_kurriyalukaram(A):
            cons = A[-1].consonant
            notes.append(f"{''.join(x.text for x in A)} + {''.join(x.text for x in B)}: u drops")
            A.pop()
            A.append(Letter(cons + PULLI, _TR[cons], "o", cons, ""))
            # the consonant now joins the next word
            A.pop()
            B[0] = _merge(cons, first)
        elif A[-1].kind == "o":
            cons = A[-1].consonant
            lone_short = len(A) == 2 and A[0].kind == "k"
            if lone_short:
                notes.append(f"{''.join(x.text for x in A)} + {''.join(x.text for x in B)}: consonant doubles")
            else:
                A.pop()
            B[0] = _merge(cons, first)
        else:
            glide = "ய" if (A[-1].vowel in _Y_GLIDE) else "வ"
            B[0] = _merge(glide, first)
    for _, W, printed_start in words:
        if aytam_short:
            for j, L in enumerate(W):
                if L.kind == "a":
                    W[j] = Letter(L.text, L.tr, "k", "", "")
        if written_ikaram and printed_start and len(W) > 1:
            L, M = W[0], W[1]
            if L.kind == "k" and L.vowel == "இ" and L.consonant in HARD and M.consonant == "ய":
                W[0] = Letter(L.text, L.tr, "s", L.consonant, L.vowel)
        if ai_short:
            for j, L in enumerate(W):
                if j > 0 and L.vowel in ("ஐ", "ஔ") and L.kind == "n":
                    W[j] = Letter(L.text, L.tr, "k", L.consonant, L.vowel)
    if aytam_short:
        notes.append("āytam counted as a short letter")
    if ai_short:
        notes.append("ai inside a word counted as short (aikārakkuṟukkam)")
    if u_ikaram:
        notes.append("final u before y read as a silent i (kuṟṟiyalikaram)")
    if written_ikaram:
        notes.append("written i before y read as a silent i (kuṟṟiyalikaram)")
    streams: list[Stream] = []
    for li in range(len(lines)):
        ls: list[Letter] = []
        br: set[int] = set()
        for wl, W, printed_start in words:
            if wl != li or not W:
                continue
            if printed_start:
                br.add(len(ls))
            ls.extend(W)
        streams.append(Stream(ls, br))
    return streams, notes


# ---------------------------------------------------------------- feet

@dataclass
class Foot:
    letters: list[Letter]
    acai: list[Acai]
    name: str
    final_u: bool = False

    @property
    def word(self) -> str:
        return "".join(L.text for L in self.letters)

    @property
    def tr(self) -> str:
        return "".join(L.tr for L in self.letters)

    def ending(self) -> str:
        n = len(self.acai)
        last = self.acai[-1].kind
        if n == 2:
            return "mā" if last == NER else "viḷam"
        if n == 3:
            return "kāy" if last == NER else "kaṉi"
        return "single"

    def starts_with(self) -> str:
        return self.acai[0].kind


def _final_u_unit(a: Acai) -> bool:
    if a.kind != NER or len(a.letters) != 1:
        return False
    L = a.letters[0]
    return L.kind == "k" and L.vowel == "உ" and bool(L.consonant)


def make_foot(ls: list[Letter], last_in_poem: bool = False) -> Foot:
    ac = acai_of(ls)
    pat = tuple(a.kind for a in ac)
    if last_in_poem and len(ac) == 2 and _final_u_unit(ac[-1]):
        return Foot(ls, ac, "kācu" if ac[0].kind == NER else "piṟappu", final_u=True)
    return Foot(ls, ac, FOOT_NAMES.get(pat, "?"))


def link_name(a: Foot, b: Foot) -> str:
    end, start = a.ending(), b.starts_with()
    if end == "mā":
        return "veṇṭaḷai" if start == NIRAI else "āciriyattaḷai"
    if end == "viḷam":
        return "veṇṭaḷai" if start == NER else "āciriyattaḷai"
    if end == "kāy":
        return "veṇṭaḷai" if start == NER else "kalittaḷai"
    if end == "kaṉi":
        return "oṉṟiya vañcittaḷai" if start == NIRAI else "oṉṟā vañcittaḷai"
    return "?"


def _inner_ok(f: Foot) -> bool:
    n = len(f.acai)
    return n == 2 or (n == 3 and f.acai[-1].kind == NER)


def _end_ok(f: Foot) -> bool:
    return f.name in ("nāḷ", "malar", "kācu", "piṟappu")


def _segmentations(st: Stream, n_feet: int):
    """All ways to cut a line into n feet; a foot may not start with a bare consonant."""
    ls = st.letters
    cand = [i for i in range(1, len(ls)) if ls[i].kind not in ("o", "a")]
    for cuts in combinations(cand, n_feet - 1):
        bounds = [0, *cuts, len(ls)]
        yield [ls[bounds[j]:bounds[j + 1]] for j in range(n_feet)], set(cuts)


def _cost(cuts: set[int], st: Stream) -> int:
    natural = st.breaks - {0}
    return len(cuts ^ natural)


# ---------------------------------------------------------------- scan

@dataclass
class Scan:
    lines: list[list[Foot]]
    links: list[dict]
    meter: str
    ok: bool
    checks: list[dict] = field(default_factory=list)
    monai: list[dict] = field(default_factory=list)
    etukai: dict | None = None
    notes: list[str] = field(default_factory=list)
    moved: int = 0            # foot boundaries that differ from the word breaks

    def as_dict(self) -> dict:
        return {
            "meter": self.meter, "ok": self.ok, "checks": self.checks,
            "lines": [[{
                "text": f.word, "tr": f.tr, "foot": f.name, "final_u": f.final_u,
                "acai": [{"kind": a.kind, "text": a.text, "tr": a.tr} for a in f.acai],
            } for f in line] for line in self.lines],
            "links": self.links, "monai": self.monai, "etukai": self.etukai,
            "joins": self.notes, "moved": self.moved,
        }


def _checks(lines: list[list[Foot]]) -> list[dict]:
    feet = [f for l in lines for f in l]
    shape = [len(l) for l in lines]
    bad_feet = [f.word for f in feet[:-1] if not _inner_ok(f)]
    bad_links = [f"{a.word} → {b.word}" for a, b in zip(feet, feet[1:]) if link_name(a, b) != "veṇṭaḷai"]
    return [
        {"id": "shape", "ok": shape == [4, 3], "text": f"Two lines of 4 and 3 feet (found {' + '.join(map(str, shape))})"},
        {"id": "feet", "ok": not bad_feet, "text": "Every foot but the last has two units, or three ending in nēr" + (f" (not: {', '.join(bad_feet)})" if bad_feet else "")},
        {"id": "links", "ok": not bad_links, "text": f"All {max(len(feet) - 1, 0)} linkages are veṇṭaḷai" + (f" (not: {'; '.join(bad_links)})" if bad_links else "")},
        {"id": "end", "ok": bool(feet) and _end_ok(feet[-1]), "text": f"Ends in nāḷ, malar, kācu or piṟappu (found {feet[-1].name if feet else '—'})"},
    ]


def _same_monai(x: Letter, y: Letter) -> bool:
    if x.consonant and y.consonant:
        return x.consonant == y.consonant or any(x.consonant in g and y.consonant in g for g in _MONAI_CONS_GROUPS)
    if not x.consonant and not y.consonant:
        return x.vowel == y.vowel or any(x.vowel in g and y.vowel in g for g in _MONAI_VOWEL_GROUPS)
    return False


def _toTai(scan: Scan, original_first_letters: list[Letter]) -> None:
    for li, line in enumerate(scan.lines):
        if not line:
            continue
        first = line[0].letters[0]
        hits = [fi for fi, f in enumerate(line) if fi > 0 and _same_monai(first, f.letters[0])]
        if hits:
            scan.monai.append({"line": li, "feet": [0] + hits})
    if len(scan.lines) == 2 and all(len(l) and len(l[0].letters) > 1 for l in scan.lines):
        a, b = scan.lines[0][0].letters, scan.lines[1][0].letters
        if a[0].kind == b[0].kind and a[1].consonant and a[1].consonant == b[1].consonant:
            scan.etukai = {"letter": a[1].consonant}


def monai_etukai(text: str) -> tuple[list[dict], dict | None]:
    """Mōṉai and etukai, read off the printed words of each line."""
    lines = [l.split(" ") for l in normalize(text).split("\n") if l.strip()]
    monai = []
    for li, words in enumerate(lines):
        firsts = [letters(w)[0] for w in words if letters(w)]
        hits = [i for i in range(1, len(firsts)) if _same_monai(firsts[0], firsts[i])]
        if hits:
            monai.append({"line": li, "words": [0] + hits})
    etukai = None
    if len(lines) == 2:
        a, b = letters(lines[0][0]), letters(lines[1][0])
        if len(a) > 1 and len(b) > 1 and a[0].kind == b[0].kind and a[1].consonant and a[1].consonant == b[1].consonant:
            etukai = {"letter": a[1].consonant}
    return monai, etukai


def scan_kural(text: str) -> Scan:
    """Scan a couplet and test it as a kuṟaḷ veṇpā."""
    raw = [l.split(" ") for l in normalize(text).split("\n") if l.strip()]
    flags = ["u_ikaram", "written_ikaram", "ai_short", "aytam_short"]
    result = None
    for n in range(len(flags) + 1):
        for combo in combinations(flags, n):
            r = _scan_with(raw, **{f: True for f in combo})
            if r.ok:
                result = r
                break
        if result:
            break
    result = result or _scan_with(raw)
    result.monai, result.etukai = monai_etukai(text)
    return result


def _scan_with(raw: list[list[str]], **opts) -> Scan:
    streams, notes = join_words(raw, **opts)
    best = None
    if len(streams) == 2:
        l1 = []
        for segs, cuts in _segmentations(streams[0], 4):
            feet = [make_foot(s) for s in segs]
            if all(_inner_ok(f) for f in feet) and all(link_name(a, b) == "veṇṭaḷai" for a, b in zip(feet, feet[1:])):
                l1.append((feet, _cost(cuts, streams[0])))
        l2 = []
        for segs, cuts in _segmentations(streams[1], 3):
            feet = [make_foot(s, last_in_poem=(j == 2)) for j, s in enumerate(segs)]
            if all(_inner_ok(f) for f in feet[:2]) and _end_ok(feet[2]) and all(link_name(a, b) == "veṇṭaḷai" for a, b in zip(feet[:2], feet[1:2])):
                l2.append((feet, _cost(cuts, streams[1])))
        for f1, c1 in l1:
            for f2, c2 in l2:
                if link_name(f1[-1], f2[0]) != "veṇṭaḷai":
                    continue
                if best is None or c1 + c2 < best[2]:
                    best = (f1, f2, c1 + c2)
    if best:
        lines = [best[0], best[1]]
        moved = best[2]
        ok = True
    else:
        # no valid reading: show the feet at the word breaks, as printed
        lines = []
        for li, st in enumerate(streams):
            cuts = sorted(st.breaks - {0})
            bounds = [0, *cuts, len(st.letters)]
            segs = [st.letters[bounds[j]:bounds[j + 1]] for j in range(len(bounds) - 1)]
            lines.append([make_foot(s, last_in_poem=(li == len(streams) - 1 and j == len(segs) - 1)) for j, s in enumerate(segs)])
        moved = 0
        ok = False
    feet = [f for l in lines for f in l]
    links = [{"from": a.word, "to": b.word, "name": link_name(a, b)} for a, b in zip(feet, feet[1:])]
    scan = Scan(lines, links, "kuṟaḷ veṇpā" if ok else "not a regular kuṟaḷ veṇpā", ok, _checks(lines), notes=notes, moved=moved)
    _toTai(scan, [])
    return scan


# ---------------------------------------------------------------- re-joining

def rejoin(parts: list[str]) -> set[str]:
    """Join word parts by the common joining rules and return the possible
    results. Used to check a proposed word split: the split is accepted
    only if one of these equals the printed word.
    """
    results = {""}
    for part in parts:
        B0 = letters(part)
        nxt = set()
        for acc in results:
            A = letters(acc)
            B = list(B0)
            plain = acc + part
            nxt.add(plain)
            if not A or not B:
                continue
            first = B[0]
            if not first.consonant and first.kind in ("k", "n"):
                if A[-1].kind == "k" and A[-1].vowel == "உ" and A[-1].consonant and len(A) > 1:
                    # a final u drops before a vowel (உய்வு + உண்டாம் -> உய்வுண்டாம்)
                    cons = A[-1].consonant
                    nxt.add("".join(x.text for x in A[:-1]) + _merge(cons, first).text + "".join(x.text for x in B[1:]))
                if _is_kurriyalukaram(A):
                    cons = A[-1].consonant
                    nxt.add("".join(x.text for x in A[:-1]) + _merge(cons, first).text + "".join(x.text for x in B[1:]))
                if A[-1].kind == "o":
                    cons = A[-1].consonant
                    joined = _merge(cons, first).text + "".join(x.text for x in B[1:])
                    nxt.add("".join(x.text for x in A[:-1]) + joined)       # கடல் + ஐ -> கடலை
                    nxt.add("".join(x.text for x in A) + joined)            # கண் + இல் -> கண்ணில்
                if A[-1].kind in ("k", "n") and A[-1].vowel:
                    for g in ("ய", "வ"):
                        nxt.add(acc + _merge(g, first).text + "".join(x.text for x in B[1:]))
            elif first.consonant in HARD:
                nxt.add(acc + first.consonant + PULLI + part)               # doubling: நன்றி + கண் -> நன்றிக்கண்
            if A[-1].kind == "o" and A[-1].consonant == "ம" and first.consonant:
                # ம் changes to the nasal of the next consonant
                nasal = {"க": "ங", "ச": "ஞ", "த": "ந", "ப": "ம", "ட": "ண", "ற": "ன"}.get(first.consonant)
                if nasal:
                    nxt.add(acc[:-2] + nasal + PULLI + part)
            if A[-1].kind == "o" and A[-1].consonant in ("ல", "ள", "ன", "ண") and first.consonant in HARD:
                # ல் ன் -> ற், ள் ண் -> ட் before a hard consonant (தன் + காத்து -> தற்காத்து)
                swap = {"ல": "ற", "ன": "ற", "ள": "ட", "ண": "ட"}[A[-1].consonant]
                nxt.add(acc[:-2] + swap + PULLI + part)
            if A[-1].kind == "o" and A[-1].consonant in ("ல", "ள", "ன", "ண") and first.consonant == "த":
                # the த changes too: ல் + த -> ற்ற (முதல் + து -> முதற்று), ன் + த -> ன்ற,
                # ள் + த -> ட்ட, ண் + த -> ண்ட
                pre, t = {"ல": ("ற", "ற"), "ன": ("ன", "ற"), "ள": ("ட", "ட"), "ண": ("ண", "ட")}[A[-1].consonant]
                rest = first.text.replace("த", t, 1) + "".join(x.text for x in B[1:])
                nxt.add(acc[:-2] + pre + PULLI + rest)
        results = nxt
    return results
