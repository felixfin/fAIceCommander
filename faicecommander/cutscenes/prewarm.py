"""Builds every cached set piece of the intro and outro once, a step per frame, on the loading screen -
so that no cut ever has to wait for a model to be built (that froze the picture for up to 4 s)."""
import numpy as np

from . import intro, outro, props


def steps():
    """Callables that each build (or load) one group of props under a throw-away root."""
    def humans(r):
        for female, tone, x in intro.SLAVES:
            props.human(r, (x, 1.4, 0), female, tone)                    # intro: the slaves
        for female, tone, _, h in intro.TUBES:
            props.stasis_tube(r, (0, 0, 0), female, tone, h)             # ... and the tubes
        for i in range(6):
            props.human(r, (0, 0, 0), i % 2 == 1, i % 5, "upright")      # outro: the collars fall
        for k in range(10):
            props.human(r, (0, 0, 0), k % 2 == 1, k % 5, "cheer" if k % 3 else "upright", None)  # the crowd
        for k in range(10, 20):
            props.human(r, (0, 0, 0), k % 2 == 1, k % 5, "cheer" if k % 3 else "upright", None)

    return [
        lambda r: intro.starfield(r), lambda r: intro.starfield(r, 200, 60, seed=14),
        lambda r: props.burning_planet(r, 6.0), lambda r: props.burning_planet(r, 9.0),
        props.slave_hall, humans,
        props.mother_mech, lambda r: props.catlien(r, 2.4, queen=True),
        props.operating_table, props.hangar, props.empty_ship, props.helmet,
        lambda r: props.brain_jar(r, (0, 0, 0)), lambda r: props.brain(r, 0.24),
        lambda r: [props.RobotArm(r, (0, 0, 0), tool=t) for t in ((0.4, 1.0, 0.9), (1.0, 0.3, 0.2))],
        lambda r: props.RobotArm(r, (0, 0, 0), color=(0.85, 0.6, 0.1), tool=(1.0, 0.8, 0.4)),
        lambda r: outro._city(r, np.random.default_rng(10)),
    ]
