"""Level 7 - The Mother: the boss. Thrust stops; her dreadnought holds the top of the screen.

She fights in three phases (health thresholds in phase_at):
1. aimed shots, artificial black hole bombs, hypno pulses that travel from her ship to yours -
   close your eyes before the ring reaches you;
2. faster, fans of shots, swarms of space mice, dives towards you, shoots down some of your nukes;
3. enraged: glowing red, faster still, wide volleys, more mice, more dives (and raider escorts on
   medium/hard).
After a pulse she is 50 % more vulnerable for a few seconds. Her energy regenerates - the centre of
her hull hurts most. She roars when she changes phase and hisses when a nuke hits."""
import math

from panda3d.core import NodePath

from ...render import models as M
from ..entities.raider import raider_spec
from ..hypno import CALM, HypnoCycle, Sonar
from .base import Level

ESCORT = {"raider_speed_px": 230, "raider_fire_interval_s": [1.6, 2.8], "raider_shot_speed_px": 420,
          "shot_damage_percent": 7, "score_per_raider": 500, "raider_toughness": 1.0,
          "mouse_speed_px": 200, "mouse_damage_percent": 10}
DIVE_IN, DIVE_HOLD, DIVE_OUT = 1.1, 1.6, 1.3


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
        self.pulse_t, self.bomb_t = d["pulse_first_s"], d["bomb_first_s"]
        self.shot_t, self.mouse_t, self.dive_t, self.escort_t = 2.5, 0.0, 0.0, 4.0
        self.dive = None          # seconds into the current dive
        self.phase = 0
        self.rings = []
        self.ring_tpl = NodePath("ring-template")
        M.build_hypno_rings(self.ring_tpl, (0, 0, 0), [1.0, 0.9, 0.8], width=0.06)
        self.won_t = None
        self.seen_nukes = set()
        self.escort = raider_spec({**ESCORT, "raider_weapons": None}, w.u)
        self.escort["weapons"] = {"laser": 0.7, "mouse": 0.3}
        self._enter_phase(0)

    # ------------------------------------------------------------ hud

    @property
    def progress(self):
        return self.mother.health / 100.0 if self.won_t is None else 0.0

    @property
    def note(self):
        m = self.mother
        if m.vulnerable > 0:
            return f"VULNERABLE {m.vulnerable:.0f} s"
        return ("", "PHASE 2", "PHASE 3 · ENRAGED")[self.phase]

    @property
    def complete(self):
        return self.won_t is not None and self.won_t > 3.0

    # ------------------------------------------------------------ phases

    def _per_phase(self, key):
        return self.data[key][self.phase]

    def _enter_phase(self, phase):
        self.phase = phase
        m = self.mother
        m.speed_mult = self._per_phase("speed_mult")
        m.rage = 1.0 if phase == 2 else 0.0
        self.mouse_t = self._per_phase("mouse_interval_s") * 0.5
        self.dive_t = self._per_phase("lunge_interval_s") * 0.6
        self.bomb_t = min(self.bomb_t, self._per_phase("bomb_interval_s"))

    def _check_phase(self, events):
        limits = self.data["phase_at"]
        target = sum(1 for limit in limits if self.mother.health <= limit)
        if target > self.phase:
            self._enter_phase(target)
            events.append(("mother_phase", target + 1))

    # ------------------------------------------------------------ frame

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
            for r in w.raiders + w.mice:
                w.explode(r.x, r.y, 1.8 if r.kind == "raider" else 0.5)
                r.remove()
            return events
        if self.elapsed < self.ENTER_S:  # flies in from above
            m.y = self.home_y + 12 * (1 - self.elapsed / self.ENTER_S) ** 2
            return events
        self._check_phase(events)
        self._move(dt, events)
        self._attack(dt, events)
        self._defend()
        self._escorts(dt)
        self._update_rings(dt)
        if self.hypno.active:
            ping = self.sonar.update(dt, w.ship, w.shots + w.mice)
            if ping:
                events.append(ping)
        return events

    def _move(self, dt, events):
        """Dives: she drops towards the ship, holds there firing, and pulls back."""
        m, d = self.mother, self.data
        depth = self.world.u(d["lunge_px"])
        if self.dive is None:
            interval = self._per_phase("lunge_interval_s")
            if interval > 0 and self.hypno.phase == CALM:
                self.dive_t -= dt
                if self.dive_t <= 0:
                    self.dive, self.dive_t = 0.0, interval * self.world.rng.uniform(0.8, 1.2)
                    events.append(("mother_roar",))
            m.y = self.home_y
            return
        self.dive += dt
        t = self.dive
        if t < DIVE_IN:
            k = (1 - math.cos(math.pi * t / DIVE_IN)) / 2
        elif t < DIVE_IN + DIVE_HOLD:
            k = 1.0
        elif t < DIVE_IN + DIVE_HOLD + DIVE_OUT:
            k = (1 + math.cos(math.pi * (t - DIVE_IN - DIVE_HOLD) / DIVE_OUT)) / 2
        else:
            k, self.dive = 0.0, None
        m.y = self.home_y - depth * k

    def _volley(self, n, spread_deg=13.0):
        w, d, m, ship = self.world, self.data, self.mother, self.world.ship
        nose = (m.x, m.front_y(m.x) or m.y)
        speed = w.u(d["shot_speed_px"])
        lead = math.hypot(ship.x - nose[0], ship.y - nose[1]) / speed
        base = math.atan2(ship.y - nose[1], ship.x + ship.vx * lead * 0.7 - nose[0])
        for i in range(n):
            a = base + math.radians(spread_deg * (i - (n - 1) / 2))
            w.fire_enemy(nose[0], nose[1], math.cos(a) * speed, math.sin(a) * speed, d["shot_damage_percent"],
                         "mother", sound=i == 0)

    def _attack(self, dt, events):
        w, d, m, ship = self.world, self.data, self.mother, self.world.ship
        nose = (m.x, m.front_y(m.x) or m.y)
        self.shot_t -= dt
        if self.shot_t <= 0:
            self.shot_t = self._per_phase("shot_interval_s") * (0.6 if self.dive is not None else 1.0)
            self._volley(self._per_phase("fan_shots"))
        interval = self._per_phase("mouse_interval_s")
        if interval > 0:
            self.mouse_t -= dt
            if self.mouse_t <= 0:
                self.mouse_t = interval
                for i in range(d["mouse_count"]):
                    side = (-1, 1)[i % 2]
                    x = m.x + side * m.width * (0.25 + 0.1 * (i // 2))
                    a = math.radians(-90 + side * 25)
                    w.throw_mouse(x, nose[1] + 2.0, math.cos(a), math.sin(a), w.u(d["mouse_speed_px"]),
                                  d["mouse_turn_deg"], d["mouse_damage_percent"], d["score_per_mouse"])
        if self.hypno.phase != CALM:
            return  # during a pulse she only shoots
        self.bomb_t -= dt
        if self.bomb_t <= 0:
            self.bomb_t = self._per_phase("bomb_interval_s")
            w.fire_bomb(nose[0], nose[1], ship.x, ship.y + 1.0, w.u(d["bomb_speed_px"]), self._form_hole)
        self.pulse_t -= dt
        if self.pulse_t <= 0 and self.dive is None:
            lo, hi = d["pulse_interval_s"]
            self.pulse_t = w.rng.uniform(lo, hi) * (0.8 if self.phase == 2 else 1.0)
            travel = math.hypot(ship.x - m.x, ship.y - nose[1]) / self.ring_speed
            self.hypno.warning_s = max(1.5, travel)
            events += self.hypno.trigger()
            events.append(("mother_scream",))
            ring = self.ring_tpl.copyTo(w.root)
            ring.setPos(m.x, nose[1], 0.05)
            self.rings.append([ring, 0.0, travel])

    def _defend(self):
        """Point defence against new nukes (from phase 2 on)."""
        w, m = self.world, self.mother
        chance = self._per_phase("intercept_chance")
        for n in w.nukes:
            if id(n) in self.seen_nukes:
                continue
            self.seen_nukes.add(id(n))
            if chance > 0 and w.rng.random() < chance:
                w.intercept(n, m.x + w.rng.uniform(-2, 2), m.front_y(m.x) or m.y, w.u(700))

    def _escorts(self, dt):
        start = self.data["escort_phase"]
        w = self.world
        if not start or self.phase + 1 < start or w.raiders:
            return
        self.escort_t -= dt  # a short breather after each escort you shoot down
        if self.escort_t <= 0:
            self.escort_t = 6.0
            w.spawn_raider(w.rng.uniform(-0.6, 0.6) * w.half_width, w.top_y + 3, self.escort)

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
