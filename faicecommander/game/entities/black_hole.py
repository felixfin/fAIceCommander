"""Black holes drift towards the ship and pull it sideways; touching the event horizon is fatal."""
import math

from panda3d.core import NodePath

from ...render import models as M


class BlackHoleTemplate:
    def __init__(self):
        self.store = NodePath("black-hole-template")
        self.model = M.build_black_hole(self.store, 1.0)


class BlackHole:
    def __init__(self, parent, template, x, y, vy, horizon, pull):
        self.node = template.store.copyTo(parent)
        self.x, self.y, self.vy = x, y, vy
        self.horizon, self.pull = horizon, pull
        self.node.setScale(horizon * 1.25)  # the visible black sphere is a little larger than the kill radius
        self.alive = True
        self.t = 0.0

    def update(self, dt, scroll):
        self.t += dt
        self.y -= (scroll + self.vy) * dt
        self.node.setPos(self.x, self.y, 0)
        self.node.setH(self.t * 40)  # swirling accretion disk

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
