"""The play plane: ship, weapons, asteroids, collisions and effects (logic in 2D, visuals in 3D)."""
import math

import numpy as np

from ..config import Units
from ..render.effects import Beam, EffectTemplates, Explosion, Puff
from .entities.asteroid import Asteroid, AsteroidLibrary
from .entities.projectiles import BoltTemplate, LaserBolt, Nuke, NukeTemplate
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
        self.ring_speed = self.u(cfg["effects.shockwave_speed_px"])
        self.nuke_speed = self.u(cfg["weapons.nuke.speed_px"])
        self.nuke_accel = self.u(cfg["weapons.nuke.accel_px"])
        self.nuke_radius = self.u(cfg["weapons.nuke.blast_radius_px"])
        self.nuke_fuse = cfg["weapons.nuke.fuse_s"]
        self.beam_half_width = self.u(cfg["weapons.beam.half_width_px"])
        self.targets = {1: cfg["targets.asteroid_1"].dict(), 2: cfg["targets.asteroid_2"].dict()}
        self.ship = Ship(self.root, cfg, self.u)
        self.weapons = Weapons(cfg, self.u)
        self.rocks = AsteroidLibrary()
        self.bolt_tpl = BoltTemplate()
        self.nuke_tpl = NukeTemplate()
        self.fx_tpl = EffectTemplates()
        self.beam = Beam(self.root, self.fx_tpl)
        self.top_y, self.bottom_y = 22.0, -14.0
        self.asteroids, self.bolts, self.nukes, self.effects = [], [], [], []
        self.events = []
        self.score = 0.0
        self.split = None  # set by levels with category 2 asteroids
        self._puff_t = 0.0

    def set_bounds(self, top_y, bottom_y):
        """Visible extent of the play plane along y (from the camera)."""
        self.top_y, self.bottom_y = top_y, bottom_y

    def reset(self, unlocked=("laser", "shield"), nukes=0):
        for group in (self.asteroids, self.bolts, self.nukes):
            for e in group:
                e.remove()
            group.clear()
        for fx in self.effects:
            fx.root.removeNode()
        self.effects.clear()
        self.beam.hide()
        self.ship.reset()
        self.weapons.reset(unlocked, nukes)
        self.events.clear()
        self.split = None

    def emit(self, event):
        self.events.append(event)

    def pop_events(self):
        ev, self.events = self.events, []
        return ev

    # ------------------------------------------------------------ spawning

    def spawn_asteroid(self, category, size_px, speed_px, spread_deg, damage, score, x=None, y=None, vel=None):
        r = self.u(self.rng.uniform(*size_px)) / 2
        if x is None:
            x = self.rng.uniform(-self.half_width, self.half_width)
            y = self.top_y + r
        if vel is None:
            speed = self.u(self.rng.uniform(*speed_px))
            ang = math.radians(self.rng.uniform(-spread_deg, spread_deg))
            vel = (speed * math.sin(ang), -speed * math.cos(ang))
        a = Asteroid(self.root, self.rocks, self.rng, x, y, r, vel[0], vel[1], category, self.targets[category],
                     damage, score)
        self.asteroids.append(a)
        return a

    def count(self, category):
        return sum(1 for a in self.asteroids if a.alive and a.category == category)

    def fire_laser(self, x, y, speed):
        self.bolts.append(LaserBolt(self.root, self.bolt_tpl, x, y, speed))

    def fire_nuke(self, x, y):
        self.nukes.append(Nuke(self.root, self.nuke_tpl, x, y, self.nuke_speed, self.nuke_accel, self.nuke_fuse))

    def explode(self, x, y, size):
        d = math.hypot(x - self.ship.x, y - self.ship.y)
        fx = Explosion(self.root, self.fx_tpl, (x, y, 0), size, self.rng, self.ring_speed, d)
        self.effects.append(fx)
        return fx

    # ------------------------------------------------------------ simulation

    def update(self, dt, ctl):
        ship = self.ship
        ship.update(dt, ctl.steer, self.half_width)
        self.weapons.update(dt, ctl, ship, self)
        ship.hull = min(100.0, ship.hull + self.hull_regen * dt)
        for b in self.bolts:
            b.update(dt)
            if b.y > self.top_y + 2:
                b.remove()
        for n in self.nukes:
            n.update(dt)
        margin = self.half_width + 6
        for a in self.asteroids:
            a.update(dt, self.scroll)
            if a.y < self.bottom_y - 3 or abs(a.x) > margin:
                a.remove()
        self._update_beam(dt)
        self._update_nukes(dt)
        self._collide()
        self.asteroids = [a for a in self.asteroids if a.alive]
        self.bolts = [b for b in self.bolts if b.alive]
        self.nukes = [n for n in self.nukes if n.alive]
        alive = []
        for fx in self.effects:
            if isinstance(fx, Explosion) and fx.boom_due(ship.x, ship.y):
                self.emit(("boom", fx.size))
            if fx.update(dt):
                alive.append(fx)
        self.effects = alive

    def _kill(self, a, cause):
        a.remove()
        self.explode(a.x, a.y, 0.6 + a.radius * (1.0 if a.category == 1 else 1.3))
        self.emit(("kill", a, cause))
        if a.category == 2 and cause != "nuke" and self.split:
            s = self.split
            self.emit(("split", a))
            for _ in range(int(self.rng.integers(1, s["max"] + 1))):
                ang = self.rng.uniform(0, 2 * math.pi)
                speed = self.u(self.rng.uniform(*s["speed_px"]))
                vel = (a.vx + speed * math.cos(ang), a.vy + speed * math.sin(ang))
                off = a.radius * 0.5
                self.spawn_asteroid(1, s["size_px"], None, 0, s["damage"], s["score"],
                                    x=a.x + off * math.cos(ang), y=a.y + off * math.sin(ang), vel=vel)

    def _update_beam(self, dt):
        if not self.weapons.beam_on:
            self.beam.hide()
            return
        ship = self.ship
        y0 = ship.prow_y
        hits = [a for a in self.asteroids if a.alive and a.y > y0 - a.radius
                and abs(a.x - ship.x) < a.radius + self.beam_half_width]
        target = min(hits, key=lambda a: a.y - a.radius) if hits else None
        y1 = max(y0, target.y - a_radius_on_axis(target, ship.x)) if target else self.top_y + 4
        self.beam.show(ship.x, y0, y1, target is not None, dt)
        if target is not None:
            target.beam_heat = 1.0
            if target.hurt("beam", dt):
                self._kill(target, "beam")

    def _update_nukes(self, dt):
        self._puff_t += dt
        for n in self.nukes:
            if self._puff_t > 0.025:
                self.effects.append(Puff(self.root, (n.x, n.y - 0.6, 0.1), self.rng))
            hit = any(a.alive and (a.x - n.x) ** 2 + (a.y - n.y) ** 2 < (a.radius + n.radius) ** 2
                      for a in self.asteroids)
            if hit or n.expired or n.y > self.top_y - 1:
                self._detonate(n)
        if self._puff_t > 0.025:
            self._puff_t = 0.0

    def _detonate(self, n):
        n.remove()
        self.explode(n.x, n.y, 3.0)
        self.emit(("nuke_boom",))
        for a in self.asteroids:
            if a.alive and math.hypot(a.x - n.x, a.y - n.y) < self.nuke_radius + a.radius:
                if a.hurt("nuke"):
                    self._kill(a, "nuke")

    def _collide(self):
        ship = self.ship
        for a in self.asteroids:
            if not a.alive:
                continue
            for b in self.bolts:
                if b.alive and (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.radius + b.radius) ** 2:
                    b.remove()
                    a.beam_heat = 0.6
                    if a.hurt("laser"):
                        self._kill(a, "laser")
                        break
            if a.alive and (a.x - ship.x) ** 2 + (a.y - ship.y) ** 2 < (a.radius + ship.radius) ** 2:
                dmg = a.damage * (self.shield_factor if ship.shield_on else 1.0)
                ship.hull = max(0.0, ship.hull - dmg)
                a.remove()
                self.explode(a.x, a.y, 0.4 + a.radius * 0.7)
                self.emit(("hit", dmg))


def a_radius_on_axis(a, x):
    """Half chord of the asteroid's circle at the beam's x: the beam stops at the rock's surface."""
    dx = min(abs(a.x - x), a.radius)
    return math.sqrt(max(a.radius ** 2 - dx ** 2, 0.0))
