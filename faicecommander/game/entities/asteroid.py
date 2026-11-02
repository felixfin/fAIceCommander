"""Asteroids: pools of procedural rock meshes (category 1 and the cracked category 2), instanced
with random size and spin. Damage follows the spec's per-weapon numbers (see targets.* in config)."""
from panda3d.core import NodePath

from ...render import models as M


class AsteroidLibrary:
    def __init__(self, count=10, seed=500):
        self.store = NodePath("asteroid-library")
        self.rocks = {1: [], 2: []}
        for i in range(count):
            V, F, cols, _ = M.asteroid_mesh(seed + i, 1.0)
            self.rocks[1].append(M.part(self.store, V, F, cols))
        for i in range(4):
            self.rocks[2].append(M.build_asteroid(self.store, seed + 50 + i, 1.0, category=2))


class Asteroid:
    def __init__(self, parent, library, rng, x, y, radius, vx, vy, category, resist, damage, score):
        pool = library.rocks[category]
        self.node = pool[int(rng.integers(len(pool)))].copyTo(parent)
        self.node.setScale(radius)
        self.x, self.y, self.radius = x, y, radius
        self.vx, self.vy = vx, vy
        self.category = category
        self.resist = resist      # {"laser": hits, "beam": seconds, "nuke": nukes} to destroy
        self.damage = damage      # hull percent on collision
        self.score = score
        self.health = 1.0
        self.hpr = rng.uniform(0, 360, 3)
        self.spin = rng.uniform(-90, 90, 3) / (1 if category == 1 else 2.5)
        self.alive = True
        self.beam_heat = 0.0

    def hurt(self, weapon, amount=1.0):
        """amount: 1 per laser hit / nuke, dt per second of beam. Returns True if destroyed."""
        self.health -= amount / self.resist[weapon]
        return self.health <= 1e-6

    def update(self, dt, scroll):
        self.x += self.vx * dt
        self.y += (self.vy - scroll) * dt
        self.hpr += self.spin * dt
        self.node.setPos(self.x, self.y, 0)
        self.node.setHpr(*self.hpr)
        self.beam_heat = max(0.0, self.beam_heat - dt * 3)
        heat = self.beam_heat * 0.6 + (1.0 - self.health) * 1.4  # damage taken shows as a lasting glow
        if heat > 0.01:
            self.node.setColorScale(1 + heat * 1.6, 1 + heat * 0.55, 1 + heat * 0.1, 1)
        else:
            self.node.clearColorScale()

    def remove(self):
        self.alive = False
        self.node.removeNode()
