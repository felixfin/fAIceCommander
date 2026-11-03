"""Black holes pull the ship sideways. Natural ones (level 6) drift towards you and touching the
event horizon is fatal; the Mother's artificial ones (level 7) sit still, drain your hull when you are
close and collapse after a while."""
import math

import numpy as np
from panda3d.core import NodePath

from ...render import models as M


class BlackHoleTemplate:
    def __init__(self):
        self.store = NodePath("black-hole-template")
        self.model = M.build_black_hole(self.store, 1.0)
        self.bomb = NodePath("hole-bomb")
        V, F = M.icosphere(2)
        M.part(self.bomb, V * 0.35, F, (0.02, 0.0, 0.02))
        M.glow(self.bomb, (0, 0, 0), 1.4, (0.8, 0.05, 0.4, 0.9))


class BlackHole:
    def __init__(self, parent, template, x, y, vy, horizon, pull, life=None, drain=0.0, drain_radius=0.0):
        self.node = template.store.copyTo(parent)
        self.x, self.y, self.vy = x, y, vy
        self.horizon, self.pull = horizon, pull
        self.life, self.drain, self.drain_radius = life, drain, drain_radius
        self.deadly = life is None
        self.node.setScale(horizon * 1.25)  # the visible black sphere is a little larger than the kill radius
        self.alive = True
        self.t = 0.0

    @property
    def collapsed(self):
        return self.life is not None and self.t >= self.life

    def update(self, dt, scroll):
        self.t += dt
        self.y -= (scroll + self.vy) * dt
        self.node.setPos(self.x, self.y, 0)
        self.node.setH(self.t * 40)  # swirling accretion disk
        if self.life is not None:  # artificial holes grow in, then shrink away
            k = min(1.0, self.t / 0.6, max(0.0, (self.life - self.t) / 0.8))
            self.node.setScale(max(0.01, self.horizon * 1.25 * k))

    def drift(self, x, y, cap):
        """Sideways drift speed (units/s) towards the hole for something at (x, y)."""
        dx, dy = self.x - x, self.y - y
        d = max(math.hypot(dx, dy), 0.5)
        v = min(cap, self.pull / d ** 2)
        return v * dx / d

    def distance(self, x, y):
        return math.hypot(self.x - x, self.y - y)

    def remove(self):
        self.alive = False
        self.node.removeNode()


class HoleBomb:
    """Flies to where the ship was and turns into an artificial black hole there."""
    radius = 0.35

    def __init__(self, parent, template, x, y, tx, ty, speed):
        self.node = template.bomb.copyTo(parent)
        self.x, self.y, self.tx, self.ty = x, y, tx, ty
        d = max(math.hypot(tx - x, ty - y), 1e-3)
        self.vx, self.vy = (tx - x) / d * speed, (ty - y) / d * speed
        self.time_left = d / speed
        self.alive = True
        self.node.setPos(x, y, 0.2)

    @property
    def arrived(self):
        return self.time_left <= 0

    def update(self, dt):
        self.time_left -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.node.setPos(self.x, self.y, 0.2)
        self.node.setScale(1.0 + 0.2 * np.sin(self.time_left * 20))

    def remove(self):
        self.alive = False
        self.node.removeNode()
