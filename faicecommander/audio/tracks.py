"""Procedural soundtrack. Each track is a set of equally long, seamlessly looping stems that the
MusicDirector fades in and out (drums, bass, arp, pad, lead, heartbeat ...)."""
import numpy as np

from .synth import (
    BAR, BEAT, STEP, Mixer, clap, crash, fade, hat, kick, lp, master, noise, note, pad_tail, reverb, rng, saw, sine,
    snare, square, sweep_lp, t_arr,
)

BARS = 16
LOOP = BARS * BAR


# ---------------------------------------------------------------- instruments

def supersaw_pad(m, start, dur, chord, gain, cutoff=1100, pan_spread=0.25):
    t = t_arr(dur)
    s = sum(saw(f * (1 + d), t, ph0=np.random.random()) for f in chord for d in (-0.007, 0.0, 0.006))
    s = lp(s, cutoff)
    env = np.minimum(1, t / 1.0) * np.minimum(1, (dur - t) / 0.7)
    s = reverb(pad_tail(s * env, 2.5), 0.5)
    m.add(start, s, gain, -pan_spread)
    m.add(start + 0.011, s, gain, pan_spread)


def reese(m, start, dur, f, gain, cutoff=380):
    t = t_arr(dur)
    s = saw(f * 1.006, t) + saw(f * 0.994, t, 0.37) + 0.8 * sine(f, t)
    s = np.tanh(lp(s, cutoff, 4) * 2.2)
    s = lp(s, 900) + 0.6 * sine(f, t)
    m.add(start, fade(s, 0.008, 0.02), gain)


def wobble(m, start, dur, f, rate_steps, gain, bend=0.0, drive=2.6):
    """Jump-up / dubstep bass: detuned saws through an LFO-swept resonant low-pass, optional pitch drop."""
    t = t_arr(dur)
    freq = f * (1 + bend * np.exp(-t * 18))
    x = saw(freq, t) + 0.7 * saw(freq * 1.01, t) + 0.5 * saw(freq / 2, t)
    lfo = 0.5 - 0.5 * np.cos(2 * np.pi * t / (rate_steps * STEP))
    y = sweep_lp(x, 90 + 2400 * lfo ** 1.6, q=1.6)
    y = np.tanh(y * drive) + 0.55 * sine(freq / 2, t)
    m.add(start, fade(y, 0.006, 0.03), gain)


def pluck(f, dur=STEP * 1.6, cutoff=3200, decay=16):
    t = t_arr(dur)
    s = square(f, t) * 0.6 + saw(f * 1.003, t) * 0.4
    return lp(s * np.exp(-t * decay), cutoff)


def arp(m, bar, seq, gain, echo=True, cutoff=3200):
    for st, n in enumerate(seq):
        if n is None:
            continue
        s = pluck(note(n), cutoff=cutoff)
        t0 = bar * BAR + st * STEP
        m.add(t0, s, gain, -0.35)
        if echo:
            m.add(t0 + 3 * STEP, s, gain * 0.35, 0.5)
            m.add(t0 + 6 * STEP, s, gain * 0.15, -0.5)


def lead(m, start, dur, f, gain, vibrato=5.0):
    t = t_arr(dur)
    fv = f * (1 + 0.006 * np.sin(2 * np.pi * vibrato * t) * np.minimum(1, t / 0.25))
    s = saw(fv, t) + 0.5 * square(fv * 2.001, t, 0.3)
    s = lp(s, 2600) * np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.05)
    s = reverb(pad_tail(s, 1.5), 0.35)
    m.add(start, s, gain, 0.15)
    m.add(start + 3 * STEP, s, gain * 0.3, -0.4)


def sonar_ping(freq=1320):
    t = t_arr(1.2)
    return (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * 2 * freq * t)) * np.exp(-t * 7)


def heartbeat_stem(seed):
    rng(seed)
    m = Mixer(LOOP)
    t = t_arr(0.35)
    thump = np.sin(2 * np.pi * (48 + 30 * np.exp(-t * 20)) * t) * np.exp(-t * 14)
    thump = lp(thump + noise(len(t)) * np.exp(-t * 80) * 0.1, 400)
    for b in range(int(LOOP / (2 * BEAT))):
        t0 = b * 2 * BEAT
        m.add(t0, thump, 1.0)
        m.add(t0 + 0.24, thump, 0.65)
    return m.buf


# ---------------------------------------------------------------- tracks

def track_void():
    """Title, calibration, game over: mysterious, sparse, with sonar pings."""
    rng(1)
    pad, sonar = Mixer(LOOP), Mixer(LOOP)
    chords = [[note(n) for n in c] for c in (("F2", "C3", "Ab3", "Eb4", "G4"), ("Db2", "Ab2", "F3", "C4"),
                                             ("Bb1", "F2", "Db3", "Ab3", "C4"), ("C2", "G2", "Eb3", "Bb3", "D4"))]
    for i, ch in enumerate(chords):
        supersaw_pad(pad, i * 4 * BAR, 4 * BAR + 0.6, ch, 0.05, cutoff=800, pan_spread=0.4)
    t = t_arr(LOOP)
    wind = lp(noise(len(t)), 500) * (0.5 + 0.5 * np.sin(2 * np.pi * t / LOOP * 2)) * 0.15
    pad.add(0, wind, 1.0)
    for b in range(0, BARS, 2):
        for k, p in enumerate((0, -0.6, 0.6, -0.3)):
            sonar.add(b * BAR + k * 0.27, sonar_ping(), 0.3 * 0.55 ** k, p)
    return master({"pad": pad.buf, "sonar": sonar.buf}, 0.7)


def _dnb_drums(m, bar, fill=False, heavy=False):
    t0 = bar * BAR
    K, S, H, HO = kick(1.2 if heavy else 1.0), snare(), hat(), hat(True)
    for st in ((0, 10) if not heavy else (0, 3, 10)):
        m.add(t0 + st * STEP, K, 0.95)
    for st in (4, 12):
        m.add(t0 + st * STEP, S, 0.7)
        if heavy:
            m.add(t0 + st * STEP, clap(), 0.45)
    m.add(t0 + 7 * STEP, S, 0.18, 0.2)
    m.add(t0 + 15 * STEP, S, 0.12, -0.2)
    for st in range(16):
        m.add(t0 + st * STEP + (0.012 if st % 2 else 0), H, 0.22 if st % 2 == 0 else 0.1, 0.35)
    if bar % 2 == 1:
        m.add(t0 + 14 * STEP, HO, 0.15, -0.3)
    if fill:
        for k, st in enumerate(range(8, 16)):
            m.add(t0 + st * STEP, S, 0.2 + k * 0.06, -0.2 + k * 0.05)
    if bar % 8 == 0:
        m.add(t0, crash(), 0.25)


def track_neural_breaks():
    """Level 1: liquid drum & bass, rolling reese bass."""
    rng(2)
    st = {k: Mixer(LOOP) for k in ("drums", "bass", "arp", "pad", "lead")}
    roots = ["F1", "F1", "Db2", "Db2", "Ab1", "Ab1", "Eb1", "Gb1"] * 2
    arp_a = ["F4", "C5", "Ab4", "Eb5", "F4", "C5", "Ab4", "F5", "F4", "C5", "Ab4", "Eb5", "G5", "Eb5", "C5", "Ab4"]
    arp_b = ["Db5", "Ab4", "F4", "C5", "Db5", "Ab4", "F5", "C5", "Db5", "Ab4", "F4", "Eb5", "F5", "Eb5", "Db5", "C5"]
    for b in range(BARS):
        _dnb_drums(st["drums"], b, fill=(b % 8 == 7))
        f = note(roots[b])
        for s0, ln in ((0, 6), (6, 4), (10, 6)):
            reese(st["bass"], b * BAR + s0 * STEP, ln * STEP * 0.95, f, 0.34)
        arp(st["arp"], b, arp_a if roots[b] in ("F1", "Ab1", "Eb1", "Gb1") else arp_b, 0.17)
    chords = [("F3", "Ab3", "C4", "Eb4", "G4"), ("Db3", "F3", "Ab3", "C4"), ("Ab2", "C3", "Eb3", "G3"),
              ("Eb3", "Gb3", "Bb3", "Db4")]
    for i in range(BARS // 2):
        supersaw_pad(st["pad"], i * 2 * BAR, 2 * BAR + 0.5, [note(n) for n in chords[i % 4]], 0.035)
    melody = [("C5", 0, 6), ("Ab4", 6, 4), ("Bb4", 10, 6), ("C5", 16, 4), ("Eb5", 20, 8), ("Db5", 28, 4),
              ("C5", 32, 6), ("Ab4", 38, 4), ("F4", 42, 6), ("G4", 48, 8), ("Ab4", 56, 8)]
    for rep in range(2):
        for n, s0, ln in melody:
            lead(st["lead"], rep * 8 * BAR + s0 * STEP * 2, ln * STEP * 2 * 0.95, note(n), 0.08)
    stems = master({k: m.buf for k, m in st.items()})
    stems["heartbeat"] = heartbeat_stem(22) * 0.5
    return stems


def track_debris():
    """Level 2: jump-up drum & bass - hard drums, pitch-dropping wobble bass, offbeat stabs, siren lead."""
    rng(3)
    st = {k: Mixer(LOOP) for k in ("drums", "bass", "arp", "pad", "lead")}
    roots = ["G1", "G1", "Eb1", "F1", "G1", "Bb1", "C2", "D2"] * 2
    for b in range(BARS):
        _dnb_drums(st["drums"], b, fill=(b % 4 == 3), heavy=True)
        f = note(roots[b])
        pattern = ((0, 3, 4, 0.6), (3, 3, 2, 0.0), (6, 4, 1, 0.3), (10, 2, 2, 0.0), (12, 4, 4, 0.8))
        for s0, ln, rate, bend in pattern:
            wobble(st["bass"], b * BAR + s0 * STEP, ln * STEP * 0.97, f * (2 if s0 == 10 else 1), rate, 0.3, bend)
        chord = [note(n) for n in (("G3", "Bb3", "D4") if b % 4 < 2 else ("Eb3", "G3", "Bb3"))]
        for s0 in (2, 6, 10, 14):
            t = t_arr(STEP * 0.9)
            stab = sum(saw(c, t) + saw(c * 1.01, t) for c in chord)
            st["arp"].add(b * BAR + s0 * STEP, lp(stab * np.exp(-t * 14), 2500), 0.1, 0.25 if s0 % 4 else -0.25)
    for i in range(BARS // 4):
        supersaw_pad(st["pad"], i * 4 * BAR, 4 * BAR + 0.5,
                     [note(n) for n in (("G2", "D3", "Bb3", "F4"), ("Eb2", "Bb2", "G3", "D4"))[i % 2]], 0.03)
    for rep in range(4):  # siren riff
        t0 = rep * 4 * BAR + 2 * BAR
        t = t_arr(2 * BAR)
        f = note("D5") * 2 ** ((np.sin(2 * np.pi * t / (BAR / 2)) * 0.5 + 0.5) * 5 / 12)
        s = lp(saw(f, t) + 0.6 * square(f * 0.5, t), 3000) * np.minimum(1, t / 0.1) * np.minimum(1, (2 * BAR - t) / 0.3)
        st["lead"].add(t0, reverb(pad_tail(s, 1.0), 0.3), 0.09, 0.2)
    stems = master({k: m.buf for k, m in st.items()})
    stems["heartbeat"] = heartbeat_stem(33) * 0.5
    return stems


TRACKS = {
    "void": track_void,
    "neural_breaks": track_neural_breaks,
    "debris": track_debris,
}

TITLES = {"void": "THE VOID", "neural_breaks": "NEURAL BREAKS", "debris": "DEBRIS RUNNER"}
