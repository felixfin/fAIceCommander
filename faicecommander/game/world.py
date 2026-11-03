"""The play plane: ship, weapons, targets, enemy fire, black holes and effects (logic in 2D, visuals in 3D)."""
import math

import numpy as np

from ..config import Units
from ..render.effects import Beam, BrainBurst, EffectTemplates, Explosion, Puff
from .entities.asteroid import Asteroid, AsteroidLibrary
from .entities.black_hole import BlackHole, BlackHoleTemplate, HoleBomb
from .entities.brain import Brain, BrainLibrary
from .entities.mothership import Mothership, MothershipModel
from .entities.mouse import MouseTemplate, SpaceMouse
from .entities.projectiles import BoltTemplate, Flak, LaserBolt, Nuke, NukeTemplate
from .entities.raider import EnemyShot, Raider, RaiderTemplate
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
        self.splatter_distance = self.u(cfg["effects.splatter_distance_px"])
        self.nuke_speed = self.u(cfg["weapons.nuke.speed_px"])
        self.nuke_accel = self.u(cfg["weapons.nuke.accel_px"])
        self.nuke_radius = self.u(cfg["weapons.nuke.blast_radius_px"])
        self.nuke_fuse = cfg["weapons.nuke.fuse_s"]
        self.beam_half_width = self.u(cfg["weapons.beam.half_width_px"])
        self.resist = {k: cfg[f"targets.{name}"].dict() for k, name in
                       ((1, "asteroid_1"), (2, "asteroid_2"), ("brain", "brain"), ("raider", "raider"))}
        self.ship = Ship(self.root, cfg, self.u)
        self.weapons = Weapons(cfg, self.u)
        self.rocks = AsteroidLibrary()
        self.brain_lib = BrainLibrary()
        self.raider_tpl = RaiderTemplate()
        self.mouse_tpl = MouseTemplate()
        self.hole_tpl = BlackHoleTemplate()
        self.mother_model = MothershipModel()  # builds in the background
        self.bolt_tpl = BoltTemplate()
        self.nuke_tpl = NukeTemplate()
        self.fx_tpl = EffectTemplates()
        self.beam = Beam(self.root, self.fx_tpl)
        self.top_y, self.bottom_y = 22.0, -14.0
        self.asteroids, self.brains, self.raiders, self.mice = [], [], [], []
        self.bolts, self.nukes, self.shots, self.holes, self.effects = [], [], [], [], []
        self.bombs, self.flak = [], []
        self.mother = None
        self.scroll_mult = 1.0   # 0 while the ship holds position (boss fight)
        self.events = []
        self.score = 0.0
        self.split = None        # set by levels with category 2 asteroids
        self.death_cause = None  # "hull" or "absorbed"
        self.hole_proximity = 0.0
        self._puff_t = 0.0

    @property
    def speed(self):
        """Current forward speed (constant thrust, stopped for the boss)."""
        return self.scroll * self.scroll_mult

    @property
    def targets(self):
        return [t for group in (self.asteroids, self.brains, self.raiders, self.mice) for t in group if t.alive]

    def set_bounds(self, top_y, bottom_y):
        """Visible extent of the play plane along y (from the camera)."""
        self.top_y, self.bottom_y = top_y, bottom_y

    def reset(self, unlocked=("laser", "shield"), nukes=0):
        if self.mother is not None:
            self.mother.remove()
            self.mother = None
        for group in (self.asteroids, self.brains, self.raiders, self.mice, self.bolts, self.nukes, self.shots,
                      self.holes, self.bombs, self.flak):
            for e in group:
                e.remove()
            group.clear()
        for fx in self.effects:
            fx.root.removeNode()
        self.effects.clear()
        self.beam.hide()
        self.ship.reset()
        self.ship.node.show()
        self.weapons.reset(unlocked, nukes)
        self.events.clear()
        self.split = None
        self.death_cause = None
        self.hole_proximity = 0.0
        self.scroll_mult = 1.0

    def emit(self, event):
        self.events.append(event)

    def pop_events(self):
        ev, self.events = self.events, []
        return ev

    # ------------------------------------------------------------ spawning

    def spawn_asteroid(self, category, size_px, speed_px, spread_deg, damage, score, x=None, y=None, vel=None,
                       wobble=0.0):
        r = self.u(self.rng.uniform(*size_px)) / 2
        if x is None:
            x = self.rng.uniform(-self.half_width, self.half_width)
            y = self.top_y + r
        if vel is None:
            speed = self.u(self.rng.uniform(*speed_px))
            ang = math.radians(self.rng.uniform(-spread_deg, spread_deg))
            vel = (speed * math.sin(ang), -speed * math.cos(ang))
        a = Asteroid(self.root, self.rocks, self.rng, x, y, r, vel[0], vel[1], category, self.resist[category],
                     damage, score, wobble)
        self.asteroids.append(a)
        return a

    def spawn_brain(self, x, y, radius, life, damage, score):
        b = Brain(self.root, self.brain_lib, self.rng, x, y, radius, life, self.resist["brain"], damage, score)
        self.brains.append(b)
        return b

    def spawn_raider(self, x, y, spec):
        """spec: see entities.raider.raider_spec()."""
        r = Raider(self.root, self.raider_tpl, self.rng, x, y, spec, self.resist["raider"])
        self.raiders.append(r)
        return r

    def throw_mouse(self, x, y, dx, dy, speed, turn_deg, damage, score):
        self.mice.append(SpaceMouse(self.root, self.mouse_tpl, self.rng, x, y, dx, dy, speed, turn_deg, damage, score))
        self.emit(("mouse_throw",))

    def intercept(self, nuke, x, y, speed):
        """The Mother's point defence: a flak shot that homes in on a nuke and sets it off early."""
        self.flak.append(Flak(self.root, self.raider_tpl, x, y, nuke, speed))
        self.emit(("flak",))

    def spawn_hole(self, x, y, vy, horizon, pull, **kw):
        h = BlackHole(self.root, self.hole_tpl, x, y, vy, horizon, pull, rng=self.rng, **kw)
        self.holes.append(h)
        return h

    def spawn_mother(self, x, y, width, speed, data):
        self.mother = Mothership(self.root, self.mother_model.get(), x, y, width, speed, self.rng, data)
        return self.mother

    def fire_bomb(self, x, y, tx, ty, speed, on_arrival):
        b = HoleBomb(self.root, self.hole_tpl, x, y, tx, ty, speed)
        b.on_arrival = on_arrival
        self.bombs.append(b)
        self.emit(("bomb",))

    def count(self, category):
        return sum(1 for a in self.asteroids if a.alive and a.category == category)

    def fire_laser(self, x, y, speed):
        self.bolts.append(LaserBolt(self.root, self.bolt_tpl, x, y, speed))

    def fire_nuke(self, x, y):
        self.nukes.append(Nuke(self.root, self.nuke_tpl, x, y, self.nuke_speed, self.nuke_accel, self.nuke_fuse))

    def fire_enemy(self, x, y, vx, vy, damage, source="raider", sound=True):
        self.shots.append(EnemyShot(self.root, self.raider_tpl, x, y, vx, vy, damage))
        if sound:
            self.emit(("enemy_shot", source))

    def explode(self, x, y, size):
        d = math.hypot(x - self.ship.x, y - self.ship.y)
        fx = Explosion(self.root, self.fx_tpl, (x, y, 0), size, self.rng, self.ring_speed, d)
        self.effects.append(fx)
        return fx

    def raider_bounds(self):
        return (-self.half_width * 0.9, self.half_width * 0.9, self.ship.y + 6.0, min(self.top_y - 8, self.ship.y + 13))

    # ------------------------------------------------------------ simulation

    GROUPS = ("asteroids", "brains", "raiders", "mice", "bolts", "nukes", "shots", "holes", "bombs", "flak")

    def _prune(self):
        """Drop removed entities (levels may remove some between frames, e.g. when the Mother dies)."""
        for name in self.GROUPS:
            setattr(self, name, [e for e in getattr(self, name) if e.alive])

    def update(self, dt, ctl):
        self._prune()
        ship = self.ship
        drift = sum(h.drift(ship.x, ship.y, ship.max_speed * 2) for h in self.holes if h.alive)
        drift += sum(r.pull(ship.x) for r in self.raiders if r.alive)
        ship.update(dt, ctl.steer, self.half_width, drift)
        self.weapons.update(dt, ctl, ship, self)
        if self.death_cause is None:  # no repairs once the ship is lost
            ship.hull = min(100.0, ship.hull + self.hull_regen * dt)
        for b in live(self.bolts):
            b.update(dt)
            if b.y > self.top_y + 2:
                b.remove()
        for n in live(self.nukes):
            n.update(dt)
        margin = self.half_width + 6
        for a in live(self.asteroids):
            for h in live(self.holes):
                a.vx += h.drift(a.x, a.y, 20.0) * dt * 1.5
            a.update(dt, self.speed)
            if a.y < self.bottom_y - 3 or abs(a.x) > margin:
                a.remove()
        for b in live(self.brains):
            b.update(dt, self.speed, ship.x)
            if b.expired or b.y < self.bottom_y - 2:
                b.remove()
        bounds = self.raider_bounds()
        for r in live(self.raiders):
            r.update(dt, ship, bounds, self.raiders, self)
        for m in live(self.mice):
            m.update(dt, ship, self.speed)
            if m.y < self.bottom_y - 2 or m.y > self.top_y + 6 or abs(m.x) > margin:
                m.remove()
        for f in live(self.flak):
            f.update(dt)
            if f.reached:
                f.remove()
                if f.target.alive:
                    self._detonate(f.target)
                    self.emit(("intercepted",))
            elif not f.target.alive:
                f.remove()
        for s in live(self.shots):
            s.update(dt)
            if s.y < self.bottom_y - 2 or s.y > self.top_y + 3 or abs(s.x) > margin:
                s.remove()
        for b in live(self.bombs):
            b.update(dt)
            if b.arrived:
                b.remove()
                b.on_arrival(b.x, b.y)
        if self.mother is not None:
            self.mother.update(dt, self.half_width * 0.75)
        self._update_holes(dt)
        self._update_beam(dt)
        self._update_nukes(dt)
        self._collide()
        self._prune()
        alive = []
        for fx in self.effects:
            if isinstance(fx, Explosion) and fx.boom_due(ship.x, ship.y):
                self.emit(("boom", fx.size))
            if fx.update(dt):
                alive.append(fx)
        self.effects = alive

    def _update_holes(self, dt):
        ship = self.ship
        self.hole_proximity = 0.0
        for h in live(self.holes):
            h.update(dt, self.speed)
            if h.y < self.bottom_y - 6:
                h.remove()
                continue
            if h.collapsed:
                h.remove()
                self.emit(("hole_collapse",))
                continue
            d = h.distance(ship.x, ship.y)
            self.hole_proximity = max(self.hole_proximity, min(1.0, max(0.0, 1 - (d - h.horizon) / 10)))
            if not h.deadly:
                if d < h.drain_radius:
                    factor = self.shield_factor if ship.shield_on else 1.0
                    ship.hull = max(0.0, ship.hull - h.drain * factor * dt)
                    if ship.hull <= 0 and self.death_cause is None:
                        self.death_cause = "drained"
                continue
            if d < h.horizon + ship.radius * 0.5 and self.death_cause is None:
                self.death_cause = "absorbed"
                ship.hull = 0.0
                self.emit(("absorbed",))
            for a in self.asteroids:
                if a.alive and h.distance(a.x, a.y) < h.horizon:
                    a.remove()  # swallowed without a trace

    def _kill(self, t, cause):
        t.remove()
        self.emit(("kill", t, cause))
        if t.kind == "brain":
            self.effects.append(BrainBurst(self.root, self.fx_tpl, (t.x, t.y, 0.3), 1.0 + t.radius, self.rng))
            if math.hypot(t.x - self.ship.x, t.y - self.ship.y) < self.splatter_distance:
                self.emit(("splatter", (t.x, t.y, 0.3)))
            return
        if t.kind == "raider":
            self.explode(t.x, t.y, 1.8)
            return
        if t.kind == "mouse":
            self.explode(t.x, t.y, 0.5)
            self.emit(("squeak",))
            return
        self.explode(t.x, t.y, 0.6 + t.radius * (1.0 if t.category == 1 else 1.3))
        if t.category == 2 and cause != "nuke" and self.split:
            s = self.split
            self.emit(("split", t))
            for _ in range(int(self.rng.integers(1, s["max"] + 1))):
                ang = self.rng.uniform(0, 2 * math.pi)
                speed = self.u(self.rng.uniform(*s["speed_px"]))
                vel = (t.vx + speed * math.cos(ang), t.vy + speed * math.sin(ang))
                off = t.radius * 0.5
                self.spawn_asteroid(1, s["size_px"], None, 0, s["damage"], s["score"],
                                    x=t.x + off * math.cos(ang), y=t.y + off * math.sin(ang), vel=vel)

    def _update_beam(self, dt):
        if not self.weapons.beam_on:
            self.beam.hide()
            return
        ship = self.ship
        y0 = ship.prow_y
        hits = [t for t in self.targets if t.y > y0 - t.radius and abs(t.x - ship.x) < t.radius + self.beam_half_width]
        target = min(hits, key=lambda t: t.y - t.radius) if hits else None
        y1 = max(y0, target.y - radius_on_axis(target, ship.x)) if target else self.top_y + 4
        m = self.mother
        front = m.front_y(ship.x) if m is not None else None
        if front is not None and front < y1:
            self.beam.show(ship.x, y0, max(y0, front), True, dt)
            if m.hurt("beam", ship.x, dt):
                self._mother_down()
            return
        self.beam.show(ship.x, y0, y1, target is not None, dt)
        if target is not None:
            target.beam_heat = 1.0
            if target.hurt("beam", dt):
                self._kill(target, "beam")

    def _update_nukes(self, dt):
        self._puff_t += dt
        for n in self.nukes:
            if not n.alive:  # set off by flak this frame
                continue
            if self._puff_t > 0.025:
                self.effects.append(Puff(self.root, (n.x, n.y - 0.6, 0.1), self.rng))
            hit = any((t.x - n.x) ** 2 + (t.y - n.y) ** 2 < (t.radius + n.radius) ** 2 for t in self.targets)
            hit = hit or (self.mother is not None and self.mother.contains(n.x, n.y + n.radius))
            if hit or n.expired or n.y > self.top_y - 1:
                self._detonate(n)
        if self._puff_t > 0.025:
            self._puff_t = 0.0

    def _detonate(self, n):
        n.remove()
        self.explode(n.x, n.y, 3.0)
        self.emit(("nuke_boom",))
        for t in self.targets:
            if math.hypot(t.x - n.x, t.y - n.y) < self.nuke_radius + t.radius and t.hurt("nuke"):
                self._kill(t, "nuke")
        m = self.mother
        if m is not None and (m.contains(n.x, n.y + self.nuke_radius) or m.contains(n.x, n.y)):
            if m.hurt("nuke", n.x):
                self._mother_down()
        for s in live(self.shots):
            if math.hypot(s.x - n.x, s.y - n.y) < self.nuke_radius:
                s.remove()

    def _mother_down(self):
        m = self.mother
        if m is None or not m.alive:
            return
        self.emit(("mother_down", m.x, m.y))
        self.explode(m.x, m.y - 1.5, 3.5)
        m.alive = False

    def _collide(self):
        ship = self.ship
        m = self.mother
        if m is not None and m.alive:
            for b in self.bolts:
                if b.alive and m.contains(b.x, b.y):
                    b.remove()
                    self.emit(("mother_hit", m.zone(b.x)))
                    if m.hurt("laser", b.x):
                        self._mother_down()
        for t in self.targets:
            for b in self.bolts:
                if b.alive and (t.x - b.x) ** 2 + (t.y - b.y) ** 2 < (t.radius + b.radius) ** 2:
                    b.remove()
                    t.beam_heat = 0.6
                    if t.kind == "raider":
                        self.emit(("metal_hit",))
                    if t.hurt("laser"):
                        self._kill(t, "laser")
                        break
            if t.alive and t.kind != "raider" and (t.x - ship.x) ** 2 + (t.y - ship.y) ** 2 < (t.radius + ship.radius) ** 2:
                self._hit_ship(t.damage)
                t.remove()
                if t.kind == "brain":
                    self.effects.append(BrainBurst(self.root, self.fx_tpl, (t.x, t.y, 0.3), 1.0, self.rng))
                    self.emit(("splatter", (t.x, t.y, 0.3)))
                elif t.kind == "mouse":
                    self.explode(t.x, t.y, 0.5)
                    self.emit(("squeak",))
                else:
                    self.explode(t.x, t.y, 0.4 + t.radius * 0.7)
        for s in live(self.shots):
            if (s.x - ship.x) ** 2 + (s.y - ship.y) ** 2 < (s.radius + ship.radius) ** 2:
                s.remove()
                self._hit_ship(s.damage)

    def _hit_ship(self, damage):
        dmg = damage * (self.shield_factor if self.ship.shield_on else 1.0)
        self.ship.hull = max(0.0, self.ship.hull - dmg)
        if self.ship.hull <= 0 and self.death_cause is None:
            self.death_cause = "hull"
        self.emit(("hit", dmg))


def live(group):
    """Entities still alive: something earlier in the frame (a nuke, the Mother's death) may have removed some."""
    return [e for e in group if e.alive]


def radius_on_axis(t, x):
    """Half chord of the target's circle at the beam's x: the beam stops at its surface."""
    dx = min(abs(t.x - x), t.radius)
    return math.sqrt(max(t.radius ** 2 - dx ** 2, 0.0))
