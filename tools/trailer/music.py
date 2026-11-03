"""The trailer score, composed against the EDL (tools/trailer/edl.py): every hard cut gets its hit.
Writes build/trailer/music.wav (stereo, 44.1 kHz).

Run: .venv/Scripts/python tools/trailer/music.py
"""
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import edl  # noqa: E402
from faicecommander.audio import cats  # noqa: E402
from faicecommander.audio.synth import (  # noqa: E402
    SR, Mixer, clap, crash, hat, hp, kick, lp, noise, note, rng, saw, sine, snare, t_arr,
)
from faicecommander.audio.tracks import (  # noqa: E402
    braam, choir, impact, ostinato, piano, reese, riser, strings, supersaw_pad, taiko, wobble,
)

OUT = ROOT / "build" / "trailer" / "music.wav"
DROP, DROP_END = 52.0, 75.0
BPM = 174
BEAT = 60 / BPM
BAR = 4 * BEAT
STEP = BEAT / 4


def cuts(t0, t1):
    return [at for at, _, src, _ in edl.CLIPS if t0 <= at < t1 and src[0] != "black"]


def ecg(m, t0, t1, every=1.1):
    t = t_arr(0.12)
    beep = np.sin(2 * np.pi * 1050 * t) * np.minimum(1, (0.12 - t) / 0.03)
    k = t0
    while k < t1:
        m.add(k, beep, 0.08, 0.2)
        k += every


def drop_section(st, t0, bars, cat):
    """Drum & bass drop: heavy drums, wobble / reese bass alternating, stabs, cat screams on the 1."""
    roots = ["C2", "C2", "Ab1", "Bb1"]
    chords = [("C3", "Eb3", "G3"), ("C3", "Eb3", "G3"), ("Ab2", "C3", "Eb3"), ("Bb2", "D3", "F3")]
    for b in range(bars):
        tb = t0 + b * BAR
        K, S, H = kick(1.3), snare(), hat()
        for s0 in (0, 3, 10):
            st["drums"].add(tb + s0 * STEP, K, 0.95)
        for s0 in (4, 12):
            st["drums"].add(tb + s0 * STEP, S, 0.75)
            st["drums"].add(tb + s0 * STEP, clap(), 0.4)
        for s0 in range(16):
            st["drums"].add(tb + s0 * STEP, H, 0.2 if s0 % 2 == 0 else 0.1, 0.3)
        if b % 4 == 3:
            for k, s0 in enumerate(range(8, 16)):
                st["drums"].add(tb + s0 * STEP, S, 0.2 + k * 0.07)
        if b % 4 == 0:
            st["drums"].add(tb, crash(2.0), 0.3)
        r = note(roots[b % 4])
        if (b // 2) % 2 == 0:
            wobble(st["bass"], tb, BAR * 0.98, r, (4, 2, 3, 1.5)[b % 4], 0.32, bend=0.6 if b % 4 == 3 else 0.0)
        else:
            for s0, ln in ((0, 6), (6, 4), (10, 6)):
                reese(st["bass"], tb + s0 * STEP, ln * STEP * 0.95, r, 0.34, cutoff=600)
        ch = [note(n) for n in chords[b % 4]]
        for s0 in (2, 6, 10, 14):
            t = t_arr(STEP * 1.5)
            stab = sum(saw(f * 2 * (1 + d), t) for f in ch for d in (-0.01, 0.0, 0.01))
            st["synth"].add(tb + s0 * STEP, lp(stab, 4500) * np.exp(-t * 10), 0.045, 0.3 if s0 % 8 == 2 else -0.3)
        if b % 2 == 0:
            st["fx"].add(tb, cat, 0.35, (-0.4, 0.4)[(b // 2) % 2])


def compose():
    rng(16)
    np.random.seed(16)
    total = edl.LENGTH + 4.0
    st = {k: Mixer(total, np.float32) for k in ("bed", "drums", "brass", "bass", "synth", "fx")}
    tt = t_arr(total)
    # an ever-present C drone that swells towards the drop and vanishes in the silences
    swell = np.interp(tt, [0, 8, 16.8, 28, 36, 44.5, 50.4, 52, 75, 83, 90, total],
                      [0.4, 0.7, 0.6, 0.9, 0.7, 0.8, 1.0, 0.0, 0.6, 1.0, 0.7, 0.0])
    for t0, t1 in ((27.2, 28.0), (30.5, 31.1), (50.4, 52.0), (81.8, 83.0)):  # silences
        swell *= 1 - np.clip(1 - np.minimum(np.abs(tt - t0), np.abs(tt - t1)) / 0.15, 0, 1) * ((tt > t0) & (tt < t1))
        swell[(tt > t0 + 0.1) & (tt < t1 - 0.05)] = 0.0
    drone = sine(note("C1"), tt) * 0.8 + saw(note("C2") * 1.002, tt) * 0.12 + saw(note("G2") * 0.998, tt) * 0.08
    st["bed"].add(0, lp(drone, 240) * swell, 0.9)
    del drone, tt
    # 0-8: heartbeat and ECG in the dark, a hit on the first card
    tb = t_arr(0.35)
    thump = lp(sine(48 + 30 * np.exp(-tb * 20), tb) * np.exp(-tb * 14), 400)
    k = 0.2
    while k < 7.5:
        st["drums"].add(k, thump, 0.6)
        st["drums"].add(k + 0.24, thump, 0.35)
        k += 1.05
    ecg(st["fx"], 0.4, 3.0)
    impact(st["fx"], 5.5, 0.7)
    braam(st["brass"], 5.5, 2.5, note("C2"), 0.22)
    # 8-16.8: a hit on every cut, taikos rolling underneath, low strings
    strings(st["bed"], 8.0, 9.0, [note(n) for n in ("C2", "G2", "C3", "Eb3")], 0.05)
    for i in range(18):
        st["drums"].add(8.0 + i * 0.5, taiko(0.5, 55), 0.3 + 0.02 * i)
    for at in cuts(8.0, 16.8):
        st["drums"].add(at, taiko(0.7, 45), 0.9)
        braam(st["brass"], at, 1.2, note("C2") * (1.0 if int(at) % 2 else 1.059), 0.12)
    # 16.8-27.2: the slaves - nervous strings, eerie choir, soft hits on the cards
    strings(st["bed"], 16.8, 10.5, [note(n) for n in ("B2", "C3", "Gb3", "G3")], 0.05, tremolo=7.0, cutoff=1800,
            attack=1.5)
    choir(st["bed"], 17.5, 9.5, [note(n) for n in ("C4", "Db4", "G4")], 0.1, "u")
    for at in (19.0, 23.8):
        impact(st["fx"], at, 0.55)
    # 28-36: the Mother - BRAAAM, a silence, the queen's face, the battle
    braam(st["brass"], 28.0, 2.6, note("C2"), 0.28)
    choir(st["bed"], 28.0, 2.6, [note(n) for n in ("C3", "Gb3", "C4")], 0.12, "a")
    riser(st["fx"], 29.0, 1.5, 0.15)
    impact(st["fx"], 31.1, 0.9)
    braam(st["brass"], 31.1, 2.6, note("Db2"), 0.32)
    ostinato(st["bed"], 33.5, 2.5, ["C3", "C3", "Eb3", "C3", "G3", "C3", "Ab3", "G3"], 0.165, 0.08)
    for i in range(16):
        st["drums"].add(33.5 + i * 0.165, taiko(0.6, 60 if i % 2 == 0 else 80), 0.6 if i % 4 == 0 else 0.35)
    # 36-44.5: one survived - a hit, then piano and a theme of hope
    impact(st["fx"], 36.0, 0.6)
    for i, (n_, at) in enumerate((("C5", 36.3), ("Eb5", 37.2), ("G4", 38.1), ("Ab4", 39.0), ("G4", 40.0),
                                   ("Eb5", 40.9), ("D5", 41.8), ("C5", 42.7))):
        piano(st["bed"], at, note(n_), 0.12, (-0.3, 0.3)[i % 2])
    for i, ch in enumerate((("C3", "G3", "C4", "Eb4"), ("Ab2", "Eb3", "C4"), ("Bb2", "F3", "D4"))):
        strings(st["bed"], 38.0 + i * 2.2, 2.6, [note(n) for n in ch], 0.045 + 0.01 * i, attack=0.6)
    impact(st["fx"], 40.6, 0.5)
    # 44.5-52: your face; a riser over gameplay micro-cuts, then silence before the drop
    choir(st["bed"], 44.5, 6.0, [note(n) for n in ("C4", "Eb4", "G4", "Bb4")], 0.1, "o")
    riser(st["fx"], 47.5, 2.9, 0.25)
    for at in cuts(48.0, 50.4):
        st["drums"].add(at, taiko(0.8, 50), 0.9)
        st["fx"].add(at, hp(noise(int(0.15 * SR)), 2000) * np.exp(-t_arr(0.15) * 30), 0.4)
    impact(st["fx"], 50.4, 0.5, sub=28)
    # 52-75: the drop
    bars = int((DROP_END - DROP) / BAR)
    drop_section(st, DROP, bars, cats.hypno_scream() * 0.8)
    for at in cuts(DROP, DROP_END):
        if at > DROP + 0.05:
            st["fx"].add(at, hp(noise(int(0.2 * SR)), 1500) * np.exp(-t_arr(0.2) * 18), 0.25)
    impact(st["fx"], DROP, 0.9)
    supersaw_pad(st["synth"], DROP, DROP_END - DROP, [note(n) for n in ("C3", "G3", "Eb4")], 0.02, cutoff=2200)
    # 75-83: the finale - half time, braams, the chain explosion, the big hit
    for b in range(3):
        tb = 75.0 + b * BAR * 2
        st["drums"].add(tb, kick(1.4), 1.0)
        st["drums"].add(tb + BAR, snare(160, 6000), 0.9)
        st["drums"].add(tb + BAR, clap(), 0.5)
        wobble(st["bass"], tb, BAR * 2 * 0.98, note("C2"), 3, 0.35, bend=0.5)
    braam(st["brass"], 75.0, 3.5, note("C2"), 0.3)
    choir(st["bed"], 75.0, 6.5, [note(n) for n in ("C3", "G3", "C4", "Eb4")], 0.13, "a")
    impact(st["fx"], 78.6, 0.8)
    impact(st["fx"], 80.8, 1.0, sub=26)
    # 83-90: the title - one last chord, then a tape stop into nothing
    impact(st["fx"], 83.0, 1.0)
    braam(st["brass"], 83.0, 6.0, note("C2"), 0.34)
    choir(st["bed"], 83.0, 6.5, [note(n) for n in ("C3", "G3", "C4", "E4", "G4")], 0.16, "a")
    strings(st["bed"], 83.0, 6.5, [note(n) for n in ("C3", "G3", "C4", "E4")], 0.05, attack=0.3)
    mix = sum(m.buf.astype(np.float64) for m in st.values())
    # the tape stop at the very end
    a, b = int(88.6 * SR), int(90.0 * SR)
    seg = mix[a:b]
    speed = np.linspace(1.0, 0.05, len(seg))
    pos = np.cumsum(speed)
    pos = np.clip(pos, 0, len(seg) - 1)
    mix[a:b] = np.stack([np.interp(pos, np.arange(len(seg)), seg[:, c]) for c in (0, 1)], 1) * np.linspace(1, 0, len(seg))[:, None]
    mix[b:] = 0
    return mix / np.abs(mix).max() * 0.85


if __name__ == "__main__":
    mix = compose()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(OUT), SR, mix.astype(np.float32))
    print("wrote", OUT, round(len(mix) / SR, 1), "s")
