"""Level 5 - Patrol: a few asteroids and waves of Catlien raiders that stay on screen, roam in all four
directions and attack with disruptor shots, thrown space mice and belly rolls that drag your ship
towards them. When a raider is destroyed and its wave is gone, the next wave arrives. Destroy them
all to continue."""
from ..entities.raider import raider_spec
from .base import Level


class Patrol(Level):
    number = 5
    key = "level_05"
    unlocked = ("laser", "beam", "nuke", "shield")
    nukes = 3
    banner = "Catlien raiders incoming - destroy them all"
    progress_label = "RAIDERS"

    def start(self):
        super().start()
        self.waves = list(self.data["raider_waves"])
        self.total = sum(self.waves)
        self.spec = raider_spec(self.data, self.world.u)
        self.killed = 0
        self._next_wave()
        self.wanted, self.recount = 1, 0.0

    def _next_wave(self):
        w = self.world
        n = self.waves.pop(0)
        for i in range(n):
            x = (-0.45 + 0.9 * i / max(1, n - 1)) * w.half_width if n > 1 else 0.0
            w.spawn_raider(x, w.top_y + 4 + i * 2, self.spec)
        if self.killed:
            w.emit(("wave",))

    @property
    def remaining(self):
        return len(self.world.raiders) + sum(self.waves)

    @property
    def title(self):
        return f"LEVEL {self.number} · {self.name.upper()} · RAIDERS LEFT {self.remaining}"

    @property
    def progress(self):
        return 1.0 - self.remaining / self.total

    @property
    def complete(self):
        return self.remaining == 0

    def update(self, dt, ctl):
        events = super().update(dt, ctl)
        self.killed += sum(1 for ev in events if ev[0] == "kill" and ev[1].kind == "raider")
        if self.waves and not self.world.raiders:
            self._next_wave()
        return events

    def spawn(self, dt):
        d, w = self.data, self.world
        self.recount -= dt
        if self.recount <= 0:
            lo, hi = d["asteroid_count"]
            self.wanted = int(w.rng.integers(lo, hi + 1))
            self.recount = 7.0
        self.keep_rocks(self.wanted)
