from ...config import Config
from .level_01_asteroid_belt import AsteroidBelt
from .level_02_debris_field import DebrisField
from .level_03_hypno_nebula import HypnoNebula
from .level_04_the_void import TheVoid
from .level_05_patrol import Patrol
from .level_06_event_horizon import EventHorizon
from .level_07_the_mother import TheMother

LEVELS = [AsteroidBelt, DebrisField, HypnoNebula, TheVoid, Patrol, EventHorizon, TheMother]
DIFFICULTIES = ("easy", "medium", "hard")


def level_data(levels_cfg, key, difficulty="easy"):
    """The [key] table with the [<difficulty>.<key>] overrides applied (easy has none)."""
    data = levels_cfg[key].dict()
    override = levels_cfg.get(f"{difficulty}.{key}")
    if override is not None:
        data.update(override.dict())
    return Config(data)
