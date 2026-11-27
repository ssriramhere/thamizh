"""Import Caṅkam anthologies from Project Madurai etexts.

    python pipeline/import_pm.py SRC_DIR

Reads pm0110.html (Kuṟuntokai) and pm0057.html (Puṟanāṉūṟu) and writes
data/build/<text>.json: one record per poem with its number, lines, tiṇai,
tuṟai or speaker, poet, and (Puṟanāṉūṟu) the person addressed. The modern
titles of the Puṟanāṉūṟu poems and the editor's notes are dropped, and so is
the editorial punctuation, so the poem is shown as the words alone.

The header page of each etext is copied unchanged to
data/sources/projectmadurai/, as Project Madurai's terms ask.
"""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TINAI = {"குறிஞ்சி": "kuṟiñci", "முல்லை": "mullai", "மருதம்": "marutam", "நெய்தல்": "neytal", "பாலை": "pālai"}
PURAM = {"வெட்சி": "veṭci", "கரந்தை": "karantai", "வஞ்சி": "vañci", "காஞ்சி": "kāñci", "உழிஞை": "uḻiñai",
         "நொச்சி": "nocci", "தும்பை": "tumpai", "வாகை": "vākai", "பாடாண்": "pāṭāṇ", "பொதுவியல்": "potuviyal",
         "கைக்கிளை": "kaikkiḷai", "பெருந்திணை": "peruntiṇai", "நொட்சி": "nocci", "வஞ்சியும்": "vañci"}


def text_of(path: Path) -> str:
    s = path.read_text(encoding="utf-8-sig", errors="replace")
    s = re.sub(r"<(style|script|head)\b.*?</\1>", "", s, flags=re.I | re.S)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    return unicodedata.normalize("NFC", s)


def header(t: str, start: str) -> str:
    return t[: t.find(start)].strip() + "\n"


def bare(line: str) -> str:
    """The words of a line without editorial punctuation."""
    line = line.replace("·", "ஃ")                          # the etext writes āytam as a middle dot
    line = re.sub(r"[`_¨¦¡]", "", line)                     # stray marks from the etext's old encoding
    line = re.sub(r"(?:\.\s*){3,}|\?{3,}", " … ", line)   # gaps in the manuscript
    line = re.sub(r"[;:!?,.\"'“”‘’()\[\]—–-]", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def kuruntokai(t: str) -> list[dict]:
    body = t[t.find("\n1. "):]
    poems = []
    for m in re.finditer(r"\n(\d{1,3})\.\s+(\S+)\s*-\s*([^\n]+?)\s*\n(.*?)\n\s*-\s*([^\n]+?)\s*(?=\n)", body, re.S):
        n, tinai, speaker, verse, poet = m.groups()
        lines = [bare(x) for x in verse.strip().split("\n") if bare(x)]
        poems.append({"n": int(n), "tinai": TINAI.get(tinai, tinai), "tinai_ta": tinai,
                      "speaker_ta": speaker.strip(), "poet_ta": poet.strip().rstrip("."), "lines": lines})
    return poems


KEYS = {"பாடியவர்": "poet_ta", "பாடியவன்": "poet_ta", "பாடியோர்": "poet_ta", "பாடினோர்": "poet_ta",
        "பாடப்பட்டோன்": "addressed_ta", "பாடப்பட்டோர்": "addressed_ta", "திணை": "tinai_ta",
        "துறை": "turai_ta", "சிறப்பு": None, "குறிப்பு": None}
KEY_RE = "|".join(KEYS)


def purananuru(t: str) -> list[dict]:
    body = t[t.find("\n1."):]
    body = body[: body.find("This page was first put up")]
    # Find each number in order, so a number inside a note can't start a poem.
    marks, pos = [], 0
    for n in range(1, 401):
        m = re.compile(r"\n[ \t]*%d[ \t]*\.[^\n]*" % n).search(body, pos)
        if m:
            marks.append((n, m))
            pos = m.end()
    poems = []
    for i, (n, m) in enumerate(marks):
        chunk = body[m.end(): marks[i + 1][1].start() if i + 1 < len(marks) else len(body)]
        rec = {"n": n, "lines": []}
        rows = [x.strip().replace("பாடப் பட்டோ", "பாடப்பட்டோ").replace("பாடப்பாட்டோ", "பாடப்பட்டோ")
                for x in chunk.split("\n")]
        while rows and not rows[0]:
            rows.pop(0)
        first_blank = rows.index("") if "" in rows else len(rows)
        keyline = lambda r: re.match(r"(%s)\s*([:;]|\s+(%s)|\s*$)" % (KEY_RE, KEY_RE), r)
        last_key = max([i for i in range(first_blank) if keyline(rows[i])], default=-1)
        i = last_key + 1
        for r in rows[: last_key + 1]:
            for k, v in re.findall(r"(%s)\s*[:;]\s*(.*?)(?=\s+(?:%s)\s*[:;]|$)" % (KEY_RE, KEY_RE), r):
                if KEYS[k]:
                    rec[KEYS[k]] = re.sub(r"\s+", " ", re.split(r"['‘“(\[]", v)[0]).strip().rstrip(".;").strip()
        cont = last_key >= 0 and not rows[last_key].endswith((".", ")", "]"))
        while i < first_blank and rows[i]:
            r = rows[i]
            if r[0] in "([" or (cont and (len(r.split()) > 7 or "'" in r or "’" in r)):
                cont = not r.endswith((".", ")", "]", ")."))
                i += 1
                continue
            if cont and ". " in r and not r.endswith("."):
                rows[i] = r.rsplit(". ", 1)[1]       # the note ends mid-line and the poem starts after it
            elif cont and r.endswith("."):
                i += 1
                cont = False
                continue
            break
        for r in rows[i:]:
            if bare(r) and not re.fullmatch(r"புறநானூறு முற்றும்\.?", r) and not re.match(r"\d+\s+\d+\s+கிடைத்தில", bare(r)):
                rec["lines"].append(bare(r))
        while rec["lines"] and rec["lines"][-1] == "…":
            rec["lines"].pop()
        if "tinai_ta" in rec:
            first = re.match(r"[஀-௿]+", rec["tinai_ta"])
            first = first.group(0) if first else rec["tinai_ta"]
            rec["tinai"] = PURAM.get(first, first)
        if rec["lines"]:
            poems.append(rec)
    return poems


def main() -> None:
    src = Path(sys.argv[1])
    out = ROOT / "data/build"
    out.mkdir(parents=True, exist_ok=True)
    hdr = ROOT / "data/sources/projectmadurai"
    hdr.mkdir(parents=True, exist_ok=True)
    for code, name, fn, start in [("pm0110", "kuruntokai", kuruntokai, "\nகுறுந்தொகை\n(எட்டுத்தொகை"),
                                  ("pm0057", "purananuru", purananuru, "\n   புறநானூறு\n")]:
        t = text_of(src / f"{code}.html")
        (hdr / f"{code}-header.txt").write_text(header(t, start), encoding="utf-8")
        poems = fn(t)
        fixes = json.loads((ROOT / "data/corrections_pm.json").read_text()).get(name, {})
        for p in poems:
            f = fixes.get(str(p["n"]))
            if f:
                if "drop_lines" in f:
                    p["lines"] = [l for i, l in enumerate(p["lines"]) if i not in f["drop_lines"]]
                p.update({k: v for k, v in f.items() if k not in ("drop_lines", "why", "status")})
        (out / f"{name}.json").write_text(json.dumps(poems, ensure_ascii=False, indent=1), encoding="utf-8")
        nums = [p["n"] for p in poems]
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        print(f"{name}: {len(poems)} poems, {sum(len(p['lines']) for p in poems)} lines, missing {missing[:20]}"
              f"{'…' if len(missing) > 20 else ''}, without tiṇai {sum(1 for p in poems if 'tinai_ta' not in p)}")


if __name__ == "__main__":
    main()
