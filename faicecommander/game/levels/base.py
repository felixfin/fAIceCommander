"""Shared level logic: timing/progress towards the next star, scoring, win/lose checks.

Each level_XX_*.py subclasses Level and only adds what is special about it.
"""


class Level:
    number = 0
    key = ""
    unlocked = ("laser", "shield")
    nukes = 0

    def __init__(self, world, data):
        self.world = world
        self.data = data
        self.name = data["name"]
        self.duration = data.get("duration_s", 90)
        self.damage = data.get("damage_percent", 25)
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
        self.world.update(dt, ctl, self.damage)
        events = self.world.pop_events()
        for kind, payload in events:
            if kind == "kill":
                self.world.score += self.data.get("score_per_kill", 100)
        return events

    def spawn(self, dt):
        raise NotImplementedError
