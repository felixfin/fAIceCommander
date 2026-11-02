"""Procedural sound effects. Each function returns a mono float array at synth.SR."""
import numpy as np

from .synth import SR, bp, hp, lp, noise, reverb, rng, saw, sine, square, sweep_lp, t_arr


def _norm(x, peak=0.9):
    return x / max(np.abs(x).max(), 1e-9) * peak


def laser():
    """The classic 'zirrr': falling square/FM sweep with a bright click."""
    t = t_arr(0.22)
    f = 2200 * np.exp(-t * 14) + 260
    s = square(f, t, 0.35) * 0.5 + sine(f * 1.5 + 300 * np.sin(2 * np.pi * 70 * t), t) * 0.5
    s = lp(s, 6000) * np.exp(-t * 11)
    s[: int(0.004 * SR)] += noise(int(0.004 * SR)) * 0.6
    return _norm(s, 0.7)


def beam_loop():
    """1 s seamless loop: electric buzz with a shimmer (integer cycles at every frequency)."""
    t = t_arr(1.0)
    s = saw(110, t) + 0.7 * saw(220, t, 0.3) + 0.25 * sine(2200, t) * (0.5 + 0.5 * sine(30, t))
    s = s * (0.8 + 0.2 * sine(15, t))
    s += bp(noise(len(t)), 3000, 8000) * 0.15
    return _norm(lp(s, 5000), 0.55)


def shield_loop():
    t = t_arr(1.0)
    s = sine(60, t) * 0.6 + saw(120, t) * 0.25 + sine(1200, t) * 0.08 * (0.5 + 0.5 * sine(6, t))
    return _norm(lp(s, 1800) * (0.85 + 0.15 * sine(4, t)), 0.45)


def shield_on():
    t = t_arr(0.45)
    f = 200 * 2 ** (t / 0.45 * 2.5)
    return _norm(reverb(saw(f, t) * np.minimum(1, (0.45 - t) / 0.1) * 0.5 + sine(f * 2, t) * 0.3, 0.3), 0.6)


def shield_off():
    return shield_on()[::-1] * 0.8


def explosion(size=1.0, dur=1.6):
    """Low boom + filtered debris noise + crackle; bigger size = deeper and longer."""
    dur *= 0.7 + 0.5 * size
    t = t_arr(dur)
    boom = np.sin(2 * np.pi * (30 + 70 / size * np.exp(-t * 7)) * t) * np.exp(-t * (3.5 / size))
    rumble = lp(noise(len(t)), 300 + 500 / size) * np.exp(-t * (2.5 / size))
    crackle = hp(noise(len(t)) * (np.random.random(len(t)) > 0.995), 2000) * np.exp(-t * 3) * 3
    hit = bp(noise(len(t)), 400, 4000) * np.exp(-t * 18)
    return _norm(np.tanh((boom * 1.2 + rumble * 0.8 + crackle * 0.3 + hit * 0.6) * 1.6), 0.85)


def thud():
    """Dull hull impact."""
    t = t_arr(0.5)
    s = np.sin(2 * np.pi * (55 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 9)
    s += lp(noise(len(t)), 900) * np.exp(-t * 25) * 0.7
    s += np.sin(2 * np.pi * 180 * t) * np.exp(-t * 20) * 0.3  # metal ring
    return _norm(np.tanh(s * 2.2), 0.95)


def nuke_launch():
    t = t_arr(1.0)
    whoosh = sweep_lp(hp(noise(len(t)), 250), 400 + 4000 * t, q=1.2) * np.minimum(1, t / 0.05) * np.exp(-t * 2.2)
    ign = np.sin(2 * np.pi * (80 * np.exp(-t * 12) + 40) * t) * np.exp(-t * 10)
    return _norm(whoosh * 0.9 + ign * 0.8, 0.8)


def nuke_boom():
    t = t_arr(3.5)
    s = explosion(2.4, 2.4)
    s = np.concatenate([s, np.zeros(max(0, len(t) - len(s)))])[: len(t)]
    sub = np.sin(2 * np.pi * (22 + 40 * np.exp(-t * 3)) * t) * np.exp(-t * 0.9)
    return _norm(np.tanh(s + sub * 0.9), 0.95)


def crack():
    """Category 2 asteroid splitting."""
    t = t_arr(0.35)
    s = hp(noise(len(t)), 1500) * np.exp(-t * 22) + lp(noise(len(t)), 600) * np.exp(-t * 9) * 0.8
    return _norm(s, 0.75)


def switch():
    t = t_arr(0.09)
    return _norm(square(1400, t, 0.3) * np.exp(-t * 50) + square(2100, t) * np.exp(-t * 70) * 0.5, 0.45)


def empty():
    t = t_arr(0.22)
    return _norm(square(95, t) * np.exp(-t * 9) + saw(97, t) * 0.5 * np.exp(-t * 9), 0.5)


def beep(freq=880, dur=0.16):
    t = t_arr(dur)
    return _norm(sine(freq, t) * np.minimum(1, (dur - t) / 0.03) * np.minimum(1, t / 0.005), 0.5)


def chime():
    """Star reached: rising arpeggio."""
    out = np.zeros(int(2.2 * SR))
    for k, f in enumerate((523.25, 659.25, 783.99, 1046.5, 1318.5)):
        t = t_arr(1.4)
        s = (sine(f, t) + 0.3 * sine(2 * f, t)) * np.exp(-t * 3)
        i = int(k * 0.11 * SR)
        out[i:i + len(s)] += s[: len(out) - i]
    return _norm(reverb(out, 0.4), 0.7)


def game_over():
    """Tape-stop power down."""
    t = t_arr(2.0)
    f = 220 * np.exp(-t * 1.6)
    s = saw(f, t) + saw(f * 1.5, t) * 0.5 + sine(f / 2, t)
    s = lp(s, 1500) * np.exp(-t * 1.2)
    return _norm(reverb(s, 0.35), 0.75)


def alarm():
    """Low hull warning blip."""
    t = t_arr(0.35)
    return _norm((square(740, t, 0.5) * (t < 0.15) + square(560, t, 0.5) * (t >= 0.17)) * 0.6 * np.exp(-t * 3), 0.4)


SFX = {
    "laser": laser, "beam_loop": beam_loop, "shield_loop": shield_loop, "shield_on": shield_on,
    "shield_off": shield_off, "boom_small": lambda: explosion(0.8), "boom_big": lambda: explosion(1.5),
    "thud": thud, "nuke_launch": nuke_launch, "nuke_boom": nuke_boom, "crack": crack, "switch": switch,
    "empty": empty, "beep": beep, "beep_high": lambda: beep(1320, 0.22), "chime": chime, "game_over": game_over,
    "alarm": alarm,
}


def render_all(seed=7):
    rng(seed)
    np.random.seed(seed)
    return {name: fn() for name, fn in SFX.items()}
