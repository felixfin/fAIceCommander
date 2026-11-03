"""Post-processes the raw Piper lines into the game's voice WAVs (runs in the game's .venv).

tools/voice/raw/<id>.wav (22.05 kHz) -> faicecommander/assets/voice/<id>.wav (44.1 kHz mono, 16 bit)
Run: .venv/Scripts/python tools/voice/tts_process.py
"""
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from faicecommander.audio.synth import SR, bp, fade, hp, lp, pad_tail, reverb  # noqa: E402

HERE = Path(__file__).parent
RAW = HERE / "raw"
OUT = ROOT / "faicecommander" / "assets" / "voice"


def load(path):
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        x = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float64) / 32768
    return resample_poly(x, SR, rate)


def save(path, x):
    x = x / max(1e-9, np.max(np.abs(x))) * 0.95
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((x * 32767).astype(np.int16).tobytes())


def compress(x, threshold=0.25, ratio=3.5, attack=0.004, release=0.12):
    """Simple feed-forward compressor with a smoothed envelope, then make-up gain."""
    env = np.abs(x)
    a, r = np.exp(-1 / (attack * SR)), np.exp(-1 / (release * SR))
    sm = np.empty_like(env)
    level = 0.0
    for i, v in enumerate(env):
        level = a * level + (1 - a) * v if v > level else r * level + (1 - r) * v
        sm[i] = level
    gain = np.where(sm > threshold, (threshold + (sm - threshold) / ratio) / np.maximum(sm, 1e-9), 1.0)
    return x * gain


def saturate(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def chorus(x, ms=14.0, depth_ms=3.0, rate=0.35, mix=0.35):
    n = np.arange(len(x))
    d = (ms + depth_ms * np.sin(2 * np.pi * rate * n / SR)) * SR / 1000
    idx = np.clip(n - d, 0, len(x) - 1)
    return x * (1 - mix) + np.interp(idx, n, x) * mix


def stretch(x, factor, win=1024, hop=256, tol=256):
    """WSOLA time stretch (factor > 1 = longer), pitch unchanged: overlap-adds windowed frames, each
    shifted (within tol samples) to line up with the previous one - keeps the voice's harmonics clean."""
    w = np.hanning(win)
    n_out = int(len(x) * factor)
    out, norm = np.zeros(n_out + win), np.zeros(n_out + win)
    x = np.pad(x, (tol, win + tol))
    pos_out, prev = 0, None
    while True:
        pos_in = int(pos_out / factor) + tol
        if pos_in + win + tol >= len(x) or pos_out >= n_out:
            break
        best = 0 if prev is None else int(np.argmax(np.correlate(x[pos_in - tol: pos_in + win + tol], prev, "valid"))) - tol
        out[pos_out:pos_out + win] += x[pos_in + best: pos_in + best + win] * w
        norm[pos_out:pos_out + win] += w
        prev = x[pos_in + best + hop: pos_in + best + hop + win]
        pos_out += hop
    return out[:n_out] / np.maximum(norm[:n_out], 1e-3)


def pitch_down(x, semitones):
    """Lower pitch and formants together (a bigger, darker throat), keeping the duration."""
    r = 2 ** (semitones / 12)
    y = stretch(x, r)
    y = resample_poly(y, 1000, int(round(1000 * r)))[: len(x)]
    return np.pad(y, (0, len(x) - len(y)))


def mask(x, delay_ms=2.2, gain=0.3):
    """A faint resonance like a voice behind a helmet mask (a short feedback comb)."""
    d = int(delay_ms * SR / 1000)
    y = x.copy()
    for i in range(d, len(y), d):
        k = min(d, len(y) - i)
        y[i:i + k] += gain * y[i - d:i - d + k]
    return y * 0.7 + x * 0.3


def narrator(x, space=0.16, size=1.3):
    """Deep and dark (a hint of Batman and Vader): pitched down 5 semitones, a quiet sub-octave growl,
    rasp, a faint mask resonance, heavy low end and dark highs, compression, dark hall."""
    deep = pitch_down(x, 5.0)
    growl = pitch_down(x, 12.0)                     # an octave below: the gravel under the voice
    x = deep + 0.16 * saturate(lp(growl, 700), 2.5)
    x = x + 0.12 * saturate(bp(x, 150, 1200), 4.0)  # rasp
    x = mask(x)
    x = lp(x, 5200)
    x = hp(x, 50)
    x = x + lp(x, 200) * 0.7            # chest
    x = x + bp(x, 1800, 3500) * 0.18     # just enough presence to stay intelligible
    x = compress(x)
    x = pad_tail(x, 1.2)
    return fade(reverb(x, mix=space, size=size), 0.002, 0.4)


def surgeon(x):
    """Synthetic medical AI: narrow band, metallic comb, faint ring modulation."""
    x = bp(hp(x, 120), 280, 5200)
    d = int(0.0045 * SR)
    comb = x.copy()
    comb[d:] += 0.55 * x[:-d]
    t = np.arange(len(x)) / SR
    x = comb * (0.82 + 0.18 * np.sin(2 * np.pi * 55 * t))
    x = compress(saturate(x, 1.4))
    x = pad_tail(x, 0.6)
    return fade(reverb(x, mix=0.12, size=0.6), 0.002, 0.25)


def comms(x):
    """Voice in his helmet: band-limited radio, a little grit, short room."""
    x = bp(x, 320, 3600, order=3)
    x = compress(saturate(x, 2.2), threshold=0.3)
    x = x + np.random.default_rng(7).normal(0, 0.004, len(x)) * (np.abs(x) > 0.01)
    x = pad_tail(x, 0.5)
    return fade(reverb(x, mix=0.1, size=0.5), 0.002, 0.2)


def epic(x):
    """The final call: narrator, doubled and in a huge hall."""
    return narrator(chorus(x, mix=0.3), space=0.32, size=1.7)


def honor(x):
    """Honor himself, quiet and close: warm, slight air, small room."""
    x = hp(x, 60)
    x = x + lp(x, 220) * 0.45
    x = compress(x, threshold=0.3, ratio=2.5)
    x = pad_tail(x, 1.0)
    return fade(reverb(x, mix=0.16, size=1.0), 0.002, 0.4)


CHAIN = {"intro_08": surgeon, "intro_10": comms, "intro_11": epic, "outro_04": honor}

for path in sorted(RAW.glob("*.wav")):
    out = CHAIN.get(path.stem, narrator)(load(path))
    save(OUT / path.name, out)
    print(f"{path.stem}: {len(out) / SR:.2f}s  {CHAIN.get(path.stem, narrator).__name__}")
