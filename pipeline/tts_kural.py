"""Recite every couplet with Google Cloud Text-to-Speech (Chirp 3 HD, natural style).

Writes audio/kural/<voice>/<n>.mp3 for each voice. Mono MP3 at 48 kbps.

Usage: python pipeline/tts_kural.py OUT_DIR [--voices Orus,Aoede] [--range 1-1330] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from google.cloud import texttospeech as tts
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--voices", default="Orus,Aoede")
    ap.add_argument("--range", default="1-1330")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    a, _, b = args.range.partition("-")
    todo = range(int(a), int(b or a) + 1)
    kurals = {k["n"]: k for k in json.loads((ROOT / "data/build/kural_text.json").read_text())}
    client = tts.TextToSpeechClient(transport="rest")
    out = Path(args.out)
    chars = 0

    def one(job):
        nonlocal chars
        voice, n = job
        dest = out / voice / f"{n}.mp3"
        if dest.exists():
            return 0
        text = kurals[n]["text"].replace("\n", ". ") + "."
        for attempt in range(5):
            try:
                r = client.synthesize_speech(
                    input=tts.SynthesisInput(text=text),
                    voice=tts.VoiceSelectionParams(language_code="ta-IN", name=f"ta-IN-Chirp3-HD-{voice}"),
                    audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16, sample_rate_hertz=24000),
                )
                break
            except Exception:
                import time
                time.sleep(3 * (attempt + 1))
        else:
            return -1
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".wav") as w:
            w.write(r.audio_content)
            w.flush()
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", w.name, "-ac", "1", "-ar", "24000",
                            "-c:a", "libmp3lame", "-b:a", "48k", str(dest)], check=True)
        return len(text)

    jobs = [(v, n) for v in args.voices.split(",") for n in todo]
    with ThreadPoolExecutor(args.workers) as ex:
        res = list(ex.map(one, jobs))
    print(f"{sum(1 for r in res if r > 0)} new clips, {sum(1 for r in res if r < 0)} failed, {sum(r for r in res if r > 0):,} characters")


if __name__ == "__main__":
    main()
