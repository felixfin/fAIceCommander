"""Endless mode (unlocked by defeating the Mother): "The swarm is in chaos. Clean up what's left."

Asteroids all the time; every 30 s a new phase adds brains, raiders or black holes; hypno pulses
now and then. Difficulty rises steadily; one extra nuke every minute."""
from ..hypno import HypnoCycle, Sonar
from .base import Level

PHASES = ("asteroids", "brains", "raiders", "holes")


class Endless(Level):
    number = 0
    key = "endless"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "The swarm is in chaos. Clean up what's left."
    progress_label = "NEXT PHASE"
    endless = True

    def __init__(self, world, data, levels):
        super().__init__(world, data)
        self.lv = levels

    def start(self):
        super().start()
        w = self.world
        d2 = self.lv["level_02"]
        w.split = {"max": d2["fragments_max"], "size_px": d2["small_size_px"], "speed_px": d2["fragment_speed_px"],
                   "damage": d2["damage_percent"], "score": d2["score_per_kill"]}
        d3 = self.lv["level_03"]
        self.hypno = HypnoCycle(w.rng, d3["pulse_warning_s"], d3["pulse_duration_s"], 45.0, (35, 50),
                                d3["eyes_grace_s"])
        self.sonar = Sonar()
        self.brain_t = 0.0
        self.next_nuke = 60.0

    @property
    def difficulty(self):
        return self.data["start_difficulty"] + self.data["difficulty_per_min"] * self.elapsed / 60

    @property
    def phase(self):
        return PHASES[int(self.elapsed // 30) % len(PHASES)]

    @property
    def title(self):
        m, s = divmod(int(self.elapsed), 60)
        return f"ENDLESS · {m:02d}:{s:02d} · DIFFICULTY {self.difficulty:.1f}"

    @property
    def progress(self):
        return (self.elapsed % 30) / 30

    @property
    def complete(self):
        return False

    def update(self, dt, ctl):
        hyp = self.hypno.update(dt, ctl.eyes_closed)
        self.world.ship.frozen = self.hypno.frozen
        events = super().update(dt, ctl) + hyp
        if self.elapsed >= self.next_nuke:
            self.next_nuke += 60.0
            self.world.weapons.nukes = min(5, self.world.weapons.nukes + 1)
        if self.hypno.active:
            ping = self.sonar.update(dt, self.world.ship, self.world.asteroids + self.world.shots + self.world.brains)
            if ping:
                events.append(ping)
        return events

    def spawn(self, dt):
        w, lv, diff = self.world, self.lv, self.difficulty
        d1, d2 = lv["level_01"], lv["level_02"]
        speed = [v * (0.8 + 0.2 * diff) for v in d1["asteroid_speed_px"]]
        while w.count(1) < min(8, int(1 + diff * 1.5)):
            w.spawn_asteroid(1, d1["asteroid_size_px"], speed, d1["asteroid_spread_deg"], d1["damage_percent"],
                             d1["score_per_kill"])
        while w.count(2) < (0 if diff < 1.4 else 1 if diff < 3 else 2):
            w.spawn_asteroid(2, d2["large_size_px"], speed, 30, d2["large_damage_percent"], d2["score_per_large"])
        phase = self.phase
        if phase == "brains":
            d4 = lv["level_04"]
            self.brain_t += dt * d4["brain_spawn_per_s"] * 0.5 * diff
            while self.brain_t >= 1 and len(w.brains) < d4["max_brains"]:
                self.brain_t -= 1
                x = w.rng.uniform(-w.half_width, w.half_width)
                y = w.rng.uniform(w.ship.y + 6, w.top_y - 2)
                lo, hi = d4["brain_life_s"]
                w.spawn_brain(x, y, w.u(d4["brain_size_px"]), w.rng.uniform(lo, hi), d4["damage_percent"],
                              d4["score_per_kill"])
        elif phase == "raiders" and not w.raiders:
            d5 = lv["level_05"]
            for i in range(1 if diff < 2 else 2):
                w.spawn_raider(w.rng.uniform(-w.half_width, w.half_width) * 0.7, w.top_y + 3 + i * 2,
                               w.u(d5["raider_speed_px"]), d5["raider_fire_interval_s"], w.u(d5["raider_shot_speed_px"]),
                               d5["shot_damage_percent"], d5["score_per_raider"])
        elif phase == "holes" and not w.holes and w.rng.random() < 0.25 * dt:
            d6 = lv["level_06"]
            w.spawn_hole(w.rng.uniform(-w.half_width, w.half_width) * 0.8, w.top_y + 4,
                         w.u(w.rng.uniform(*d6["hole_speed_px"])), w.u(d6["hole_radius_px"]), d6["hole_pull"])
