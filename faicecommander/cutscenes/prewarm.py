"""Builds every cached set piece of the intro and outro once, a step per frame, on the loading screen -
so that no cut ever has to wait for a model to be built (that froze the picture for up to 4 s)."""
import numpy as np

from . import intro, outro, props


def steps():
    """Callables that each build (or load) one group of props under a throw-away root."""
    def humans(r):
        for i, (x, female) in enumerate(((-3.0, False), (-1.8, True), (-0.6, False), (0.6, True), (1.8, False),
                                         (3.0, True))):
            props.human(r, (x, 1.5, 0), female)                         # intro: the slaves
        for i, x in enumerate((-3.0, -1.8, -0.6, 0.6, 1.8, 3.0)):
            props.human(r, (x, 1.0, 0), female=i % 2 == 1)              # outro: the collars fall
        for k in range(4):
            props.human(r, (0, 0, 0), female=k % 2 == 1, collar=(0.15, 0.15, 0.15), skin=k)  # the crowd

    return [
        lambda r: intro.starfield(r), lambda r: intro.starfield(r, 200, 60, seed=14),
        lambda r: props.burning_planet(r, 6.0), lambda r: props.burning_planet(r, 9.0),
        props.slave_hall, humans,
        lambda r: props.catlien(r, 2.0), lambda r: props.catlien(r, 2.4, queen=True),
        props.operating_table, props.hangar, props.empty_ship, props.helmet,
        lambda r: props.brain_jar(r, (0, 0, 0)), lambda r: props.brain(r, 0.24),
        lambda r: [props.RobotArm(r, (0, 0, 0), tool=t) for t in ((0.4, 1.0, 0.9), (1.0, 0.3, 0.2))],
        lambda r: props.RobotArm(r, (0, 0, 0), color=(0.85, 0.6, 0.1), tool=(1.0, 0.8, 0.4)),
        lambda r: outro._city(r, np.random.default_rng(10)),
    ]
