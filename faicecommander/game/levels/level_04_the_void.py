"""Level 4 - The Void: no asteroids, no stars, nothing - only Boltzmann brains forming out of
nothing ahead of the ship. Few at first, more and more as the level goes on (up to max_brains);
each lives a random time (1-6 s on easy) and on medium/hard they drift towards you. Shoot them
and they burst."""
import math

from .base import Level


class TheVoid(Level):
    number = 4
    key = "level_04"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "Nothing out here. Nothing at all."

    def start(self):
        super().start()
        self.spawn_t = 0.0

    def spawn(self, dt):
        d, w = self.data, self.world
        self.spawn_t += dt * self.ramp("brain_spawn_per_s")
        cap = int(round(self.ramp("max_brains")))
        while self.spawn_t >= 1.0:
            self.spawn_t -= 1.0
            if len(w.brains) >= cap:
                continue
            pos = self._free_spot()
            if pos:
                lo, hi = d["brain_life_s"]
                b = w.spawn_brain(pos[0], pos[1], w.u(d["brain_size_px"]), w.rng.uniform(lo, hi),
                                  d["damage_percent"], d["score_per_kill"])
                b.seek = w.u(d["brain_seek_px"]) * w.rng.uniform(0.6, 1.3)
                w.emit(("brain_spawn",))

    def _free_spot(self):
        """Somewhere on screen ahead of the ship, never on the ship and not inside another brain."""
        w = self.world
        keepout = w.u(self.data["brain_keepout_px"])
        for _ in range(12):
            x = w.rng.uniform(-w.half_width, w.half_width)
            y = w.rng.uniform(w.ship.y + 2.0, w.top_y - 2.0)
            if math.hypot(x - w.ship.x, y - w.ship.y) < keepout:
                continue
            if all(math.hypot(x - b.x, y - b.y) > 2.2 for b in w.brains):
                return x, y
        return None
