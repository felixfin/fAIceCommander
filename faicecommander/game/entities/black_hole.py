"""Black holes pull the ship sideways. Natural ones (level 6) drift towards you and touching the
event horizon is fatal; the Mother's artificial ones (level 7) sit still, drain your hull when you are
close and collapse after a while."""
import math

import numpy as np

from ...render import models as M


class BlackHoleTemplate:
    def __init__(self):
        def build(root):
            M.build_black_hole(root.attachNewNode("black-hole-template"), 1.0)
            bomb = root.attachNewNode("hole-bomb")
            V, F = M.icosphere(2)
            M.part(bomb, V * 0.35, F, (0.02, 0.0, 0.02))
            M.glow(bomb, (0, 0, 0), 1.4, (0.8, 0.05, 0.4, 0.9))
        lib = M.cached("black-hole", build)
        self.store = lib.find("black-hole-template")
        self.model = self.store.getChild(0)
        self.bomb = lib.find("hole-bomb")


REF_HORIZON = 0.9  # world units (18 px): the hole size the configured pull refers to


class BlackHole:
    def __init__(self, parent, template, x, y, vy, horizon, pull, life=None, drain=0.0, drain_radius=0.0,
                 breathe=0.0):
        self.node = template.store.copyTo(parent)
        self.x, self.y, self.vy = x, y, vy
        self.base_horizon = self.horizon = horizon
        self.pull = pull
        self.life, self.drain, self.drain_radius = life, drain, drain_radius
        self.deadly = life is None
        self.breathe = breathe                   # the horizon swells and shrinks by this share
        self.breathe_w = 2 * math.pi / np.random.uniform(2.5, 4.5)
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
        if self.breathe:
            self.horizon = self.base_horizon * (1 + self.breathe * math.sin(self.t * self.breathe_w))
            self.node.setScale(self.horizon * 1.25)
        if self.life is not None:  # artificial holes grow in, then shrink away
            k = min(1.0, self.t / 0.6, max(0.0, (self.life - self.t) / 0.8))
            self.node.setScale(max(0.01, self.horizon * 1.25 * k))

    def drift(self, x, y, cap):
        """Sideways drift speed (units/s) towards the hole for something at (x, y): bigger holes pull
        harder (with the square of the horizon) and the pull reaches far (1 / distance^1.5)."""
        dx, dy = self.x - x, self.y - y
        d = max(math.hypot(dx, dy), 0.5)
        v = min(cap, self.pull * (self.horizon / REF_HORIZON) ** 2 / d ** 1.5)
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
