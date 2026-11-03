"""The intro: humanity's last hope, ending with the player becoming FaceCommander (live webcam + helmet).

Eleven shots (lengths in timeline.INTRO, which the score in audio/tracks.py follows):
signal - planet - slaves - mother - queen - battle - pod - medbay - hangar - waking - becoming.
"""
import math

import numpy as np
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import NodePath, TextNode

from ..render import models as M
from .engine import Cutscene, Line, Shot
from .props import (
    Booms, Drifters, RobotArm, backlight, beam, brain_jar, burning_planet, empty_ship, escape_pod, hangar, human,
    human_ship, lerp, look, operating_table, shake, slave_hall, smoke, tag,
)
from .timeline import INTRO

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
FINAL = "FaceCommander - you are our last hope!"


def _line(at, idx, style="caption"):
    line_id, text = LINES[idx]
    return Line(at, text, line_id, style)


def starfield(root, n=260, radius=90.0, seed=11):
    """Distant stars as tiny unlit points (flattened into one node)."""
    stars = root.attachNewNode("stars")
    rng = np.random.default_rng(seed)
    V, F = M.icosphere(0)
    for _ in range(n):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        warm = rng.random()
        M.part(stars, V, F, (0.8 + 0.2 * warm, 0.8 + 0.1 * warm, 1.0 - 0.2 * warm), pos=tuple(d * radius),
               scale=rng.uniform(0.06, 0.2), unlit=True)
    stars.flattenStrong()
    return stars


# ---------------------------------------------------------------- 1 signal

def _signal(root, app):
    app.backdrop.set_visible(False)
    starfield(root)
    planet = burning_planet(root, 6.0)
    planet.setPos(4, 140, 2)
    dust = Drifters(root, 40, (-6, 2, -3), (6, 30, 3), (0, -2.5, 0), (0.8, 0.8, 0.9, 0.35), (0.02, 0.05), seed=2)
    app.cinema.flicker(0.9)
    app.audio.sfx.play("static", 0.5)
    return {"planet": planet, "dust": dust, "beat": 0.0, "static": 2.5}


def _signal_update(t, dt, s, app):
    s["dust"].update(dt, t)
    s["planet"].setH(t * 2)
    s["beat"] += dt
    if s["beat"] >= 1.1:  # an ECG monitor in the dark
        s["beat"] = 0.0
        app.audio.sfx.play("beep", 0.3)
    s["static"] -= dt
    if s["static"] <= 0:
        s["static"] = 2.2
        app.audio.sfx.play("static", 0.3)
        app.cinema.flicker(0.5)
    look(app, lerp((0, -4, 0.5), (0.5, 18, 1.0), t / 7.0), (4, 140, 2))


# ---------------------------------------------------------------- 2 burning world

def _planet(root, app):
    app.backdrop.set_visible(True, stars=False)
    starfield(root)
    planet = burning_planet(root, 9.0)
    planet.setPos(0, 34, -5)
    rng = np.random.default_rng(2)
    swarm = []
    for k in range(18):
        r = app.world.raider_tpl.store.copyTo(root)
        r.setScale(1.6)
        r.setPos(-48 + k * 2.4 + rng.uniform(-1, 1), 2 + (k % 3) * 4 + rng.uniform(-1, 1), 2 + rng.uniform(-1, 3))
        r.setH(-100 + rng.uniform(-8, 8))
        swarm.append((r, rng.uniform(5.5, 8.0)))
    embers = Drifters(root, 50, (-12, 0, -4), (12, 25, 8), (0.5, -4, 1.2), (1.0, 0.45, 0.1, 0.8), (0.04, 0.12),
                      seed=3, flicker=0.6)
    return {"root": root, "planet": planet, "swarm": swarm, "embers": embers, "rng": rng, "fire": 0.0, "hits": []}


def _planet_update(t, dt, s, app):
    s["planet"].setH(t * 2.5)
    s["embers"].update(dt, t)
    for r, v in s["swarm"]:
        r.setX(r.getX() + v * dt)
        r.setZ(r.getZ() - v * dt * 0.08)
    s["fire"] -= dt
    rng = s["rng"]
    if s["fire"] <= 0 and t > 2.0:  # orbital bombardment: a beam from the swarm, a flash on the surface
        s["fire"] = 0.35
        src = s["swarm"][int(rng.integers(len(s["swarm"])))][0].getPos(s["root"])
        d = rng.normal(size=3)
        d[1] = -abs(d[1]) - 0.5
        d /= np.linalg.norm(d)
        hit = tuple(np.array((0, 34, -5)) + d * 9.0)
        s["hits"].append([beam(s["root"], tuple(src), hit, (1.0, 0.3, 0.08), 0.05),
                          M.glow(s["root"], hit, 2.5, (1.0, 0.6, 0.2, 0.9)), 0.0])
        app.audio.sfx.play("enemy_shot", 0.25)
    alive = []
    for h in s["hits"]:
        h[2] += dt
        h[0].setAlphaScale(max(0.0, 1 - h[2] / 0.3))
        h[1].setAlphaScale(max(0.0, 1 - h[2] / 0.6))
        if h[2] > 0.6:
            h[0].removeNode()
            h[1].removeNode()
        else:
            alive.append(h)
    s["hits"] = alive
    look(app, lerp((-9, -12, 5), (7, -9, 2), t / 11.0), (0, 30, -3))


# ---------------------------------------------------------------- 3 slaves

def _slaves(root, app):
    app.backdrop.set_visible(False)
    hall = root.attachNewNode("hall")
    slave_hall(hall)
    hall.flattenStrong()
    backlight(root, (0, 12, 2.5), 14.0)
    backlight(root, (0, 5, 1.2), 6.0, (0.7, 0.02, 0.02, 0.3))
    people = []
    for i, (x, female) in enumerate(((-3.0, False), (-1.8, True), (-0.6, False), (0.6, True), (1.8, False),
                                     (3.0, True))):
        h = human(root, (x, 1.5, 0), female)
        h.setH(180 + (i - 2.5) * 4)
        tag(root, ("FEMALE " if female else "MALE ") + ("4471", "0932", "1187", "5530", "2206", "0019")[i],
            (x, 1.1, 1.95), 0.15)
        people.append(h)
    master = M.build_catlien(root, 2.0)
    master.setPos(0, 4.4, 0.3)
    master.setLightOff(1)
    for x in (-3.0, -1.8, -0.6, 0.6, 1.8, 3.0):  # leashes from the collars to the master's claw
        Vt, Ft = M.tube_mesh([(x, 1.5, 1.36), (x * 0.6, 2.6, 0.7), (x * 0.15, 3.6, 1.1), (0.35, 3.9, 1.5)], 0.012, 6)
        M.part(root, Vt, Ft, (0.05, 0.05, 0.05), orient=None)
    dust = Drifters(root, 60, (-5, -2, 0), (5, 8, 4), (0.1, 0, 0.15), (1.0, 0.5, 0.4, 0.3), (0.015, 0.04), seed=4)
    return {"people": people, "dust": dust, "strike": 3.2, "rng": np.random.default_rng(7)}


def _slaves_update(t, dt, s, app):
    s["dust"].update(dt, t)
    for i, h in enumerate(s["people"]):  # they sway, barely - exhausted
        h.setR(1.5 * math.sin(t * 0.7 + i))
    s["strike"] -= dt
    if s["strike"] <= 0:  # lightning outside the hall: dark, then white
        s["strike"] = s["rng"].uniform(3.0, 4.5)
        app.cinema.flicker(0.85)
        app.flash.trigger(0.55, (0.8, 0.85, 1.0))
        app.audio.sfx.play("thunder", 0.6)
    look(app, lerp((0.4, -6.0, 0.9), (-0.3, -2.6, 1.3), t / 12.5), (0, 3.0, 1.4))


# ---------------------------------------------------------------- 4 the Mother

def _mother(root, app):
    app.backdrop.set_visible(True, stars=False)
    starfield(root)
    ship = app.world.mother_model.get().copyTo(root)
    ship.setColorScale(0.6, 0.55, 0.6, 1)
    rng = np.random.default_rng(8)
    fog = [smoke(root, (rng.uniform(-9, 9), rng.uniform(-8, 6), rng.uniform(-1.5, 2.5)), rng.uniform(3, 6),
                 (0.03, 0.025, 0.04, 0.7)) for _ in range(16)]
    lights = [beam(root, (x, -3.5, -0.4), (x * 2.5, -25, -6), (1.0, 0.2, 0.15), 0.025) for x in (-3, 3)]
    rings = NodePath("rings")
    M.build_hypno_rings(rings, (0, 0, 0), [1.0, 0.9, 0.8], width=0.08)
    pulses = []
    for k in range(3):
        r = rings.copyTo(root)
        r.setPos(0, 1.5, 2.8)
        r.setP(90)
        pulses.append(r)
    return {"ship": ship, "fog": fog, "lights": lights, "pulses": pulses, "hum": 0.0}


def _mother_update(t, dt, s, app):
    for k, f in enumerate(s["fog"]):  # fog pulls back to reveal her
        f.setX(f.getX() + math.copysign(dt * (0.5 + 0.3 * t), f.getX()))
        f.setAlphaScale(max(0.0, 1 - t / 7))
    for k, b in enumerate(s["lights"]):
        b.setH(20 * math.sin(t * 0.6 + k * 2))
    for k, r in enumerate(s["pulses"]):
        u = ((t * 0.45 + k / 3) % 1.0)
        r.setScale(1 + u * 7)
        r.setAlphaScale(0.6 * (1 - u) * min(1.0, t / 2))
    s["hum"] -= dt
    if s["hum"] <= 0:
        s["hum"] = 3.0
        app.audio.sfx.play("hypno_hum", 0.5)
    look(app, lerp((0.5, -22, -3.5), (1.2, -7.5, -1.2), t / 9.0), (0, -1.0, 1.4))


# ---------------------------------------------------------------- 5 her face

def _queen(root, app):
    app.backdrop.set_visible(False)
    queen = M.build_catlien(root, 2.4, queen=True)
    queen.setPos(0, 0.8, -1.6)
    Vh, Fh = M.hemisphere(3)
    M.part(root, Vh * np.array([2.2, 1.6, 2.6]), Fh, (0.9, 0.3, 0.2, 0.12), pos=(0, 0.2, -0.6),
           alpha=True, two_sided=True, hpr=(0, -15, 0))
    backlight(root, (0, 3.5, 1.5), 7.0, (0.9, 0.04, 0.02, 0.5))
    queen.find("**/throne").hide()
    eyes = [g for g in queen.findAllMatches("**/glow")]
    for g in eyes:
        g.setAlphaScale(0.0)
    return {"eyes": eyes, "woke": False, "rng": np.random.default_rng(9)}


def _queen_update(t, dt, s, app):
    if t > 0.3 and not s["woke"]:
        s["woke"] = True
        app.audio.sfx.play("mother_roar", 1.0)
        app.flash.trigger(0.6, (1.0, 0.15, 0.05))
        app.cinema.flicker(0.6)
    k = min(1.0, max(0.0, (t - 0.3) / 0.25))
    for g in s["eyes"]:
        g.setAlphaScale(k)
    amount = 0.04 * max(0.0, 1 - (t - 0.3) / 2.5) if t > 0.3 else 0.0
    pos = lerp((1.2, -6.0, -0.3), (0.7, -4.3, 0.2), t / 4.5)
    look(app, shake(pos, amount, s["rng"]), (0, 0, 0.9))


# ---------------------------------------------------------------- 6 battle

def _battle(root, app):
    app.backdrop.set_visible(True, stars=False)
    starfield(root)
    ship = app.world.mother_model.get().copyTo(root)
    fleet = []
    for i in range(9):
        f = human_ship(app, root, (-12 + i * 3, -16 - (i % 3) * 3, 1.0 + (i % 3) * 1.5))
        f.setScale(0.8)
        fleet.append(f)
    arcs = root.attachNewNode("arcs")
    return {"ship": ship, "fleet": fleet, "booms": Booms(app, root), "next": 0.3, "lasers": [], "arcs": arcs,
            "rng": np.random.default_rng(10), "jump": False}


def _battle_update(t, dt, s, app):
    rng = s["rng"]
    s["booms"].update(dt)
    for f in s["fleet"]:
        f.setY(f.getY() + dt * 4)
    lasers = []
    for node, life in s["lasers"]:
        life -= dt
        if life <= 0:
            node.removeNode()
        else:
            node.setAlphaScale(life / 0.25)
            lasers.append((node, life))
    s["lasers"] = lasers
    s["next"] -= dt
    if s["next"] <= 0:
        s["next"] = 0.18
        if t < 7.0 and s["fleet"]:  # the fleet fires, hits blossom on the hull
            f = s["fleet"][int(rng.integers(len(s["fleet"])))]
            hit = (rng.uniform(-5, 5), rng.uniform(-3, 3), rng.uniform(0.5, 1.5))
            x, y, z = f.getPos()
            s["lasers"].append((beam(f.getParent(), (x, y + 1.2, z), hit, (0.4, 1.0, 0.3), 0.04), 0.25))
            if rng.random() < 0.45:
                s["booms"].add(hit, rng.uniform(0.8, 1.8))
                app.audio.sfx.play("boom_small", 0.45)
            else:
                app.audio.sfx.play("laser", 0.3)
        elif t >= 7.6 and s["fleet"] and rng.random() < 0.55:  # then the fleet dies
            f = s["fleet"].pop(int(rng.integers(len(s["fleet"]))))
            s["booms"].add(tuple(f.getPos()), 2.2)
            f.removeNode()
            app.audio.sfx.play("boom_big", 0.7)
    if t > 7.0 and not s["jump"]:  # her hyperdrive flares - and fails
        s["jump"] = True
        app.flash.trigger(0.9, (0.5, 0.7, 1.0))
        app.audio.sfx.play("power_up", 0.6)
        app.audio.sfx.play("nuke_boom", 0.7)
        s["ship"].setColorScale(0.7, 0.85, 1.6, 1)
    if s["jump"]:
        for arc in s["arcs"].getChildren():
            arc.removeNode()
        if t < 9.5:
            for _ in range(3):  # electric arcs crawling over her hull
                a = (rng.uniform(-6, 6), rng.uniform(-4, 4), rng.uniform(0.5, 1.8))
                b = (a[0] + rng.uniform(-2, 2), a[1] + rng.uniform(-2, 2), a[2] + rng.uniform(-0.5, 0.8))
                beam(s["arcs"], a, b, (0.5, 0.8, 1.0), 0.03)
        k = max(0.0, 1 - (t - 7.0) / 3)
        s["ship"].setColorScale(0.6 + 0.1 * k, 0.6 + 0.25 * k, 0.65 + 0.95 * k, 1)
    amount = 0.12 if (7.0 < t < 8.0) else 0.03
    pos = (14 * math.sin(t * 0.12 - 0.4), -27 + t * 0.9, 9 - t * 0.2)
    look(app, shake(pos, amount, rng), (0, -4, 0))


# ---------------------------------------------------------------- 7 escape pod

def _pod(root, app):
    app.backdrop.set_visible(True, stars=False)
    starfield(root)
    pod = escape_pod(root)
    rng = np.random.default_rng(12)
    junk = []
    for k in range(14):
        if k % 3 == 0:
            j = human_ship(app, root, (0, 0, 0))
            j.setScale(rng.uniform(0.2, 0.4))
        else:
            j = app.world.rocks.rocks[1][int(rng.integers(len(app.world.rocks.rocks[1])))].copyTo(root)
            j.setScale(rng.uniform(0.15, 0.4))
            j.setColorScale(0.35, 0.3, 0.3, 1)
        j.setPos(rng.uniform(-5, 5), rng.uniform(-3, 9), rng.uniform(-2.5, 2.5))
        M.glow(j, (0, 0, 0), 1.5, (1.0, 0.4, 0.1, 0.5))
        junk.append((j, rng.normal(0, 0.6, 3), rng.uniform(-60, 60, 3)))
    sparks = Drifters(root, 30, (-4, -2, -2), (4, 6, 2), (0, -1.5, 0), (1.0, 0.7, 0.3, 0.9), (0.02, 0.06), seed=5,
                      flicker=0.9)
    return {"pod": pod, "junk": junk, "sparks": sparks, "beacon": pod.find("**/beacon")}


def _pod_update(t, dt, s, app):
    s["pod"].setHpr(t * 35, t * 18, t * 9)
    s["pod"].setPos(0, t * 0.6, 0)
    s["sparks"].update(dt, t)
    s["beacon"].setAlphaScale(1.0 if int(t * 3) % 2 == 0 else 0.1)
    for j, v, spin in s["junk"]:
        j.setPos(j.getPos() + tuple(v * dt))
        j.setHpr(j.getHpr() + tuple(spin * dt))
    look(app, (2.2, -4.0 + t * 0.7, 0.9), (0, t * 0.6, 0))


# ---------------------------------------------------------------- 8 med bay

def _medbay(root, app):
    app.backdrop.set_visible(False)
    root.setColorScale(0.55, 0.45, 0.5, 1)  # a dark room: most lights are dead
    operating_table(root)
    V, F = M.box(1, 1, 1)
    M.part(root, V, F, (0.03, 0.04, 0.045), pos=(0, 0, -0.05), scale=(14, 14, 0.1), smooth=None)
    M.part(root, V, F, (0.04, 0.05, 0.06), pos=(0, 4.5, 2.5), scale=(14, 0.2, 6), smooth=None)
    M.part(root, V, F, (0.7, 0.95, 1.0), pos=(1.8, 0.5, 3.2), scale=(0.15, 2.5, 0.04), unlit=True, smooth=None)
    M.glow(root, (1.8, 0.5, 3.0), 2.0, (0.4, 0.8, 1.0, 0.18))  # one cold tube still works ...
    alarm = M.glow(root, (-2.5, 3.0, 2.6), 3.0, (1.0, 0.05, 0.03, 0.4))  # ... the rest is emergency red
    arms = [RobotArm(root, (sx * 1.2, y, 0), tool=tool) for sx, y, tool in
            ((-1, -0.3, (0.4, 1.0, 0.9)), (1, 0.4, (1.0, 0.3, 0.2)), (1, -0.9, (0.4, 1.0, 0.9)))]
    jar, brain = brain_jar(root, (-1.9, 1.6, 0.9))
    bubbles = Drifters(jar, 14, (-0.25, -0.25, 0.05), (0.25, 0.25, 0.75), (0, 0, 0.35), (0.6, 1.0, 0.8, 0.6),
                       (0.015, 0.03), seed=6)
    scan = beam(root, (-0.7, 0, 1.3), (0.7, 0, 1.3), (0.3, 1.0, 0.5), 0.006)
    monitor = tag(root, "", (1.5, 1.9, 1.8), 0.07, (0.3, 1.0, 0.5, 1))
    return {"arms": arms, "brain": brain, "bubbles": bubbles, "scan": scan, "monitor": monitor, "servo": 0.0,
            "alarm": alarm}


def _medbay_update(t, dt, s, app):
    s["bubbles"].update(dt, t)
    s["brain"].setH(t * 12)
    s["brain"].setZ(0.42 + 0.03 * math.sin(t * 1.7))
    for k, arm in enumerate(s["arms"]):
        p = t * (0.7 + 0.2 * k) + k
        arm.pose(-90 * (1 if k == 0 else -1) + 25 * math.sin(p * 0.5), 35 + 15 * math.sin(p), 55 + 20 * math.sin(p * 1.3),
                 30 * math.sin(p * 2.1))
    s["servo"] -= dt
    if s["servo"] <= 0:
        s["servo"] = 1.3
        app.audio.sfx.play("servo", 0.35)
    s["scan"].setY(-1.1 + (t * 0.6) % 2.2)  # the scanner sweeps along the body
    bpm = "".join("^" if (int(t * 8) - i) % 9 == 0 else "-" for i in range(18))
    s["monitor"].node().setText(f"VITALS {bpm}\nBRAIN ACTIVITY 12 %")
    s["alarm"].setAlphaScale(0.4 + 0.6 * abs(math.sin(t * 2.2)))
    if int(t * 7) % 23 == 0:
        app.cinema.flicker(0.3)
    look(app, lerp((2.6, -3.2, 2.6), (1.4, -2.0, 2.0), t / 8.0), (-0.3, 0.6, 1.0))


# ---------------------------------------------------------------- 9 shipyard

LOCK_T = 7.6


def _hangar(root, app):
    app.backdrop.set_visible(False)
    bay = root.attachNewNode("bay")
    hangar(bay)
    bay.flattenStrong()
    ship = empty_ship(root)
    helmet = M.cached("helmet", M.build_helmet).getChild(0).copyTo(root)
    helmet.setScale(0.3)
    cable = root.attachNewNode("cable")
    Vc, Fc = M.lathe([(0.015, 0.0), (0.015, 1.0)], 6, "z")
    M.part(cable, Vc, Fc, (0.1, 0.1, 0.11), orient=None)
    brain = M.build_brain(root, 0.24, aura=False)  # what the helmet leaves in the cockpit
    brain.setPos(0, 0.55, 0.47)
    brain.hide()
    halo = M.glow(root, (0, 0.55, 0.5), 0.65, (1.0, 0.4, 0.7, 0.4))
    halo.hide()
    arms = [RobotArm(root, (sx * 2.2, y, -0.7), color=(0.85, 0.6, 0.1), tool=(1.0, 0.8, 0.4)) for sx, y in
            ((-1, -0.6), (1, 0.2), (-1, 1.0))]
    sparks = [Drifters(root, 18, (sx * 1.6 - 0.4, y - 0.4, -0.2), (sx * 1.6 + 0.4, y + 0.4, 0.6), (0, 0, -2.5),
                       (1.0, 0.85, 0.5, 1.0), (0.015, 0.05), seed=20 + k, flicker=0.9)
              for k, (sx, y) in enumerate(((-1, -0.6), (1, 0.2), (-1, 1.0)))]
    lights = [M.glow(ship, p, 0.35, (0.3, 1.0, 0.5, 0.9)) for p in ((0.6, 1.3, 0.25), (-0.6, 1.3, 0.25), (0, -1.2, 0.35))]
    for g in lights:
        g.hide()
    return {"ship": ship, "helmet": helmet, "cable": cable, "brain": brain, "halo": halo, "arms": arms,
            "sparks": sparks, "lights": lights, "locked": False, "weld": 0.0, "rng": np.random.default_rng(13)}


def _hangar_update(t, dt, s, app):
    for sp in s["sparks"]:
        sp.update(dt, t)
    for k, arm in enumerate(s["arms"]):
        p = t * 1.1 + k * 2
        arm.pose(90 * (1 if k != 1 else -1) + 10 * math.sin(p), 45 + 10 * math.sin(p * 0.7), 50 + 15 * math.sin(p * 1.4), 20)
    s["weld"] -= dt
    if s["weld"] <= 0 and t < LOCK_T:
        s["weld"] = 1.2
        app.audio.sfx.play("weld", 0.35)
    h = max(0.0, 1 - t / LOCK_T)
    z = 0.62 + 3.6 * h * h
    s["helmet"].setPos(0.0, 0.55, z)  # the helmet - with his brain inside - lowers into the cockpit
    s["helmet"].setH(10 * math.sin(t * 0.8) * h)
    s["cable"].setPos(0, 0.55, z + 0.5)
    s["cable"].setScale(1, 1, max(0.01, 4.0 - z))
    if t >= LOCK_T and not s["locked"]:
        s["locked"] = True
        app.audio.sfx.play("clunk", 1.0)
        app.audio.sfx.play("power_up", 0.8)
        app.flash.trigger(0.7, (0.6, 1.0, 0.7))
        s["helmet"].hide()
        s["cable"].hide()
        s["brain"].show()
        s["halo"].show()
    if s["locked"]:
        u = t - LOCK_T
        for k, g in enumerate(s["lights"]):  # systems come online one by one
            g.show() if u > 0.4 + k * 0.4 else g.hide()
        s["brain"].setColorScale(1 + 0.5 * math.exp(-u * 2), 1, 1 + 0.5 * math.exp(-u * 2), 1)
    a = t * 0.22
    pos = (5.2 * math.cos(a), 5.2 * math.sin(a) - 1.2, 2.8 - 0.6 * min(1, t / LOCK_T))
    look(app, shake(pos, 0.05 if 0 < t - LOCK_T < 0.6 else 0.0, s["rng"]), (0, 0.4, 0.5))


# ---------------------------------------------------------------- 10 waking

BOOT = [("NEURAL LINK", "OK", (0.4, 1, 0.6, 1)), ("LIFE SUPPORT", "31 %", (1, 0.8, 0.3, 1)),
        ("FACE TRACKING", "ONLINE", (0.4, 1, 0.6, 1)), ("WEAPONS", "ARMED", (0.4, 1, 0.6, 1)),
        ("IDENTITY", "UNKNOWN", (1, 0.3, 0.3, 1))]


def _waking(root, app):
    app.backdrop.set_visible(True, stars=True)
    bay = root.attachNewNode("bay")
    hangar(bay)
    bay.flattenStrong()
    doors = []
    V, F = M.box(1, 1, 1)
    for sgn in (1, -1):  # the bay doors ahead
        d = M.part(root, V, F, (1, 1, 1), pos=(sgn * 3.5, 11.5, 3), scale=(7, 0.4, 7.5),
                   vcol=M.paint((0.04, 0.04, 0.05), (0.2, 0.2, 0.22), -0.5, 0.5, grime=0.4), smooth=None)
        M.part(d, V, F, (1.0, 0.25, 0.1), pos=(-0.49 * sgn, -0.6, 0.0), scale=(0.01, 0.05, 0.9), unlit=True, smooth=None)
        doors.append((d, sgn))
    starfield(root, 200, 60, seed=14)
    lines = [OnscreenText("", parent=app.hud.center, pos=(-0.95, 0.42 - k * 0.075), scale=0.045, fg=col,
                          align=TextNode.ALeft, font=app.hud.font, mayChange=True) for k, (_, _, col) in enumerate(BOOT)]

    def cleanup():
        for ln in lines:
            ln.destroy()
    return {"doors": doors, "lines": lines, "cleanup": cleanup, "beeped": 0}


def _waking_update(t, dt, s, app):
    app.hypno_alpha = max(0.0, 0.55 - t * 0.07)  # blurred, swimming vision
    for k, (label, value, _) in enumerate(BOOT):
        at = 1.0 + k * 1.1
        if t < at:
            s["lines"][k].setText("")
            continue
        text = f"{label} {'.' * (16 - len(label))} "
        shown = text + value if t > at + 0.5 else text[: int((t - at) * 40)]
        s["lines"][k].setText(shown)
        if t > at + 0.5 and s["beeped"] <= k:
            s["beeped"] = k + 1
            app.audio.sfx.play("beep_high" if k < 4 else "alarm", 0.4)
    open_ = min(1.0, max(0.0, (t - 3.0) / 5.0))
    for d, sgn in s["doors"]:
        d.setX(sgn * (3.5 + 6.0 * open_ * open_))
    look(app, (0.03 * math.sin(t * 0.9), 0.6, 0.75 + 0.02 * math.sin(t * 1.3)), (0, 12, 1.2))


# ---------------------------------------------------------------- 11 becoming

def _becoming(root, app):
    app.backdrop.set_visible(False)
    app.webcam_fullscreen(True)
    app.hypno_alpha = 0.0
    helmet = None
    if not app.tracker_ok:  # no camera: show the helmet itself
        helmet = M.build_helmet(root)
        look(app, (0, -9, 0.2), (0, 0, -0.3))
    return {"helmet": helmet, "hit": False, "cleanup": lambda: app.webcam_fullscreen(False)}


def _becoming_update(t, dt, s, app):
    if t > 2.0 and not s["hit"]:
        s["hit"] = True
        app.flash.trigger(0.8, (1.0, 0.6, 0.9))
    if s["helmet"] is not None:
        s["helmet"].setH(15 * math.sin(t * 0.8))


SHOTS = {
    "signal": (_signal, _signal_update, [_line(1.2, 0)]),
    "planet": (_planet, _planet_update, [_line(1.0, 1)]),
    "slaves": (_slaves, _slaves_update, [_line(0.8, 2), _line(6.5, 3)]),
    "mother": (_mother, _mother_update, [_line(1.0, 4)]),
    "queen": (_queen, _queen_update, []),
    "battle": (_battle, _battle_update, [_line(0.6, 5), _line(7.0, 6)]),
    "pod": (_pod, _pod_update, []),
    "medbay": (_medbay, _medbay_update, [_line(1.2, 7)]),
    "hangar": (_hangar, _hangar_update, [_line(1.0, 8)]),
    "waking": (_waking, _waking_update, [_line(0.8, 9)]),
    "becoming": (_becoming, _becoming_update, [Line(2.0, FINAL, "intro_11", "card")]),
}


def make_intro(app):
    shots = [Shot(dur, *SHOTS[name]) for name, dur in INTRO]
    return Cutscene(app, shots, "cinematic", {"bed": 1.0, "drums": 1.0, "brass": 1.0, "fx": 1.0})
