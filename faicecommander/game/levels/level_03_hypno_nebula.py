"""Level 3 - Hypno Nebula: a dense asteroid field and short, frequent hypno light pulses.

A pulse is announced 3 s ahead: look hard at the field, then close your eyes and dodge from memory
(and by the sonar, which beeps for objects ahead). No new asteroids appear while your eyes are
closed - except on hard. Eyes open during a pulse = the ship freezes until the pulse is over.
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
        if self.hypno.active and not d["pulse_spawns"]:
            return  # what you saw is what you get
        self.recount -= dt
        if self.recount <= 0:
            lo, hi = d["asteroid_count"]
            self.wanted = int(w.rng.integers(lo, hi + 1))
            self.recount = 8.0
        self.keep_rocks(self.wanted)
