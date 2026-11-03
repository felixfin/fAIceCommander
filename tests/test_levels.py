"""Milestone 3 rules: hypno pulses, sonar, brains, raiders, black holes - and every level runs."""
import math
import types

import numpy as np
import pytest
from panda3d.core import NodePath

from faicecommander.config import Config, Units
from faicecommander.game.hypno import PULSE, WARNING, HypnoCycle, Sonar
from faicecommander.game.entities.raider import raider_spec
from faicecommander.game.levels import DIFFICULTIES, LEVELS, level_data
from faicecommander.game.world import World
from faicecommander.input.gestures import Controls

CFG = Config.load("config.toml")
LV = Config.load("levels.toml")
DT = 1 / 60


@pytest.fixture(scope="module")
def world():
    w = World(types.SimpleNamespace(render=NodePath("render")), CFG)
    w.set_bounds(30.0, -12.0)
    return w


def run_cycle(eyes, seconds, cycle):
    events = []
    for k in range(int(seconds / DT)):
        events += cycle.update(DT, eyes(k * DT))
    return events


def new_cycle():
    return HypnoCycle(np.random.default_rng(1), 3.0, 10.0, 2.0, (20, 25), 0.5)


def test_pulse_is_announced_then_lasts_ten_seconds():
    c = new_cycle()
    events = run_cycle(lambda t: True, 2.0 + 0.05, c)
    assert c.phase == WARNING and ("hypno_warning",) in events
    run_cycle(lambda t: True, 3.0, c)
    assert c.phase == PULSE
    events = run_cycle(lambda t: True, 10.0, c)
    assert ("hypno_end", True) in events and not c.frozen


def test_open_eyes_freeze_the_ship_until_the_pulse_ends():
    c = new_cycle()
    run_cycle(lambda t: True, 5.05, c)
    assert c.active
    events = run_cycle(lambda t: t < 3.0, 4.0, c)  # eyes open after 3 s into the pulse
    assert ("frozen",) in events and c.frozen
    run_cycle(lambda t: True, 5.0, c)  # closing them again does not help ...
    assert c.active and c.frozen
    run_cycle(lambda t: True, 1.0, c)  # ... until the pulse is over
    assert c.phase != PULSE and not c.frozen


def test_grace_time_to_close_the_eyes():
    c = new_cycle()
    run_cycle(lambda t: True, 5.0 - DT, c)  # warning ends exactly now
    events = run_cycle(lambda t: t > 0.3, 10.5, c)  # still open for 0.3 s after the pulse hits
    assert ("frozen",) not in events and ("hypno_end", True) in events


def test_sonar_pans_and_raises_pitch_on_collision_course():
    ship = types.SimpleNamespace(x=0.0, y=-5.0, radius=1.1)
    sonar = Sonar()
    rock = types.SimpleNamespace(x=-3.0, y=3.0, radius=0.5, alive=True)
    ping = None
    for _ in range(200):
        ping = ping or sonar.update(DT, ship, [rock])
    assert ping[1] == "sonar_l2" and ping[2] < 1.5
    sonar, rock.x, ping = Sonar(), 0.2, None
    for _ in range(200):
        ping = ping or sonar.update(DT, ship, [rock])
    assert ping[1] == "sonar_c" and ping[2] == 1.5


def test_brains_never_form_on_the_ship_and_stay_below_the_cap(world):
    lvl = LEVELS[3](world, LV["level_04"])
    lvl.start()
    keepout = world.u(LV["level_04.brain_keepout_px"])
    for _ in range(int(6 / DT)):
        lvl.update(DT, Controls())
        assert len(world.brains) <= LV["level_04.max_brains"][1]
        for b in world.brains:
            if b.t < 0.05:  # freshly formed
                assert math.hypot(b.x - world.ship.x, b.y - world.ship.y) >= keepout - 0.5


def spec(**kw):
    d = level_data(LV, "level_05", "easy").dict()
    d.update(kw)
    return raider_spec(Config(d), Units(CFG))


def test_raider_toughness_scales_the_laser_hits(world):
    world.reset()
    r = world.spawn_raider(0, 5, spec(raider_toughness=1.5))
    hits = 0
    while not r.hurt("laser"):
        hits += 1
    assert hits + 1 == math.ceil(CFG["targets.raider.laser"] * 1.5)


class Recorder:
    """Stands in for the world: records what a raider fires."""

    def __init__(self):
        self.shots, self.mice, self.events = [], [], []

    def fire_enemy(self, x, y, vx, vy, damage, source="raider", sound=True):
        self.shots.append((x, y, vx, vy))

    def throw_mouse(self, *args):
        self.mice.append(args)

    def emit(self, ev):
        self.events.append(ev)


def test_raider_shoots_towards_the_ship_and_stays_in_bounds(world):
    world.reset()
    r = world.spawn_raider(3, 8, spec(raider_fire_interval_s=[0.5, 0.6], raider_weapons={"laser": 1.0}))
    r.cooldown = 0.0
    rec = Recorder()
    for _ in range(int(5 / DT)):
        r.update(DT, world.ship, world.raider_bounds(), [r], rec)
        x0, x1, y0, y1 = world.raider_bounds()
        assert x0 - 1e-6 <= r.x <= x1 + 1e-6 and y0 - 1e-6 <= r.y
    assert rec.shots and all(vy < 0 for _, _, _, vy in rec.shots)


def test_raiders_throw_mice_that_home_in_and_die_from_one_laser(world):
    world.reset()
    r = world.spawn_raider(4, 8, spec(raider_fire_interval_s=[0.3, 0.3], raider_weapons={"mouse": 1.0}))
    r.cooldown = 0.0
    for _ in range(int(1.0 / DT)):
        world.update(DT, Controls())
    assert world.mice
    m = world.mice[0]
    x_start = m.x
    for _ in range(int(0.6 / DT)):
        m.update(DT, world.ship, 0.0)
    assert abs(m.x - world.ship.x) < abs(x_start - world.ship.x)  # it steers towards the ship
    assert m.hurt("laser")


def test_belly_roll_pulls_the_ship_towards_the_raider(world):
    world.reset()
    r = world.spawn_raider(8, 6, spec(raider_weapons={"belly": 1.0}))
    r.belly_ready, r.cooldown = 0.0, 0.0
    x0 = world.ship.x
    for _ in range(int(1.5 / DT)):
        world.update(DT, Controls())
    assert r.showing_belly and world.ship.x > x0 + 1.0
    hp = r.health
    r.hurt("laser")
    assert hp - r.health == pytest.approx(2.0 / r.resist["laser"])  # the belly takes double damage


def test_black_hole_pulls_and_absorbs(world):
    world.reset()
    ship = world.ship
    h = world.spawn_hole(ship.x + 3.0, ship.y + 1.0, 0.0, world.u(18), LV["level_06.hole_pull"])
    x0 = ship.x
    world.update(DT * 10, Controls())
    assert ship.x > x0  # pulled towards the hole on the right
    h.x, h.y = ship.x + 0.3, ship.y
    world.update(DT, Controls())
    assert world.death_cause == "absorbed" and ship.hull == 0


def test_steering_against_a_distant_hole_works(world):
    world.reset()
    ship = world.ship
    world.spawn_hole(ship.x + 4.5, ship.y + 2.0, 0.0, world.u(18), LV["level_06.hole_pull"])
    x0 = ship.x
    for _ in range(30):
        world.update(DT, Controls(steer=-1.0))
    assert ship.x < x0 and world.death_cause is None


def test_bigger_black_holes_pull_harder(world):
    world.reset()
    small = world.spawn_hole(10, 0, 0.0, world.u(12), 55.0)
    big = world.spawn_hole(10, 0, 0.0, world.u(30), 55.0)
    assert big.drift(5, 0, 99) > small.drift(5, 0, 99) * 5


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
@pytest.mark.parametrize("cls", LEVELS)
def test_every_level_runs(world, cls, difficulty):
    lvl = cls(world, level_data(LV, cls.key, difficulty))
    lvl.start()
    k = 0
    for _ in range(int(8 / DT)):
        k += 1
        ctl = Controls(mouth_open=k % 20 < 10, mouth_pressed=k % 20 == 0, weapon_step=1 if k % 120 == 0 else 0,
                       eyes_closed=True)
        lvl.update(DT, ctl)
    assert 0.0 <= lvl.progress <= 1.0
