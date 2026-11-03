"""The outro after the Mother falls: her eye cracks, the swarm loses its mind, the collars fall,
and James remembers his name. Then the credits."""
import math

import numpy as np

from .engine import Cutscene, Line, Shot
from .props import Booms, backlight, human, human_ship, lerp, look

LINES = [
    ("outro_01", "The Mother is dead."),
    ("outro_02", "Across the galaxy, the swarm loses its mind."),
    ("outro_03", "On a thousand worlds, the collars fall."),
    ("outro_04", "My name is... James Nathaniel Honor."),
]


def _line(at, idx, style="caption"):
    line_id, text = LINES[idx]
    return Line(at, text, line_id, style)


def _eye(root, app):
    app.backdrop.set_visible(True, stars=False)
    ship = app.world.mother_model.get().copyTo(root)
    return {"ship": ship, "booms": Booms(app, root), "next": 0.0}


def _eye_update(t, dt, s, app):
    s["booms"].update(dt)
    s["next"] -= dt
    if s["next"] <= 0 and t < 6.5:
        s["next"] = 0.35
        rng = s["booms"].rng
        k = t / 6.5  # chain reaction from the eye outwards along the ribs
        s["booms"].add((rng.uniform(-6, 6) * k, -1.2 + rng.uniform(-1, 4) * k, 1.5), 0.8 + 1.5 * k)
        app.audio.sfx.play("boom_big" if k > 0.5 else "boom_small", 0.6)
    if 6.4 < t < 6.5:
        app.flash.trigger(0.95, (1.0, 0.95, 0.9))
        app.audio.sfx.play("nuke_boom")
        app.shake(1.5)
    look(app, lerp((0.9, -4.6, 3.0), (2, -16, 9), t / 7.5), (0, -1.0, 2.2))


def _wave(root, app):
    ship = human_ship(app, root, (0, 0, 0), grey=False)
    ring = app.world.fx_tpl.ring.copyTo(root)
    ring.setPos(0, 40, 0)
    return {"ship": ship, "ring": ring}


def _wave_update(t, dt, s, app):
    r = 2 + t * 9
    s["ring"].setScale(r, r, 1)
    s["ring"].setColorScale(1, 1, 1, max(0.0, 1 - t / 7))
    s["ship"].setR(6 * math.sin(t * 3) * math.exp(-max(0.0, t - 4)))
    look(app, (4, -7, 2.5), (0, 3, 0))


def _chaos(root, app):
    raiders = []
    rng = np.random.default_rng(5)
    for _ in range(10):
        r = app.world.raider_tpl.store.copyTo(root)
        r.setPos(rng.uniform(-10, 10), rng.uniform(0, 20), rng.uniform(-2, 4))
        raiders.append((r, rng.normal(0, 2, 3), rng.uniform(-90, 90, 3)))
    return {"raiders": raiders, "booms": Booms(app, root), "next": 1.0}


def _chaos_update(t, dt, s, app):
    s["booms"].update(dt)
    for r, v, spin in s["raiders"]:
        r.setPos(r.getPos() + tuple(v * dt))
        r.setHpr(r.getHpr() + tuple(spin * dt))  # drifting, tumbling, leaderless
    s["next"] -= dt
    if s["next"] <= 0 and s["raiders"]:
        s["next"] = 1.3
        r, _, _ = s["raiders"].pop(0)
        s["booms"].add(tuple(r.getPos()), 1.8)
        r.removeNode()
        app.audio.sfx.play("boom_small", 0.6)
    look(app, (0, -18 + t * 0.5, 6), (0, 8, 1))


def _collars(root, app):
    app.backdrop.set_visible(False)
    backlight(root, (0, 6, 1.5), 9.0, (0.8, 0.55, 0.3, 0.4))  # dawn instead of red
    people = [human(root, (x, 1.0, 0), female=i % 2 == 1) for i, x in enumerate((-2.2, -1.1, 1.1, 2.2))]
    collars = [p.find("**/collar") for p in people]
    for p in people:
        p.setH(180)
    return {"collars": collars}


def _collars_update(t, dt, s, app):
    for i, c in enumerate(s["collars"]):
        start = 2.0 + i * 0.6
        if t > start:  # click - and down it goes
            u = t - start
            c.setZ(-0.5 * 9.8 * u * u * 0.08)
            c.setColorScale(0.3, 0.3, 0.3, 1)
    look(app, (0, -6.5, 1.3), (0, 1.5, 1.1))


def _name(root, app):
    app.webcam_fullscreen(True)
    return {"cleanup": lambda: app.webcam_fullscreen(False)}


def _credits(root, app):
    app.webcam_fullscreen(False)
    app.backdrop.set_visible(True, stars=True)
    look(app, (0, -15, 18), (0, 3.5, 0))
    return {}


CREDITS = ("fAIceCommander 3D\n\nan idea by Felix\n\nmodels, music and code generated with Claude\n\n"
           "Panda3D · MediaPipe · OpenCV · NumPy · SciPy\n\nThank you for playing.\n\nENDLESS MODE UNLOCKED")


def make_outro(app):
    shots = [
        Shot(7.5, _eye, _eye_update),
        Shot(7.0, _wave, _wave_update, [_line(1.5, 0)]),
        Shot(9.0, _chaos, _chaos_update, [_line(1.0, 1)]),
        Shot(8.0, _collars, _collars_update, [_line(1.0, 2)]),
        Shot(8.0, _name, None, [_line(2.0, 3, "card")]),
        Shot(12.0, _credits, None, [Line(0.5, CREDITS, None, "credits")]),
    ]
    return Cutscene(app, shots, "victory", {"drums": 0.8, "pad": 1.0, "arp": 0.8, "choir": 1.0, "lead": 1.0})
