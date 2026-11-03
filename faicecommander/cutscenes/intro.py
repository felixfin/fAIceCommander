"""The intro: humanity's last hope, ending with the player becoming FaceCommander (live webcam + helmet)."""
import math

import numpy as np

from ..render import models as M
from .engine import Cutscene, Line, Shot
from .props import Booms, backlight, burning_planet, escape_pod, human, human_ship, lerp, look, tag

LINES = [
    ("intro_01", "For centuries, humanity has been at war with the Catliens."),
    ("intro_02", "Feline. Brilliant. Merciless. Their swarms have burned world after world."),
    ("intro_03", "Most of us are slaves now - pets of the higher castes."),
    ("intro_04", "They neuter the males. They milk the females."),
    ("intro_05", "One mind steers the swarm: the Mother. Destroy her, and the swarm falls into chaos."),
    ("intro_06", "Commander James Nathaniel Honor found her. His fleet struck hard."),
    ("intro_07", "Her hyperdrive failed. But his fleet was lost."),
    ("intro_08", "AI surgeon: Only the head and part of the torso could be saved."),
    ("intro_09", "We built him a ship from the wreckage. There is nothing left for another attempt."),
    ("intro_10", "Commander? Can you hear me? You don't know who you are. But you know the way. Star by star."),
]


def _line(at, idx, style="caption"):
    line_id, text = LINES[idx]
    return Line(at, text, line_id, style)


# ---------------------------------------------------------------- shots

def _darkness(root, app):
    app.backdrop.set_visible(False)
    look(app, (0, -10, 0), (0, 0, 0))
    return {"beat": 0.0}


def _darkness_update(t, dt, s, app):
    s["beat"] += dt
    if s["beat"] >= 1.1:  # an ECG monitor in the dark
        s["beat"] = 0.0
        app.audio.sfx.play("beep", 0.35)


def _planet(root, app):
    app.backdrop.set_visible(True, stars=False)
    planet = burning_planet(root)
    planet.setPos(0, 30, -6)
    swarm = []
    rng = np.random.default_rng(2)
    for _ in range(14):
        r = app.world.raider_tpl.store.copyTo(root)
        r.setPos(rng.uniform(-20, 0), rng.uniform(5, 20), rng.uniform(2, 8))
        r.setH(-110)
        swarm.append((r, rng.uniform(5, 9)))
    return {"planet": planet, "swarm": swarm}


def _planet_update(t, dt, s, app):
    s["planet"].setH(t * 3)
    for r, v in s["swarm"]:
        r.setX(r.getX() + v * dt)
    look(app, lerp((-6, -22, 6), (6, -20, 4), t / 9), (0, 20, 0))


def _slaves(root, app):
    app.backdrop.set_visible(False)
    backlight(root, (0, 6, 1.5), 9.0)
    for i, (x, female) in enumerate(((-2.2, False), (-1.1, True), (1.1, True), (2.2, False))):
        h = human(root, (x, 1.0, 0), female)
        h.setH(180)
        tag(root, ("FEMALE " if female else "MALE ") + ("4471", "0932", "1187", "5530")[i], (x, 0.6, 1.95))
    master = M.build_catlien(root, 1.35)
    master.setPos(0, 2.6, -0.2)
    master.setLightOff(1)
    for x in (-2.2, -1.1, 1.1, 2.2):  # leashes from the collars to the master's hand
        Vt, Ft = M.tube_mesh([(x, 1.0, 1.36), (x * 0.5, 1.8, 0.9), (0.2, 2.4, 1.0)], 0.012, 6)
        M.part(root, Vt, Ft, (0.05, 0.05, 0.05), orient=None)
    return {}


def _slaves_update(t, dt, s, app):
    look(app, lerp((0, -6.5, 1.2), (0.6, -5.0, 1.4), t / 12), (0, 1.5, 1.2))


def _mother(root, app):
    app.backdrop.set_visible(True, stars=False)
    ship = app.world.mother_model.get().copyTo(root)
    return {"ship": ship}


def _mother_update(t, dt, s, app):
    look(app, lerp((0.4, -14, 6), (0.9, -4.4, 2.9), t / 9), (0, -1.3, 2.4))


def _battle(root, app):
    ship = app.world.mother_model.get().copyTo(root)
    fleet = []
    for i in range(5):
        f = human_ship(app, root, (-8 + i * 4, -18 - (i % 2) * 3, 1.5 + (i % 3)))
        f.setScale(0.9)
        fleet.append(f)
    return {"ship": ship, "fleet": fleet, "booms": Booms(app, root), "next": 0.4}


def _battle_update(t, dt, s, app):
    s["booms"].update(dt)
    for k, f in enumerate(s["fleet"]):
        f.setY(f.getY() + dt * 5)
    s["next"] -= dt
    if s["next"] <= 0:
        s["next"] = 0.5
        rng = s["booms"].rng
        if t < 6:  # hits on the mothership
            s["booms"].add((rng.uniform(-5, 5), rng.uniform(-3, 3), 1.2), rng.uniform(1.0, 2.0))
            app.audio.sfx.play("boom_big", 0.5)
        elif s["fleet"]:  # then the fleet dies
            f = s["fleet"].pop(int(rng.integers(len(s["fleet"]))))
            s["booms"].add(tuple(f.getPos()), 2.0)
            f.removeNode()
            app.audio.sfx.play("boom_small", 0.7)
    look(app, (12 * math.sin(t * 0.15), -26 + t, 12), (0, -4, 0))


def _pod(root, app):
    pod = escape_pod(root)
    return {"pod": pod}


def _pod_update(t, dt, s, app):
    s["pod"].setHpr(t * 25, t * 12, t * 7)
    look(app, (2, -5 + t * 0.15, 0.8), (0, 0, 0))


def _shipyard(root, app):
    app.backdrop.set_visible(False)
    ship = M.build_ship(root)
    ship.setH(30)
    helmet = M.build_helmet(root)
    helmet.setScale(0.32)
    sparks = [M.glow(root, (0, 0, 0), 0.25, (1.0, 0.85, 0.5, 1.0)) for _ in range(6)]
    for x in (-3, 3):
        Vb, Fb = M.box(0.2, 6, 0.2)  # gantry
        M.part(root, Vb, Fb, (0.2, 0.2, 0.22), pos=(x, 0, 3))
    return {"ship": ship, "helmet": helmet, "sparks": sparks}


def _shipyard_update(t, dt, s, app):
    rng = np.random.default_rng(int(t * 30))
    for spark in s["sparks"]:
        spark.setPos(rng.uniform(-1, 1), rng.uniform(-1.4, 1.2), rng.uniform(0.1, 0.5))
        spark.setScale(rng.uniform(0.1, 0.35))
    h = max(0.0, 1 - t / 7)
    s["helmet"].setPos(0.15, 0.55, 0.55 + 3 * h)  # the helmet lowers into the cockpit
    look(app, (5.5 * math.cos(t * 0.25), 5.5 * math.sin(t * 0.25) - 1, 3.2), (0, 0.3, 0.3))


def _waking(root, app):
    app.backdrop.set_visible(False)
    ship = M.build_ship(root)
    return {"ship": ship}


def _waking_update(t, dt, s, app):
    app.hypno_alpha = max(0.0, 0.5 - t * 0.06)  # blurred, swimming vision
    look(app, (0, -1.0 + 0.05 * math.sin(t), 0.8), (0, 2, 0.5))


def _becoming(root, app):
    app.backdrop.set_visible(False)
    app.webcam_fullscreen(True)
    app.hypno_alpha = 0.0
    helmet = None
    if not app.tracker_ok:  # no camera: show the helmet itself
        helmet = M.build_helmet(root)
        look(app, (0, -9, 0.2), (0, 0, -0.3))
    return {"helmet": helmet, "cleanup": lambda: app.webcam_fullscreen(False)}


def _becoming_update(t, dt, s, app):
    if s["helmet"] is not None:
        s["helmet"].setH(15 * math.sin(t * 0.8))


def make_intro(app):
    shots = [
        Shot(7.0, _darkness, _darkness_update, [_line(1.0, 0)]),
        Shot(9.0, _planet, _planet_update, [_line(1.0, 1)]),
        Shot(12.0, _slaves, _slaves_update, [_line(0.8, 2), _line(6.5, 3)]),
        Shot(9.0, _mother, _mother_update, [_line(1.0, 4)]),
        Shot(11.0, _battle, _battle_update, [_line(0.6, 5), _line(6.3, 6)]),
        Shot(7.0, _pod, _pod_update, [_line(1.0, 7)]),
        Shot(9.0, _shipyard, _shipyard_update, [_line(1.0, 8)]),
        Shot(8.0, _waking, _waking_update, [_line(0.8, 9)]),
        Shot(8.0, _becoming, _becoming_update, [Line(2.0, "FaceCommander - you are our last hope!", "intro_11", "card")]),
    ]
    return Cutscene(app, shots, "cinematic", {"drone": 1.0, "drums": 0.8, "choir": 1.0, "pulse": 0.6})
