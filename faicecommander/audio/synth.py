"""DSP building blocks for the procedural soundtrack and sound effects (numpy/scipy, no samples)."""
import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
BPM = 174
BEAT = 60 / BPM
STEP = BEAT / 4
BAR = BEAT * 4

_rng = np.random.default_rng(174)


def rng(seed):
    global _rng
    _rng = np.random.default_rng(seed)
    return _rng


def t_arr(dur):
    return np.arange(int(dur * SR)) / SR


def noise(n):
    return _rng.normal(size=n)


def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR * 0.45), "low", fs=SR, output="sos"), x, axis=0)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos"), x, axis=0)


def sweep_lp(x, fc, block=256, q=0.9):
    """Low-pass with a time-varying cutoff (array, one value per sample), processed in blocks."""
    y = np.empty_like(x)
    zi = np.zeros((1, 2))
    for i in range(0, len(x), block):
        f = float(np.clip(fc[min(i + block // 2, len(fc) - 1)], 30, SR * 0.45))
        w0 = 2 * np.pi * f / SR
        alpha = np.sin(w0) / (2 * q)
        cw = np.cos(w0)
        b = np.array([(1 - cw) / 2, 1 - cw, (1 - cw) / 2])
        a = np.array([1 + alpha, -2 * cw, 1 - alpha])
        sos = np.concatenate([b / a[0], a / a[0]])[None, :]
        y[i:i + block], zi = sosfilt(sos, x[i:i + block], zi=zi)
    return y


def phase(f, t):
    """Running phase in cycles for a constant or per-sample frequency."""
    return np.cumsum(np.broadcast_to(f, t.shape)) / SR if np.ndim(f) else f * t


def saw(f, t, ph0=0.0):
    return 2 * ((phase(f, t) + ph0) % 1.0) - 1


def square(f, t, duty=0.5):
    return np.where((phase(f, t) % 1.0) < duty, 1.0, -1.0)


def sine(f, t):
    return np.sin(2 * np.pi * phase(f, t))


def note(name_oct):
    names = {"C": -9, "Db": -8, "D": -7, "Eb": -6, "E": -5, "F": -4, "Gb": -3, "G": -2, "Ab": -1, "A": 0,
             "Bb": 1, "B": 2}
    n, o = name_oct[:-1], int(name_oct[-1])
    return 440 * 2 ** ((names[n] + 12 * (o - 4)) / 12)


def fade(x, a=0.005, r=0.01):
    n = len(x)
    env = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        env[:na] = np.linspace(0, 1, na)
    if nr:
        env[n - nr:] *= np.linspace(1, 0, nr)
    return x * (env if x.ndim == 1 else env[:, None])


def _comb(x, d, g):
    """y[n] = x[n] + g*y[n-d], computed d samples at a time."""
    y = x.copy()
    for i in range(d, len(x), d):
        k = min(d, len(x) - i)
        y[i:i + k] += g * y[i - d:i - d + k]
    return y


def _allpass(x, d, g):
    """y[n] = -g*x[n] + x[n-d] + g*y[n-d], computed d samples at a time."""
    y = -g * x
    for i in range(d, len(x), d):
        k = min(d, len(x) - i)
        y[i:i + k] += x[i - d:i - d + k] + g * y[i - d:i - d + k]
    return y


def reverb(x, mix=0.3, size=1.0):
    """Schroeder reverb: four parallel combs into two allpasses."""
    out = sum(_comb(x, int(d * size), g) for d, g in ((1557, 0.84), (1617, 0.83), (1491, 0.85), (1422, 0.86)))
    for d, g in ((225, 0.5), (556, 0.5)):
        out = _allpass(out, d, g)
    return x * (1 - mix) + lp(out, 5000) * mix * 0.25


def pad_tail(x, seconds):
    return np.concatenate([x, np.zeros(int(seconds * SR))])


# ---------------------------------------------------------------- drums

def kick(punch=1.0):
    t = t_arr(0.42)
    f = 45 + 120 * punch * np.exp(-t * 32)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)
    s += noise(len(t)) * np.exp(-t * 400) * 0.35
    return np.tanh(s * 1.8)


def snare(tone=190, bright=7000):
    t = t_arr(0.32)
    n = bp(noise(len(t)), 900, bright) * np.exp(-t * 18)
    return np.tanh((n * 1.4 + np.sin(2 * np.pi * tone * t) * np.exp(-t * 28) * 0.7) * 1.5)


def clap():
    t = t_arr(0.3)
    env = sum(np.exp(-np.clip(t - d, 0, None) * 60) * (t >= d) for d in (0, 0.011, 0.023)) + np.exp(-t * 12) * 0.5
    return bp(noise(len(t)), 1000, 5000) * env


def hat(open_=False):
    t = t_arr(0.25 if open_ else 0.05)
    return hp(noise(len(t)), 7000) * np.exp(-t * (14 if open_ else 90))


def crash(dur=2.2):
    t = t_arr(dur)
    return hp(noise(len(t)), 3500) * np.exp(-t * 2.2)


# ---------------------------------------------------------------- mixing

class Mixer:
    """Stereo bus of fixed length. Sound running past the end wraps to the start: stems loop seamlessly."""

    def __init__(self, seconds):
        self.n = int(round(seconds * SR))
        self.buf = np.zeros((self.n, 2))

    def add(self, start, sig, gain=1.0, pan=0.0):
        if sig.ndim == 1:
            sig = np.stack([sig * np.sqrt(0.5 * (1 - pan)), sig * np.sqrt(0.5 * (1 + pan))], 1)
        sig = sig * gain
        i = int(round(start * SR)) % self.n
        while len(sig):
            k = min(len(sig), self.n - i)
            self.buf[i:i + k] += sig[:k]
            sig, i = sig[k:], 0


def master(stems, peak=0.9):
    """Scales all stems of a track together so that their sum never clips."""
    total = sum(stems.values())
    k = peak / max(np.abs(total).max(), 1e-9)
    return {name: np.tanh(s * k * 1.15) / np.tanh(1.15) for name, s in stems.items()}
