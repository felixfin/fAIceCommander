"""Fireworks for the outro: rockets with sparkling trails that burst into shells of coloured sparks
(peony, ring and willow), falling under gravity with drag, plus a flash at each burst."""
import math

import numpy as np

from ..render import models as M

PALETTE = [(1.0, 0.3, 0.25), (0.35, 1.0, 0.5), (0.4, 0.6, 1.0), (1.0, 0.85, 0.3), (1.0, 0.4, 0.9), (0.4, 1.0, 1.0)]


class Fireworks:
    def __init__(self, app, root, launch_area, apex=(9, 14), rate=1.6, seed=1, gravity=4.0, sound=True, spark=0.22):
        self.app, self.root = app, root
        self.rng = np.random.default_rng(seed)
        self.area = launch_area            # ((x0, x1), (y0, y1), z)
        self.apex, self.rate, self.g, self.sound, self.spark = apex, rate, gravity, sound, spark
        self.rockets, self.sparks, self.flashes = [], [], []
        self.next = 0.2

    def launch(self):
        rng = self.rng
        (x0, x1), (y0, y1), z = self.area
        p = np.array([rng.uniform(x0, x1), rng.uniform(y0, y1), z], float)
        height = rng.uniform(*self.apex)
        v = np.array([rng.uniform(-1.5, 1.5), rng.uniform(-0.5, 0.5), math.sqrt(2 * self.g * height)])
        head = M.glow(self.root, tuple(p), 0.35, (1.0, 0.85, 0.6, 1.0))
        self.rockets.append([p, v, head, 0.0])
        if self.sound:
            self.app.audio.sfx.play("fw_launch", 0.35, rate=rng.uniform(0.85, 1.15))

    def burst(self, p):
        rng = self.rng
        kind = rng.choice(["peony", "ring", "willow"], p=[0.55, 0.2, 0.25])
        col = PALETTE[int(rng.integers(len(PALETTE)))]
        col2 = PALETTE[int(rng.integers(len(PALETTE)))]
        n = 70 if kind != "ring" else 50
        speed = rng.uniform(5.5, 8.0)
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        for k in range(n):
            if kind == "ring":
                a = 2 * math.pi * k / n
                u = np.cross(axis, (0, 0, 1.0))
                u /= max(np.linalg.norm(u), 1e-6)
                w = np.cross(axis, u)
                d = u * math.cos(a) + w * math.sin(a)
            else:
                d = rng.normal(size=3)
                d /= np.linalg.norm(d)
            v = d * speed * rng.uniform(0.85, 1.05)
            c = col if k % 3 else col2
            life = rng.uniform(1.6, 2.4) * (1.6 if kind == "willow" else 1.0)
            node = M.glow(self.root, tuple(p), self.spark, (*c, 1.0))
            self.sparks.append([p.copy(), v, node, 0.0, life, kind == "willow"])
        flash = M.glow(self.root, tuple(p), 6.0, (*col, 0.8))
        self.flashes.append([flash, 0.0])
        if self.sound:
            self.app.audio.sfx.play("fw_burst", 0.55, rate=rng.uniform(0.85, 1.1))

    def update(self, dt):
        self.next -= dt
        if self.next <= 0:
            self.next = self.rng.exponential(1 / self.rate)
            self.launch()
        alive = []
        for r in self.rockets:
            p, v, head, t = r
            v[2] -= self.g * dt
            p += v * dt
            r[3] = t + dt
            head.setPos(*p)
            if v[2] <= 0.5:
                head.removeNode()
                self.burst(p)
            else:
                if int(r[3] * 30) % 2 == 0:  # sparkling trail
                    self.sparks.append([p.copy(), self.rng.normal(0, 0.3, 3), M.glow(self.root, tuple(p), 0.12,
                                        (1.0, 0.7, 0.3, 0.8)), 0.0, 0.5, False])
                alive.append(r)
        self.rockets = alive
        alive = []
        for s in self.sparks:
            p, v, node, t, life, willow = s
            t += dt
            s[3] = t
            if t >= life:
                node.removeNode()
                continue
            drag = 2.2 if willow else 1.4
            v *= math.exp(-drag * dt)
            v[2] -= self.g * dt * (0.6 if willow else 0.35)
            p += v * dt
            node.setPos(*p)
            u = t / life
            twinkle = 0.6 + 0.4 * math.sin(t * 40 + p[0] * 9) if u > 0.6 else 1.0
            node.setAlphaScale((1 - u) ** 1.2 * twinkle)
            node.setScale(self.spark * (1 - 0.5 * u))
            alive.append(s)
        self.sparks = alive
        alive = []
        for f in self.flashes:
            f[1] += dt
            if f[1] > 0.5:
                f[0].removeNode()
            else:
                f[0].setAlphaScale(1 - f[1] / 0.5)
                alive.append(f)
        self.flashes = alive
