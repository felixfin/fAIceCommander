"""Catlien voices: a small source-filter synthesiser for meows, yowls, growls, hisses and purrs.

The source is a harmonic pulse train following a pitch contour (with jitter, growl roughness and
sub-harmonics for aggression); a time-varying formant envelope shapes it into "m-ia-ow" vowels.
"""
import numpy as np
from scipy.signal import istft, stft

from .synth import SR, hp, bp, lp, noise, reverb, t_arr

NPERSEG = 1024


def _out(y, peak):
    return y / max(np.abs(y).max(), 1e-9) * peak


def contour(t, points):
    """Piecewise-linear curve through (fraction of the duration, value) points."""
    xs, ys = zip(*points)
    return np.interp(t / max(t[-1], 1e-9), xs, ys)


def _smooth_noise(n, rate_hz, rng):
    k = max(2, int(n / SR * rate_hz) + 2)
    return np.interp(np.arange(n), np.linspace(0, n - 1, k), rng.normal(size=k))


def _source(f0, rough, sub, rng, max_h=40):
    """Band-limited harmonic pulse train; rough = growl (fast irregular amplitude), sub = 1/2 f0 share."""
    n = len(f0)
    f = f0 * (1 + 0.012 * _smooth_noise(n, 30, rng))  # jitter
    ph = np.cumsum(f) / SR * 2 * np.pi
    s = np.zeros(n)
    for k in range(1, max_h + 1):
        mask = (k * f) < SR * 0.42
        if not mask.any():
            break
        s += np.sin(k * ph) * mask / k ** 1.05
        if sub > 0 and k % 2:  # sub-harmonic series (period doubling = rasp)
            s += np.sin((k - 0.5) * ph) * mask * sub / k ** 1.2
    if rough > 0:
        growl = 1 + rough * (np.sin(np.cumsum(55 + 25 * _smooth_noise(n, 8, rng)) / SR * 2 * np.pi)
                             + 0.6 * _smooth_noise(n, 70, rng))
        s *= np.clip(growl, 0, None)
    return s


def _formants(x, tracks, dur):
    """tracks: [(freq_points, bandwidth, gain), ...] with freq_points as for contour()."""
    f, times, Z = stft(x, SR, nperseg=NPERSEG)
    tt = np.clip(times, 0, dur)
    env = np.full((len(f), len(times)), 0.006)
    for points, bw, gain in tracks:
        fc = contour(tt, points) if len(tt) > 1 else np.array([points[0][1]])
        env += gain / (1 + ((f[:, None] - fc[None, :]) / bw) ** 2)
    _, y = istft(Z * env, SR, nperseg=NPERSEG)
    return y[: len(x)]


def voice(dur, f0_points, vowels, rough=0.0, sub=0.0, hiss=0.0, breath=0.05, attack=0.03, release=0.12,
          formant_scale=1.0, seed=1):
    """One cat call. vowels: formant tracks [(points, bw, gain)]; formant_scale shifts them (big cat < 1)."""
    rng = np.random.default_rng(seed)
    t = t_arr(dur)
    f0 = contour(t, f0_points)
    src = _source(f0, rough, sub, rng)
    src += noise(len(t)) * breath
    tracks = [([(p, v * formant_scale) for p, v in pts], bw * formant_scale, g) for pts, bw, g in vowels]
    y = _formants(src, tracks, dur)
    env = np.minimum(1, t / attack) * np.minimum(1, (dur - t) / release)
    env *= contour(t, [(0, 0.7), (0.15, 1.0), (0.7, 0.9), (1, 0.6)])
    y = y * env
    if hiss > 0:  # the spitting "hhh" of an angry cat, strongest at the start
        h = bp(noise(len(t)), 2500, 9000) * contour(t, [(0, 1.0), (0.25, 0.5), (1, 0.15)]) * env
        y += h * hiss * np.abs(y).max()
    return y / max(np.abs(y).max(), 1e-9)


MEOW = [([(0, 450), (0.35, 950), (0.75, 700), (1, 420)], 140, 1.0),
        ([(0, 2100), (0.35, 1500), (0.75, 1100), (1, 800)], 220, 0.7),
        ([(0, 3000), (1, 2700)], 300, 0.35),
        ([(0, 4300), (1, 4000)], 450, 0.15)]


# a clear "mee-AOW": closed "m/i" (low F1, high F2), wide open "a", rounded "ow" (both formants fall)
MEOW_CLEAR = [([(0, 300), (0.18, 350), (0.42, 950), (0.75, 750), (1, 450)], 110, 1.0),
              ([(0, 2500), (0.18, 2300), (0.42, 1500), (0.75, 1100), (1, 800)], 180, 0.85),
              ([(0, 3300), (0.5, 2800), (1, 2600)], 260, 0.4)]


def angry_meow(variant=1):
    """Raider fire: an unmistakable, angry 'mee-AOW' - mostly tonal, a little rasp, a short spit."""
    shapes = {1: (0.6, [(0, 560), (0.3, 980), (0.6, 880), (1, 520)]),
              2: (0.7, [(0, 650), (0.25, 1150), (0.55, 1000), (1, 560)]),
              3: (0.55, [(0, 480), (0.35, 860), (1, 430)])}
    dur, f0 = shapes[variant]
    y = voice(dur, f0, MEOW_CLEAR, rough=0.12, sub=0.08, hiss=0.12, breath=0.02, attack=0.02, release=0.1,
              seed=10 + variant)
    return _out(reverb(y, 0.1, 0.5), 0.95)


def mother_meow():
    """Her shots: the same call from a huge throat."""
    y = voice(0.9, [(0, 160), (0.3, 300), (0.7, 240), (1, 120)], MEOW, rough=0.6, sub=0.5, hiss=0.2,
              formant_scale=0.62, seed=30)
    return _out(reverb(lp(y, 6000), 0.3, 1.4), 0.9)


def mother_roar():
    """Phase changes and dives: a long, rolling big-cat roar."""
    dur = 2.4
    y = voice(dur, [(0, 85), (0.2, 150), (0.5, 135), (0.85, 95), (1, 70)],
              [([(0, 380), (0.3, 700), (1, 420)], 130, 1.0), ([(0, 1100), (0.4, 950), (1, 700)], 200, 0.6),
               ([(0, 2200), (1, 2000)], 300, 0.25)], rough=0.9, sub=0.7, breath=0.25, attack=0.08, release=0.5,
              seed=31)
    t = t_arr(dur)
    rumble = lp(noise(len(t)), 220) * contour(t, [(0, 0), (0.2, 1), (1, 0)]) * 0.6
    return _out(reverb(np.tanh((y + rumble) * 1.8), 0.35, 1.8), 0.95)


def mother_scream():
    """When she fires a hypno pulse: an eerie high yowl over a low growl."""
    dur = 2.0
    hi = voice(dur, [(0, 600), (0.2, 1100), (0.45, 900), (0.6, 1200), (1, 500)], MEOW, rough=0.2, sub=0.1,
               hiss=0.1, release=0.5, seed=32)
    lo = voice(dur, [(0, 110), (0.5, 140), (1, 90)], MEOW, rough=0.8, sub=0.6, formant_scale=0.55, seed=33)
    return _out(reverb(hi * 0.7 + lo * 0.6, 0.4, 1.6), 0.85)


def mother_death():
    """Her last scream: rising, breaking and falling away into the explosion."""
    dur = 4.0
    y = voice(dur, [(0, 400), (0.15, 1100), (0.3, 1300), (0.55, 700), (0.8, 220), (1, 70)], MEOW, rough=0.7,
              sub=0.6, hiss=0.3, release=1.2, seed=34)
    low = voice(dur, [(0, 120), (0.3, 180), (1, 50)], MEOW, rough=1.0, sub=0.8, formant_scale=0.5, seed=35)
    return _out(reverb(np.tanh((y * 0.8 + low * 0.7) * 1.6), 0.45, 2.0), 0.9)


def hypno_scream():
    """Start of a hypno pulse: a chorus of cats screaming through the light."""
    dur = 2.2
    t = t_arr(dur)
    out = np.zeros(len(t))
    for k, (shift, delay) in enumerate(((1.0, 0.0), (1.19, 0.08), (0.84, 0.15), (1.42, 0.22))):
        y = voice(dur - delay, [(0, 500 * shift), (0.3, 1000 * shift), (0.6, 850 * shift), (1, 450 * shift)],
                  MEOW, rough=0.3, sub=0.2, hiss=0.15, release=0.6, seed=40 + k)
        i = int(delay * SR)
        out[i:i + len(y)] += y * (0.9 - k * 0.12)
    return _out(reverb(out, 0.45, 1.7), 0.85)


def hypno_loop(dur=4.0):
    """Seamless loop while a pulse is active: a low drone with cats yowling in the distance."""
    t = t_arr(dur)
    drone = np.sin(2 * np.pi * 55 * t) * 0.5 + np.sin(2 * np.pi * 110.5 * t) * 0.3 + np.sin(2 * np.pi * 165 * t) * 0.2
    drone *= 0.7 + 0.3 * np.sin(2 * np.pi * t / dur * 2)
    yowls = np.zeros(len(t) + int(1.5 * SR))
    for k, (at, f) in enumerate(((0.2, 700), (1.6, 560), (2.7, 820))):
        y = voice(1.6, [(0, f * 0.7), (0.4, f * 1.3), (0.7, f), (1, f * 0.6)], MEOW, rough=0.25, sub=0.2,
                  release=0.6, seed=50 + k)
        i = int(at * SR)
        yowls[i:i + len(y)] += y * 0.55
    wet = reverb(yowls, 0.6, 1.8)
    loop = wet[: len(t)].copy()
    tail = wet[len(t):]
    loop[: len(tail)] += tail  # wrap the reverb tail round to the start: no seam
    out = drone * 0.6 + lp(loop, 4500) * 0.8
    return out / np.abs(out).max() * 0.5


def squeak():
    """A space mouse squeals (thrown, or shot down)."""
    dur = 0.18
    t = t_arr(dur)
    f0 = contour(t, [(0, 2800), (0.4, 4200), (1, 3000)])
    s = np.sin(np.cumsum(f0) / SR * 2 * np.pi) * np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.05)
    s += 0.3 * np.sin(2 * np.cumsum(f0) / SR * 2 * np.pi) * np.exp(-t * 20)
    return s / np.abs(s).max() * 0.6


def mouse_throw():
    t = t_arr(0.45)
    whoosh = bp(noise(len(t)), 600, 3500) * np.sin(np.pi * t / 0.45) ** 2 * 0.5
    sq = np.concatenate([np.zeros(int(0.08 * SR)), squeak()])[: len(t)]
    sq = np.pad(sq, (0, len(t) - len(sq)))
    return (whoosh + sq) / np.abs(whoosh + sq).max() * 0.6


def purr_growl(dur=3.2):
    """Belly roll: a deep purr that swells into a growl while the tractor pulls you in."""
    t = t_arr(dur)
    purr_env = 0.5 + 0.5 * np.sin(2 * np.pi * 26 * t) ** 2  # ~26 Hz purr pulses
    body = lp(noise(len(t)), 400) * purr_env
    growl = voice(dur, [(0, 90), (0.5, 130), (1, 100)],
                  [([(0, 400), (1, 500)], 120, 1.0), ([(0, 1000), (1, 900)], 200, 0.4)],
                  rough=0.9, sub=0.6, breath=0.2, attack=0.4, release=0.5, seed=60)
    hum = np.sin(2 * np.pi * 52 * t) * purr_env * 0.4
    y = body * contour(t, [(0, 0.6), (1, 0.9)]) + growl * contour(t, [(0, 0.2), (0.5, 0.8), (1, 0.5)]) + hum
    y = hp(y, 35) * np.minimum(1, t / 0.2) * np.minimum(1, (dur - t) / 0.4)
    return y / np.abs(y).max() * 0.75
