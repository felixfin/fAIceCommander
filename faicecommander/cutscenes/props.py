"""Props for the cutscenes, built from the game's procedural models."""
import math

import numpy as np
from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, Point3, SamplerState, TextNode,
    Texture, TransparencyAttrib,
)

from ..render import models as M
from ..render.effects import Explosion


def look(app, pos, target):
    app.camera.setPos(*pos)
    app.camera.lookAt(Point3(*target))


def lerp(a, b, u):
    u = min(1.0, max(0.0, u))
    u = u * u * (3 - 2 * u)  # smoothstep
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def shake(pos, amount, rng):
    return tuple(p + rng.uniform(-amount, amount) for p in pos)


def cached_copy(root, name, build):
    """A copy of a set piece from the model cache (built - and cached - on first use). Building the
    props takes up to seconds and would freeze the picture at the cut; loading them takes milliseconds."""
    return M.cached(name, build).copyTo(root)


# ---------------------------------------------------------------- atmosphere

def smoke(root, pos, size, color=(0.05, 0.04, 0.04, 0.6)):
    """A soft, dark (alpha-blended, not additive) puff: smoke, fog banks, dust."""
    c = M.glow(root, pos, size, color)
    c.clearAttrib(M.ColorBlendAttrib.getClassType())
    c.setTransparency(TransparencyAttrib.MAlpha)
    c.setBin("transparent", 30)
    return c


class Drifters:
    """Small particles (embers, dust, sparks) that drift through a box and wrap around."""

    def __init__(self, root, n, lo, hi, vel, color, size=(0.03, 0.08), seed=1, flicker=0.0):
        self.rng = np.random.default_rng(seed)
        self.lo, self.hi = np.array(lo, float), np.array(hi, float)
        self.pos = self.rng.uniform(self.lo, self.hi, (n, 3))
        self.vel = np.array(vel, float) * self.rng.uniform(0.6, 1.4, (n, 1))
        self.flicker = flicker
        self.nodes = [M.glow(root, tuple(p), self.rng.uniform(*size), color) for p in self.pos]

    def update(self, dt, t):
        self.pos += self.vel * dt + self.rng.normal(0, 0.15, self.pos.shape) * dt
        span = self.hi - self.lo
        self.pos = self.lo + (self.pos - self.lo) % span
        for i, (node, p) in enumerate(zip(self.nodes, self.pos)):
            node.setPos(*p)
            if self.flicker:
                node.setAlphaScale(1 - self.flicker * (0.5 + 0.5 * math.sin(t * 9 + i * 1.7)))


def beam(root, a, b, color, width=0.05):
    """A straight glowing beam from a to b (lasers, bombardment, scanner lines)."""
    a, b = np.array(a, float), np.array(b, float)
    node = root.attachNewNode("beam")
    for w, alpha in ((width, 1.0), (width * 3, 0.35)):
        V, F = M.lathe([(w, 0.0), (w, 1.0)], 8, "y")
        M.part(node, V, F, (*color[:3], alpha), additive=True, orient=None)
    node.setPos(*a)
    node.lookAt(Point3(*b))
    node.setScale(1, float(np.linalg.norm(b - a)), 1)
    return node


# ---------------------------------------------------------------- worlds

def burning_planet(root, radius=7.0):
    """A world on fire: black crust, glowing magma veins at two scales, a hot atmosphere halo."""
    return cached_copy(root, f"planet-{radius:g}", lambda r: _burning_planet(r, radius))


def _value_noise(P, octaves, seed, base=2.0, gain=0.55):
    """Fractal 3D value noise at points P (n, 3) - smooth, seamless on a sphere."""
    rng = np.random.default_rng(seed)
    total, amp, norm = np.zeros(len(P)), 1.0, 0.0
    for o in range(octaves):
        f = base * 2 ** o
        lattice = rng.random((32, 32, 32))
        q = P * f + rng.uniform(0, 32, 3)
        i0 = np.floor(q).astype(int)
        u = q - i0
        u = u * u * (3 - 2 * u)
        acc = np.zeros(len(P))
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                    acc += w * lattice[(i0[:, 0] + dx) % 32, (i0[:, 1] + dy) % 32, (i0[:, 2] + dz) % 32]
        total += acc * amp
        norm += amp
        amp *= gain
    return total / norm


def _planet_textures(w=2048, h=1024, seed=4):
    """Equirectangular crust (albedo) and lava (emission) maps from noise sampled on the sphere."""
    lon = (np.arange(w) + 0.5) / w * 2 * np.pi
    lat = (np.arange(h) + 0.5) / h * np.pi - np.pi / 2
    LON, LAT = np.meshgrid(lon, lat)
    P = np.stack([np.cos(LAT) * np.cos(LON), np.cos(LAT) * np.sin(LON), np.sin(LAT)], -1).reshape(-1, 3)
    rock = _value_noise(P, 6, seed)
    warp = _value_noise(P * 1.0, 3, seed + 1)
    ridge = 1 - np.abs(_value_noise(P + warp[:, None] * 0.35, 5, seed + 2, base=3.0) * 2 - 1)  # 1 on the crack lines
    cracks = np.clip((ridge - 0.86) / 0.14, 0, 1) ** 1.6
    fields = np.clip((_value_noise(P, 3, seed + 3, base=1.5) - 0.6) / 0.2, 0, 1)            # burning regions
    heat = np.clip(cracks + fields * (0.4 + 0.6 * rock), 0, 1)
    crust = np.stack([0.11 + 0.12 * rock, 0.085 + 0.09 * rock, 0.075 + 0.07 * rock], -1) * (1 - 0.6 * heat[:, None])
    lava = np.stack([heat * 1.0, heat ** 1.5 * 0.45, heat ** 3 * 0.12], -1)

    def tex(name, rgb):
        img = np.clip(rgb.reshape(h, w, 3), 0, 1)
        t = Texture(name)
        t.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgb)
        t.setRamImage(np.ascontiguousarray((img[::-1, :, ::-1] * 255).astype(np.uint8)).tobytes())
        t.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        t.setAnisotropicDegree(8)
        return t
    return tex("crust", crust), tex("lava", lava)


def _uv_sphere(parent, radius, tex, unlit=False, additive=False, nlat=96, nlon=192):
    vd = GeomVertexData("sphere", GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
    vw, nw, tw = GeomVertexWriter(vd, "vertex"), GeomVertexWriter(vd, "normal"), GeomVertexWriter(vd, "texcoord")
    for i in range(nlat + 1):
        la = -math.pi / 2 + math.pi * i / nlat
        for j in range(nlon + 1):
            lo = 2 * math.pi * j / nlon
            n = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
            vw.addData3(n[0] * radius, n[1] * radius, n[2] * radius)
            nw.addData3(*n)
            tw.addData2(j / nlon, i / nlat)
    prim = GeomTriangles(Geom.UHStatic)
    row = nlon + 1
    for i in range(nlat):
        for j in range(nlon):
            a, b = i * row + j, i * row + j + 1
            prim.addVertices(a, b, a + row)
            prim.addVertices(b, b + row, a + row)
    g = Geom(vd)
    g.addPrimitive(prim)
    node = GeomNode("sphere")
    node.addGeom(g)
    np_ = parent.attachNewNode(node)
    np_.setTexture(tex)
    M.style(np_, unlit=unlit, additive=additive)
    return np_


def _burning_planet(root, radius):
    planet = root.attachNewNode("planet")
    crust, lava = _planet_textures()
    _uv_sphere(planet, radius, crust)                               # lit rock: day and night side
    _uv_sphere(planet, radius * 1.002, lava, additive=True)         # the cracks glow everywhere
    rng = np.random.default_rng(4)
    halo = planet.attachNewNode("halo")
    Va, Fa = M.annulus(radius * 0.98, radius * 1.18, 128, 4)
    Va = Va[:, [0, 2, 1]]  # into the x-z plane: the billboard turns that towards the camera

    def halo_col(p):
        u = min(1.0, max(0.0, (math.hypot(p[0], p[2]) / radius - 0.98) / 0.2))
        return (1.0, 0.35 + 0.2 * (1 - u), 0.08, 0.55 * (1 - u) ** 1.5)

    M.part(halo, Va, Fa, (1, 1, 1), additive=True, orient=None, vcol=halo_col)
    halo.setBillboardPointEye()
    M.glow(planet, (0, 0, 0), radius * 3.2, (1.0, 0.25, 0.04, 0.35))
    for _ in range(12):  # smoke columns rising from the fires
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        smoke(planet, tuple(d * radius * 1.05), radius * rng.uniform(0.12, 0.25), (0.06, 0.03, 0.02, 0.55))
    return planet


def human(root, pos, female=False, collar=(1.0, 0.1, 0.05), skin=None):
    """A man or a woman with a slave collar (cached models; skin tone varies along the row)."""
    if skin is None:
        skin = int(abs(pos[0]) * 7 + pos[1] * 3) % len(M.SKIN_TONES)
    key = "-".join(f"{c:.2f}" for c in collar)
    node = cached_copy(root, f"human-{int(female)}-{skin}-{key}",
                       lambda r: M.build_human(r, female=female, skin=skin, collar=collar))
    node.setPos(*pos)
    node.setColorScale(0.8, 0.75, 0.75, 1)  # dim, unhealthy light
    return node


def catlien(root, scale=1.0, queen=False):
    node = cached_copy(root, f"catlien-{int(queen)}", lambda r: M.build_catlien(r, 1.0, queen=queen))
    node.setScale(scale)
    return node


def helmet(root):
    return cached_copy(root, "helmet", M.build_helmet)


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


def slave_hall(root, depth=14.0):
    """A dark, pillared hall: wet floor, columns with chains, red light far behind."""
    return cached_copy(root, "slave-hall", lambda r: _slave_hall(r, depth))


def _slave_hall(root, depth):
    V, F = M.box(1, 1, 1)
    M.part(root, V, F, (0.03, 0.025, 0.025), pos=(0, depth / 2, -0.05), scale=(16, depth + 6, 0.1), smooth=None)
    rng = np.random.default_rng(6)
    for k in range(6):
        y = -1.0 + k * depth / 5
        for x in (-4.2, 4.2):
            col = M.paint((0.02, 0.02, 0.025), (0.12, 0.1, 0.1), 0.0, 6.0, grime=0.4)
            Vc, Fc = M.lathe([(0.55, 0.0), (0.45, 0.4), (0.38, 0.6), (0.38, 5.4), (0.5, 5.8), (0.6, 6.2)], 10, "z")
            M.part(root, Vc, Fc, (1, 1, 1), pos=(x, y, 0), orient="z", vcol=col)
            for j in range(2):  # chains hanging from the columns
                pts = [(x * 0.9, y, 5.0), (x * 0.82 + rng.uniform(-0.2, 0.2), y + 0.4, 3.3 - j),
                       (x * 0.86, y + 0.7, 2.4 - j * 0.6)]
                for p0, p1 in zip(M._bezier(pts + [pts[-1]], 14)[:-1], M._bezier(pts + [pts[-1]], 14)[1:]):
                    Vl, Fl = M.lathe([(0.035, 0), (0.035, 0.05)], 6, "y")
                    link = M.part(root, Vl, Fl, (0.12, 0.11, 0.1), orient="y")
                    link.setPos(*p0)
                    link.lookAt(Point3(*p1))
    for _ in range(8):  # fog lying on the floor
        smoke(root, (rng.uniform(-5, 5), rng.uniform(1, depth), 0.3), rng.uniform(2.0, 3.5), (0.1, 0.03, 0.03, 0.35))
    root.flattenStrong()


def empty_ship(parent):
    """The FaceCommander ship without a commander in the cockpit (cached)."""
    return M.cached("ship-empty", lambda r: M.build_ship(r, brain=False)).getChild(0).copyTo(parent)


def human_ship(app, root, pos, grey=True):
    """A ship of Honor's fleet (the game's ship model, without a commander)."""
    if not hasattr(app, "_cut_ship_tpl"):
        app._cut_ship_tpl = empty_ship(app.hidden)
    ship = app._cut_ship_tpl.copyTo(root)
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
    beacon = M.glow(pod, (0, 0.35, 0.3), 0.3, (1.0, 0.1, 0.05, 0.9))
    beacon.setName("beacon")
    return pod


# ---------------------------------------------------------------- med bay and hangar

class RobotArm:
    """A three-segment surgical / welding arm on a base; angles are set per frame."""

    def __init__(self, root, pos, color=(0.7, 0.72, 0.75), tool=(0.4, 1.0, 0.9)):
        key = "-".join(f"{c:.2f}" for c in (*color, *tool))
        self.base = cached_copy(root, f"arm-{key}", lambda r: self._build(r, color, tool)).find("arm")
        self.base.setPos(*pos)
        self.joints = [self.base.find(f"**/j{k}") for k in range(3)]

    @staticmethod
    def _build(root, color, tool):
        base = root.attachNewNode("arm")
        paint = M.paint((0.08, 0.08, 0.09), color, -0.1, 0.1, grime=0.15)
        Vb, Fb = M.lathe([(0.28, 0.0), (0.24, 0.12), (0.14, 0.2)], 16, "z")
        M.part(base, Vb, Fb, (1, 1, 1), orient="z", vcol=paint)
        parent, offset = base, 0.2
        Vi, Fi = M.icosphere(1)
        for k, ln in enumerate((0.9, 0.75, 0.35)):
            j = parent.attachNewNode(f"j{k}")
            j.setZ(offset)
            r0, r1 = 0.08 - k * 0.015, 0.06 - k * 0.012
            Vs, Fs = M.sweep([(0.0, r0, r0, 0, 3), (ln, r1, r1, 0, 3)], 12, "x")
            M.part(j, Vs[:, [1, 2, 0]], Fs, (1, 1, 1), orient="center", vcol=paint)  # segment along local z
            M.part(j, Vi * (0.1 - k * 0.02), Fi, (0.15, 0.15, 0.16))
            parent, offset = j, ln
        tip = parent.attachNewNode("tip")
        tip.setZ(offset)
        M.glow(tip, (0, 0, 0), 0.18, (*tool, 0.9))

    def pose(self, yaw, a0, a1, a2):
        self.base.setH(yaw)
        for j, a in zip(self.joints, (a0, a1, a2)):
            j.setP(a)


def operating_table(root):
    """The table, a body under a sheet, the head clamp, monitors."""
    return cached_copy(root, "operating-table", _operating_table)


def _operating_table(root):
    V, F = M.box(1, 1, 1)
    M.part(root, V, F, (0.3, 0.32, 0.34), pos=(0, 0, 0.85), scale=(1.0, 2.4, 0.1), smooth=None)
    M.part(root, V, F, (0.12, 0.12, 0.13), pos=(0, 0, 0.42), scale=(0.3, 0.3, 0.84), smooth=None)
    sheet = M.paint((0.35, 0.4, 0.42), (0.75, 0.82, 0.85), 0.85, 1.25, grime=0.2)
    body = [(-1.1, 0.25, 0.1, 0.0, 2.2), (-0.4, 0.3, 0.16, 0.02, 2.4), (0.2, 0.38, 0.2, 0.04, 2.6),
            (0.7, 0.3, 0.16, 0.03, 2.4), (0.95, 0.12, 0.08, 0.01, 2.0)]
    Vb, Fb = M.sweep(body, 20)
    M.part(root, Vb, Fb, (1, 1, 1), pos=(0, 0, 0.95), orient=None, vcol=sheet)
    for x in (-0.18, 0.18):  # dark stains seeping through the sheet
        M.part(root, *M.icosphere(1), (0.3, 0.0, 0.02), pos=(x, 0.55, 1.12), scale=(0.12, 0.08, 0.02))
    clamp = M.paint((0.05, 0.05, 0.06), (0.4, 0.42, 0.45), 0.9, 1.4)
    Vc, Fc = M.lathe([(0.25, 0.0), (0.27, 0.05), (0.27, 0.25), (0.22, 0.3)], 18, "y")
    M.part(root, Vc, Fc, (1, 1, 1), pos=(0, 1.0, 1.05), orient="y", vcol=clamp)


def brain(root, scale):
    """A bare brain (cached)."""
    return cached_copy(root, f"brain-{scale:g}", lambda r: M.build_brain(r, scale, aura=False)).getChild(0)


def brain_jar(root, pos):
    """The commander's brain floating in a glowing tank with bubbles."""
    jar = cached_copy(root, "jar", _brain_jar)
    jar.setPos(*pos)
    return jar, jar.find("**/brain")


def _brain_jar(jar):
    Vg, Fg = M.lathe([(0.0, 0.0), (0.32, 0.0), (0.34, 0.05), (0.34, 0.75), (0.3, 0.8), (0.0, 0.8)], 24, "z")
    M.part(jar, Vg, Fg, (0.4, 1.0, 0.7, 0.22), orient="z", alpha=True, two_sided=True)
    Vc, Fc = M.lathe([(0.37, -0.05), (0.38, 0.05), (0.36, 0.1)], 24, "z")
    M.part(jar, Vc, Fc, (0.25, 0.25, 0.27), orient="z")
    M.part(jar, Vc, Fc, (0.25, 0.25, 0.27), pos=(0, 0, 0.75), orient="z")
    M.build_brain(jar, 0.2, aura=False).setPos(0, 0, 0.42)
    M.glow(jar, (0, 0, 0.4), 0.9, (0.4, 1.0, 0.7, 0.4))


def hangar(root):
    """A dim shipyard bay: floor grid, side walls with lit windows, two gantry cranes."""
    return cached_copy(root, "hangar", _hangar)


def _hangar(root):
    V, F = M.box(1, 1, 1)
    floor = M.paint((0.03, 0.035, 0.04), (0.16, 0.17, 0.19), -0.1, 0.1, grime=0.5)
    M.part(root, V, F, (1, 1, 1), pos=(0, 0, -0.75), scale=(20, 24, 0.1), vcol=floor, smooth=None)
    for k in range(-6, 7):  # floor guide lines
        M.part(root, V, F, (0.7, 0.55, 0.1), pos=(k * 1.5, 0, -0.69), scale=(0.03, 24, 0.01), unlit=True, smooth=None)
    for x in (-7, 7):
        M.part(root, V, F, (1, 1, 1), pos=(x, 0, 3), scale=(0.3, 24, 7.5), vcol=M.paint((0.03, 0.03, 0.035),
               (0.15, 0.15, 0.17), -0.5, 0.5, grime=0.4), smooth=None)
        for j in range(8):
            M.part(root, V, F, (1.0, 0.75, 0.4), pos=(x * 0.98, -9 + j * 2.5, 4.5), scale=(0.05, 1.2, 0.35),
                   unlit=True, smooth=None)
    for y in (-2.5, 2.5):  # gantries over the ship
        M.part(root, V, F, (0.18, 0.18, 0.2), pos=(0, y, 4.0), scale=(14, 0.3, 0.3), smooth=None)
        for k in range(10):
            M.part(root, V, F, (0.95, 0.75, 0.1) if k % 2 else (0.05, 0.05, 0.05), pos=(-6.3 + k * 1.4, y, 3.8),
                   scale=(1.4, 0.32, 0.05), smooth=None)
    for x in (-4, 0, 4):
        M.glow(root, (x, 0, 4.6), 2.5, (1.0, 0.85, 0.6, 0.25))  # work lamps
    root.flattenStrong()


class Booms:
    """Explosions that a shot updates every frame."""

    def __init__(self, app, root):
        self.app, self.root, self.list = app, root, []
        self.rng = np.random.default_rng()

    def add(self, pos, size):
        self.list.append(Explosion(self.root, self.app.world.fx_tpl, pos, size, self.rng, 3.0, 2.0))

    def update(self, dt):
        self.list = [fx for fx in self.list if fx.update(dt)]
