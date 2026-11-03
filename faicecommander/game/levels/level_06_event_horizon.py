"""Level 6 - Event Horizon: an asteroid field plus black holes of different sizes. The bigger the
hole, the stronger its pull - and every horizon slowly swells and shrinks. The pull drags the ship
sideways; steer against it. Touching the event horizon means being absorbed: game over."""
from .base import Level


class EventHorizon(Level):
    number = 6
    key = "level_06"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "Gravity anomalies detected - steer against the pull"

    def spawn(self, dt):
        d, w = self.data, self.world
        self.keep_rocks(d["asteroid_count"])
        if (len(w.holes) < d["max_holes"] and self.elapsed > d["hole_first_s"]
                and w.rng.random() < d["hole_chance_per_s"] * dt):
            x = w.rng.uniform(-w.half_width * 0.8, w.half_width * 0.8)
            if any(abs(h.x - x) < 6 and h.y > w.top_y - 6 for h in w.holes):
                return  # keep a new hole apart from one that has just appeared
            w.spawn_hole(x, w.top_y + 4, w.u(w.rng.uniform(*d["hole_speed_px"])),
                         w.u(w.rng.uniform(*d["hole_radius_px"])), d["hole_pull"], breathe=d["hole_breathe"])
            w.emit(("hole_spawn",))
