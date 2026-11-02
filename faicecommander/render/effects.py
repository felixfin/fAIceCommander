"""Animated effects: explosions with a Death-Star-style shockwave ring, red hit flash."""
import math

import numpy as np
from panda3d.core import CardMaker, NodePath, TransparencyAttrib

from . import models as M


class EffectTemplates:
    """Geometry built once and copied per effect."""

    def __init__(self):
        self.store = NodePath("effect-templates")
        V, F = M.annulus(0.78, 1.0, seg=96, rings=5)

        def ring_col(p):
            u = (math.hypot(p[0], p[1]) - 0.78) / 0.22
            return (0.65 + 0.35 * u, 0.85, 1.0, math.sin(math.pi * min(max(u, 0.0), 1.0)) ** 2)

        self.ring = M.part(self.store, V, F, (1, 1, 1), orient=None, additive=True, vcol=ring_col)
        self.debris = []
        for seed in range(6):
            Vd, Fd, cols, _ = M.asteroid_mesh(100 + seed, 1.0, sub=0)
            self.debris.append(M.part(self.store, Vd, Fd, cols))


class Explosion:
    """Flash, fireball sprites, tumbling debris and an expanding shockwave ring on the play plane."""

    def __init__(self, parent, templates, pos, size, rng, duration=1.3, ring_speed=9.0):
        self.root = parent.attachNewNode("explosion")
        self.root.setPos(*pos)
        self.size, self.duration, self.ring_speed = size, duration, ring_speed
        self.t = 0.0
        self.sprites = []
        for _ in range(int(14 + 10 * size)):
            d = rng.normal(size=3)
            d /= np.linalg.norm(d)
            card = M.glow(self.root, (0, 0, 0), 1.0, (1, 1, 1, 1))
            self.sprites.append((card, d * rng.uniform(0.2, 1.0), rng.uniform(0.6, 1.5)))
        self.flash = M.glow(self.root, (0, 0, 0), 1.0, (1, 1, 0.9, 1))
        self.ring = templates.ring.copyTo(self.root)
        self.debris = []
        for _ in range(int(5 + 6 * size)):
            d = rng.normal(size=3)
            d[2] *= 0.4
            d /= np.linalg.norm(d)
            node = templates.debris[int(rng.integers(len(templates.debris)))].copyTo(self.root)
            node.setScale(rng.uniform(0.05, 0.14) * size)
            spin = rng.uniform(-360, 360, 3)
            self.debris.append((node, d * rng.uniform(2.5, 6.0) * (0.6 + 0.4 * size), spin))

    @property
    def ring_radius(self):
        return 0.4 + self.ring_speed * self.t

    def update(self, dt):
        self.t += dt
        u = self.t / self.duration
        if u >= 1.0:
            self.root.removeNode()
            return False
        s = self.size
        fade = (1 - u) ** 1.3
        spread = (0.3 + 2.2 * u ** 0.5) * s
        for card, d, k in self.sprites:
            card.setPos(*(d * spread))
            card.setScale(k * s * (1 + u))
            hot = max(0.0, 1 - u * 1.8)
            card.setColor(1.0, 0.45 + 0.5 * hot, 0.1 + 0.6 * hot, 0.8 * fade)
        self.flash.setScale(3.2 * s * max(0.0, 1 - u * 3))
        r = self.ring_radius
        self.ring.setScale(r, r, 1)
        self.ring.setColorScale(1, 1, 1, (1 - u) * 0.95)
        for node, v, spin in self.debris:
            node.setPos(*(v * self.t))
            node.setHpr(*(spin * self.t))
        return True


class ScreenFlash:
    """Transparent blood-red pulse over the game area when the ship is hit."""

    def __init__(self, render2d):
        cm = CardMaker("flash")
        cm.setFrame(-1, 1, -1, 1)
        self.card = render2d.attachNewNode(cm.generate())
        self.card.setTransparency(TransparencyAttrib.MAlpha)
        self.card.setColor(0.7, 0.0, 0.02, 0)
        self.card.setBin("fixed", 0)
        self.alpha = 0.0

    def fit(self, bottom):
        """Cover the game area only (render2d y from bottom to 1)."""
        self.card.setPos(0, 0, (1 + bottom) / 2)
        self.card.setScale(1, 1, (1 - bottom) / 2)

    def trigger(self, strength=0.55):
        self.alpha = max(self.alpha, strength)

    def update(self, dt):
        self.alpha = max(0.0, self.alpha - dt * 1.4)
        self.card.setColor(0.7, 0.0, 0.02, self.alpha)
