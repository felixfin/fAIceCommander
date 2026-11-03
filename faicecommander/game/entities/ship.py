"""The FaceCommander ship: sideways movement, banking, hull/energy, shield bubble."""
import math

import numpy as np

from ...render import models as M


class Ship:
    def __init__(self, parent, cfg, units):
        self.node = parent.attachNewNode("ship")
        self.scale = cfg["world.ship_scale"]
        self.model = M.cached("ship", M.build_ship).getChild(0).copyTo(self.node)
        self.model.setScale(self.scale)
        self.radius = units(cfg["world.ship_radius_px"])
        self.max_speed = units(cfg["world.ship_max_speed_px"])
        self.shield = self.node.attachNewNode("shield")
        V, F = M.icosphere(2)
        bubble = M.part(self.shield, V * np.array([1.45, 1.6, 0.8]), F, (0.3, 0.7, 1.0, 0.16), alpha=True,
                        two_sided=True)
        M.neon_edges(bubble, (0.4, 0.8, 1.0, 0.35), 1.0)
        self.shield.hide()
        self.y = -5.0
        self.reset()

    def reset(self):
        self.x, self.vx, self.t = 0.0, 0.0, 0.0
        self.hull, self.energy = 100.0, 100.0
        self.shield_on = False
        self.frozen = False
        self.hit_cooldown = 0.0
        self.node.setPos(self.x, self.y, 0)

    @property
    def muzzles(self):
        """World positions of the two pod cannons."""
        dx, dy = 0.98 * self.scale, 1.65 * self.scale
        return [(self.x - dx, self.y + dy), (self.x + dx, self.y + dy)]

    @property
    def prow_y(self):
        return self.y + M.SHIP_PROW * self.scale

    def update(self, dt, steer, half_width, drift=0.0):
        """drift: sideways speed forced on the ship (black hole pull), added to its own movement."""
        self.t += dt
        self.hit_cooldown = max(0.0, self.hit_cooldown - dt)
        target = 0.0 if self.frozen else steer * self.max_speed
        self.vx += (target - self.vx) * min(1.0, dt * 7.0)
        self.x = max(-half_width, min(half_width, self.x + (self.vx + drift) * dt))
        if abs(self.x) >= half_width:
            self.vx = 0.0
        bank = self.vx / self.max_speed * 28.0
        self.node.setPos(self.x, self.y, 0.08 * math.sin(self.t * 2.1))
        self.model.setHpr(-self.vx / self.max_speed * 6.0, 0, bank)
        if self.frozen:  # iced over by a hypno pulse
            self.model.setColorScale(0.55, 0.8, 1.5, 1)
        else:
            self.model.clearColorScale()
        if self.shield_on:
            self.shield.show()
            self.shield.setAlphaScale(0.75 + 0.25 * math.sin(self.t * 9))
        else:
            self.shield.hide()
