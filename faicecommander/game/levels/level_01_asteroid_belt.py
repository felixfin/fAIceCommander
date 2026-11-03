"""Level 1 - Asteroid Belt: a steady field of category 1 asteroids (3 on easy), one hit each."""
from .base import Level


class AsteroidBelt(Level):
    number = 1
    key = "level_01"

    def spawn(self, dt):
        self.keep_rocks(self.data["asteroid_count"])
