"""Level 7 - The Mother: the boss. Thrust stops; her dreadnought holds the top of the screen and moves
sideways only. Small aimed shots every 4 s, an artificial black hole bomb about every two minutes and
hypno pulses that travel from her ship to yours - close your eyes before the ring reaches you. After a
pulse she is 50 % more vulnerable for 10 s. Her energy regenerates, so hit hard - the centre hurts most."""
import math

from panda3d.core import NodePath

from ...render import models as M
from ..hypno import CALM, HypnoCycle, Sonar
from .base import Level


class TheMother(Level):
    number = 7
    key = "level_07"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "The Mother. End this."
    progress_label = "THE MOTHER"
    ENTER_S = 3.0

    def start(self):
        super().start()
        d, w = self.data, self.world
        w.scroll_mult = 0.0
        self.home_y = w.ship.y + w.u(d["mother_distance_px"])
        self.mother = w.spawn_mother(0.0, self.home_y + 12, w.u(d["mother_width_px"]), w.u(d["mother_speed_px"]), d)
        self.hypno = HypnoCycle(w.rng, 1.0, d["pulse_duration_s"], 0.0, None, d["eyes_grace_s"])
        self.sonar = Sonar(reach=30.0, width=5.0)
        self.ring_speed = w.u(d["ring_speed_px"])
        self.pulse_t, self.shot_t, self.bomb_t = d["pulse_first_s"], 2.5, d["bomb_first_s"]
        self.rings = []
        self.ring_tpl = NodePath("ring-template")
        M.build_hypno_rings(self.ring_tpl, (0, 0, 0), [1.0, 0.9, 0.8], width=0.06)
        self.won_t = None

    @property
    def progress(self):
        return self.mother.health / 100.0 if self.won_t is None else 0.0

    @property
    def note(self):
        m = self.mother
        return f"VULNERABLE {m.vulnerable:.0f} s" if m.vulnerable > 0 else ""

    @property
    def complete(self):
        return self.won_t is not None and self.won_t > 3.0

    def update(self, dt, ctl):
        w, d, m = self.world, self.data, self.mother
        hyp = self.hypno.update(dt, ctl.eyes_closed)
        w.ship.frozen = self.hypno.frozen
        for ev in hyp:
            if ev[0] == "hypno_end":
                m.vulnerable = d["vulnerable_s"]
        events = super().update(dt, ctl) + hyp
        if self.won_t is not None:
            self.won_t += dt
            return events
        if any(ev[0] == "mother_down" for ev in events):
            self.won_t = 0.0
            w.score += d["score_victory"]
            self._clear_rings()
            return events
        if self.elapsed < self.ENTER_S:  # flies in from above
            m.y = self.home_y + 12 * (1 - self.elapsed / self.ENTER_S) ** 2
            return events
        m.y = self.home_y
        self._attack(dt, events)
        self._update_rings(dt)
        if self.hypno.active:
            ping = self.sonar.update(dt, w.ship, w.shots)
            if ping:
                events.append(ping)
        return events

    def _attack(self, dt, events):
        w, d, m, ship = self.world, self.data, self.mother, self.world.ship
        nose = (m.x, m.front_y(m.x) or m.y)
        self.shot_t -= dt
        if self.shot_t <= 0:
            self.shot_t = d["shot_interval_s"]
            speed = w.u(d["shot_speed_px"])
            lead = math.hypot(ship.x - nose[0], ship.y - nose[1]) / speed
            dx, dy = ship.x + ship.vx * lead * 0.7 - nose[0], ship.y - nose[1]
            n = math.hypot(dx, dy)
            w.fire_enemy(nose[0], nose[1], dx / n * speed, dy / n * speed, d["shot_damage_percent"])
        calm = self.hypno.phase == CALM
        if calm:  # during a pulse she only fires small shots
            self.bomb_t -= dt
            if self.bomb_t <= 0:
                self.bomb_t = d["bomb_interval_s"]
                w.fire_bomb(nose[0], nose[1], ship.x, ship.y + 1.0, w.u(d["bomb_speed_px"]), self._form_hole)
            self.pulse_t -= dt
            if self.pulse_t <= 0:
                lo, hi = d["pulse_interval_s"]
                self.pulse_t = w.rng.uniform(lo, hi)
                travel = math.hypot(ship.x - m.x, ship.y - nose[1]) / self.ring_speed
                self.hypno.warning_s = max(1.5, travel)
                events += self.hypno.trigger()
                ring = self.ring_tpl.copyTo(w.root)
                ring.setPos(m.x, nose[1], 0.05)
                self.rings.append([ring, 0.0, travel])

    def _form_hole(self, x, y):
        d, w = self.data, self.world
        w.spawn_hole(x, y, 0.0, w.u(d["hole_radius_px"]), d["hole_pull"], life=d["hole_life_s"],
                     drain=d["hole_drain_per_s"], drain_radius=w.u(d["hole_drain_radius_px"]))
        w.emit(("hole_formed",))

    def _update_rings(self, dt):
        alive = []
        for entry in self.rings:
            ring, t, travel = entry
            t += dt
            entry[1] = t
            r = 0.5 + self.ring_speed * t
            ring.setScale(r)
            ring.setAlphaScale(max(0.0, 1.0 - max(0.0, t - travel) / 1.5))
            if t > travel + 1.5:
                ring.removeNode()
            else:
                alive.append(entry)
        self.rings = alive

    def _clear_rings(self):
        for ring, _, _ in self.rings:
            ring.removeNode()
        self.rings = []

    def spawn(self, dt):
        pass
