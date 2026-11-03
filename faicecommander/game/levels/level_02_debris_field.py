"""Level 2 - Debris Field: category 1 asteroids plus category 2 asteroids (4 + 1 on easy).

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
        d = self.data
        self.keep_rocks(d["large_count"], 2, "large_size_px", "large_damage_percent", "score_per_large", spread=0.6)
        self.keep_rocks(d["small_count"], 1, "small_size_px")
