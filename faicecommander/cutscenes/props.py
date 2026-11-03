"""Props for the cutscenes, built from the game's procedural models."""
import math

import numpy as np
from panda3d.core import Point3, TextNode

from ..render import models as M
from ..render.effects import Explosion


def look(app, pos, target):
    app.camera.setPos(*pos)
    app.camera.lookAt(Point3(*target))


def lerp(a, b, u):
    u = min(1.0, max(0.0, u))
    u = u * u * (3 - 2 * u)  # smoothstep
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def burning_planet(root, radius=7.0):
    planet = root.attachNewNode("planet")
    V, F = M.icosphere(3)
    rng = np.random.default_rng(4)
    dirs = [rng.normal(size=3) for _ in range(18)]

    def lava(p):
        n = sum(math.sin(5 * float(np.dot(p, d / np.linalg.norm(d))) + i) for i, d in enumerate(dirs)) / 6
        hot = max(0.0, n - 0.15)
        return (0.08 + 1.0 * hot, 0.03 + 0.45 * hot ** 1.5, 0.02 + 0.1 * hot ** 3, 1)

    M.part(planet, V * radius, F, (1, 1, 1), vcol=lava, unlit=True)
    M.glow(planet, (0, 0, 0), radius * 3.2, (1.0, 0.3, 0.05, 0.5))
    return planet


def human(root, pos, female=False, collar=(1.0, 0.1, 0.05)):
    """A dark human silhouette with a glowing slave collar."""
    node = root.attachNewNode("human")
    dark = (0.02, 0.02, 0.025)
    V, F = M.lathe([(0.0, 0.0), (0.16, 0.05), (0.2 if female else 0.18, 0.5), (0.24 if female else 0.27, 1.05),
                    (0.12, 1.3), (0.0, 1.32)], 14, "z")
    M.part(node, V, F, dark, orient="z")
    Vh, Fh = M.icosphere(2)
    M.part(node, Vh * np.array([0.12, 0.13, 0.15]), Fh, dark, pos=(0, 0, 1.5))
    Vc, Fc = M.lathe([(0.085, 1.33), (0.09, 1.36), (0.085, 1.39)], 16, "z")
    ring = M.part(node, Vc, Fc, collar, orient="z", unlit=True, name="collar")
    M.glow(ring, (0, -0.08, 1.36), 0.18, (*collar, 0.9))
    node.setPos(*pos)
    node.setLightOff(1)  # a pure silhouette against the backlight
    return node


def tag(root, text, pos, scale=0.18, color=(1, 0.35, 0.3, 1)):
    tn = TextNode("tag")
    tn.setText(text)
    tn.setAlign(TextNode.ACenter)
    tn.setTextColor(*color)
    np_ = root.attachNewNode(tn)
    np_.setPos(*pos)
    np_.setScale(scale)
    np_.setLightOff(1)
    np_.setBillboardPointEye()
    return np_


def backlight(root, pos, size, color=(0.9, 0.05, 0.03, 0.45)):
    return M.glow(root, pos, size, color)


def human_ship(app, root, pos, grey=True):
    ship = M.build_ship(root) if not hasattr(app, "_cut_ship_tpl") else app._cut_ship_tpl.copyTo(root)
    if not hasattr(app, "_cut_ship_tpl"):
        app._cut_ship_tpl = ship.copyTo(app.hidden)
    if grey:
        ship.setColorScale(0.55, 0.6, 0.7, 1)
    ship.setPos(*pos)
    return ship


def escape_pod(root):
    pod = root.attachNewNode("pod")
    V, F = M.lathe([(0.0, 0.7), (0.3, 0.55), (0.42, 0.2), (0.42, -0.4), (0.3, -0.6), (0.0, -0.65)], 18, "y")
    M.part(pod, V, F, (1, 1, 1), orient="y", vcol=M.paint((0.15, 0.15, 0.16), (0.7, 0.7, 0.72), -0.4, 0.4))
    for k in range(3):
        Vb, Fb = M.box(0.9, 0.06, 0.06)
        M.part(pod, Vb, Fb, (0.9, 0.5, 0.1), pos=(0, -0.3 + k * 0.3, 0), hpr=(0, 0, k * 60))
    M.glow(pod, (0, -0.75, 0), 0.4, (1.0, 0.25, 0.1, 0.9))
    M.glow(pod, (0, 0.35, 0.3), 0.2, (0.3, 1.0, 0.4, 0.9))
    return pod


class Booms:
    """Explosions that a shot updates every frame."""

    def __init__(self, app, root):
        self.app, self.root, self.list = app, root, []
        self.rng = np.random.default_rng()

    def add(self, pos, size):
        self.list.append(Explosion(self.root, self.app.world.fx_tpl, pos, size, self.rng, 3.0, 2.0))

    def update(self, dt):
        self.list = [fx for fx in self.list if fx.update(dt)]
