"""Shared level logic: timing/progress towards the next star, scoring, win/lose checks.

Each level_XX_*.py subclasses Level and only adds what is special about it.
"""


class Level:
    number = 0
    key = ""
    unlocked = ("laser", "shield")
    nukes = 0
    banner = "Reach the next star"
    hypno = None   # HypnoCycle in levels with hypno pulses
    progress_label = "NEXT STAR"
    note = ""      # extra status line under the progress bar

    def __init__(self, world, data):
        self.world = world
        self.data = data
        self.name = data["name"]
        self.music = data.get("music", "neural_breaks")
        self.duration = data.get("duration_s", 90)
        self.void = data.get("void", False)
        self.elapsed = 0.0

    @property
    def title(self):
        return f"LEVEL {self.number} · {self.name.upper()}"

    @property
    def progress(self):
        return min(1.0, self.elapsed / self.duration)

    @property
    def complete(self):
        return self.elapsed >= self.duration

    def start(self):
        self.elapsed = 0.0
        self.world.reset(self.unlocked, self.nukes)

    def update(self, dt, ctl):
        self.elapsed += dt
        self.world.score += self.data.get("score_per_second", 0) * dt
        self.spawn(dt)
        self.world.update(dt, ctl)
        events = self.world.pop_events()
        for ev in events:
            if ev[0] == "kill":
                self.world.score += ev[1].score
        return events

    def spawn(self, dt):
        raise NotImplementedError

    def ramp(self, key):
        """A [start, end] value from the data, interpolated over the level's progress."""
        lo, hi = self.data[key]
        return lo + (hi - lo) * self.progress

    def keep_rocks(self, count, category=1, size="asteroid_size_px", damage="damage_percent",
                   score="score_per_kill", spread=1.0):
        """Tops the field up to count asteroids of a category (paths bend by asteroid_wobble_px)."""
        d, w = self.data, self.world
        wobble = w.u(d.get("asteroid_wobble_px", 0))
        while w.count(category) < count:
            w.spawn_asteroid(category, d[size], d["asteroid_speed_px"], d["asteroid_spread_deg"] * spread, d[damage],
                             d[score], wobble=wobble)
