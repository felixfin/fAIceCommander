"""Milestone 4: the Mother's damage zones and attacks, highscores, endless mode."""
import types

import pytest
from panda3d.core import NodePath

from faicecommander.config import Config
from faicecommander.game.levels import LEVELS
from faicecommander.game.levels.endless import Endless
from faicecommander.game.save import SaveData
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


def boss(world):
    lvl = LEVELS[6](world, LV["level_07"])
    lvl.start()
    m = lvl.mother
    m.regen = 0.0
    return lvl, m


def test_thrust_stops_for_the_boss(world):
    lvl, _ = boss(world)
    assert world.speed == 0.0
    LEVELS[0](world, LV["level_01"]).start()
    assert world.speed > 0.0


def test_zones_match_the_spec(world):
    _, m = boss(world)
    half = m.width / 2
    assert m.zone(m.x) == 3
    assert m.zone(m.x + half * 0.08) == 3       # centre 10 % of the full width = 0.1 of the half width
    assert m.zone(m.x + half * 0.15) == 2       # inner 15 % per side: 0.1 .. 0.4 of the half width
    assert m.zone(m.x + half * 0.38) == 2
    assert m.zone(m.x - half * 0.8) == 1
    assert m.zone(m.x + half * 1.1) is None


@pytest.mark.parametrize("weapon,zone_x,zone", [("laser", 0.0, 3), ("laser", 0.3, 2), ("laser", 0.8, 1),
                                                ("nuke", 0.0, 3), ("nuke", 0.8, 1)])
def test_damage_per_zone(world, weapon, zone_x, zone):
    _, m = boss(world)
    m.hurt(weapon, m.x + m.width / 2 * zone_x)
    assert m.health == pytest.approx(100 - LV["level_07"][weapon][zone - 1])


def test_beam_damage_per_second_and_vulnerability_bonus(world):
    _, m = boss(world)
    for _ in range(60):
        m.hurt("beam", m.x, DT)
    after_beam = 100 - LV["level_07.beam"][2]
    assert m.health == pytest.approx(after_beam)
    m.vulnerable = 5.0
    m.hurt("laser", m.x)
    assert m.health == pytest.approx(after_beam - LV["level_07.laser"][2] * 1.5)


def test_mother_regenerates(world):
    _, m = boss(world)
    m.regen = 1.0
    m.health = 50.0
    m.update(1.0, 5.0)
    assert m.health == pytest.approx(51.0)


def test_lasers_hit_the_hull_from_below(world):
    lvl, m = boss(world)
    m.y = lvl.home_y
    lvl.elapsed = 10.0
    world.fire_laser(m.x, world.ship.y + 2, 30.0)
    for _ in range(120):
        world.update(DT, Controls())
    assert m.health < 100.0


def test_she_gets_angrier_and_throws_mice(world):
    lvl, m = boss(world)
    lvl.elapsed = lvl.ENTER_S
    m.health = LV["level_07.phase_at"][0] - 1
    events = []
    for _ in range(int(12 / DT)):
        events += lvl.update(DT, Controls(eyes_closed=True))
        world.ship.hull = 100.0
    assert ("mother_phase", 2) in events and lvl.phase == 1 and m.speed_mult > 1
    assert "mouse_throw" in [e[0] for e in events]


def test_she_shoots_down_nukes(world):
    lvl, m = boss(world)
    lvl.elapsed = lvl.ENTER_S
    m.health = LV["level_07.phase_at"][1] - 1
    lvl.data = Config({**lvl.data.dict(), "intercept_chance": [1.0, 1.0, 1.0]})
    world.fire_nuke(world.ship.x, world.ship.y + 1)
    events = []
    for _ in range(int(2 / DT)):
        events += lvl.update(DT, Controls(eyes_closed=True))
    assert "intercepted" in [e[0] for e in events]


def test_she_shoots_and_bombs(world):
    lvl, m = boss(world)
    lvl.elapsed = lvl.ENTER_S
    lvl.bomb_t = 0.5
    events = []
    for _ in range(int(6 / DT)):
        events += lvl.update(DT, Controls(eyes_closed=True))
    kinds = [e[0] for e in events]
    assert "enemy_shot" in kinds and "bomb" in kinds and "hole_formed" in kinds


def test_artificial_hole_drains_and_collapses(world):
    lvl, m = boss(world)
    ship = world.ship
    world.spawn_hole(ship.x + 2.5, ship.y + 1.0, 0.0, world.u(14), 0.0, life=1.0, drain=5.0, drain_radius=5.0)
    hull = ship.hull
    world.hull_regen = 0.0
    world.update(0.5, Controls())
    assert ship.hull == pytest.approx(hull - 2.5, abs=0.1)
    world.update(0.6, Controls())
    assert not world.holes
    world.hull_regen = CFG["ship.hull_regen_per_s"]


def test_pulse_makes_her_vulnerable(world):
    lvl, m = boss(world)
    lvl.elapsed = lvl.ENTER_S
    lvl.pulse_t = 0.0
    for _ in range(int(20 / DT)):
        lvl.update(DT, Controls(eyes_closed=True))
        if m.vulnerable > 0:
            break
    assert m.vulnerable > 0


def test_highscores(tmp_path):
    save = SaveData(tmp_path / "save.json")
    assert save.qualifies("hard", 10) and not save.qualifies("practice", 10_000)
    for i in range(12):
        save.add("hard", f"p{i}", 100 * i, "L1")
    table = save.top("hard")
    assert len(table) == 10 and table[0]["score"] == 1100 and table[0]["name"] == "P11"
    assert not save.qualifies("hard", 150) and save.qualifies("hard", 250)
    save.unlock_endless()
    again = SaveData(tmp_path / "save.json")
    assert again.endless_unlocked and again.last_name == "P11"


def test_endless_runs_and_cycles_phases(world):
    lvl = Endless(world, LV["endless"], LV)
    lvl.start()
    phases = set()
    for k in range(int(125 / 0.05)):
        lvl.update(0.05, Controls(eyes_closed=True, mouth_pressed=k % 10 == 0, mouth_open=k % 10 < 5))
        phases.add(lvl.phase)
        world.ship.hull = 100.0
    assert phases == {"asteroids", "brains", "raiders", "holes"} and not lvl.complete
    assert lvl.difficulty > LV["endless.start_difficulty"]
