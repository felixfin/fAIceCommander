"""The play plane: ship, projectiles, asteroids, collisions and effects (logic in 2D, visuals in 3D)."""
import math

import numpy as np

from ..config import Units
from ..render.effects import EffectTemplates, Explosion
from .entities.asteroid import Asteroid, AsteroidLibrary
from .entities.projectiles import BoltTemplate, LaserBolt
from .entities.ship import Ship
from .weapons import Weapons


class World:
    def __init__(self, base, cfg):
        self.base, self.cfg = base, cfg
        self.u = Units(cfg)
        self.root = base.render.attachNewNode("world")
        self.rng = np.random.default_rng()
        self.half_width = self.u(cfg["world.field_half_width_px"])
        self.scroll = self.u(cfg["world.scroll_speed_px"])
        self.shield_factor = cfg["ship.shield_damage_factor"]
        self.hull_regen = cfg["ship.hull_regen_per_s"]
        self.ship = Ship(self.root, cfg, self.u)
        self.weapons = Weapons(cfg, self.u)
        self.rocks = AsteroidLibrary()
        self.bolt_tpl = BoltTemplate()
        self.fx_tpl = EffectTemplates()
        self.top_y, self.bottom_y = 22.0, -14.0
        self.asteroids, self.bolts, self.effects = [], [], []
        self.events = []
        self.score = 0.0

    def set_bounds(self, top_y, bottom_y):
        """Visible extent of the play plane along y (from the camera)."""
        self.top_y, self.bottom_y = top_y, bottom_y

    def reset(self, unlocked=("laser", "shield"), nukes=0):
        for group in (self.asteroids, self.bolts):
            for e in group:
                e.remove()
            group.clear()
        for fx in self.effects:
            fx.root.removeNode()
        self.effects.clear()
        self.ship.reset()
        self.weapons.reset(unlocked, nukes)
        self.events.clear()

    # ------------------------------------------------------------ spawning

    def spawn_asteroid(self, size_px, speed_px, spread_deg, category=1, hp=1):
        r = self.u(self.rng.uniform(*size_px)) / 2
        x = self.rng.uniform(-self.half_width, self.half_width)
        speed = self.u(self.rng.uniform(*speed_px))
        ang = math.radians(self.rng.uniform(-spread_deg, spread_deg))
        vx, vy = speed * math.sin(ang), -speed * math.cos(ang)
        a = Asteroid(self.root, self.rocks, self.rng, x, self.top_y + r, r, vx, vy, category, hp)
        self.asteroids.append(a)
        return a

    def fire_laser(self, x, y, speed, damage):
        self.bolts.append(LaserBolt(self.root, self.bolt_tpl, x, y, speed, damage))

    def explode(self, x, y, size):
        self.effects.append(Explosion(self.root, self.fx_tpl, (x, y, 0), size, self.rng))

    # ------------------------------------------------------------ simulation

    def update(self, dt, ctl, damage_percent):
        ship = self.ship
        ship.update(dt, ctl.steer, self.half_width)
        self.weapons.update(dt, ctl, ship, self.fire_laser)
        ship.hull = min(100.0, ship.hull + self.hull_regen * dt)
        for b in self.bolts:
            b.update(dt)
            if b.y > self.top_y + 2:
                b.remove()
        margin = self.half_width + 6
        for a in self.asteroids:
            a.update(dt, self.scroll)
            if a.y < self.bottom_y - 3 or abs(a.x) > margin:
                a.remove()
        self._collide(damage_percent)
        self.asteroids = [a for a in self.asteroids if a.alive]
        self.bolts = [b for b in self.bolts if b.alive]
        self.effects = [fx for fx in self.effects if fx.update(dt)]

    def _collide(self, damage_percent):
        ship = self.ship
        for a in self.asteroids:
            if not a.alive:
                continue
            for b in self.bolts:
                if b.alive and (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.radius + b.radius) ** 2:
                    b.remove()
                    a.hp -= b.damage
                    if a.hp <= 0:
                        self.explode(a.x, a.y, 0.6 + a.radius)
                        self.events.append(("kill", a))
                        a.remove()
                        break
            if a.alive and (a.x - ship.x) ** 2 + (a.y - ship.y) ** 2 < (a.radius + ship.radius) ** 2:
                dmg = damage_percent * (self.shield_factor if ship.shield_on else 1.0)
                ship.hull = max(0.0, ship.hull - dmg)
                self.explode(a.x, a.y, 0.4 + a.radius * 0.7)
                self.events.append(("hit", dmg))
                a.remove()

    def pop_events(self):
        ev, self.events = self.events, []
        return ev
