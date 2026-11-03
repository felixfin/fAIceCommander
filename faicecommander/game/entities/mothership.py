"""The Mother's dreadnought: holds the top of the screen, three damage zones, regenerates.
The level (level_07) drives her phases: faster sideways movement, dives towards you, rage glow."""
import math
import threading

from ...render import models as M

# half widths of the hull along its length (model units at width 14, y towards the player is negative)
HULL = [(-5.0, 0.12), (-4.3, 0.9), (-2.8, 2.4), (-0.8, 4.6), (1.5, 6.6), (3.6, 7.0), (5.0, 5.0)]
ZONES = (0.30, 0.15, 0.10)  # outer / inner / centre share of the width per side
BASE_SHADE = 0.55


class MothershipModel:
    """Built in a background thread at startup: the model has ~1000 parts and takes a few seconds."""

    def __init__(self):
        self.model = None
        self.thread = threading.Thread(target=self._build, name="mothership-builder", daemon=True)
        self.thread.start()

    def _build(self):
        def build(root):
            M.build_mothership(root).flattenStrong()
        self.model = M.cached("mothership", build).getChild(0)

    def get(self):
        self.thread.join()
        return self.model


def half_width_at(y):
    """Hull half width (model units) at local y; 0 outside the hull."""
    if y < HULL[0][0] or y > HULL[-1][0]:
        return 0.0
    for (y0, w0), (y1, w1) in zip(HULL, HULL[1:]):
        if y0 <= y <= y1:
            return w0 + (w1 - w0) * (y - y0) / (y1 - y0)
    return 0.0


class Mothership:
    kind = "mother"

    def __init__(self, parent, model, x, y, width, speed, rng, data):
        self.node = model.copyTo(parent)
        self.k = width / 14.0
        self.node.setScale(self.k)
        self.x, self.y, self.width = x, y, width
        self.speed, self.rng = speed, rng
        self.health = 100.0
        self.alive = True
        self.goal_x = x
        self.regen = data["regen_per_s"]
        self.table = {w: list(data[w]) for w in ("laser", "beam", "nuke")}
        self.vulnerable = 0.0          # seconds of +50 % damage left
        self.bonus = data["vulnerable_bonus"]
        self.flash = 0.0
        self.speed_mult = 1.0
        self.rage = 0.0                # 0..1: red glow in her last phase
        self.t = 0.0
        self.node.setPos(x, y, 0)

    def zone(self, x):
        """1 (outer), 2 (inner) or 3 (centre) for a hit at world x; None beside the ship."""
        u = abs(x - self.x) / (self.width / 2)
        if u > 1:
            return None
        outer, inner, _ = ZONES
        if u > 1 - outer * 2:
            return 1
        if u > 1 - (outer + inner) * 2:
            return 2
        return 3

    def contains(self, x, y):
        return abs(x - self.x) <= half_width_at((y - self.y) / self.k) * self.k

    def front_y(self, x):
        """Lowest y of the hull at world x (where a beam from below hits it), None if x misses."""
        dx = abs(x - self.x) / self.k
        for i in range(201):
            y = HULL[0][0] + (HULL[-1][0] - HULL[0][0]) * i / 200
            if half_width_at(y) >= dx:
                return self.y + y * self.k
        return None

    def hurt(self, weapon, x, amount=1.0):
        """Damage by zone (amount: 1 per laser hit / nuke, dt for the beam). Returns True when destroyed."""
        z = self.zone(x)
        if z is None:
            return False
        dmg = self.table[weapon][z - 1] * amount * (1 + self.bonus if self.vulnerable > 0 else 1.0)
        self.health = max(0.0, self.health - dmg)
        self.flash = 1.0
        return self.health <= 0

    def update(self, dt, x_limit):
        self.t += dt
        speed = self.speed * self.speed_mult
        if abs(self.goal_x - self.x) < 0.5:
            self.goal_x = self.rng.uniform(-x_limit, x_limit)
        step = max(-speed * dt, min(speed * dt, self.goal_x - self.x))
        self.x += step
        self.node.setPos(self.x, self.y, 0)
        self.node.setR(-step / max(dt, 1e-6) / self.speed * 3)
        self.vulnerable = max(0.0, self.vulnerable - dt)
        if self.health > 0:
            self.health = min(100.0, self.health + self.regen * dt)
        self.flash = max(0.0, self.flash - dt * 4)
        glow = self.flash * 0.6 + (0.35 if self.vulnerable > 0 else 0.0)
        rage = self.rage * (0.5 + 0.5 * math.sin(self.t * 5.0))
        b = BASE_SHADE  # seen from above the hull catches the key light; keep it dark and menacing
        self.node.setColorScale(b * (1 + glow + rage * 0.9), b * (1 + glow * 0.3),
                                b * (1 + glow * (0.8 if self.vulnerable > 0 else 0.1)), 1)

    def remove(self):
        self.alive = False
        self.node.removeNode()
