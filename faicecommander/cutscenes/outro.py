"""The outro after the Mother falls: her ship tears itself apart, the shockwave rolls over you, the
leaderless swarm crashes into itself, the collars fall - and the freed worlds party under fireworks.
James remembers his name. Then the credits (with more fireworks). Shot lengths: timeline.OUTRO."""
import math

import numpy as np

from ..render import models as M
from .engine import Cutscene, Line, Shot
from .fireworks import Fireworks
from .props import Booms, Drifters, backlight, cached_copy, helmet, human, human_ship, lerp, look, shake, smoke
from .timeline import OUTRO

LINES = [
    ("outro_01", "The Mother is dead."),
    ("outro_02", "Across the galaxy, the swarm loses its mind."),
    ("outro_03", "On a thousand worlds, the collars fall."),
    ("outro_04", "My name is Honor - James Nathaniel Honor."),
]
AFTERMATH = {"pad": 1.0, "choir": 0.6}
BUILD = {"pad": 1.0, "choir": 1.0, "bass": 0.7, "drums": 0.5, "chords": 0.5}
PARTY = {"pad": 1.0, "choir": 1.0, "bass": 1.0, "drums": 1.0, "chords": 1.0, "lead": 1.0}


def _line(at, idx, style="caption"):
    line_id, text = LINES[idx]
    return Line(at, text, line_id, style)


def _eye(root, app):
    app.backdrop.set_visible(True, stars=False)
    app.audio.music.set_layers(AFTERMATH)
    ship = app.world.mother_model.get().copyTo(root)
    app.audio.sfx.play("mother_death", 1.0)
    return {"ship": ship, "booms": Booms(app, root), "next": 0.0, "rng": np.random.default_rng(3), "big": False}


def _eye_update(t, dt, s, app):
    s["booms"].update(dt)
    s["next"] -= dt
    rng = s["rng"]
    if s["next"] <= 0 and t < 6.5:
        s["next"] = 0.22
        k = t / 6.5  # chain reaction from the bridge outwards along the ribs
        s["booms"].add((rng.uniform(-6, 6) * k, -1.2 + rng.uniform(-1, 4) * k, 1.5), 0.8 + 1.8 * k)
        app.audio.sfx.play("boom_big" if k > 0.5 else "boom_small", 0.6)
        if rng.random() < 0.3:
            app.cinema.flicker(0.3)
    s["ship"].setColorScale(0.6 + 0.6 * t / 7.5, 0.55, 0.55, 1)
    if t > 6.4 and not s["big"]:
        s["big"] = True
        app.flash.trigger(0.95, (1.0, 0.95, 0.9))
        app.audio.sfx.play("nuke_boom")
        s["ship"].hide()
        for _ in range(8):
            s["booms"].add((rng.uniform(-5, 5), rng.uniform(-3, 3), 1.2), 3.0)
    amount = 0.03 + 0.1 * (t / 7.5) ** 2
    look(app, shake(lerp((0.9, -4.6, 3.0), (2, -16, 9), t / 7.5), amount, rng), (0, -1.0, 2.2))


def _wave(root, app):
    ship = human_ship(app, root, (0, 0, 0), grey=False)
    ring = app.world.fx_tpl.ring.copyTo(root)
    ring.setPos(0, 40, 0)
    debris = Drifters(root, 60, (-15, -10, -4), (15, 50, 6), (0, -14, 0), (1.0, 0.6, 0.3, 0.8), (0.04, 0.12), seed=8)
    return {"ship": ship, "ring": ring, "debris": debris, "rng": np.random.default_rng(4), "hit": False}


def _wave_update(t, dt, s, app):
    s["debris"].update(dt, t)
    r = 2 + t * 9
    s["ring"].setScale(r, r, 1)
    s["ring"].setColorScale(1, 1, 1, max(0.0, 1 - t / 7))
    if t > 3.6 and not s["hit"]:  # the shockwave reaches you
        s["hit"] = True
        app.flash.trigger(0.5, (0.7, 0.85, 1.0))
        app.audio.sfx.play("boom_big", 1.0)
    jolt = 0.25 * math.exp(-(t - 3.6) * 2) if t > 3.6 else 0.0
    s["ship"].setR(10 * math.sin(t * 7) * jolt * 4)
    look(app, shake((4, -7, 2.5), jolt, s["rng"]), (0, 3, 0))


def _chaos(root, app):
    app.audio.music.set_layers(BUILD)
    raiders = []
    rng = np.random.default_rng(5)
    for _ in range(16):
        r = app.world.raider_tpl.store.copyTo(root)
        r.setScale(1.4)
        r.setPos(rng.uniform(-12, 12), rng.uniform(0, 24), rng.uniform(-3, 5))
        raiders.append((r, rng.normal(0, 2.5, 3), rng.uniform(-120, 120, 3)))
    return {"raiders": raiders, "booms": Booms(app, root), "next": 0.6}


def _chaos_update(t, dt, s, app):
    s["booms"].update(dt)
    for r, v, spin in s["raiders"]:
        r.setPos(r.getPos() + tuple(v * dt))
        r.setHpr(r.getHpr() + tuple(spin * dt))  # drifting, tumbling, leaderless
    s["next"] -= dt
    if s["next"] <= 0 and s["raiders"]:
        s["next"] = 0.55
        r, _, _ = s["raiders"].pop(0)
        s["booms"].add(tuple(r.getPos()), 2.0)
        r.removeNode()
        app.audio.sfx.play(f"meow_{1 + len(s['raiders']) % 3}", 0.5)
        app.audio.sfx.play("boom_small", 0.7)
    look(app, (0, -18 + t * 0.8, 6), (0, 8, 1))


def _collars(root, app):
    app.backdrop.set_visible(False)
    backlight(root, (0, 7, 2.0), 11.0, (1.0, 0.65, 0.3, 0.45))  # dawn instead of red
    people = [human(root, (x, 1.0, 0), female=i % 2 == 1) for i, x in enumerate((-3.0, -1.8, -0.6, 0.6, 1.8, 3.0))]
    collars = [p.find("**/collar") for p in people]
    for p in people:
        p.setH(180)
    dust = Drifters(root, 50, (-5, -1, 0), (5, 6, 4), (0, 0, 0.3), (1.0, 0.8, 0.5, 0.4), (0.02, 0.05), seed=9)
    return {"people": people, "collars": collars, "dust": dust, "cheered": False}


def _collars_update(t, dt, s, app):
    s["dust"].update(dt, t)
    for i, c in enumerate(s["collars"]):
        start = 1.5 + i * 0.45
        if t > start:  # click - and down it goes
            u = t - start
            if u < dt * 1.5:
                app.audio.sfx.play("clunk", 0.35)
            c.setZ(-0.5 * 9.8 * u * u * 0.08)
            c.setColorScale(0.3, 0.3, 0.3, 1)
    if t > 4.6:  # and they jump
        if not s["cheered"]:
            s["cheered"] = True
            app.audio.sfx.play("cheer", 0.9)
        for i, p in enumerate(s["people"]):
            p.setZ(max(0.0, math.sin((t - 4.6) * 6 + i * 1.3)) * 0.35)
    look(app, lerp((0, -6.5, 1.3), (0, -5.0, 1.6), t / 9.0), (0, 1.5, 1.1))


def _city(root, rng):
    """A liberated city at night: blocky towers with lit windows on a dark plain (cached), a crowd in front."""
    cached_copy(root, "city", lambda r: _towers(r, np.random.default_rng(10)))
    crowd = []
    for k in range(40):
        h = human(root, (rng.uniform(-9, 9), rng.uniform(2.0, 6.0), 0), female=k % 2 == 1, collar=(0.15, 0.15, 0.15),
                  skin=k % len(M.SKIN_TONES))
        h.setH(180 + rng.uniform(-30, 30))
        crowd.append((h, rng.uniform(0, 6.3), rng.uniform(4, 7)))
    return crowd


def _towers(root, rng):
    V, F = M.box(1, 1, 1)
    M.part(root, V, F, (0.02, 0.02, 0.03), pos=(0, 20, -0.1), scale=(80, 60, 0.2), smooth=None)
    for k in range(34):
        x = rng.uniform(-26, 26)
        y = rng.uniform(24, 42)
        w, h = rng.uniform(1.2, 3.0), rng.uniform(2.0, 8.0)
        M.part(root, V, F, (0.03, 0.03, 0.04), pos=(x, y, h / 2), scale=(w, w, h), smooth=None)
        for j in range(int(h * 1.6)):
            if rng.random() < 0.45:
                wx = x + rng.uniform(-w / 2.4, w / 2.4)
                M.part(root, V, F, (1.0, 0.8, 0.45), pos=(wx, y - w / 2 - 0.01, rng.uniform(0.4, h - 0.3)),
                       scale=(0.12, 0.02, 0.16), unlit=True, smooth=None)
    root.flattenStrong()


def _fireworks(root, app):
    app.backdrop.set_visible(True, stars=True)
    app.audio.music.set_layers(PARTY)
    rng = np.random.default_rng(10)
    city = root.attachNewNode("city")
    crowd = _city(city, rng)
    for k in range(5):
        smoke(root, (rng.uniform(-20, 20), rng.uniform(18, 30), rng.uniform(3, 8)), 8.0, (0.1, 0.06, 0.08, 0.25))
    fw = Fireworks(app, root, ((-22, 22), (26, 38), 1.0), apex=(12, 20), rate=2.8, seed=11, spark=0.45)
    ship = human_ship(app, root, (-30, 10, 8), grey=False)
    ship.setH(-90)
    app.audio.sfx.play("cheer", 0.8)
    return {"fw": fw, "crowd": crowd, "ship": ship, "cheer": 3.8}


def _fireworks_update(t, dt, s, app):
    s["fw"].update(dt)
    for h, ph, f in s["crowd"]:
        h.setZ(max(0.0, math.sin(t * f + ph)) * 0.3)
    s["ship"].setPos(-30 + t * 7, 10 + 2 * math.sin(t * 0.8), 8 + math.sin(t * 1.3))  # victory lap
    s["ship"].setR(20 * math.sin(t * 2.2))
    s["cheer"] -= dt
    if s["cheer"] <= 0:
        s["cheer"] = 3.6
        app.audio.sfx.play("cheer", 0.6)
    look(app, lerp((0, -6, 1.4), (1.5, -4, 1.8), t / 10.0), (0, 30, 11))


def _name(root, app):
    app.webcam_fullscreen(True)
    if not app.tracker_ok:  # no camera: show the helmet itself
        helmet(root)
        look(app, (0, -9, 0.2), (0, 0, -0.3))
    return {"cleanup": lambda: app.webcam_fullscreen(False)}


def _credits(root, app):
    app.webcam_fullscreen(False)
    app.backdrop.set_visible(True, stars=True)
    fw = Fireworks(app, root, ((-14, 14), (16, 26), -6.0), apex=(9, 16), rate=2.0, seed=12, spark=0.32)
    ship = human_ship(app, root, (0, 4, 0), grey=False)
    return {"fw": fw, "ship": ship}


def _credits_update(t, dt, s, app):
    s["fw"].update(dt)
    s["ship"].setPos(0, 4 + t * 0.4, 0.3 * math.sin(t))
    s["ship"].setR(5 * math.sin(t * 0.7))
    look(app, (0, -9, 3.5), (0, 8, 3))


CREDITS = ("fAIceCommander 3D\n\nan idea by Felix\n\nmodels, music and code generated with Claude\n\n"
           "Panda3D · MediaPipe · OpenCV · NumPy · SciPy\nvoices: Piper TTS with public-domain voice models\n\n"
           "Thank you for playing.\n\nENDLESS MODE UNLOCKED")

SHOTS = {
    "eye": (_eye, _eye_update, []),
    "wave": (_wave, _wave_update, [_line(1.5, 0)]),
    "chaos": (_chaos, _chaos_update, [_line(1.0, 1)]),
    "collars": (_collars, _collars_update, [_line(1.0, 2)]),
    "fireworks": (_fireworks, _fireworks_update, []),
    "name": (_name, None, [_line(2.0, 3, "card")]),
    "credits": (_credits, _credits_update, [Line(0.5, CREDITS, None, "credits")]),
}


def make_outro(app):
    shots = [Shot(dur, *SHOTS[name]) for name, dur in OUTRO]
    return Cutscene(app, shots, "victory", AFTERMATH)
