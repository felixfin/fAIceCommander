"""Catlien raiders: stay on screen, roam in all four directions and shoot at the ship with lead."""
import math

import numpy as np
from panda3d.core import NodePath

from ...render import models as M


class RaiderTemplate:
    SCALE = 0.75

    def __init__(self):
        self.store = NodePath("raider-template")
        self.model = M.build_fighter(self.store)
        self.model.setScale(self.SCALE)
        self.shot = NodePath("enemy-shot")
        V, F = M.icosphere(1)
        M.part(self.shot, V * np.array([0.09, 0.3, 0.09]), F, (1.0, 0.3, 0.12), unlit=True)
        M.glow(self.shot, (0, 0, 0), 0.6, (1.0, 0.2, 0.05, 0.9))


class EnemyShot:
    radius = 0.16

    def __init__(self, parent, template, x, y, vx, vy, damage):
        self.node = template.shot.copyTo(parent)
        self.x, self.y, self.vx, self.vy, self.damage = x, y, vx, vy, damage
        self.alive = True
        self.node.setH(math.degrees(math.atan2(-vx, vy)))
        self.node.setPos(x, y, 0.1)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.node.setPos(self.x, self.y, 0.1)

    def remove(self):
        self.alive = False
        self.node.removeNode()


class Raider:
    kind = "raider"
    category = "raider"
    radius = 1.25

    def __init__(self, parent, template, rng, x, y, speed, fire_interval, shot_speed, shot_damage, resist, score):
        self.node = template.store.copyTo(parent)
        self.model = self.node.getChild(0)
        self.rng = rng
        self.x, self.y = x, y
        self.vx, self.vy = 0.0, 0.0
        self.speed, self.fire_interval = speed, fire_interval
        self.shot_speed, self.shot_damage = shot_speed, shot_damage
        self.resist, self.score = resist, score
        self.health = 1.0
        self.alive = True
        self.beam_heat = 0.0
        self.goal = (x, y)
        self.retarget = 0.0
        self.cooldown = rng.uniform(1.5, 2.5)  # give the player a moment when they arrive
        self.t = 0.0

    def hurt(self, weapon, amount=1.0):
        self.health -= amount / self.resist[weapon]
        self.beam_heat = max(self.beam_heat, 0.6)
        return self.health <= 1e-6

    def update(self, dt, ship, bounds, others, fire):
        """bounds: (x_min, x_max, y_min, y_max) of the area the raider roams in."""
        self.t += dt
        x0, x1, y0, y1 = bounds
        self.retarget -= dt
        if self.retarget <= 0 or math.hypot(self.goal[0] - self.x, self.goal[1] - self.y) < 1.0:
            self.goal = (self.rng.uniform(x0, x1), self.rng.uniform(y0, y1))
            self.retarget = self.rng.uniform(1.2, 2.6)
        ax, ay = self.goal[0] - self.x, self.goal[1] - self.y
        for o in others:  # keep apart from the other raiders
            if o is not self and o.alive:
                dx, dy = self.x - o.x, self.y - o.y
                d = math.hypot(dx, dy)
                if 1e-3 < d < 4.5:
                    ax += dx / d * (4.5 - d) * 3
                    ay += dy / d * (4.5 - d) * 3
        n = math.hypot(ax, ay)
        if n > 1e-6:
            tvx, tvy = ax / n * self.speed, ay / n * self.speed
            k = min(1.0, dt * 2.5)
            self.vx += (tvx - self.vx) * k
            self.vy += (tvy - self.vy) * k
        self.x = min(x1, max(x0, self.x + self.vx * dt))
        self.y = min(y1 + 6, max(y0, self.y + self.vy * dt))  # may still be flying in from above
        self.node.setPos(self.x, self.y, 0.15)
        self.model.setHpr(self.vx / self.speed * 8, 0, -self.vx / self.speed * 30)
        self.cooldown -= dt
        if self.cooldown <= 0 and self.y < y1 + 1:
            self.cooldown = self.rng.uniform(*self.fire_interval)
            self._fire(ship, fire)
        self.beam_heat = max(0.0, self.beam_heat - dt * 3)
        heat = self.beam_heat * 0.8 + (1 - self.health) * 0.8
        if heat > 0.01:
            self.node.setColorScale(1 + heat * 1.8, 1 + heat * 0.5, 1, 1)
        else:
            self.node.clearColorScale()

    def _fire(self, ship, fire):
        sx, sy = self.x, self.y - 1.4
        dist = math.hypot(ship.x - sx, ship.y - sy)
        lead = dist / self.shot_speed
        tx = ship.x + ship.vx * lead * self.rng.uniform(0.6, 1.0)  # not perfectly accurate
        dx, dy = tx - sx, ship.y - sy
        n = math.hypot(dx, dy)
        fire(sx, sy, dx / n * self.shot_speed, dy / n * self.shot_speed, self.shot_damage)

    def remove(self):
        self.alive = False
        self.node.removeNode()
