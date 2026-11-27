"""Recite the Caṅkam poems and time every word.

Each line is synthesized on its own (Google Cloud Text-to-Speech, Chirp 3 HD)
and the lines are joined with a short pause, so line boundaries are exact.
The joined lines are then timed with Speech-to-Text in chunks of under 55 s
(the limit for a direct request is one minute), and the recognized words are
matched to the printed words letter by letter, as for the Kuṟaḷ.

Usage: python pipeline/tts_poems.py TEXT AUDIO_OUT [--workers 6]
Writes AUDIO_OUT/<text>/<male|female>/<n>.mp3 (mono, 32 kbps) and
data/build/<text>_timings.json: {"<n>": {"male": [[start, end], ...], ...}}
with one [start, end] per printed word (a gap … gets none).
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tempfile
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from stt_kural import align  # noqa: E402

VOICES = {"male": "Orus", "female": "Aoede"}
RATE = 24000
PAUSE = 0.4
LINES = 8          # lines per request: well under a minute of speech


def main() -> None:
    from google.cloud import speech
    from google.cloud import texttospeech as tts
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--range")
    args = ap.parse_args()
    poems = json.loads((ROOT / f"data/build/{args.text}.json").read_text())
    if args.range:
        a, _, b = args.range.partition("-")
        poems = [p for p in poems if int(a) <= p["n"] <= int(b or a)]
    T = tts.TextToSpeechClient(transport="rest")
    S = speech.SpeechClient(transport="rest")
    dest = ROOT / f"data/build/{args.text}_timings.json"
    done = json.loads(dest.read_text()) if dest.exists() else {}

    def retry(fn):
        for i in range(8):
            try:
                return fn()
            except Exception:
                time.sleep(min(60, 4 * 2 ** i))
        raise RuntimeError("gave up")

    def synth(text, voice):
        r = retry(lambda: T.synthesize_speech(
            input=tts.SynthesisInput(text=text),
            voice=tts.VoiceSelectionParams(language_code="ta-IN", name=f"ta-IN-Chirp3-HD-{voice}"),
            audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16, sample_rate_hertz=RATE)))
        with wave.open(io.BytesIO(r.audio_content)) as w:
            return w.readframes(w.getnframes())

    def recognize(pcm):
        r = retry(lambda: S.recognize(
            config=speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, sample_rate_hertz=RATE,
                                            language_code="ta-IN", enable_word_time_offsets=True),
            audio=speech.RecognitionAudio(content=pcm)))
        return [(w.word, w.start_time.total_seconds(), w.end_time.total_seconds())
                for res in r.results for w in res.alternatives[0].words]

    def one(job):
        p, key = job
        n = str(p["n"])
        mp3 = Path(args.out) / args.text / key / f"{n}.mp3"
        if mp3.exists() and key in done.get(n, {}):
            return None
        silence = b"\x00\x00" * int(RATE * PAUSE)
        lines = [[w for w in line.split() if w != "…"] for line in p["lines"]]
        lines = [l for l in lines if l]
        pcm, timing = b"", []
        # one request per chunk of up to LINES lines; each chunk is timed on its own
        for i in range(0, len(lines), LINES):
            chunk = lines[i:i + LINES]
            seg = synth(". ".join(" ".join(l) for l in chunk) + ".", VOICES[key])
            s0 = len(pcm) / 2 / RATE
            printed = [w for l in chunk for w in l]
            heard = recognize(seg)
            if heard:
                t, _ = align(printed, heard)
            else:   # nothing heard: spread the time over the words by length
                dur, tot, t0, t = len(seg) / 2 / RATE, sum(len(w) for w in printed) or 1, 0.0, []
                for w in printed:
                    d = dur * len(w) / tot
                    t.append([t0, t0 + d]); t0 += d
            timing += [[round(a + s0, 2), round(b + s0, 2)] for a, b in t]
            pcm += seg + silence
        mp3.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            with wave.open(tmp.name, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp.name, "-ac", "1", "-c:a", "libmp3lame",
                            "-b:a", "32k", str(mp3)], check=True)
        return n, key, timing

    jobs = [(p, k) for p in poems for k in VOICES]
    saved = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for res in ex.map(one, jobs):
            if res:
                n, key, timing = res
                done.setdefault(n, {})[key] = timing
                saved += 1
                if saved % 50 == 0:
                    dest.write_text(json.dumps(done, ensure_ascii=False, separators=(",", ":")))
    dest.write_text(json.dumps(done, ensure_ascii=False, separators=(",", ":")))
    print(f"{args.text}: {saved} clips made; {len(done)} poems timed")


if __name__ == "__main__":
    main()
