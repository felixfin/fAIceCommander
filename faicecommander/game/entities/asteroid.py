"""Asteroids: a pool of procedural rock meshes, instanced with random size and spin."""
from panda3d.core import NodePath

from ...render import models as M


class AsteroidLibrary:
    def __init__(self, count=10, seed=500):
        self.store = NodePath("asteroid-library")
        self.rocks = []
        for i in range(count):
            V, F, cols, _ = M.asteroid_mesh(seed + i, 1.0)
            self.rocks.append(M.part(self.store, V, F, cols))


class Asteroid:
    def __init__(self, parent, library, rng, x, y, radius, vx, vy, category=1, hp=1):
        self.node = library.rocks[int(rng.integers(len(library.rocks)))].copyTo(parent)
        self.node.setScale(radius)
        self.x, self.y, self.radius = x, y, radius
        self.vx, self.vy = vx, vy
        self.category, self.hp = category, hp
        self.hpr = rng.uniform(0, 360, 3)
        self.spin = rng.uniform(-90, 90, 3)
        self.alive = True

    def update(self, dt, scroll):
        self.x += self.vx * dt
        self.y += (self.vy - scroll) * dt
        self.hpr += self.spin * dt
        self.node.setPos(self.x, self.y, 0)
        self.node.setHpr(*self.hpr)

    def remove(self):
        self.alive = False
        self.node.removeNode()
