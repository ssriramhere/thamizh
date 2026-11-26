"""Word timings for the recitation clips, from Google Cloud Speech-to-Text.

For each clip, the recogniser reports each word it hears with a start and an
end time. Those words are matched to the printed words letter by letter, so
the timings always belong to the printed text even where a word was misheard.

Usage: python pipeline/stt_kural.py AUDIO_DIR [--workers 16]
Reads AUDIO_DIR/<voice>/<n>.mp3 (voice Orus = male, Aoede = female) and
writes data/build/kural_timings.json:
  {"<n>": {"male": [[start, end], ...], "female": [...], "match": {"male": 0.97, ...}}}
one [start, end] per printed word, in seconds.
"""
from __future__ import annotations

import argparse
import difflib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES = {"male": "Orus", "female": "Aoede"}


def align(printed: list[str], heard: list[tuple[str, float, float]]):
    times = []
    for w, s, e in heard:
        n = max(1, len(w))
        times += [(s + (e - s) * i / n, s + (e - s) * (i + 1) / n) for i in range(n)]
    ps, hs = "".join(printed), "".join(w for w, _, _ in heard)
    sm = difflib.SequenceMatcher(None, ps, hs, autojunk=False)
    m = {}
    for a, b, n in sm.get_matching_blocks():
        for i in range(n):
            m[a + i] = b + i
    out, pos = [], 0
    for w in printed:
        idx = [m[i] for i in range(pos, pos + len(w)) if i in m]
        pos += len(w)
        out.append([round(times[min(idx)][0], 2), round(times[max(idx)][1], 2)] if idx else None)
    for i, r in enumerate(out):        # a word not heard at all sits between its neighbours
        if r is None:
            s = out[i - 1][1] if i and out[i - 1] else 0.0
            e = next((x[0] for x in out[i + 1:] if x), s + 0.3)
            out[i] = [s, max(s, e)]
    return out, round(sm.ratio(), 3)


def main() -> None:
    from google.cloud import speech
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    kurals = {k["n"]: k for k in json.loads((ROOT / "data/build/kural_text.json").read_text())}
    dest = ROOT / "data/build/kural_timings.json"
    done = json.loads(dest.read_text()) if dest.exists() else {}
    client = speech.SpeechClient(transport="rest")
    cfg = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.MP3, sample_rate_hertz=24000,
                                   language_code="ta-IN", enable_word_time_offsets=True)

    def one(job):
        n, key = job
        printed = kurals[n]["text"].split()
        audio = speech.RecognitionAudio(content=(Path(args.audio) / VOICES[key] / f"{n}.mp3").read_bytes())
        for attempt in range(5):
            try:
                r = client.recognize(config=cfg, audio=audio)
                break
            except Exception:
                time.sleep(3 * (attempt + 1))
        else:
            return n, key, None, None
        heard = [(w.word, w.start_time.total_seconds(), w.end_time.total_seconds())
                 for res in r.results for w in res.alternatives[0].words]
        if not heard:
            return n, key, None, 0.0
        t, ratio = align(printed, heard)
        return n, key, t, ratio

    jobs = [(n, k) for n in sorted(kurals) for k in VOICES if k not in done.get(str(n), {})]
    with ThreadPoolExecutor(args.workers) as ex:
        for n, key, t, ratio in ex.map(one, jobs):
            if t is None:
                continue
            rec = done.setdefault(str(n), {})
            rec[key] = t
            rec.setdefault("match", {})[key] = ratio
    dest.write_text(json.dumps(done, ensure_ascii=False, separators=(",", ":")))
    ratios = [v for r in done.values() for v in r.get("match", {}).values()]
    print(f"{sum(len([k for k in r if k in VOICES]) for r in done.values())} clips timed; "
          f"match below 0.8: {sum(1 for x in ratios if x < 0.8)}; mean {sum(ratios) / max(1, len(ratios)):.3f}")


if __name__ == "__main__":
    main()
