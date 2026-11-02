"""Level 1 - Asteroid Belt: always three category 1 asteroids, one hit each, 25 % damage."""
from .base import Level


class AsteroidBelt(Level):
    number = 1
    key = "level_01"

    def spawn(self, dt):
        d = self.data
        while self.world.count(1) < d["asteroid_count"]:
            self.world.spawn_asteroid(1, d["asteroid_size_px"], d["asteroid_speed_px"], d["asteroid_spread_deg"],
                                      d["damage_percent"], d["score_per_kill"])
