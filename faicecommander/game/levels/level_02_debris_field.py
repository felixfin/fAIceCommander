"""Level 2 - Debris Field: four category 1 asteroids plus one category 2 asteroid.

Category 2 (30-50 px) takes two laser hits, two seconds of beam or one nuke, deals 50 % damage and
breaks into up to three category 1 asteroids when shot (a nuke vaporises it). Beam and nukes unlock here.
"""
from .base import Level


class DebrisField(Level):
    number = 2
    key = "level_02"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "Upgrade received: LASER BEAM and 3 NUKES"

    def start(self):
        super().start()
        d = self.data
        self.world.split = {"max": d["fragments_max"], "size_px": d["small_size_px"],
                            "speed_px": d["fragment_speed_px"], "damage": d["damage_percent"],
                            "score": d["score_per_kill"]}

    def spawn(self, dt):
        d, w = self.data, self.world
        while w.count(2) < d["large_count"]:
            w.spawn_asteroid(2, d["large_size_px"], d["asteroid_speed_px"], d["asteroid_spread_deg"] * 0.6,
                             d["large_damage_percent"], d["score_per_large"])
        while w.count(1) < d["small_count"]:
            w.spawn_asteroid(1, d["small_size_px"], d["asteroid_speed_px"], d["asteroid_spread_deg"],
                             d["damage_percent"], d["score_per_kill"])
