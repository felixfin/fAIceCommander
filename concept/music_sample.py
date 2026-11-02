"""Procedural music teaser for fAIceCommander 3D (numpy/scipy synthesis, no samples).

Structure (174 BPM):
  bars 0-1   "Leere"      mysterious pad + sonar pings + riser
  bars 2-9   "Level"      drum & bass: breakbeat, reese bass, arp, pad
  bars 10-13 "Mutter"     half-time wobble (boss layer), siren
  tail       impact + reverb
In the game these are separate layers/stems that are cross-faded per level and situation.
"""
import os

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter, sosfilt

SR = 44100
BPM = 174
BEAT = 60 / BPM
STEP = BEAT / 4
BAR = BEAT * 4
N_BARS = 14
TOTAL = N_BARS * BAR + 2.5
rng = np.random.default_rng(174)

L = np.zeros(int(TOTAL * SR))
R = np.zeros_like(L)


def t_arr(dur):
    return np.arange(int(dur * SR)) / SR


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def add(start, sig, gain=1.0, pan=0.0):
    i = int(start * SR)
    n = min(len(sig), len(L) - i)
    if n <= 0:
        return
    L[i:i + n] += sig[:n] * gain * np.sqrt(0.5 * (1 - pan))
    R[i:i + n] += sig[:n] * gain * np.sqrt(0.5 * (1 + pan))


def saw(f, t):
    ph = np.cumsum(np.broadcast_to(f, t.shape)) / SR if np.ndim(f) else f * t
    return 2 * (ph % 1.0) - 1


# ---------------------------------------------------------------- drums

def kick():
    t = t_arr(0.4)
    f = 45 + 120 * np.exp(-t * 32)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)
    s += rng.normal(size=len(t)) * np.exp(-t * 400) * 0.35
    return np.tanh(s * 1.8)


def snare():
    t = t_arr(0.3)
    n = bp(rng.normal(size=len(t)), 900, 7000) * np.exp(-t * 18)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28)
    return np.tanh((n * 1.4 + tone * 0.7) * 1.5)


def hat(open_=False):
    t = t_arr(0.25 if open_ else 0.05)
    return hp(rng.normal(size=len(t)), 7000) * np.exp(-t * (14 if open_ else 90))


def crash():
    t = t_arr(2.2)
    return hp(rng.normal(size=len(t)), 3500) * np.exp(-t * 2.2)


K, S, HC, HO = kick(), snare(), hat(), hat(True)
kick_times = []


def dnb_bar(b):
    t0 = b * BAR
    for st in (0, 10):
        add(t0 + st * STEP, K, 0.9)
        kick_times.append(t0 + st * STEP)
    for st in (4, 12):
        add(t0 + st * STEP, S, 0.65)
    add(t0 + 7 * STEP, S, 0.18, 0.2)
    add(t0 + 15 * STEP, S, 0.12, -0.2)
    for st in range(16):
        add(t0 + st * STEP + (0.012 if st % 2 else 0), HC, 0.22 if st % 2 == 0 else 0.1, 0.35)
    if b % 2 == 1:
        add(t0 + 14 * STEP, HO, 0.15, -0.3)


def halftime_bar(b):
    t0 = b * BAR
    for st in (0, 11):
        add(t0 + st * STEP, K, 1.0)
        kick_times.append(t0 + st * STEP)
    add(t0 + 8 * STEP, S, 0.85)
    add(t0 + 8 * STEP, hat(True), 0.1)
    for st in range(0, 16, 2):
        add(t0 + st * STEP, HC, 0.18, 0.3)


# ---------------------------------------------------------------- tonal parts

def note(name_oct):
    names = {"C": -9, "Db": -8, "D": -7, "Eb": -6, "E": -5, "F": -4, "Gb": -3, "G": -2, "Ab": -1, "A": 0, "Bb": 1, "B": 2}
    n, o = name_oct[:-1], int(name_oct[-1])
    return 440 * 2 ** ((names[n] + 12 * (o - 4)) / 12)


def reverb(x, mix=0.3):
    out = np.zeros_like(x)
    for d, g in ((1557, 0.84), (1617, 0.83), (1491, 0.85), (1422, 0.86)):
        a = np.zeros(d + 1)
        a[0], a[d] = 1, -g
        out += lfilter([1], a, x)
    for d, g in ((225, 0.5), (556, 0.5)):
        b = np.zeros(d + 1)
        b[0], b[d] = -g, 1
        a = np.zeros(d + 1)
        a[0], a[d] = 1, -g
        out = lfilter(b, a, out)
    return x * (1 - mix) + lp(out, 5000) * mix * 0.25


def pad(start, dur, chord, gain):
    t = t_arr(dur)
    s = np.zeros_like(t)
    for f in chord:
        for det in (-0.007, 0.0, 0.006):
            s += saw(f * (1 + det), t + rng.random())
    s = lp(s, 1100, 2)
    env = np.minimum(1, t / 1.2) * np.minimum(1, (dur - t) / 0.8)
    s = s * env * (0.85 + 0.15 * np.sin(2 * np.pi * 0.3 * t))
    s = reverb(s, 0.5)
    add(start, s, gain, -0.25)
    add(start + 0.011, s, gain, 0.25)


def sonar(start, gain=0.35):
    t = t_arr(1.2)
    s = (np.sin(2 * np.pi * 1320 * t) + 0.3 * np.sin(2 * np.pi * 2640 * t)) * np.exp(-t * 7)
    for k, pan in enumerate((0, -0.6, 0.6, -0.3)):
        add(start + k * 0.27, s, gain * 0.55 ** k, pan)


def riser(start, dur):
    t = t_arr(dur)
    n = rng.normal(size=len(t))
    s = lp(n, 900) * (1 - t / dur) + hp(n, 2500) * (t / dur)
    add(start, s * (t / dur) ** 2, 0.28)


def reese(start, dur, f, gain):
    t = t_arr(dur)
    s = saw(f * 1.006, t) + saw(f * 0.994, t + 0.37) + 0.8 * np.sin(2 * np.pi * f * t)
    s = np.tanh(lp(s, 380, 4) * 2.2)
    s = lp(s, 900) + 0.6 * np.sin(2 * np.pi * f * t)
    env = np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.02)
    add(start, s * env, gain)


def wobble(start, dur, f, rate_steps, gain):
    """Saw through a resonant state-variable low-pass driven by an LFO (dubstep wobble)."""
    t = t_arr(dur)
    x = saw(f, t) + saw(f * 1.01, t) * 0.7 + saw(f / 2, t) * 0.5
    lfo = 0.5 - 0.5 * np.cos(2 * np.pi * t / (rate_steps * STEP))
    fc = 90 + 2200 * lfo ** 1.6
    fcoef = 2 * np.sin(np.pi * fc / SR)
    low = band = 0.0
    y = np.empty_like(x)
    q = 0.35
    for i in range(len(x)):
        low += fcoef[i] * band
        high = x[i] - low - q * band
        band += fcoef[i] * high
        y[i] = low
    y = np.tanh(y * 2.6) + 0.5 * np.sin(2 * np.pi * f / 2 * t)
    env = np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.03)
    add(start, y * env, gain)


def arp_bar(b, seq, gain):
    t0 = b * BAR
    tt = t_arr(STEP * 1.6)
    for st, n in enumerate(seq):
        if n is None:
            continue
        f = note(n)
        s = np.sign(np.sin(2 * np.pi * f * tt)) * 0.6 + saw(f * 1.003, tt) * 0.4
        s = lp(s * np.exp(-tt * 16), 3200)
        add(t0 + st * STEP, s, gain, -0.35)
        add(t0 + st * STEP + 3 * STEP, s, gain * 0.35, 0.5)  # ping-pong echo
        add(t0 + st * STEP + 6 * STEP, s, gain * 0.15, -0.5)


def siren(start, dur, gain):
    t = t_arr(dur)
    f = 620 + 280 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 1.4)) + 8 * np.sin(2 * np.pi * 6 * t)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.3) * np.minimum(1, (dur - t) / 0.4)
    add(start, reverb(s, 0.5), gain, 0.3)


def impact(start, gain=0.8):
    t = t_arr(2.5)
    boom = np.sin(2 * np.pi * (32 + 40 * np.exp(-t * 6)) * t) * np.exp(-t * 1.6)
    add(start, boom, gain)
    add(start, crash(), gain * 0.35)


# ---------------------------------------------------------------- arrangement

FM9 = [note("F3"), note("Ab3"), note("C4"), note("Eb4"), note("G4")]
DB = [note("Db3"), note("F3"), note("Ab3"), note("C4")]

# intro: the void
pad(0.0, 2 * BAR + 0.5, FM9, 0.05)
for b in range(2):
    sonar(b * BAR + 0.0)
    sonar(b * BAR + 2 * BEAT, 0.25)
riser(BAR * 1.0, BAR)

# level section
impact(2 * BAR, 0.7)
roots = ["F1", "F1", "Db2", "Db2", "Ab1", "Ab1", "Eb1", "Gb1"]
arp_a = ["F4", "C5", "Ab4", "Eb5", "F4", "C5", "Ab4", "F5", "F4", "C5", "Ab4", "Eb5", "G5", "Eb5", "C5", "Ab4"]
arp_b = ["Db5", "Ab4", "F4", "C5", "Db5", "Ab4", "F5", "C5", "Db5", "Ab4", "F4", "Eb5", "F5", "Eb5", "Db5", "C5"]
for i, b in enumerate(range(2, 10)):
    dnb_bar(b)
    f = note(roots[i])
    for st0, ln in ((0, 6), (6, 4), (10, 6)):  # rolling reese rhythm
        reese(b * BAR + st0 * STEP, ln * STEP * 0.95, f, 0.32)
    if b >= 4:
        arp_bar(b, arp_a if roots[i] in ("F1", "Ab1", "Eb1", "Gb1") else arp_b, 0.07)
pad(2 * BAR, 4 * BAR, FM9, 0.035)
pad(6 * BAR, 4 * BAR, DB, 0.035)
riser(9 * BAR, BAR)

# boss layer: half-time wobble
impact(10 * BAR, 0.9)
siren(10 * BAR, 2 * BAR, 0.05)
wob = [("F1", 3), ("F1", 2), ("Ab1", 3), ("Gb1", 1.5)]
for i, b in enumerate(range(10, 14)):
    halftime_bar(b)
    n, rate = wob[i]
    wobble(b * BAR, BAR * 0.98, note(n), rate, 0.3)
pad(10 * BAR, 4 * BAR, FM9, 0.03)
impact(14 * BAR, 1.0)
sonar(14 * BAR + 0.4, 0.2)

# sidechain-ish ducking of everything but drums is skipped for the teaser; master bus:
mix = np.stack([L, R], 1)
mix = hp(mix.T, 25).T
mix = np.tanh(mix * 1.4) / np.tanh(1.4)
mix /= np.abs(mix).max() / 0.89
fade = np.minimum(1, (len(mix) - np.arange(len(mix))) / (SR * 1.0))[:, None]
mix *= fade
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio", "music_teaser.wav")
os.makedirs(os.path.dirname(out), exist_ok=True)
wavfile.write(out, SR, (mix * 32767).astype(np.int16))
print("wrote", out, f"{len(mix) / SR:.1f}s")
