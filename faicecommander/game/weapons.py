"""Weapon selection and energy.

Laser: one pulse per mouth opening · Beam: fires while the mouth is open and energy lasts ·
Nuke: one per mouth opening (limited per level) · Shield: each opening toggles it.
"""

ORDER = ("laser", "beam", "nuke", "shield")


class Weapons:
    def __init__(self, cfg, units):
        self.laser_cost = cfg["weapons.laser.energy_cost"]
        self.laser_speed = units(cfg["weapons.laser.speed_px"])
        self.laser_interval = cfg["weapons.laser.min_interval_s"]
        self.beam_drain = cfg["weapons.beam.energy_per_s"]
        self.beam_grace = cfg["weapons.beam.grace_s"]
        self.nuke_cost = cfg["weapons.nuke.energy_cost"]
        self.shield_drain = cfg["weapons.shield.energy_per_s"]
        self.energy_regen = cfg["ship.energy_regen_per_s"]
        self.regen_delay = cfg["ship.energy_regen_delay_s"]
        self.reset(("laser", "shield"))

    def reset(self, unlocked, nukes=0):
        self.unlocked = [w for w in ORDER if w in unlocked]
        self.selected = self.unlocked[0]
        self.nukes = nukes
        self.cooldown = 0.0
        self.idle = 99.0
        self.beam_on = False
        self.beam_hold = 0.0

    def update(self, dt, ctl, ship, world):
        """world provides fire_laser(x, y, speed), fire_nuke(x, y) and emit(event)."""
        self.cooldown = max(0.0, self.cooldown - dt)
        if ctl.weapon_step and len(self.unlocked) > 1:
            i = (self.unlocked.index(self.selected) + ctl.weapon_step) % len(self.unlocked)
            self.selected = self.unlocked[i]
            world.emit(("switch", self.selected))
            if self.selected != "shield" and ship.shield_on:
                ship.shield_on = False
                world.emit(("shield", False))
        active = not ship.frozen
        if active and ctl.mouth_pressed:
            if self.selected == "laser":
                if self.cooldown <= 0 and ship.energy >= self.laser_cost:
                    ship.energy -= self.laser_cost
                    self.cooldown = self.laser_interval
                    self.idle = 0.0
                    for x, y in ship.muzzles:
                        world.fire_laser(x, y, self.laser_speed)
                    world.emit(("laser",))
                else:
                    world.emit(("empty",))
            elif self.selected == "nuke":
                if self.nukes > 0 and ship.energy >= self.nuke_cost:
                    self.nukes -= 1
                    ship.energy -= self.nuke_cost
                    self.idle = 0.0
                    world.fire_nuke(ship.x, ship.prow_y)
                    world.emit(("nuke_launch",))
                else:
                    world.emit(("empty",))
            elif self.selected == "shield":
                if ship.shield_on or ship.energy > 5:
                    ship.shield_on = not ship.shield_on
                    world.emit(("shield", ship.shield_on))
                else:
                    world.emit(("empty",))
        # a short grace period bridges a jaw that relaxes for a moment while holding the beam
        self.beam_hold = self.beam_grace if ctl.mouth_open else max(0.0, self.beam_hold - dt)
        self.beam_on = active and self.selected == "beam" and self.beam_hold > 0 and ship.energy > 0
        if self.beam_on:
            ship.energy = max(0.0, ship.energy - self.beam_drain * dt)
            self.idle = 0.0
        if ship.shield_on:
            ship.energy -= self.shield_drain * dt
            self.idle = 0.0
            if ship.energy <= 0:
                ship.energy, ship.shield_on = 0.0, False
                world.emit(("shield", False))
        elif not self.beam_on:
            self.idle += dt
            if self.idle > self.regen_delay:
                ship.energy = min(100.0, ship.energy + self.energy_regen * dt)
