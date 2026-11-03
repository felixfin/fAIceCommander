"""Catlien raiders: stay on screen, roam in all four directions and attack. Each attack is one of
- a disruptor shot with lead (they hiss and yowl when they fire),
- a thrown space mouse that homes in on you,
- a belly roll: the raider flips over for a few seconds and its belly emitter drags your ship
  sideways towards it. While it shows its belly it takes double damage."""
import math

import numpy as np

from ...render import models as M

ROLL_S = 0.4  # time to flip over / back


class RaiderTemplate:
    SCALE = 0.55

    def __init__(self):
        def build(root):
            store = root.attachNewNode("raider-template")
            M.build_fighter(store).setScale(self.SCALE)
            shot = root.attachNewNode("enemy-shot")
            V, F = M.icosphere(1)
            M.part(shot, V * np.array([0.09, 0.3, 0.09]), F, (1.0, 0.3, 0.12), unlit=True)
            M.glow(shot, (0, 0, 0), 0.6, (1.0, 0.2, 0.05, 0.9))
            M.build_tractor_beam(root.attachNewNode("tractor"))
        lib = M.cached("raider", build)
        self.store = lib.find("raider-template")
        self.model = self.store.getChild(0)
        self.shot = lib.find("enemy-shot")
        self.tractor = lib.find("tractor")


class EnemyShot:
    radius = 0.16

    def __init__(self, parent, template, x, y, vx, vy, damage):
        self.node = template.shot.copyTo(parent)
        self.x, self.y, self.vx, self.vy, self.damage = x, y, vx, vy, damage
        self.alive = True
        self.node.setH(math.degrees(math.atan2(-vx, vy)))
        self.node.setPos(x, y, 0.1)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.node.setPos(self.x, self.y, 0.1)

    def remove(self):
        self.alive = False
        self.node.removeNode()


def raider_spec(d, u, toughness=None):
    """Raider settings from a level table (px values converted with u)."""
    weapons = d.get("raider_weapons")
    return {
        "speed": u(d["raider_speed_px"]), "fire_interval": d["raider_fire_interval_s"],
        "shot_speed": u(d["raider_shot_speed_px"]), "shot_damage": d["shot_damage_percent"],
        "score": d["score_per_raider"], "toughness": toughness or d.get("raider_toughness", 1.0),
        "weapons": weapons.dict() if weapons is not None else {"laser": 1.0},
        "mouse_speed": u(d.get("mouse_speed_px", 200)), "mouse_turn": d.get("mouse_turn_deg", 70),
        "mouse_damage": d.get("mouse_damage_percent", 12), "mouse_score": d.get("score_per_mouse", 50),
        "belly_s": d.get("belly_s", 2.5), "belly_pull": u(d.get("belly_pull_px", 190)),
        "belly_cooldown": d.get("belly_cooldown_s", 9),
    }


class Raider:
    kind = "raider"
    category = "raider"
    radius = 0.95

    def __init__(self, parent, template, rng, x, y, spec, resist):
        self.node = template.store.copyTo(parent)
        self.model = self.node.getChild(0)
        self.tractor = template.tractor.copyTo(parent)
        self.tractor.hide()
        self.rng = rng
        self.x, self.y = x, y
        self.vx, self.vy = 0.0, 0.0
        self.spec = spec
        self.speed = spec["speed"]
        self.resist = {k: v * spec["toughness"] for k, v in resist.items()}
        self.score = spec["score"]
        self.health = 1.0
        self.alive = True
        self.beam_heat = 0.0
        self.goal = (x, y)
        self.retarget = 0.0
        self.cooldown = rng.uniform(1.5, 2.5)  # give the player a moment when they arrive
        self.belly_ready = rng.uniform(3.0, 6.0)
        self.belly_t = 0.0      # > 0 while rolled over (includes the flip time)
        self.roll = 0.0         # 0 upright .. 1 belly up
        self.t = 0.0

    @property
    def showing_belly(self):
        return self.roll > 0.85

    def hurt(self, weapon, amount=1.0):
        if self.showing_belly:
            amount *= 2.0  # the soft underside
        self.health -= amount / self.resist[weapon]
        self.beam_heat = max(self.beam_heat, 0.6)
        return self.health <= 1e-6

    def pull(self, ship_x):
        """Sideways drift forced on the ship while this raider shows its belly."""
        if not self.showing_belly:
            return 0.0
        dx = self.x - ship_x
        return math.copysign(min(self.spec["belly_pull"], abs(dx) * 4.0), dx)

    def update(self, dt, ship, bounds, others, world):
        """bounds: (x_min, x_max, y_min, y_max) of the area the raider roams in."""
        self.t += dt
        x0, x1, y0, y1 = bounds
        self.retarget -= dt
        if self.retarget <= 0 or math.hypot(self.goal[0] - self.x, self.goal[1] - self.y) < 1.0:
            self.goal = (self.rng.uniform(x0, x1), self.rng.uniform(y0, y1))
            self.retarget = self.rng.uniform(1.2, 2.6)
        ax, ay = self.goal[0] - self.x, self.goal[1] - self.y
        for o in others:  # keep apart from the other raiders
            if o is not self and o.alive:
                dx, dy = self.x - o.x, self.y - o.y
                d = math.hypot(dx, dy)
                if 1e-3 < d < 3.6:
                    ax += dx / d * (3.6 - d) * 3
                    ay += dy / d * (3.6 - d) * 3
        speed = self.speed * (0.25 if self.belly_t > 0 else 1.0)  # hovers while it pulls
        n = math.hypot(ax, ay)
        if n > 1e-6:
            tvx, tvy = ax / n * speed, ay / n * speed
            k = min(1.0, dt * 2.5)
            self.vx += (tvx - self.vx) * k
            self.vy += (tvy - self.vy) * k
        self.x = min(x1, max(x0, self.x + self.vx * dt))
        self.y = min(y1 + 6, max(y0, self.y + self.vy * dt))  # may still be flying in from above
        self.node.setPos(self.x, self.y, 0.15)
        self._update_roll(dt, ship)
        bank = -self.vx / self.speed * 30
        self.model.setHpr(self.vx / self.speed * 8, 0, bank * (1 - self.roll) + 180 * self.roll)
        self.belly_ready -= dt
        self.cooldown -= dt
        if self.cooldown <= 0 and self.y < y1 + 1 and self.belly_t <= 0:
            self.cooldown = self.rng.uniform(*self.spec["fire_interval"])
            self._attack(ship, others, world)
        self.beam_heat = max(0.0, self.beam_heat - dt * 3)
        heat = self.beam_heat * 0.8 + (1 - self.health) * 0.8
        if heat > 0.01:
            self.node.setColorScale(1 + heat * 1.8, 1 + heat * 0.5, 1, 1)
        else:
            self.node.clearColorScale()

    def _update_roll(self, dt, ship):
        s = self.spec
        if self.belly_t > 0:
            self.belly_t -= dt
            if self.belly_t > s["belly_s"] + ROLL_S:          # flipping over
                self.roll = min(1.0, self.roll + dt / ROLL_S)
            elif self.belly_t < ROLL_S:                       # flipping back
                self.roll = max(0.0, self.roll - dt / ROLL_S)
            else:
                self.roll = 1.0
        else:
            self.roll = max(0.0, self.roll - dt / ROLL_S)
        if self.showing_belly:
            dx, dy = ship.x - self.x, ship.y - self.y
            self.tractor.show()
            self.tractor.setPos(self.x, self.y, 0.05)
            self.tractor.setH(math.degrees(math.atan2(dx, -dy)))
            self.tractor.setScale(1.0, math.hypot(dx, dy), 1.0)
            self.tractor.setAlphaScale(0.75 + 0.25 * math.sin(self.t * 14))
        else:
            self.tractor.hide()

    def _attack(self, ship, others, world):
        s, rng = self.spec, self.rng
        w = dict(s["weapons"])
        if self.belly_ready > 0 or any(o is not self and o.alive and o.belly_t > 0 for o in others):
            w["belly"] = 0.0  # one belly at a time, with a cooldown
        names = [k for k, v in w.items() if v > 0]
        p = np.array([w[k] for k in names], float)
        choice = names[int(rng.choice(len(names), p=p / p.sum()))] if names else "laser"
        if choice == "belly":
            self.belly_t = s["belly_s"] + 2 * ROLL_S
            self.belly_ready = s["belly_cooldown"]
            world.emit(("belly",))
        elif choice == "mouse":
            sx, sy = self.x, self.y - 0.9
            dx, dy = ship.x - sx, ship.y - sy
            n = max(math.hypot(dx, dy), 1e-6)
            world.throw_mouse(sx, sy, dx / n, dy / n, s["mouse_speed"], s["mouse_turn"], s["mouse_damage"],
                              s["mouse_score"])
        else:
            self._fire(ship, world)

    def _fire(self, ship, world):
        sx, sy = self.x, self.y - 1.05
        speed = self.spec["shot_speed"]
        dist = math.hypot(ship.x - sx, ship.y - sy)
        lead = dist / speed
        tx = ship.x + ship.vx * lead * self.rng.uniform(0.6, 1.0)  # not perfectly accurate
        dx, dy = tx - sx, ship.y - sy
        n = math.hypot(dx, dy)
        world.fire_enemy(sx, sy, dx / n * speed, dy / n * speed, self.spec["shot_damage"], "raider")

    def remove(self):
        self.alive = False
        self.node.removeNode()
        self.tractor.removeNode()
