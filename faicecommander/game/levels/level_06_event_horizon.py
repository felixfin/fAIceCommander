"""Level 6 - Event Horizon: like level 1, plus at most one black hole at a time. Its pull drags the
ship sideways - steer against it. Getting too close means being absorbed: game over."""
from .base import Level


class EventHorizon(Level):
    number = 6
    key = "level_06"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "Gravity anomalies detected - steer against the pull"

    def spawn(self, dt):
        d, w = self.data, self.world
        while w.count(1) < d["asteroid_count"]:
            w.spawn_asteroid(1, d["asteroid_size_px"], d["asteroid_speed_px"], d["asteroid_spread_deg"],
                             d["damage_percent"], d["score_per_kill"])
        if not w.holes and self.elapsed > d["hole_first_s"] and w.rng.random() < d["hole_chance_per_s"] * dt:
            x = w.rng.uniform(-w.half_width * 0.8, w.half_width * 0.8)
            w.spawn_hole(x, w.top_y + 4, w.u(w.rng.uniform(*d["hole_speed_px"])), w.u(d["hole_radius_px"]),
                         d["hole_pull"])
            w.emit(("hole_spawn",))
