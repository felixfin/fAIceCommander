"""Level 5 - Patrol: one to three asteroids and two Catlien raiders that stay on screen, roam in
all four directions and shoot at you (10 % per hit). Destroy both raiders to continue."""
from .base import Level


class Patrol(Level):
    number = 5
    key = "level_05"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "Catlien raiders incoming - destroy both"

    def start(self):
        super().start()
        d, w = self.data, self.world
        self.total = d["raiders"]
        for i in range(self.total):
            x = (-0.45 + 0.9 * i / max(1, self.total - 1)) * w.half_width
            w.spawn_raider(x, w.top_y + 4 + i * 2, w.u(d["raider_speed_px"]), d["raider_fire_interval_s"],
                           w.u(d["raider_shot_speed_px"]), d["shot_damage_percent"], d["score_per_raider"])
        self.wanted, self.recount = 1, 0.0

    @property
    def remaining(self):
        return len(self.world.raiders)

    @property
    def title(self):
        return f"LEVEL {self.number} · {self.name.upper()} · RAIDERS LEFT {self.remaining}"

    @property
    def progress(self):
        return 1.0 - self.remaining / self.total

    @property
    def complete(self):
        return self.remaining == 0

    def spawn(self, dt):
        d, w = self.data, self.world
        self.recount -= dt
        if self.recount <= 0:
            lo, hi = d["asteroid_count"]
            self.wanted = int(w.rng.integers(lo, hi + 1))
            self.recount = 7.0
        while w.count(1) < self.wanted:
            w.spawn_asteroid(1, d["asteroid_size_px"], d["asteroid_speed_px"], d["asteroid_spread_deg"],
                             d["damage_percent"], d["score_per_kill"])
