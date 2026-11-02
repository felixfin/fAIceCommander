"""Level 1 - Asteroid Belt: always three category 1 asteroids, one hit each, 25 % damage."""
from .base import Level


class AsteroidBelt(Level):
    number = 1
    key = "level_01"

    def spawn(self, dt):
        d = self.data
        while len(self.world.asteroids) < d["asteroid_count"]:
            self.world.spawn_asteroid(d["asteroid_size_px"], d["asteroid_speed_px"], d["asteroid_spread_deg"])
