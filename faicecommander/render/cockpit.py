"""The cockpit behind the player: a small live 3D scene rendered into a texture that replaces the
room in the webcam image (where the person mask says "not the player").

Seen from the dashboard looking back: an armoured pilot seat right behind the player, ribbed
bulkheads, pipes and cable looms, a porthole, monitors, flickering tubes and a rotating warning
light. It shakes with the ship and turns violet during hypno pulses.
"""
import math

import numpy as np
from panda3d.core import (
    AmbientLight, Camera, NodePath, PerspectiveLens, PointLight, Spotlight, Texture,
)

from . import models as M

RUST_LO, RUST_HI = (0.05, 0.035, 0.03), (0.32, 0.22, 0.17)
STEEL_LO, STEEL_HI = (0.04, 0.045, 0.05), (0.26, 0.27, 0.29)


def _wall_paint(z0, z1, rust=0.5):
    base = M.paint(STEEL_LO, STEEL_HI, z0, z1, grime=0.35)

    def f(p):
        c = np.array(base(p))
        r = max(0.0, M._noise(p, 1.3) - (0.6 - 0.4 * rust)) * 1.8
        return tuple(np.clip(c * (1 - r) + np.array(RUST_HI) * 0.7 * r, 0, 1))
    return f


class Cockpit:
    def __init__(self, base, size=(640, 480)):
        self.base = base
        self.tex = Texture("cockpit")
        self.buffer = base.win.makeTextureBuffer("cockpit-buffer", size[0], size[1], self.tex)
        self.buffer.setSort(-30)
        self.buffer.setClearColor((0.0, 0.0, 0.0, 1))
        self.scene = NodePath("cockpit-scene")
        self.scene.setShaderAuto()
        lens = PerspectiveLens()
        lens.setFov(68, 54)
        lens.setNearFar(0.05, 60)
        self.cam = self.scene.attachNewNode(Camera("cockpit-cam", lens))
        self.cam.setPos(0, -0.4, 1.25)
        self.cam.lookAt(0, 3.0, 1.05)
        self.cam_base = self.cam.getPos()
        self.buffer.makeDisplayRegion().setCamera(self.cam)
        self.t = 0.0
        self.rng = np.random.default_rng(12)
        self._lights()
        self._build()

    # ------------------------------------------------------------ scene

    def _lights(self):
        s = self.scene
        amb = s.attachNewNode(AmbientLight("amb"))
        amb.node().setColor((0.09, 0.09, 0.11, 1))
        s.setLight(amb)
        self.lamp = s.attachNewNode(PointLight("tube"))  # flickering ceiling tube
        self.lamp.node().setAttenuation((1, 0.1, 0.25))
        self.lamp.setPos(0, 2.2, 2.25)
        s.setLight(self.lamp)
        self.alarm = s.attachNewNode(Spotlight("alarm"))  # rotating red warning light
        self.alarm.node().setColor((1.6, 0.12, 0.05, 1))
        self.alarm.node().getLens().setFov(55)
        self.alarm.node().setAttenuation((1, 0.05, 0.05))
        self.alarm.setPos(1.3, 3.2, 2.15)
        s.setLight(self.alarm)
        self.screen_light = s.attachNewNode(PointLight("screens"))  # cold monitor glow from below
        self.screen_light.node().setColor((0.15, 0.45, 0.55, 1))
        self.screen_light.node().setAttenuation((1, 0.3, 0.6))
        self.screen_light.setPos(0, 0.4, 0.6)
        s.setLight(self.screen_light)

    def _build(self):
        root = self.scene
        rng = self.rng
        V, F = M.box(1, 1, 1)
        # cramped hull: floor, ceiling and two slanted walls, with ribs
        for x, h in ((-1.7, 1), (1.7, -1)):
            M.part(root, V, F, (1, 1, 1), pos=(x, 2.5, 1.15), scale=(0.08, 6.0, 2.6), hpr=(0, 0, h * 8),
                   vcol=_wall_paint(-0.5, 0.5), smooth=None)
        M.part(root, V, F, (1, 1, 1), pos=(0, 2.5, -0.05), scale=(3.6, 6.0, 0.1), vcol=_wall_paint(-0.5, 0.5, 0.2),
               smooth=None)
        M.part(root, V, F, (1, 1, 1), pos=(0, 2.5, 2.45), scale=(3.6, 6.0, 0.1), vcol=_wall_paint(-0.5, 0.5),
               smooth=None)
        M.part(root, V, F, (1, 1, 1), pos=(0, 5.3, 1.2), scale=(3.6, 0.1, 2.6), vcol=_wall_paint(-0.5, 0.5, 0.8),
               smooth=None)  # rear bulkhead
        for k in range(5):  # structural ribs arching over the cabin
            y = 1.2 + k * 0.95
            for x, h in ((-1.6, 1), (1.6, -1)):
                M.part(root, V, F, (0.1, 0.1, 0.11), pos=(x, y, 1.15), scale=(0.16, 0.14, 2.6), hpr=(0, 0, h * 8),
                       smooth=None)
            M.part(root, V, F, (0.1, 0.1, 0.11), pos=(0, y, 2.36), scale=(3.4, 0.14, 0.14), smooth=None)
            for x in np.linspace(-1.45, 1.45, 7):  # rivets
                M.part(root, V, F, (0.3, 0.3, 0.32), pos=(x, y - 0.075, 2.3), scale=0.025, smooth=None)
        # hazard stripes on the floor edge
        for k in range(14):
            M.part(root, V, F, (0.85, 0.65, 0.05) if k % 2 else (0.03, 0.03, 0.03),
                   pos=(-1.3 + k * 0.2, 4.6, 0.01), scale=(0.2, 0.25, 0.01), hpr=(30, 0, 0), smooth=None)
        # pipes and cable looms along the walls
        for side in (-1, 1):
            for j in range(4):
                z = 0.4 + j * 0.42
                pts = [(side * (1.5 - 0.02 * j), 0.0, z), (side * 1.48, 1.8, z + 0.05 * math.sin(j)),
                       (side * 1.5, 3.6, z - 0.05), (side * 1.45, 5.2, z + 0.1)]
                col = ((0.22, 0.1, 0.06), (0.12, 0.12, 0.13), (0.3, 0.27, 0.05), (0.08, 0.08, 0.09))[j]
                M.tube(root, pts, 0.045 + 0.02 * (j % 2), col, band=(0.5, 0.45, 0.4) if j == 1 else None)
            for j in range(6):  # sagging cables from the ceiling
                x = side * rng.uniform(0.3, 1.3)
                y0 = rng.uniform(1.0, 4.5)
                M.tube(root, [(x, y0, 2.38), (x + 0.1, y0 + 0.3, 2.0 - rng.uniform(0, 0.25)),
                              (x - 0.05, y0 + 0.7, 2.05), (x, y0 + 1.0, 2.38)], 0.015, (0.03, 0.03, 0.035))
        # porthole in the rear bulkhead: a burning planet and stars outside
        Vr, Fr = M.lathe([(0.55, 0.0), (0.65, 0.02), (0.65, 0.12), (0.55, 0.14)], 32, "y")
        M.part(root, Vr, Fr, (0.18, 0.18, 0.2), pos=(-0.95, 5.08, 1.6), orient="y")
        win = root.attachNewNode("porthole")
        win.setPos(-0.95, 5.2, 1.6)
        Vd, Fd = M.lathe([(0.0, 0.0), (0.56, 0.0)], 32, "y")
        M.part(win, Vd, Fd, (0.0, 0.0, 0.01), unlit=True, orient=None, two_sided=True)
        for _ in range(40):
            a, r = rng.uniform(0, 2 * math.pi), 0.54 * math.sqrt(rng.random())
            M.part(win, *M.icosphere(0), (1, 1, 1), pos=(r * math.cos(a), -0.01, r * math.sin(a)),
                   scale=0.006 + 0.008 * rng.random(), unlit=True)
        M.glow(win, (0.2, -0.02, -0.25), 0.55, (1.0, 0.35, 0.08, 0.8))
        M.part(win, *M.hemisphere(2), (0.35, 0.08, 0.03), pos=(0.22, -0.01, -0.5), scale=(0.45, 0.02, 0.32),
               unlit=True, hpr=(0, -90, 0))
        # monitors on the side walls (glow flickers in update())
        self.screens = []
        for side, y in ((-1, 2.0), (1, 2.6), (-1, 3.6), (1, 4.2)):
            frame = root.attachNewNode("monitor")
            frame.setPos(side * 1.38, y, 1.45)
            frame.setH(-side * 82)
            M.part(frame, V, F, (0.08, 0.08, 0.09), scale=(0.62, 0.06, 0.42), smooth=None)
            scr = M.part(frame, V, F, (0.2, 0.9, 0.8) if side < 0 else (1.0, 0.55, 0.15), pos=(0, -0.035, 0),
                         scale=(0.54, 0.01, 0.34), unlit=True, smooth=None)
            for k in range(5):  # lines of "text"
                M.part(frame, V, F, (0.02, 0.05, 0.05), pos=(-0.1 + 0.05 * (k % 2), -0.042, 0.12 - k * 0.06),
                       scale=(0.3 - 0.04 * (k % 3), 0.005, 0.018), unlit=True, smooth=None)
            self.screens.append(scr)
        # the pilot seat right behind the player
        seat = root.attachNewNode("seat")
        seat.setPos(0, 2.1, 0.0)
        seat.setScale(0.85)
        paint = M.paint((0.03, 0.03, 0.035), (0.2, 0.19, 0.18), 0.0, 2.0, grime=0.3)
        back = [(0.0, 0.42, 0.1, 0.0, 3.0), (0.8, 0.48, 0.12, 0.0, 3.2), (1.5, 0.45, 0.12, 0.0, 3.2),
                (1.9, 0.32, 0.11, 0.0, 3.0), (2.15, 0.22, 0.09, 0.0, 2.6)]
        Vs, Fs = M.sweep([(z, w, d, 0, n) for z, w, d, _, n in back], 24, "y")
        sb = M.part(seat, Vs[:, [0, 2, 1]], Fs, (1, 1, 1), orient="center", vcol=paint)  # stood upright
        sb.setPos(0, 0.25, 0.0)
        for side in (-1, 1):  # wings of the headrest, harness and life-support hoses
            M.part(seat, V, F, (0.06, 0.06, 0.07), pos=(side * 0.34, 0.15, 1.85), scale=(0.1, 0.22, 0.45),
                   hpr=(side * 25, 0, 0))
            M.part(seat, V, F, (0.45, 0.33, 0.05), pos=(side * 0.2, 0.05, 1.2), scale=(0.07, 0.03, 0.9),
                   hpr=(0, 0, side * 8), smooth=None)
            M.tube(seat, [(side * 0.38, 0.3, 1.7), (side * 0.7, 0.5, 1.9), (side * 0.95, 0.9, 2.2),
                          (side * 1.1, 1.4, 2.38)], 0.04, (0.15, 0.15, 0.16), band=(0.6, 0.1, 0.05))
        # small lights that blink in update()
        self.leds = []
        for _ in range(26):
            side = rng.choice([-1, 1])
            p = (side * rng.uniform(1.35, 1.5), rng.uniform(0.8, 5.0), rng.uniform(0.5, 2.1))
            col = ((1, 0.15, 0.05), (0.2, 1, 0.3), (1, 0.7, 0.1), (0.2, 0.6, 1))[int(rng.integers(4))]
            led = root.attachNewNode("led")
            M.part(led, *M.icosphere(0), col, pos=p, scale=0.018, unlit=True)
            M.glow(led, p, 0.09, (*col, 0.9))
            self.leds.append((led, rng.uniform(0.3, 3.0), rng.uniform(0, 6.3)))
        # alarm beacon housing
        M.part(root, *M.hemisphere(2), (0.5, 0.05, 0.03, 0.8), pos=(1.3, 3.2, 2.3), scale=(0.12, 0.12, -0.1),
               unlit=True, alpha=True)
        self.alarm_glow = M.glow(root, (1.3, 3.2, 2.25), 0.5, (1.0, 0.1, 0.05, 0.8))
        self.tube_glow = M.glow(root, (0, 2.2, 2.3), 1.6, (0.8, 0.9, 1.0, 0.25))
        M.part(root, V, F, (0.9, 0.95, 1.0), pos=(0, 2.2, 2.33), scale=(1.4, 0.06, 0.03), unlit=True, smooth=None)
        # haze: big faint glows give the air some depth
        for p, c in (((0.8, 4.5, 0.6), (0.6, 0.15, 0.1, 0.12)), ((-0.9, 3.5, 2.0), (0.3, 0.45, 0.6, 0.08))):
            M.glow(root, p, 2.5, c)

    # ------------------------------------------------------------ animation

    def update(self, dt, shake=0.0, hypno=0.0):
        self.t += dt
        t = self.t
        # the tube light flickers like a dying fluorescent lamp
        flick = 1.0 if (math.sin(t * 37) + math.sin(t * 13.7) * 0.7) > -1.35 else 0.25
        k = (0.85 + 0.12 * math.sin(t * 3.1)) * flick
        self.lamp.node().setColor((0.8 * k + hypno * 0.6, 0.85 * k, 1.0 * k + hypno * 1.2, 1))
        self.tube_glow.setAlphaScale(flick)
        self.alarm.setHpr(t * 220 % 360, -25, 0)
        a = 0.5 + 0.5 * math.cos(math.radians(t * 220 % 360 - 180))
        self.alarm_glow.setAlphaScale(0.3 + 0.7 * a)
        for i, scr in enumerate(self.screens):
            scr.setColorScale(1, 1, 1, 1) if math.sin(t * (2 + i) + i) > -0.92 else scr.setColorScale(0.3, 0.3, 0.3, 1)
        for led, rate, ph in self.leds:
            led.show() if math.sin(t * rate * 6.28 + ph) > 0 else led.hide()
        sway = (0.004 * math.sin(t * 1.3), 0.0, 0.004 * math.sin(t * 1.7))
        s = shake ** 2 * 0.04
        jolt = tuple(self.rng.uniform(-s, s, 3)) if s > 0 else (0, 0, 0)
        self.cam.setPos(self.cam_base + sway + jolt)

    def destroy(self):
        self.base.graphicsEngine.removeWindow(self.buffer)
