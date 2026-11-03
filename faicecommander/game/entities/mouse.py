"""Space mice: thrown by Catlien raiders (and the Mother). They home in on the ship, squeak, and can
be shot down with a single laser hit."""
import math

from ...render import models as M


class MouseTemplate:
    def __init__(self):
        self.store = M.cached("mouse", M.build_space_mouse)
        self.model = self.store.getChild(0)


class SpaceMouse:
    kind = "mouse"
    category = "mouse"
    radius = 0.4
    RESIST = {"laser": 1, "beam": 0.15, "nuke": 1}

    def __init__(self, parent, template, rng, x, y, dx, dy, speed, turn_deg, damage, score):
        self.node = template.store.copyTo(parent)
        self.x, self.y = x, y
        self.heading = math.atan2(dy, dx)
        self.speed, self.turn = speed, math.radians(turn_deg)
        self.damage, self.score = damage, score
        self.resist = self.RESIST
        self.health = 1.0
        self.alive = True
        self.beam_heat = 0.0
        self.t = 0.0
        self.spin = rng.uniform(300, 520) * (1 if rng.random() < 0.5 else -1)

    @property
    def vx(self):
        return math.cos(self.heading) * self.speed

    @property
    def vy(self):
        return math.sin(self.heading) * self.speed

    def hurt(self, weapon, amount=1.0):
        self.health -= amount / self.resist[weapon]
        return self.health <= 1e-6

    def update(self, dt, ship, scroll):
        self.t += dt
        if self.t > 0.25 and self.y > ship.y:  # homes in, but gives up once it has passed you
            want = math.atan2(ship.y - self.y, ship.x - self.x)
            diff = (want - self.heading + math.pi) % (2 * math.pi) - math.pi
            self.heading += max(-self.turn * dt, min(self.turn * dt, diff))
        self.x += self.vx * dt
        self.y += self.vy * dt - scroll * dt * 0.3
        self.node.setPos(self.x, self.y, 0.25)
        # nose along the flight direction, tumbling around its own axis
        self.node.setHpr(math.degrees(self.heading) - 90, 0, self.t * self.spin)
        self.beam_heat = max(0.0, self.beam_heat - dt * 3)

    def remove(self):
        self.alive = False
        self.node.removeNode()
