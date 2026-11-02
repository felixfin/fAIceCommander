"""Level 3 - Hypno Nebula: a thin asteroid field (one or two at a time) and hypno light pulses.

A pulse is announced 3 s ahead and lasts 10 s. Keep your eyes closed the whole time; the sonar
beeps for objects ahead of the ship. Eyes open = the ship freezes until the pulse is over.
"""
from ..hypno import HypnoCycle, Sonar
from .base import Level


class HypnoNebula(Level):
    number = 3
    key = "level_03"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "Hypno pulses ahead: close your eyes when the siren sounds"

    def start(self):
        super().start()
        d = self.data
        self.hypno = HypnoCycle(self.world.rng, d["pulse_warning_s"], d["pulse_duration_s"], d["pulse_first_s"],
                                d["pulse_interval_s"], d["eyes_grace_s"])
        self.sonar = Sonar()
        self.wanted, self.recount = 1, 0.0

    def update(self, dt, ctl):
        hyp = self.hypno.update(dt, ctl.eyes_closed)
        self.world.ship.frozen = self.hypno.frozen
        events = super().update(dt, ctl) + hyp
        for ev in hyp:
            if ev[0] == "hypno_end" and ev[1]:
                self.world.score += self.data["score_per_pulse"]
        if self.hypno.active:
            ping = self.sonar.update(dt, self.world.ship, self.world.asteroids)
            if ping:
                events.append(ping)
        return events

    def spawn(self, dt):
        d, w = self.data, self.world
        self.recount -= dt
        if self.recount <= 0:
            lo, hi = d["asteroid_count"]
            self.wanted = int(w.rng.integers(lo, hi + 1))
            self.recount = 8.0
        while w.count(1) < self.wanted:
            w.spawn_asteroid(1, d["asteroid_size_px"], d["asteroid_speed_px"], d["asteroid_spread_deg"],
                             d["damage_percent"], d["score_per_kill"])
