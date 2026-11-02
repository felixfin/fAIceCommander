"""Screen overlays attached to the game camera (so they only cover the play area):
the hypno light and blood/brain splatter on the 'screen glass'."""
import math

import numpy as np
from panda3d.core import CardMaker, Point3, SamplerState, Texture, TransparencyAttrib

DIST = 2.0  # distance in front of the camera


def _rgba_texture(name, rgba):
    h, w = rgba.shape[:2]
    tex = Texture(name)
    tex.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgba)
    bgra = np.uint8(np.clip(rgba[::-1][..., [2, 1, 0, 3]], 0, 1) * 255)  # Panda wants BGRA, bottom-up
    tex.setRamImage(np.ascontiguousarray(bgra).tobytes())
    tex.setWrapU(SamplerState.WM_clamp)
    tex.setWrapV(SamplerState.WM_clamp)
    return tex


def _card(parent, half, tex, sort):
    cm = CardMaker("overlay")
    cm.setFrame(-half, half, -half, half)
    card = parent.attachNewNode(cm.generate())
    card.setTexture(tex)
    card.setTransparency(TransparencyAttrib.MAlpha)
    card.setLightOff(1)
    card.setShaderOff(1)
    card.setDepthTest(False)
    card.setDepthWrite(False)
    card.setBin("fixed", sort)
    card.setY(DIST)
    return card


def spiral_texture(n=512):
    y, x = np.mgrid[-1:1:n * 1j, -1:1:n * 1j]
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    arms = 0.5 + 0.5 * np.sin(5 * th + 16 * r)
    rings = 0.5 + 0.5 * np.sin(30 * r)
    v = arms ** 2 * (0.6 + 0.4 * rings)
    col = np.stack([0.55 + 0.45 * v, 0.2 + 0.75 * v ** 3, np.ones_like(v)], -1)
    alpha = np.clip(0.35 + 0.65 * v, 0, 1) * np.clip(1.4 - r * 0.5, 0, 1)
    return _rgba_texture("hypno", np.concatenate([col, alpha[..., None]], -1))


class HypnoOverlay:
    def __init__(self, camera):
        self.card = _card(camera, 3.0, spiral_texture(), 50)
        self.card.hide()
        self.t = 0.0

    def update(self, dt, alpha):
        self.t += dt
        if alpha <= 0.01:
            self.card.hide()
            return
        self.card.show()
        self.card.setR(self.t * 25)
        s = 1.0 + 0.06 * math.sin(self.t * 1.3)
        self.card.setScale(s)
        self.card.setColorScale(1, 1, 1, alpha)


def splatter_texture(seed, n=256):
    """Blood with brain matter: union of soft discs, flung droplets with streaks, drips, pink lumps."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n].astype(float)
    c = n / 2
    blood = np.zeros((n, n))
    lumps = np.zeros((n, n))

    def disc(cx, cy, r, soft=1.5):
        return np.clip((r - np.hypot(x - cx, y - cy)) / soft, 0, 1)

    for _ in range(14):
        blood = np.maximum(blood, disc(c + rng.normal(0, n * 0.08), c + rng.normal(0, n * 0.08), rng.uniform(0.07, 0.16) * n))
    for _ in range(26):
        ang = rng.uniform(0, 2 * np.pi)
        dist = rng.uniform(0.2, 0.45) * n
        r = rng.uniform(0.008, 0.03) * n
        px, py = c + np.cos(ang) * dist, c + np.sin(ang) * dist
        blood = np.maximum(blood, disc(px, py, r))
        for k in np.linspace(0.3, 1.0, 8):  # streak towards the centre
            blood = np.maximum(blood, disc(c + np.cos(ang) * dist * k, c + np.sin(ang) * dist * k, r * 0.45 * k))
    for _ in range(5):
        dx = c + rng.uniform(-0.12, 0.12) * n
        ln = rng.uniform(0.1, 0.35) * n
        w = rng.uniform(0.008, 0.016) * n
        drip = np.clip((w - np.abs(x - dx)) / 1.2, 0, 1) * ((y > c) & (y < c + ln))
        blood = np.maximum(blood, np.maximum(drip, disc(dx, c + ln, w * 1.6)))
    for _ in range(9):
        lumps = np.maximum(lumps, disc(c + rng.normal(0, n * 0.1), c + rng.normal(0, n * 0.1), rng.uniform(0.02, 0.045) * n, 2.5))
    shade = 0.75 + 0.25 * np.sin(x * 0.3 + y * 0.21) * np.sin(y * 0.17)
    rgb = np.stack([0.42 * shade, 0.0 * shade, 0.03 * shade], -1)
    pink = np.stack([0.9 * shade, 0.5 * shade, 0.56 * shade], -1)
    rgb = rgb * (1 - lumps[..., None]) + pink * lumps[..., None]
    gloss = (np.sin(x * 0.9) * np.sin(y * 0.7) > 0.93) * blood * 0.5  # wet highlights
    rgb = np.clip(rgb + gloss[..., None], 0, 1)
    alpha = np.clip(np.maximum(blood * 0.9, lumps), 0, 1)
    return _rgba_texture(f"splatter{seed}", np.concatenate([rgb, alpha[..., None]], -1))


class SplatterOverlay:
    def __init__(self, camera, duration):
        self.camera = camera
        self.duration = duration
        self.textures = [splatter_texture(s) for s in range(3)]
        self.splats = []

    def add(self, render, world_pos, rng, size=0.42):
        p = self.camera.getRelativePoint(render, Point3(*world_pos))
        if p.y <= 0.1:
            return
        card = _card(self.camera, 0.5, self.textures[int(rng.integers(len(self.textures)))], 60)
        k = DIST / p.y
        card.setPos(p.x * k, DIST, p.z * k)
        card.setR(rng.uniform(0, 360))
        card.setScale(size * rng.uniform(0.85, 1.25))
        self.splats.append([card, 0.0])

    def update(self, dt):
        alive = []
        for entry in self.splats:
            card, t = entry
            t += dt
            entry[1] = t
            if t >= self.duration:
                card.removeNode()
                continue
            card.setZ(card.getZ() - dt * 0.015)  # slowly runs down the glass
            card.setAlphaScale(min(1.0, (self.duration - t) / 0.8))
            alive.append(entry)
        self.splats = alive

    def clear(self):
        for card, _ in self.splats:
            card.removeNode()
        self.splats = []
