"""World rules without a window: damage per weapon, splitting, shockwave timing, shield."""
import types

import pytest
from panda3d.core import NodePath

from faicecommander.config import Config
from faicecommander.game.world import World
from faicecommander.input.gestures import Controls

CFG = Config.load("config.toml")
LV = Config.load("levels.toml")


@pytest.fixture(scope="module")
def world():
    return World(types.SimpleNamespace(render=NodePath("render")), CFG)


def fresh(world, split=True):
    world.reset(("laser", "beam", "nuke", "shield"), 3)
    if split:
        d = LV["level_02"]
        world.split = {"max": 3, "size_px": d["small_size_px"], "speed_px": d["fragment_speed_px"],
                       "damage": 25, "score": 100}
    return world


def big(world, x=0.0, y=10.0):
    return world.spawn_asteroid(2, (40, 40), None, 0, 50, 250, x=x, y=y, vel=(0.0, 0.0))


def test_category_2_needs_two_laser_hits(world):
    a = big(fresh(world))
    assert not a.hurt("laser")
    assert a.hurt("laser")


def test_category_2_beam_time_matches_config(world):
    a = big(fresh(world))
    frames = round(CFG["targets.asteroid_2.beam"] * 30)
    for _ in range(frames - 1):
        assert not a.hurt("beam", 1 / 30)
    assert a.hurt("beam", 1 / 30 + 1e-6)


def test_beam_destroys_a_moving_asteroid_while_tracking_it(world):
    w = fresh(world, split=False)
    w.weapons.selected = "beam"
    a = w.spawn_asteroid(1, (20, 20), None, 0, 25, 100, x=w.ship.x + 0.6, y=w.ship.y + 12, vel=(2.0, -3.0))
    t = 0.0
    while a.alive and t < 2.0:
        w.update(1 / 60, Controls(mouth_open=True, steer=1.0 if a.x > w.ship.x else -1.0))
        t += 1 / 60
    assert not a.alive and t < CFG["targets.asteroid_1.beam"] + 0.2


def test_beam_bridges_a_brief_relaxed_jaw(world):
    w = fresh(world, split=False)
    w.weapons.selected = "beam"
    w.update(1 / 60, Controls(mouth_open=True))
    for _ in range(int(CFG["weapons.beam.grace_s"] * 60) - 2):
        w.update(1 / 60, Controls(mouth_open=False))
        assert w.weapons.beam_on
    for _ in range(5):
        w.update(1 / 60, Controls(mouth_open=False))
    assert not w.weapons.beam_on


def test_one_nuke_destroys_category_2(world):
    assert big(fresh(world)).hurt("nuke")


def test_shot_category_2_splits_into_one_to_three(world):
    for _ in range(20):
        w = fresh(world)
        a = big(w)
        w._kill(a, "laser")
        assert 1 <= w.count(1) <= 3 and w.count(2) == 0
        assert any(ev[0] == "split" for ev in w.pop_events())


def test_nuked_category_2_does_not_split(world):
    w = fresh(world)
    w._kill(big(w), "nuke")
    assert w.count(1) == 0


def test_boom_is_heard_when_the_shockwave_reaches_the_ship(world):
    w = fresh(world, split=False)
    fx = w.explode(w.ship.x, w.ship.y + 10.0, 1.0)  # 10 units away
    travel = (10.0 - 0.4) / w.ring_speed
    heard_at = None
    t = 0.0
    while t < 3.0:
        if fx.boom_due(w.ship.x, w.ship.y):
            heard_at = t
            break
        fx.update(1 / 60)
        t += 1 / 60
    assert heard_at is not None and abs(heard_at - travel) < 0.05


def test_shield_reduces_collision_damage(world):
    w = fresh(world, split=False)
    for shield, expected in ((False, 50.0), (True, 50.0 * CFG["ship.shield_damage_factor"])):
        w.reset(("laser", "shield"))
        w.ship.shield_on = shield
        w.spawn_asteroid(2, (40, 40), None, 0, 50, 250, x=w.ship.x, y=w.ship.y, vel=(0.0, 0.0))
        w._collide()
        assert w.ship.hull == pytest.approx(100.0 - expected)


def test_nuke_count_and_energy(world):
    w = fresh(world, split=False)
    w.weapons.selected = "nuke"
    ctl = Controls(mouth_open=True, mouth_pressed=True)
    w.update(1 / 60, ctl)
    assert w.weapons.nukes == 2 and len(w.nukes) == 1
    assert w.ship.energy == pytest.approx(100.0 - CFG["weapons.nuke.energy_cost"])
