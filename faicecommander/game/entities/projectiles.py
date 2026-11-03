"""Laser pulses, nuclear rockets and the Mother's flak."""
import math

import numpy as np
from panda3d.core import NodePath

from ...render import models as M


class BoltTemplate:
    def __init__(self, color=M.GREEN_LASER):
        self.store = NodePath("bolt-template")
        V, F = M.icosphere(1)
        M.part(self.store, V * np.array([0.07, 0.42, 0.07]), F, color, unlit=True)
        M.glow(self.store, (0, 0, 0), 0.45, (*color, 0.8))


class LaserBolt:
    radius = 0.12

    def __init__(self, parent, template, x, y, vy):
        self.node = template.store.copyTo(parent)
        self.x, self.y, self.vy = x, y, vy
        self.alive = True
        self.node.setPos(x, y, 0)

    def update(self, dt):
        self.y += self.vy * dt
        self.node.setY(self.y)

    def remove(self):
        self.alive = False
        self.node.removeNode()


class NukeTemplate:
    """White rocket with a red warhead, fins and an exhaust flame."""

    def __init__(self):
        self.store = NodePath("nuke-template")
        V, F = M.lathe([(0.0, 0.5), (0.06, 0.4), (0.085, 0.25), (0.085, -0.3), (0.07, -0.36)], 12, "y")
        M.part(self.store, V, F, (0.85, 0.85, 0.82), orient="y")
        Vt, Ft = M.lathe([(0.0, 0.5), (0.06, 0.4), (0.087, 0.27)], 12, "y")
        M.part(self.store, Vt, Ft, (0.85, 0.12, 0.08), orient="y")
        for k in range(4):
            Vf, Ff = M.prism([(0.0, -0.1), (0.0, -0.36), (0.16, -0.4)], 0.015)
            fin = M.part(self.store, Vf, Ff, (0.3, 0.3, 0.32))
            fin.setR(k * 90)
        Vx, Fx = M.lathe([(0.06, 0), (0.0, -0.5)], 10, "y")
        M.part(self.store, Vx, Fx, (1.0, 0.75, 0.35, 0.8), pos=(0, -0.37, 0), additive=True, orient=None)
        M.glow(self.store, (0, -0.45, 0), 0.5, (1.0, 0.6, 0.2, 0.9))


class Nuke:
    radius = 0.25

    def __init__(self, parent, template, x, y, speed, accel, fuse):
        self.node = template.store.copyTo(parent)
        self.node.setScale(1.6)
        self.x, self.y = x, y
        self.vy, self.accel, self.fuse = speed, accel, fuse
        self.t = 0.0
        self.alive = True

    def update(self, dt):
        self.t += dt
        self.vy += self.accel * dt
        self.y += self.vy * dt
        self.node.setPos(self.x, self.y, 0.1)
        self.node.setR(self.t * 400)  # spin around its axis

    @property
    def expired(self):
        return self.t >= self.fuse

    def remove(self):
        self.alive = False
        self.node.removeNode()


class Flak:
    """The Mother's point-defence shot: chases a nuke and sets it off when it gets there."""
    radius = 0.2

    def __init__(self, parent, raider_template, x, y, target, speed):
        self.node = raider_template.shot.copyTo(parent)
        self.node.setScale(1.4)
        self.x, self.y, self.target, self.speed = x, y, target, speed
        self.alive = True

    @property
    def reached(self):
        return math.hypot(self.target.x - self.x, self.target.y - self.y) < self.radius + self.target.radius + 0.2

    def update(self, dt):
        dx, dy = self.target.x - self.x, self.target.y - self.y
        d = max(math.hypot(dx, dy), 1e-6)
        step = min(d, self.speed * dt)
        self.x += dx / d * step
        self.y += dy / d * step
        self.node.setH(math.degrees(math.atan2(-dx, dy)))
        self.node.setPos(self.x, self.y, 0.15)

    def remove(self):
        self.alive = False
        self.node.removeNode()
