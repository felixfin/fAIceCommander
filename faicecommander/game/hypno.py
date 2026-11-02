"""Hypno light pulses and the sonar that lets you fly blind (levels 3 and 7)."""
import math

CALM, WARNING, PULSE = "calm", "warning", "pulse"


class HypnoCycle:
    """calm -> warning (announced) -> pulse (eyes must stay closed) -> calm.

    Keeping an eye open after the grace time freezes the ship for the rest of the pulse.
    """

    def __init__(self, rng, warning_s, duration_s, first_s, interval_s, grace_s):
        self.rng = rng
        self.warning_s, self.duration_s, self.interval_s, self.grace_s = warning_s, duration_s, interval_s, grace_s
        self.phase, self.timer = CALM, first_s
        self.length = 0.0      # duration of the current pulse
        self.t_in = 0.0        # time since the current pulse started
        self.frozen = False
        self.since_end = 99.0

    @property
    def active(self):
        return self.phase == PULSE

    @property
    def remaining(self):
        return max(0.0, self.timer)

    def _pick(self, value):
        return self.rng.uniform(*value) if isinstance(value, (list, tuple)) else value

    def trigger(self):
        """Start a warning now (level 7: the mothership decides when)."""
        if self.phase == CALM:
            self.phase, self.timer = WARNING, self.warning_s
            return [("hypno_warning",)]
        return []

    def update(self, dt, eyes_closed):
        events = []
        self.timer -= dt
        self.since_end += dt
        if self.phase == CALM:
            if self.interval_s is not None and self.timer <= 0:
                events += self.trigger()
        elif self.phase == WARNING:
            if self.timer <= 0:
                self.phase = PULSE
                self.length = self.timer = self._pick(self.duration_s)
                self.t_in, self.frozen = 0.0, False
                events.append(("hypno_start",))
        elif self.phase == PULSE:
            self.t_in += dt
            if not eyes_closed and self.t_in > self.grace_s and not self.frozen:
                self.frozen = True
                events.append(("frozen",))
            if self.timer <= 0:
                events.append(("hypno_end", not self.frozen))
                self.phase, self.frozen, self.since_end = CALM, False, 0.0
                self.timer = self._pick(self.interval_s) if self.interval_s is not None else 0.0
        return events

    def overlay_alpha(self, t):
        """How strongly the hypno light shows (no fast strobing: at most ~1.5 Hz modulation)."""
        if self.phase == WARNING:
            ramp = 1 - self.timer / self.warning_s
            return 0.12 + 0.25 * ramp * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 1.5))
        if self.phase == PULSE:
            return 0.7 + 0.12 * math.sin(t * 2 * math.pi * 0.8)
        return max(0.0, 0.7 * (1 - self.since_end / 0.6))


class Sonar:
    """Beeps for objects ahead of the ship: faster when closer, higher when on a collision course,
    panned to the side the object is on."""

    PANS = ((-2.2, "sonar_l2"), (-0.8, "sonar_l1"), (0.8, "sonar_c"), (2.2, "sonar_r1"), (math.inf, "sonar_r2"))

    def __init__(self, reach=26.0, width=4.0):
        self.reach, self.width = reach, width
        self.t = 0.0

    def update(self, dt, ship, objects):
        self.t += dt
        ahead = [o for o in objects if getattr(o, "alive", True) and 0 < o.y - ship.y < self.reach
                 and abs(o.x - ship.x) < self.width + o.radius]
        if not ahead:
            interval, name, rate = 1.4, "sonar_c", 0.8  # idle ping: the sonar is listening
        else:
            o = min(ahead, key=lambda o: math.hypot(o.x - ship.x, o.y - ship.y))
            d = math.hypot(o.x - ship.x, o.y - ship.y)
            lateral = o.x - ship.x
            interval = min(1.2, max(0.12, 0.12 + d * 0.045))
            rate = 1.5 if abs(lateral) < o.radius + ship.radius + 0.3 else 1.15
            name = next(n for limit, n in self.PANS if lateral < limit)
        if self.t >= interval:
            self.t = 0.0
            return ("sonar", name, rate)
        return None
