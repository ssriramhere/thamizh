"""Make the Today's verses reel for one verse.

    python reels/make_reel.py kural 836          # writes web/reels/kural-836-male.mp4 and .jpg
    python reels/make_reel.py kuruntokai 335 --voice female

Scenes: a one-line hook, the verse recited (the site's own recitation, words lit as
they are read, with each word's meaning), the translation read in English, one word
to remember, and the link. The hook and the word are written once by Gemini from the
verse, its translation and its word glosses (no commentary) and kept in
data/reels/<text>-<n>.json, where they can be edited before rendering again.
English narration: Google Cloud TTS, Chirp 3 HD (en-IN), the same voice as the recitation.
Setup, once: cd reels && npm install
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WEB = ROOT / "web"
RATE = 24000
CAP = 8   # reels show at most this many lines; the site keeps the full poem
VOICES = {"male": "Orus", "female": "Aoede"}
TITLES = {"kural": "Tirukkuṟaḷ", "kuruntokai": "Kuṟuntokai", "purananuru": "Puṟanāṉūṟu"}
TINAI = {"kuṟiñci": ("Kuṟiñci", "mountains", "#4B3F8F"), "mullai": ("Mullai", "forest", "#2F6B3A"),
         "marutam": ("Marutam", "farmland", "#8A5A00"), "neytal": ("Neytal", "seashore", "#1F5F8B"),
         "pālai": ("Pālai", "parched land", "#A8321F")}


def verse(text: str, n: int) -> dict:
    if text == "kural":
        idx = json.loads((WEB / "data/kural/index.json").read_text())
        ch = idx["chapter_of"][str(n)] if isinstance(idx["chapter_of"], dict) else idx["chapter_of"][n]
        k = next(x for x in json.loads((WEB / f"data/kural/{ch}.json").read_text())["kurals"] if x["n"] == n)
        chap = next(c for b in idx["books"] for c in b["chapters"] if c["n"] == ch)
        return {"lines": k["lines"], "tr": k["tr"], "translation": k["ai"]["translation"], "timing": k["timing"],
                "sync": k["sync"], "ref": f"Tirukkuṟaḷ {n}", "sub": f"Chapter {ch} · {chap['tr'][:1].upper() + chap['tr'][1:]}",
                "link": f"thamizh.ai/kural?n={n}", "accent": None, "label": ""}
    p = json.loads((WEB / f"data/{text}/{n}.json").read_text())
    c = p["colophon"]
    t = TINAI.get(c.get("tinai") or "")
    return {"lines": p["lines"], "tr": p["tr"], "translation": p["ai"]["translation"], "timing": p["timing"],
            "sync": p["sync"], "ref": f"{TITLES[text]} {n}", "sub": c.get("poet_tr") or "",
            "link": f"thamizh.ai/poem?t={text}&n={n}", "accent": t[2] if t else None,
            "label": f"{t[0]} · {t[1]}" if t else ""}


def words_for_prompt(v: dict) -> str:
    seen, out = set(), []
    for g in v["sync"]:
        for ta, en in g:
            if ta not in seen and en:
                seen.add(ta)
                out.append(f"{ta} = {en}")
    return "; ".join(out)


def cap(v: dict) -> dict:
    """Keep the first CAP lines of a long poem, with the timings and glosses for their words."""
    if len(v["lines"]) <= CAP:
        return v
    k = sum(1 for l in v["lines"][:CAP] for w in l.split() if w != "…")
    v = dict(v, lines=v["lines"][:CAP], tr=v["tr"][:CAP], sync=v["sync"][:k],
             timing={x: t[:k] for x, t in v["timing"].items()}, cut={x: t[k][0] for x, t in v["timing"].items()},
             total_lines=len(v["lines"]))
    return v


def extras(text: str, n: int, v: dict) -> dict:
    """Hook and word of the day, written once and kept for editing."""
    f = ROOT / f"data/reels/{text}-{n}.json"
    if f.exists():
        return json.loads(f.read_text())
    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
    prompt = (
        f"A {TITLES[text]} verse for a short social video.\n\nTamil:\n" + "\n".join(v["lines"]) +
        f"\n\nTranslation: {v['translation']}\n\nWord meanings: {words_for_prompt(v)}\n\n"
        "1. hook: one plain English sentence of at most 12 words that makes someone want to hear the verse. "
        "Say only what the verse says; no commentary, no moral of your own, no exclamation marks, no emoji, no hashtags.\n"
        + (f"3. excerpt: the video shows only the first {CAP} lines of this {v['total_lines']}-line poem. "
           "Translate just those lines into English in the same plain style as the translation above.\n"
           if v.get("cut") else "") +
        "2. word: one word from the word meanings above worth remembering. Give ta (the Tamil word exactly as listed), "
        "tr (its ISO 15919 transliteration), en (its meaning, a few words), and note (one sentence, under 25 words, "
        "on how the word is used in this verse).")
    schema = {"type": "object", "properties": {
        "hook": {"type": "string"},
        "word": {"type": "object", "properties": {k: {"type": "string"} for k in ("ta", "tr", "en", "note")},
                 "required": ["ta", "tr", "en", "note"]},
        "excerpt": {"type": "string"}}, "required": ["hook", "word"] + (["excerpt"] if v.get("cut") else [])}
    import time
    for attempt in range(6):          # Vertex answers 429 when busy; wait and try again
        try:
            r = client.models.generate_content(model="gemini-3.5-flash", contents=prompt,
                                               config=types.GenerateContentConfig(response_mime_type="application/json",
                                                                                  response_schema=schema))
            break
        except Exception as e:
            if "429" not in str(e) or attempt == 5:
                raise
            time.sleep(20 * (attempt + 1))
    d = json.loads(r.text)
    d["model"] = "gemini-3.5-flash"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    return d


def trim(x: np.ndarray, thr: float = 0.01) -> np.ndarray:
    loud = np.nonzero(np.abs(x) > thr)[0]
    if not len(loud):
        return x
    pad = int(0.04 * RATE)
    return x[max(0, loud[0] - pad):loud[-1] + pad]


def say(client, tts, text: str, voice: str, lang: str = "en-IN") -> np.ndarray:
    r = client.synthesize_speech(
        input=tts.SynthesisInput(text=text),
        voice=tts.VoiceSelectionParams(language_code=lang, name=f"{lang}-Chirp3-HD-{VOICES[voice]}"),
        audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16, sample_rate_hertz=RATE))
    with wave.open(io.BytesIO(r.audio_content)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def load_mp3(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", choices=sorted(TITLES))
    ap.add_argument("n", type=int)
    ap.add_argument("--voice", default="male", choices=sorted(VOICES))
    ap.add_argument("--dry", action="store_true", help="write data.js and sound only")
    a = ap.parse_args()
    v = cap(verse(a.text, a.n))
    x = extras(a.text, a.n, v)
    if v.get("cut"):
        v["translation"] = x["excerpt"]

    from google.cloud import texttospeech as tts
    client = tts.TextToSpeechClient(transport="rest")
    w = x["word"]
    clips = {"hook": x["hook"], "tr": v["translation"], "word": f"One word. {w['en'][0].upper() + w['en'][1:]}.",
             }
    audio = {k: say(client, tts, s, a.voice) for k, s in clips.items()}
    # the site's name: Tamil voice for தமிழ் (an English voice can't say ழ), English for the rest
    gap = np.zeros(int(0.12 * RATE), dtype=np.float32)
    audio["end"] = np.concatenate([trim(say(client, tts, "Read the whole poem, word by word, at" if v.get("cut") else "Read it word by word, at", a.voice)), gap,
                                   trim(say(client, tts, "தமிழ்", a.voice, "ta-IN")), gap,
                                   trim(say(client, tts, "dot A I.", a.voice))])
    dur = {k: len(s) / RATE for k, s in audio.items()}
    rec = load_mp3(WEB / f"audio/{a.text}/{a.voice}/{a.n}.mp3")
    if v.get("cut"):   # stop just before the next line starts, with a short fade
        rec = rec[:int((v["cut"][a.voice] - 0.08) * RATE)].copy()
        f = int(0.25 * RATE)
        rec[-f:] *= np.linspace(1, 0, f)
    # the word of the day, said on its own by the Tamil voice
    tword = trim(say(client, tts, w["ta"], a.voice, "ta-IN"))

    # timeline, seconds
    s1 = [0, max(3.5, dur["hook"] + 1.2)]
    rec_at = s1[1] + 0.9
    s2 = [s1[1], rec_at + len(rec) / RATE + 1.0]
    tr_at = s2[1] + 0.4
    s3 = [s2[1], tr_at + dur["tr"] + 1.0]
    tw_at = s3[1] + 0.5
    w_at = tw_at + (len(tword) / RATE + 0.5 if tword is not None else 0)
    s4 = [s3[1], max(s3[1] + 4.5, w_at + dur["word"] + 1.2)]
    e_at = s4[1] + 0.4
    s5 = [s4[1], max(s4[1] + 4.0, e_at + dur["end"] + 1.2)]
    total = s5[1]

    data = {"ref": v["ref"], "sub": v["sub"], "label": v["label"], "accent": v["accent"], "hook": x["hook"],
            "lines": v["lines"], "tr": v["tr"], "translation": v["translation"],
            "timing": [[t0 + rec_at, t1 + rec_at] for t0, t1 in v["timing"][a.voice]], "sync": v["sync"],
            "word": w, "link": v["link"], "more": (v.get("total_lines") or 0) - len(v["lines"]), "tr_at": tr_at, "tr_dur": dur["tr"],
            "scenes": {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5}, "total": total}
    (HERE / "data.js").write_text("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";", encoding="utf-8")

    # sound: a quiet drone, the recitation and the narration at their times
    t = np.arange(int(RATE * total)) / RATE
    bed = sum((0.5 / h) * np.sin(2 * np.pi * 110.0 * h * t + h) for h in (1, 2, 3, 4)) + \
        sum((0.3 / h) * np.sin(2 * np.pi * 164.81 * h * t + 2 * h) for h in (1, 2, 3))
    bed *= 1 + 0.2 * np.sin(2 * np.pi * 0.25 * t)
    bed = bed / np.abs(bed).max() * 0.05
    duck = np.ones_like(t)
    duck[int(rec_at * RATE):int((rec_at + len(rec) / RATE) * RATE)] = 0.5
    bed *= duck
    fd = int(RATE * 1.5)
    bed[:fd] *= np.linspace(0, 1, fd)
    bed[-fd:] *= np.linspace(1, 0, fd)
    parts = [(0.4, audio["hook"]), (rec_at, rec), (tr_at, audio["tr"]), (w_at, audio["word"]), (e_at, audio["end"])]
    if tword is not None:
        parts.append((tw_at, tword))
    for at, seg in parts:
        i = int(at * RATE)
        seg = seg[:len(bed) - i]
        bed[i:i + len(seg)] += seg
    bed = np.clip(bed, -0.99, 0.99)
    wav = HERE / "mix.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(RATE)
        f.writeframes((bed * 32767).astype(np.int16).tobytes())
    if a.dry:
        return

    out = WEB / "reels" / f"{a.text}-{a.n}-{a.voice}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    silent = HERE / "video.mp4"
    subprocess.run(["node", str(HERE / "render.js"), str(silent)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(rec_at + 0.5), "-i", str(out), "-frames:v", "1",
                    "-vf", "scale=540:-1", "-q:v", "4", str(out.with_suffix(".jpg"))], check=True)
    print(f"{out}: {total:.1f} s")


if __name__ == "__main__":
    sys.exit(main())
