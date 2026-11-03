"""Sound effects for the cutscenes: thunder, radio static, robot servos, welding arcs, power-up,
heavy locks, fireworks and a cheering crowd. Mono float arrays at synth.SR."""
import numpy as np

from . import cats
from .synth import SR, bp, hp, lp, noise, reverb, saw, sine, sweep_lp, t_arr


def _n(x, peak=0.85):
    return x / max(np.abs(x).max(), 1e-9) * peak


def thunder():
    """A close lightning strike: sharp crack, then a long rolling rumble."""
    t = t_arr(4.5)
    crack = hp(noise(len(t)), 1500) * np.exp(-t * 25)
    rumble = lp(noise(len(t)), 160) * (np.exp(-t * 0.9) * (0.6 + 0.4 * np.sin(2 * np.pi * 1.3 * t) ** 2))
    return _n(reverb(crack * 0.8 + rumble * 2.5, 0.4, 1.8))


def static():
    """A burst of radio static with crackles."""
    t = t_arr(0.9)
    s = bp(noise(len(t)), 800, 6000) * (0.5 + 0.5 * (np.random.random(len(t)) > 0.7))
    s *= np.minimum(1, t / 0.02) * np.minimum(1, (0.9 - t) / 0.2)
    return _n(s, 0.5)


def servo():
    """A robot arm moving: geared whine up and down."""
    t = t_arr(0.9)
    f = 300 + 500 * np.sin(np.pi * t / 0.9)
    s = saw(f, t) * 0.4 + saw(f * 2.02, t) * 0.2 + bp(noise(len(t)), 2000, 5000) * 0.1
    s = lp(s, 3000) * np.sin(np.pi * t / 0.9) ** 0.6
    return _n(s, 0.45)


def weld():
    """An arc welder: buzzing crackle with sputtering sparks."""
    t = t_arr(1.4)
    buzz = saw(100, t) * 0.3 + saw(200.5, t) * 0.2
    crack = hp(noise(len(t)), 3000) * (np.random.random(len(t)) > 0.93) * 2
    s = (buzz + crack + bp(noise(len(t)), 3000, 9000) * 0.4) * (0.6 + 0.4 * np.random.random(len(t)))
    return _n(s * np.minimum(1, t / 0.05) * np.minimum(1, (1.4 - t) / 0.3), 0.55)


def power_up():
    """Systems coming online: a rising turbine whine and a deep thump."""
    t = t_arr(2.6)
    f = 80 * 2 ** (t / 2.6 * 4)
    s = saw(f, t) * 0.3 + sine(f * 2, t) * 0.3 + sine(f * 3.01, t) * 0.1
    s = sweep_lp(s, 1200 + 5000 * t / 2.6) * np.minimum(1, t / 0.5)
    thump = sine(45 + 50 * np.exp(-(t - 2.3).clip(0) * 20), t) * np.exp(-(t - 2.3).clip(0) * 5) * (t > 2.3)
    return _n(reverb(s * np.minimum(1, (2.6 - t) / 0.15) + thump * 1.5, 0.3, 1.3))


def clunk():
    """A heavy lock engaging."""
    t = t_arr(0.8)
    s = sine(70 + 120 * np.exp(-t * 40), t) * np.exp(-t * 10)
    s += sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in ((310, 14), (820, 20), (1730, 30))) * 0.4
    s += hp(noise(len(t)), 2500) * np.exp(-t * 60) * 0.5
    return _n(reverb(np.tanh(s * 1.5), 0.25, 1.0))


def fw_launch():
    """A firework rocket: a rising whistle over a hiss."""
    t = t_arr(1.3)
    f = 900 + 1800 * (t / 1.3) ** 1.5
    s = sine(f, t) * 0.4 * np.minimum(1, t / 0.1) + hp(noise(len(t)), 3000) * 0.25
    return _n(s * np.minimum(1, (1.3 - t) / 0.1), 0.5)


def fw_burst():
    """The burst: a bang and a long tail of crackles."""
    t = t_arr(3.0)
    bang = lp(noise(len(t)), 1500) * np.exp(-t * 12) + sine(60 + 80 * np.exp(-t * 15), t) * np.exp(-t * 6)
    crackle = hp(noise(len(t)), 2500) * (np.random.random(len(t)) > 0.985) * 3 * np.exp(-t * 0.9) * (t > 0.3)
    return _n(reverb(np.tanh(bang * 1.5) + crackle * 0.5, 0.35, 1.6))


def cheer():
    """A crowd celebrating: dozens of rising 'yeah' voices over a roar."""
    dur = 4.0
    t = t_arr(dur)
    out = lp(noise(len(t)), 1800) * 0.25
    rng = np.random.default_rng(17)
    for k in range(24):
        f = rng.uniform(150, 360)
        d = rng.uniform(0.6, 1.4)
        y = cats.voice(d, [(0, f), (0.4, f * 1.3), (1, f * 1.1)],
                       [([(0, 500), (0.5, 750), (1, 650)], 120, 1.0), ([(0, 1800), (1, 1300)], 200, 0.6),
                        ([(0, 2600), (1, 2600)], 260, 0.25)], rough=0.15, breath=0.2, attack=0.05, release=0.2,
                       seed=100 + k)
        i = int(rng.uniform(0, dur - d) * SR)
        out[i:i + len(y)] += y * rng.uniform(0.15, 0.35)
    env = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 1.0)
    return _n(reverb(bp(out, 120, 6000) * env, 0.4, 1.6), 0.8)


def tinnitus():
    t = t_arr(3.0)
    return _n(sine(4100, t) * np.minimum(1, t / 0.05) * np.exp(-t * 0.9), 0.25)


def hypno_hum():
    """The Mother's hypno rings: a deep throb with a ghostly overtone sweep."""
    t = t_arr(3.0)
    s = sine(55, t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t)) + sweep_lp(saw(220, t), 300 + 2500 * np.sin(np.pi * t / 3), q=4) * 0.3
    return _n(reverb(s * np.sin(np.pi * t / 3), 0.4, 1.5), 0.7)


SFX = {"thunder": thunder, "static": static, "servo": servo, "weld": weld, "power_up": power_up, "clunk": clunk,
       "fw_launch": fw_launch, "fw_burst": fw_burst, "cheer": cheer, "tinnitus": tinnitus, "hypno_hum": hypno_hum}
