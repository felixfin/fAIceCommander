"""Animated effects: explosions with a Death-Star-style shockwave ring, laser beam, rocket smoke, screen flash."""
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
            Vd, Fd, vcol, _ = M.asteroid_mesh(100 + seed, 1.0, sub=0)
            self.debris.append(M.part(self.store, Vd, Fd, (1, 1, 1), vcol=vcol))
        # laser beam: a unit-length glowing tube along +Y, scaled per frame
        self.beam = self.store.attachNewNode("beam")
        for r, col in ((0.07, (0.85, 1.0, 0.95, 0.95)), (0.18, (0.3, 1.0, 0.8, 0.55)), (0.38, (0.2, 0.9, 0.7, 0.22))):
            Vb, Fb = M.lathe([(r, 0.0), (r, 1.0)], 10, "y")
            M.part(self.beam, Vb, Fb, col, additive=True, orient=None)
        # brain burst: lumpy pink chunks and dark red droplets
        rng = np.random.default_rng(9)
        Vi, Fi = M.icosphere(1)
        self.chunks = [M.part(self.store, Vi * (1 + 0.35 * rng.normal(size=(len(Vi), 1))), Fi,
                              (0.9, 0.45 + 0.1 * k, 0.55)) for k in range(3)]
        self.drop = M.part(self.store, Vi * np.array([1.0, 2.5, 1.0]), Fi, (0.45, 0.01, 0.03))


class BrainBurst:
    """A shot Boltzmann brain bursting: chunks, blood droplets, red mist."""

    def __init__(self, parent, templates, pos, size, rng, duration=1.1):
        self.root = parent.attachNewNode("brain-burst")
        self.root.setPos(*pos)
        self.t, self.duration = 0.0, duration
        self.mist = M.glow(self.root, (0, 0, 0), 1.0, (0.65, 0.0, 0.03, 0.8))
        self.parts = []
        for k in range(26):
            d = rng.normal(size=3)
            d /= np.linalg.norm(d)
            speed = rng.uniform(1.5, 5.0) * size
            if k < 10:
                node = templates.chunks[int(rng.integers(len(templates.chunks)))].copyTo(self.root)
                s0 = rng.uniform(0.06, 0.16) * size
            else:
                node = templates.drop.copyTo(self.root)
                s0 = rng.uniform(0.03, 0.06) * size
                node.lookAt(tuple(d))
            node.setScale(s0)
            self.parts.append((node, d * speed, rng.uniform(-400, 400, 3) if k < 10 else None, s0))

    def update(self, dt):
        self.t += dt
        u = self.t / self.duration
        if u >= 1:
            self.root.removeNode()
            return False
        shrink = max(0.01, 1 - max(0.0, u - 0.6) / 0.4)
        for node, v, spin, s0 in self.parts:
            node.setPos(*(v * self.t * (1 - 0.35 * u)))
            node.setScale(s0 * shrink)
            if spin is not None:
                node.setHpr(*(spin * self.t))
        self.mist.setScale(0.8 + 2.5 * u)
        self.mist.setColor(0.65, 0.0, 0.03, 0.8 * (1 - u))
        return True


class Explosion:
    """Flash, fireball sprites, tumbling debris and an expanding shockwave ring on the play plane.

    The ring keeps travelling until it has passed the ship; `boom_due` turns True the moment it
    reaches the ship, which is when the explosion is heard.
    """

    def __init__(self, parent, templates, pos, size, rng, ring_speed, ship_distance, duration=1.3):
        self.root = parent.attachNewNode("explosion")
        self.root.setPos(*pos)
        self.x, self.y = pos[0], pos[1]
        self.size, self.duration, self.ring_speed = size, duration, ring_speed
        self.ring_life = min(5.0, max(duration, (ship_distance + 2.5) / ring_speed))
        self.t = 0.0
        self.boomed = False
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

    def boom_due(self, ship_x, ship_y):
        if self.boomed or math.hypot(ship_x - self.x, ship_y - self.y) > self.ring_radius:
            return False
        self.boomed = True
        return True

    def update(self, dt):
        self.t += dt
        if self.t >= self.ring_life:
            self.root.removeNode()
            return False
        u = min(1.0, self.t / self.duration)
        s = self.size
        if u < 1.0:
            fade = (1 - u) ** 1.3
            spread = (0.3 + 2.2 * u ** 0.5) * s
            for card, d, k in self.sprites:
                card.setPos(*(d * spread))
                card.setScale(k * s * (1 + u))
                hot = max(0.0, 1 - u * 1.8)
                card.setColor(1.0, 0.45 + 0.5 * hot, 0.1 + 0.6 * hot, 0.8 * fade)
            for node, v, spin in self.debris:
                node.setPos(*(v * self.t))
                node.setHpr(*(spin * self.t))
        elif self.sprites:
            for card, _, _ in self.sprites:
                card.removeNode()
            for node, _, _ in self.debris:
                node.removeNode()
            self.sprites, self.debris = [], []
        self.flash.setScale(max(0.0, 3.2 * s * (1 - u * 3)))
        r = self.ring_radius
        self.ring.setScale(r, r, 1)
        self.ring.setColorScale(1, 1, 1, (1 - self.t / self.ring_life) * min(1.0, 0.5 + s * 0.4))
        return True


class Puff:
    """A short-lived smoke/fire puff (rocket trail)."""

    def __init__(self, parent, pos, rng):
        self.card = M.glow(parent, pos, 0.3, (1, 0.7, 0.3, 0.8))
        self.t, self.life = 0.0, rng.uniform(0.5, 0.8)
        self.drift = rng.normal(0, 0.4, 3)
        self.drift[2] = abs(self.drift[2])
        self.root = self.card

    def update(self, dt):
        self.t += dt
        u = self.t / self.life
        if u >= 1:
            self.card.removeNode()
            return False
        self.card.setPos(self.card.getPos() + tuple(self.drift * dt))
        self.card.setScale(0.3 + 0.9 * u)
        grey = 0.55 * (1 - u)
        self.card.setColor(0.5 + 0.5 * (1 - u) ** 4, 0.45 + 0.25 * (1 - u) ** 4, 0.4, grey)
        return True


class Beam:
    """The laser beam from the ship's prow to whatever it hits."""

    def __init__(self, parent, templates):
        self.node = templates.beam.copyTo(parent)
        self.impact = M.glow(parent, (0, 0, 0), 0.9, (0.6, 1.0, 0.9, 1.0))
        self.node.hide()
        self.impact.hide()
        self.t = 0.0

    def show(self, x, y0, y1, hit, dt):
        self.t += dt
        flicker = 0.85 + 0.15 * math.sin(self.t * 60)
        self.node.show()
        self.node.setPos(x, y0, 0.05)
        self.node.setScale(flicker, max(0.01, y1 - y0), flicker)
        if hit:
            self.impact.show()
            self.impact.setPos(x, y1, 0.1)
            self.impact.setScale(0.7 + 0.4 * math.sin(self.t * 45))
        else:
            self.impact.hide()

    def hide(self):
        self.node.hide()
        self.impact.hide()


class ScreenFlash:
    """Transparent full-area pulse over the game view: blood red on hits, white for nukes."""

    def __init__(self, render2d):
        cm = CardMaker("flash")
        cm.setFrame(-1, 1, -1, 1)
        self.card = render2d.attachNewNode(cm.generate())
        self.card.setTransparency(TransparencyAttrib.MAlpha)
        self.card.setBin("fixed", 0)
        self.color = (0.7, 0.0, 0.02)
        self.alpha = 0.0
        self.card.setColor(*self.color, 0)

    def fit(self, bottom):
        """Cover the game area only (render2d y from bottom to 1)."""
        self.card.setPos(0, 0, (1 + bottom) / 2)
        self.card.setScale(1, 1, (1 - bottom) / 2)

    def trigger(self, strength=0.55, color=(0.7, 0.0, 0.02)):
        if strength >= self.alpha:
            self.color = color
        self.alpha = max(self.alpha, strength)

    def update(self, dt):
        self.alpha = max(0.0, self.alpha - dt * 1.4)
        self.card.setColor(*self.color, self.alpha)
