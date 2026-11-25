"""Tamil script: split text into letters, classify them, transliterate.

A "letter" (eḻuttu) here is one written unit: an independent vowel, a
consonant with its inherent a, a consonant with a vowel sign, a bare
consonant (with puḷḷi), or the āytam ஃ.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

VOWELS = {
    "அ": ("a", "k"), "ஆ": ("ā", "n"), "இ": ("i", "k"), "ஈ": ("ī", "n"),
    "உ": ("u", "k"), "ஊ": ("ū", "n"), "எ": ("e", "k"), "ஏ": ("ē", "n"),
    "ஐ": ("ai", "n"), "ஒ": ("o", "k"), "ஓ": ("ō", "n"), "ஔ": ("au", "n"),
}
SIGNS = {
    "ா": ("ā", "n"), "ி": ("i", "k"), "ீ": ("ī", "n"), "ு": ("u", "k"),
    "ூ": ("ū", "n"), "ெ": ("e", "k"), "ே": ("ē", "n"), "ை": ("ai", "n"),
    "ொ": ("o", "k"), "ோ": ("ō", "n"), "ௌ": ("au", "n"),
}
CONSONANTS = {
    "க": "k", "ங": "ṅ", "ச": "c", "ஞ": "ñ", "ட": "ṭ", "ண": "ṇ", "த": "t",
    "ந": "n", "ப": "p", "ம": "m", "ய": "y", "ர": "r", "ல": "l", "வ": "v",
    "ழ": "ḻ", "ள": "ḷ", "ற": "ṟ", "ன": "ṉ", "ஜ": "j", "ஷ": "ṣ", "ஸ": "s",
    "ஹ": "h",
}
PULLI = "்"
AYTAM = "ஃ"
HARD = set("கசடதபற")  # vallinam

# kinds: "k" kuṟil (short), "n" neṭil (long), "o" oṟṟu (bare consonant), "a" āytam
KIND_LABEL = {
    "k": "Short letter (kuṟil) · 1 beat",
    "n": "Long letter (neṭil) · 2 beats",
    "o": "Consonant alone (oṟṟu) · ½ beat",
    "a": "Āytam · ½ beat",
}


@dataclass
class Letter:
    text: str        # the written letter, e.g. "கு"
    tr: str          # ISO 15919, e.g. "ku"
    kind: str        # k / n / o / a
    consonant: str   # base consonant letter ("" for a vowel or āytam)
    vowel: str       # vowel letter ("" for oṟṟu / āytam)

    def as_dict(self) -> dict:
        return {"g": self.text, "tr": self.tr, "kind": self.kind,
                "c": self.consonant, "v": self.vowel}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # split decomposed two-part vowel signs are already composed by NFC;
    # keep only Tamil, spaces and newlines
    text = re.sub(r"[^஀-௿\s]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.strip().split("\n"))


_SIGN_TO_VOWEL = {
    "ா": "ஆ", "ி": "இ", "ீ": "ஈ", "ு": "உ", "ூ": "ஊ", "ெ": "எ", "ே": "ஏ",
    "ை": "ஐ", "ொ": "ஒ", "ோ": "ஓ", "ௌ": "ஔ",
}


def letters(word: str) -> list[Letter]:
    out: list[Letter] = []
    i = 0
    w = word
    while i < len(w):
        ch = w[i]
        if ch in VOWELS:
            tr, kind = VOWELS[ch]
            out.append(Letter(ch, tr, kind, "", ch))
            i += 1
        elif ch == AYTAM:
            out.append(Letter(ch, "ḵ", "a", "", ""))
            i += 1
        elif ch in CONSONANTS:
            base = CONSONANTS[ch]
            nxt = w[i + 1] if i + 1 < len(w) else ""
            # க்ஷ conjunct is written as two letters; treat each normally
            if nxt == PULLI:
                out.append(Letter(ch + PULLI, base, "o", ch, ""))
                i += 2
            elif nxt in SIGNS:
                vtr, kind = SIGNS[nxt]
                out.append(Letter(ch + nxt, base + vtr, kind, ch, _SIGN_TO_VOWEL[nxt]))
                i += 2
            else:
                out.append(Letter(ch, base + "a", "k", ch, "அ"))
                i += 1
        else:
            i += 1  # stray mark: skip
    return out


def translit(text: str) -> str:
    """ISO 15919 transliteration of a Tamil string, word by word."""
    lines = []
    for line in normalize(text).split("\n"):
        words = []
        for w in line.split(" "):
            words.append("".join(L.tr for L in letters(w)))
        lines.append(" ".join(words))
    return "\n".join(lines)
