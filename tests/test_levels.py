"""Milestone 3 rules: hypno pulses, sonar, brains, raiders, black holes - and every level runs."""
import math
import types

import numpy as np
import pytest
from panda3d.core import NodePath

from faicecommander.config import Config
from faicecommander.game.hypno import PULSE, WARNING, HypnoCycle, Sonar
from faicecommander.game.levels import LEVELS
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


def test_brains_never_form_on_the_ship_and_max_ten(world):
    lvl = LEVELS[3](world, LV["level_04"])
    lvl.start()
    keepout = world.u(LV["level_04.brain_keepout_px"])
    for _ in range(int(6 / DT)):
        lvl.update(DT, Controls())
        assert len(world.brains) <= LV["level_04.max_brains"]
        for b in world.brains:
            if b.t < 0.05:  # freshly formed
                assert math.hypot(b.x - world.ship.x, b.y - world.ship.y) >= keepout - 0.5


def test_raider_needs_six_laser_hits(world):
    world.reset()
    r = world.spawn_raider(0, 5, 10, (1, 2), 20, 10, 1000)
    hits = 0
    while not r.hurt("laser"):
        hits += 1
    assert hits + 1 == CFG["targets.raider.laser"]


def test_raider_shoots_towards_the_ship_and_stays_in_bounds(world):
    world.reset()
    r = world.spawn_raider(3, 8, world.u(220), (0.5, 0.6), world.u(420), 10, 1000)
    r.cooldown = 0.0
    shots = []
    for _ in range(int(5 / DT)):
        r.update(DT, world.ship, world.raider_bounds(), [r], lambda x, y, vx, vy, d: shots.append((x, y, vx, vy)))
        x0, x1, y0, y1 = world.raider_bounds()
        assert x0 - 1e-6 <= r.x <= x1 + 1e-6 and y0 - 1e-6 <= r.y
    assert shots and all(vy < 0 for _, _, _, vy in shots)


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


@pytest.mark.parametrize("cls", LEVELS)
def test_every_level_runs(world, cls):
    lvl = cls(world, LV[cls.key])
    lvl.start()
    k = 0
    for _ in range(int(8 / DT)):
        k += 1
        ctl = Controls(mouth_open=k % 20 < 10, mouth_pressed=k % 20 == 0, weapon_step=1 if k % 120 == 0 else 0,
                       eyes_closed=True)
        lvl.update(DT, ctl)
    assert 0.0 <= lvl.progress <= 1.0
