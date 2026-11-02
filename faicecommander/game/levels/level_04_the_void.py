"""Level 4 - The Void: no asteroids, no stars, nothing - only Boltzmann brains forming out of
nothing ahead of the ship (up to ten at once, 1-3 s each, 5 % damage). Shoot them and they burst."""
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
        self.spawn_t += dt * d["brain_spawn_per_s"]
        while self.spawn_t >= 1.0:
            self.spawn_t -= 1.0
            if len(w.brains) >= d["max_brains"]:
                continue
            pos = self._free_spot()
            if pos:
                lo, hi = d["brain_life_s"]
                w.spawn_brain(pos[0], pos[1], w.u(d["brain_size_px"]), w.rng.uniform(lo, hi),
                              d["damage_percent"], d["score_per_kill"])
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
