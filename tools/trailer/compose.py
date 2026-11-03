"""Cuts the trailer together from build/trailer/{frames,cards,voice,music.wav} following the EDL and
encodes it with FFmpeg: build/trailer/fAIceCommander3D_trailer.mp4 (1080p, 24 fps, H.264 + AAC).

Picture: clips with push-ins, white flashes on hard cuts, a short chromatic split on every cut,
animated title cards (glow; glitch on the title). Sound: the score, every sound effect the rendered
scenes and replays played (logged with their times; slowed down in slow motion), the narration,
the score ducked under the voice.

Run: .venv/Scripts/python tools/trailer/compose.py
"""
import bisect
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import edl  # noqa: E402
from cards import slug  # noqa: E402

BUILD = ROOT / "build" / "trailer"
FRAMES, CARDS, VOICE = BUILD / "frames", BUILD / "cards", BUILD / "voice"
OUT = BUILD / "fAIceCommander3D_trailer.mp4"
W, H = 1920, 1080
SR = 44100
SKIP_SFX = {"switch", "empty", "beep_high", "alarm", "beep", "brain_spawn", "static"}
LOOP_FILES = {"beam": "beam_loop", "shield": "shield_loop", "hypno": "hypno_loop", "blackhole": "blackhole_loop"}
CARD_COLORS = {"story": (235, 235, 245), "feature": (230, 120, 255), "title": (220, 110, 255),
               "tagline": (240, 240, 240)}  # BGR


def ffmpeg():
    """The real FFmpeg (the .venv one is only a stub): FFMPEG env var, else the first one on PATH
    outside the virtual environment, else the WinGet install."""
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    for d in os.environ.get("PATH", "").split(os.pathsep):
        exe = Path(d) / "ffmpeg.exe"
        if exe.exists() and ".venv" not in str(exe):
            return str(exe)
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    hits = sorted(winget.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"))
    if hits:
        return str(hits[-1])
    return shutil.which("ffmpeg")


# ---------------------------------------------------------------- picture

class FrameIndex:
    """Rendered frames of one source, looked up by source time (latest frame not after t)."""

    def __init__(self, prefix):
        files = sorted(FRAMES.glob(f"{prefix}_*.jpg"))
        self.times = [int(re.search(r"_(\d+)\.jpg$", f.name).group(1)) / 1000 for f in files]
        self.files = files
        self.cache = {}

    def get(self, t):
        if not self.files:
            return np.zeros((H, W, 3), np.uint8)
        i = max(0, bisect.bisect_right(self.times, t + 1e-4) - 1)
        if i not in self.cache:
            if len(self.cache) > 40:
                self.cache.clear()
            img = cv2.imread(str(self.files[i]))
            self.cache[i] = cv2.resize(img, (W, H)) if img.shape[:2] != (H, W) else img
        return self.cache[i]


def push(img, amount):
    if amount <= 1e-4:
        return img
    k = 1 + amount
    cw, ch = int(W / k), int(H / k)
    x0, y0 = (W - cw) // 2, (H - ch) // 2
    return cv2.resize(img[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_CUBIC)


def chroma_split(img, px):
    if px <= 0:
        return img
    out = img.copy()
    out[:, px:, 2] = img[:, :-px, 2]   # red to the right
    out[:, :-px, 0] = img[:, px:, 0]   # blue to the left
    return out


def card(text, style, u, dur, rng):
    """Animated title card at local time u."""
    mask = cv2.imread(str(CARDS / f"{slug(text)}.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
    fade = min(1.0, u / 0.15, max(0.0, (dur - u) / 0.25))
    if style == "feature":
        scale = 1.0 + 0.18 * max(0.0, 1 - u / 0.18) ** 2
    elif style == "title":
        scale = 1.12 - 0.12 * min(1.0, u / 0.35) ** 0.5
    else:
        scale = 1.0 + 0.05 * u / dur
    m = cv2.warpAffine(mask, np.float32([[scale, 0, (1 - scale) * W / 2], [0, scale, (1 - scale) * H / 2]]), (W, H))
    col = np.array(CARD_COLORS[style], np.float32) / 255
    glow = cv2.GaussianBlur(m, (0, 0), 18) * (1.6 if style in ("title", "feature") else 0.7)
    img = m[..., None] * col + glow[..., None] * col * 0.8
    if style == "title" and u < 0.9:  # glitch: displaced slices and an RGB split, settling down
        k = (1 - u / 0.9) ** 2
        for _ in range(int(14 * k) + 1):
            y = int(rng.integers(0, H - 40))
            hgt = int(rng.integers(6, 40))
            img[y:y + hgt] = np.roll(img[y:y + hgt], int(rng.integers(-80, 80) * k), axis=1)
        sh = int(16 * k)
        if sh:
            img[..., 2] = np.roll(img[..., 2], sh, axis=1)
            img[..., 0] = np.roll(img[..., 0], -sh, axis=1)
    if style == "title":  # a sheen sweeping over the logo
        x = (u - 1.0) / 1.6 * W * 1.4
        band = np.exp(-((np.arange(W) - x) / 90.0) ** 2)[None, :, None]
        img = img + m[..., None] * band * 0.8
    return np.clip(img * fade * 255, 0, 255).astype(np.uint8)


def grade(img):
    """A light filmic grade: a touch more contrast, teal shadows and warm highlights."""
    f = img.astype(np.float32) / 255
    f = f * f * (3 - 2 * f) * 0.35 + f * 0.65
    lum = f.mean(2, keepdims=True)
    f += (0.03 * (1 - lum)) * np.array([0.6, 0.3, -0.2]) + (0.03 * lum) * np.array([-0.3, 0.1, 0.4])
    return np.clip(f * 255, 0, 255).astype(np.uint8)


def frames():
    rng = np.random.default_rng(3)
    sources = {}
    total = int(edl.LENGTH * edl.FPS)
    for n in range(total):
        t = n / edl.FPS
        at, dur, src, opt = next(c for c in edl.CLIPS if c[0] <= t + 1e-6 < c[0] + c[1])
        u = t - at
        kind = src[0]
        if kind == "black":
            yield np.zeros((H, W, 3), np.uint8)
            continue
        if kind == "card":
            yield card(src[1], src[2], u, dur, rng)
            continue
        prefix = {"intro": "intro", "outro": "outro", "finale": "finale"}.get(kind) or src[1]
        if prefix not in sources:
            sources[prefix] = FrameIndex(prefix)
        s = src[-1] + u * opt.get("speed", 1.0)
        img = sources[prefix].get(s)
        if opt.get("pillar"):  # the webcam close-up is 4:3: keep the sides black
            img = img.copy()
            side = (W - H * 4 // 3) // 2
            img[:, :side] = 0
            img[:, W - side:] = 0
        img = push(img, opt.get("push", 0.0) * u / dur)
        if u < 2 / edl.FPS:  # every cut: a quick chromatic split
            img = chroma_split(img, 10 if u < 1 / edl.FPS else 4)
        img = grade(img)
        if opt.get("flash") and u < 4 / edl.FPS:
            k = (1.0, 0.65, 0.35, 0.15)[int(u * edl.FPS)]
            img = np.clip(img.astype(np.float32) + 255 * k, 0, 255).astype(np.uint8)
        yield img


# ---------------------------------------------------------------- sound

def load_wav(path):
    sr, x = wavfile.read(str(path))
    x = x.astype(np.float32) / (32768.0 if x.dtype == np.int16 else 1.0)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    if sr != SR:
        x = resample_poly(x, SR, sr, axis=0)
    return x


def sfx_dir():
    sys.path.insert(0, str(ROOT))
    from faicecommander.audio import cache
    return cache.cache_dir()


def place(buf, t, sig, gain, rate=1.0):
    if rate != 1.0:
        n = int(len(sig) / rate)
        idx = np.linspace(0, len(sig) - 1, max(2, n))
        sig = np.stack([np.interp(idx, np.arange(len(sig)), sig[:, c]) for c in (0, 1)], 1)
    i = int(t * SR)
    if i >= len(buf):
        return
    k = min(len(sig), len(buf) - i)
    buf[i:i + k] += sig[:k] * gain


def soundtrack():
    total = int((edl.LENGTH + 1) * SR)
    music = np.zeros((total, 2), np.float32)
    m = load_wav(BUILD / "music.wav")
    music[:min(total, len(m))] = m[:total]
    fx = np.zeros_like(music)
    voice = np.zeros_like(music)
    sdir = sfx_dir()
    sounds = {}

    def snd(name):
        if name not in sounds:
            p = sdir / f"sfx_{name}.wav"
            sounds[name] = load_wav(p) if p.exists() else None
        return sounds[name]

    logs = {}
    for at, dur, src, opt in edl.CLIPS:
        kind = src[0]
        if kind not in ("intro", "outro", "game", "finale"):
            continue
        prefix = kind if kind != "game" else src[1]
        if prefix not in logs:
            p = FRAMES / f"{prefix}_sfx.json"
            logs[prefix] = json.loads(p.read_text()) if p.exists() else []
        speed = opt.get("speed", 1.0)
        s0, s1 = src[-1], src[-1] + dur * speed
        gain = {"game": 0.55, "finale": 0.38}.get(kind, 0.7)
        loops_on = {}
        for typ, te, name, vol, rate in logs[prefix]:
            if typ == "loop":  # state at the clip start, and changes inside it
                if te <= s0:
                    loops_on[name] = vol
                elif te < s1:
                    loops_on.setdefault(name, 0.0)
            if not (s0 <= te < s1) or typ != "play" or name in SKIP_SFX:
                continue
            sig = snd(name)
            if sig is not None:
                place(fx, at + (te - s0) / speed, sig, vol * gain, rate * speed)
        for name, vol in loops_on.items():  # held loops (beam, shield, hypno, black hole) for the clip
            sig = snd(LOOP_FILES.get(name, name))
            if sig is None or vol <= 0:
                continue
            n = int(dur * SR)
            looped = np.tile(sig, (n // len(sig) + 1, 1))[:n]
            env = np.minimum(1, np.minimum(np.arange(n), n - np.arange(n)) / (0.03 * SR))[:, None]
            place(fx, at, looped * env, vol * gain * 0.8)
    duck = np.ones(total, np.float32)
    for at, name in edl.VOICE:
        v = load_wav(VOICE / f"{name}.wav")
        place(voice, at, v, 1.0)
        a, b = int(at * SR), int((at + len(v) / SR) * SR)
        duck[a:b] = np.minimum(duck[a:b], 0.45)
    duck = np.convolve(duck, np.ones(4410) / 4410, mode="same")  # smooth 0.1 s ramps
    mix = music * 0.85 * duck[:, None] + fx * 0.8 * (0.6 + 0.4 * duck[:, None]) + voice * 1.1
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    mix = mix / max(np.abs(mix).max(), 1e-9) * 0.95  # no clipping
    path = BUILD / "trailer_audio.wav"
    wavfile.write(str(path), SR, mix.astype(np.float32))
    return path


# ---------------------------------------------------------------- encode

def remux():
    """Only the sound changed: put the new mix under the existing picture."""
    audio = soundtrack()
    tmp = OUT.with_name("remux.mp4")
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(OUT), "-i", str(audio), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(tmp)],
                   check=True)
    tmp.replace(OUT)
    print("remuxed", OUT)


def main():
    audio = soundtrack()
    print("audio:", audio, flush=True)
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
           "-r", str(edl.FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n, img in enumerate(frames()):
        proc.stdin.write(img.tobytes())
        if n % 240 == 0:
            print(f"frame {n} / {int(edl.LENGTH * edl.FPS)}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("wrote", OUT)


if __name__ == "__main__":
    remux() if "--audio-only" in sys.argv else main()
