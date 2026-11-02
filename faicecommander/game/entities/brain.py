"""Boltzmann brains: they form out of the void, drift towards the ship with the scroll and fade
after a few seconds. Shootable - and they burst messily."""
from panda3d.core import NodePath

from ...render import models as M


class BrainLibrary:
    def __init__(self, count=3):
        self.store = NodePath("brain-library")
        self.models = [M.build_brain(self.store, 1.0, aura=True) for _ in range(count)]


class Brain:
    kind = "brain"
    category = "brain"
    FORM_S, FADE_S = 0.35, 0.35

    def __init__(self, parent, library, rng, x, y, radius, life, resist, damage, score):
        self.node = library.models[int(rng.integers(len(library.models)))].copyTo(parent)
        self.x, self.y, self.radius = x, y, radius
        self.life, self.t = life, 0.0
        self.resist, self.damage, self.score = resist, damage, score
        self.health = 1.0
        self.alive = True
        self.beam_heat = 0.0
        self.spin = rng.uniform(-60, 60, 3)
        self.hpr = rng.uniform(-30, 30, 3)
        self.node.setScale(0.001)

    @property
    def expired(self):
        return self.t >= self.life

    def hurt(self, weapon, amount=1.0):
        self.health -= amount / self.resist[weapon]
        return self.health <= 1e-6

    def update(self, dt, scroll):
        self.t += dt
        self.y -= scroll * dt
        form = min(1.0, self.t / self.FORM_S)
        fade = min(1.0, max(0.0, (self.life - self.t) / self.FADE_S))
        grow = form * (1 + 0.25 * (1 - form)) * fade  # slight overshoot while materialising
        # build_brain is about 2 units across at scale 1, so scale = radius
        self.node.setScale(max(0.001, self.radius * grow))
        self.hpr += self.spin * dt
        self.node.setPos(self.x, self.y, 0.3)
        self.node.setHpr(*self.hpr)
        self.beam_heat = max(0.0, self.beam_heat - dt * 3)
        if self.beam_heat > 0:
            self.node.setColorScale(1 + self.beam_heat, 1, 1, 1)
        else:
            self.node.clearColorScale()

    def remove(self):
        self.alive = False
        self.node.removeNode()
