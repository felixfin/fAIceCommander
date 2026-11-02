"""Laser pulses fired from the ship's pod cannons."""
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

    def __init__(self, parent, template, x, y, vy, damage=1):
        self.node = template.store.copyTo(parent)
        self.x, self.y, self.vy, self.damage = x, y, vy, damage
        self.alive = True
        self.node.setPos(x, y, 0)

    def update(self, dt):
        self.y += self.vy * dt
        self.node.setY(self.y)

    def remove(self):
        self.alive = False
        self.node.removeNode()
