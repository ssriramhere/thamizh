"""Keep one Today's reel a day ready, in both voices, for the days ahead.

    python reels/schedule.py            # yesterday to 30 days ahead
    python reels/schedule.py --ahead 7

Each day's reel follows Today's verses: the texts take turns (Kuṟaḷ, Kuṟuntokai,
Puṟanāṉūṟu), and the verse is the one that text shows that day. Missing reels are
made with make_reel.py; reels for days more than three days past are removed.
web/data/reels.json lists the reel for each day, keyed by the same day number the
site uses (days since 1970-01-01 in the reader's own date).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WEB = ROOT / "web"
TEXTS = ["kural", "kuruntokai", "purananuru"]     # same order as TEXTS in web/assets/today.js
TITLES = {"kural": "Tirukkuṟaḷ", "kuruntokai": "Kuṟuntokai", "purananuru": "Puṟanāṉūṟu"}
VOICES = ["male", "female"]


def pick(d: int) -> tuple[str, int]:
    """The text and verse for day number d, as today.js picks them."""
    text = TEXTS[d % len(TEXTS)]
    if text == "kural":
        return text, d % 1330 + 1
    ready = [p for p in json.loads((WEB / f"data/{text}/index.json").read_text())["poems"] if p["ai"]]
    return text, ready[d % len(ready)]["n"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ahead", type=int, default=30)
    a = ap.parse_args()
    today = (dt.datetime.now(dt.timezone.utc).date() - dt.date(1970, 1, 1)).days
    manifest = WEB / "data/reels.json"
    days = json.loads(manifest.read_text())["days"] if manifest.exists() else {}
    days = {k: v for k, v in days.items() if int(k) >= today - 3}

    for d in range(today - 1, today + a.ahead + 1):
        if str(d) in days:          # keep what was scheduled, even if an anthology's list changes later
            text, n = days[str(d)]["text"], days[str(d)]["n"]
        else:
            text, n = pick(d)
        ok = True
        for v in VOICES:
            if not (WEB / f"reels/{text}-{n}-{v}.mp4").exists():
                print(f"day {d}: {text} {n} {v}", flush=True)
                if subprocess.run([sys.executable, str(HERE / "make_reel.py"), text, str(n), "--voice", v]).returncode:
                    print(f"day {d}: failed, left for the next run", flush=True)
                    ok = False
        if not ok:
            days.pop(str(d), None)
            continue
        x = json.loads((ROOT / f"data/reels/{text}-{n}.json").read_text())
        days[str(d)] = {"text": text, "n": n, "ref": f"{TITLES[text]} {n}", "hook": x["hook"],
                        "date": str(dt.date(1970, 1, 1) + dt.timedelta(days=d))}

    keep = {f"{v['text']}-{v['n']}-{voice}{ext}" for v in days.values() for voice in VOICES for ext in (".mp4", ".jpg")}
    for f in (WEB / "reels").iterdir():
        if f.name not in keep:
            f.unlink()
            print("removed", f.name)
    manifest.write_text(json.dumps({"days": dict(sorted(days.items(), key=lambda kv: int(kv[0])))},
                                   ensure_ascii=False, indent=1) + "\n")
    print(f"{len(days)} days in web/data/reels.json")


if __name__ == "__main__":
    main()
