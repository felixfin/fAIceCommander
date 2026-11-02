"""Weapon selection and energy: one laser pulse per mouth opening, shield toggled per opening."""

ORDER = ("laser", "beam", "nuke", "shield")


class Weapons:
    def __init__(self, cfg, units):
        self.laser_cost = cfg["weapons.laser.energy_cost"]
        self.laser_speed = units(cfg["weapons.laser.speed_px"])
        self.laser_interval = cfg["weapons.laser.min_interval_s"]
        self.laser_damage = cfg["weapons.laser.damage"]
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

    def update(self, dt, ctl, ship, fire_laser):
        self.cooldown = max(0.0, self.cooldown - dt)
        if ctl.weapon_step:
            i = (self.unlocked.index(self.selected) + ctl.weapon_step) % len(self.unlocked)
            self.selected = self.unlocked[i]
            if self.selected != "shield":
                ship.shield_on = False
        if not ship.frozen and ctl.mouth_pressed:
            if self.selected == "laser" and self.cooldown <= 0 and ship.energy >= self.laser_cost:
                ship.energy -= self.laser_cost
                self.cooldown = self.laser_interval
                self.idle = 0.0
                for x, y in ship.muzzles:
                    fire_laser(x, y, self.laser_speed, self.laser_damage)
            elif self.selected == "shield":
                ship.shield_on = not ship.shield_on and ship.energy > 5
        if ship.shield_on:
            ship.energy -= self.shield_drain * dt
            self.idle = 0.0
            if ship.energy <= 0:
                ship.energy, ship.shield_on = 0.0, False
        else:
            self.idle += dt
            if self.idle > self.regen_delay:
                ship.energy = min(100.0, ship.energy + self.energy_regen * dt)
