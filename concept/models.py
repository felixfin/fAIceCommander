"""Procedural low-poly models for fAIceCommander 3D (concept stage).

All geometry is generated in code - no external assets, no licensing issues.
Coordinate system (Panda3D): X right, Y forward (= up the screen), Z up.
"""
import math

import numpy as np
from panda3d.core import (
    ColorBlendAttrib, CardMaker, Geom, GeomNode, GeomTriangles, GeomVertexData,
    GeomVertexFormat, GeomVertexWriter, NodePath, PNMImage, Texture, TransparencyAttrib,
)


# ---------------------------------------------------------------- mesh core

class Mesh:
    """Collects flat-shaded triangles (retro low-poly look)."""

    def __init__(self):
        self.tris = []  # ([a, b, c], [ca, cb, cc])

    def add_mesh(self, V, F, col=(1, 1, 1, 1), orient="center", center=None, vcol=None):
        V = np.asarray(V, float)
        if orient == "center" and center is None:
            center = V.mean(0)
        for i, f in enumerate(F):
            fc = col[i] if isinstance(col, list) else col
            for k in range(1, len(f) - 1):
                ids = [f[0], f[k], f[k + 1]]
                a, b, c = V[ids[0]], V[ids[1]], V[ids[2]]
                if orient is not None:
                    n = np.cross(b - a, c - a)
                    cen = (a + b + c) / 3
                    if orient == "center":
                        ref = center
                    elif orient == "y":
                        ref = np.array([0, cen[1], 0])
                    elif orient == "z":
                        ref = np.array([0, 0, cen[2]])
                    else:
                        ref = np.array([cen[0], 0, 0])
                    if np.dot(n, cen - ref) < 0:
                        ids = [ids[0], ids[2], ids[1]]
                cols = [_rgba(vcol(V[j]) if vcol else fc) for j in ids]
                self.tris.append(([V[j] for j in ids], cols))
        return self

    def node(self, name="mesh"):
        vd = GeomVertexData(name, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        vw, nw, cw = (GeomVertexWriter(vd, c) for c in ("vertex", "normal", "color"))
        prim = GeomTriangles(Geom.UHStatic)
        i = 0
        for (a, b, c), cols in self.tris:
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            if ln < 1e-12:
                continue
            n = n / ln
            for p, col in zip((a, b, c), cols):
                vw.addData3(*p)
                nw.addData3(*n)
                cw.addData4(*col)
            prim.addVertices(i, i + 1, i + 2)
            i += 3
        g = Geom(vd)
        g.addPrimitive(prim)
        gn = GeomNode(name)
        gn.addGeom(g)
        return NodePath(gn)


def _rgba(c):
    return tuple(c) if len(c) == 4 else (*c, 1.0)


def part(parent, V, F, col, pos=(0, 0, 0), hpr=(0, 0, 0), scale=1, orient="center",
         unlit=False, alpha=False, additive=False, vcol=None, two_sided=False, name="part"):
    np_ = Mesh().add_mesh(V, F, col, orient=orient, vcol=vcol).node(name)
    np_.reparentTo(parent)
    np_.setPos(*pos)
    np_.setHpr(*hpr)
    np_.setScale(*(scale if isinstance(scale, tuple) else (scale,) * 3))
    style(np_, unlit, alpha, additive, two_sided)
    return np_


def style(np_, unlit=False, alpha=False, additive=False, two_sided=False):
    if unlit:
        np_.setLightOff(1)
    if two_sided:
        np_.setTwoSided(True)
    if alpha:
        np_.setTransparency(TransparencyAttrib.MAlpha)
        np_.setDepthWrite(False)
        np_.setBin("transparent", 10)
    if additive:
        np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd,
                                            ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        np_.setDepthWrite(False)
        np_.setLightOff(1)
        np_.setTwoSided(True)
        np_.setBin("fixed", 20)


def neon_edges(np_, color, thickness=1.3):
    w = np_.copyTo(np_.getParent())
    w.setRenderModeWireframe()
    w.setRenderModeThickness(thickness)
    w.setLightOff(1)
    w.setColor(*_rgba(color), 1)
    w.setDepthOffset(2)
    return w


# ---------------------------------------------------------------- primitives

def icosphere(sub=1):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t),
         (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
         (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
         (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(sub):
        cache, nf = {}, []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = v[a] + v[b]
                v.append(m / np.linalg.norm(m))
                cache[k] = len(v) - 1
            return cache[k]

        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return np.array(v), f


def hemisphere(sub=2):
    V, F = icosphere(sub)
    return V, [f for f in F if all(V[i][2] > -0.05 for i in f)]


def box(sx, sy, sz):
    x, y, z = sx / 2, sy / 2, sz / 2
    V = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    F = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return np.array(V, float), F


def lathe(profile, seg=8, axis="y", phase=0.0):
    """Surface of revolution. profile: [(radius, height), ...]."""
    V, F = [], []
    n = len(profile)
    for r, h in profile:
        for j in range(seg):
            a = 2 * math.pi * j / seg + phase
            x, z = r * math.cos(a), r * math.sin(a)
            V.append((x, h, z) if axis == "y" else (x, z, h))
    for i in range(n - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            F.append((a, b, b + seg, a + seg))
    for end, idx in ((0, 0), (n - 1, n - 1)):
        r, h = profile[idx]
        if r > 0:
            F.append(tuple(range(idx * seg, idx * seg + seg)))
    return np.array(V, float), F


def loft(poly, layers):
    """Stack scaled copies of a convex 2D polygon. layers: [(scale, z, (dx, dy)?), ...]."""
    V, F = [], []
    n = len(poly)
    for L in layers:
        s, z = L[0], L[1]
        ox, oy = L[2] if len(L) > 2 else (0, 0)
        V += [(x * s + ox, y * s + oy, z) for x, y in poly]
    for i in range(len(layers) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            F.append((a, b, b + n, a + n))
    F.append(tuple(range(n)))
    F.append(tuple(range((len(layers) - 1) * n, len(layers) * n)))
    return np.array(V, float), F


def prism(poly, t):
    return loft(poly, [(1, -t / 2), (1, t / 2)])


def pyramid(base_pts, apex):
    V = [(*p, 0) for p in base_pts] + [apex]
    return np.array(V, float), [(0, 1, 2), (0, 1, 3), (1, 2, 3), (2, 0, 3)]


def annulus(r0, r1, seg=96, rings=3, z=0.0):
    V, F = [], []
    radii = np.linspace(r0, r1, rings)
    for r in radii:
        for j in range(seg):
            a = 2 * math.pi * j / seg
            V.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(rings - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            F.append((a, b, b + seg, a + seg))
    return np.array(V, float), F


_GLOW = None


def glow_texture():
    global _GLOW
    if _GLOW is None:
        n = 128
        img = PNMImage(n, n, 4)
        for y in range(n):
            for x in range(n):
                r = math.hypot((x + 0.5) / n - 0.5, (y + 0.5) / n - 0.5) * 2
                a = max(0.0, math.exp(-(r / 0.42) ** 2) - 0.004)
                img.setXelA(x, y, 1, 1, 1, a)
        _GLOW = Texture("glow")
        _GLOW.load(img)
    return _GLOW


def glow(parent, pos, size, color):
    cm = CardMaker("glow")
    cm.setFrame(-1, 1, -1, 1)
    c = parent.attachNewNode(cm.generate())
    c.setTexture(glow_texture())
    c.setPos(*pos)
    c.setScale(size)
    c.setColor(*_rgba(color))
    c.setBillboardPointEye()
    style(c, additive=True)
    return c


# ---------------------------------------------------------------- models

GUNMETAL = (0.40, 0.43, 0.48)
RUST = (0.72, 0.33, 0.14)
OLIVE = (0.42, 0.45, 0.36)
DARK = (0.16, 0.17, 0.2)
GREEN_LASER = (0.35, 1.0, 0.25)
CYAN = (0.3, 0.85, 1.0)


def brain_mesh(sub=3, seed=1, pink=(0.93, 0.52, 0.62)):
    V, F = icosphere(sub)
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    d = 0.055 * np.sin(17 * y + 5 * np.sin(6 * z)) * np.cos(15 * z + 4 * np.sin(7 * y)) \
        + 0.03 * np.sin(23 * x + 9 * z)
    V = V * (1 + d)[:, None]
    V[:, 0] += np.sign(x) * 0.07  # longitudinal fissure
    V *= np.array([0.82, 1.05, 0.72])
    cols = []
    for f in F:
        dd = d[list(f)].mean()
        k = 0.8 + 3.2 * dd
        cols.append(tuple(min(1, c * k) for c in pink))
    return V, F, cols


def build_brain(parent, scale=1.0, aura=True):
    root = parent.attachNewNode("brain")
    V, F, cols = brain_mesh()
    part(root, V, F, cols, orient="center")
    Vc, Fc = icosphere(2)
    part(root, Vc * np.array([0.5, 0.35, 0.3]), Fc, (0.85, 0.45, 0.55), pos=(0, -0.75, -0.35))
    Vs, Fs = lathe([(0.14, 0), (0.11, -0.6)], 8, axis="z")
    part(root, Vs, Fs, (0.8, 0.5, 0.55), pos=(0, -0.45, -0.3), orient="z")
    if aura:
        glow(root, (0, 0, 0), 2.6, (0.75, 0.35, 1.0, 0.55))
        rng = np.random.default_rng(3)
        Vi, Fi = icosphere(1)
        for _ in range(14):
            p = rng.normal(size=3)
            p = p / np.linalg.norm(p) * rng.uniform(1.2, 1.9)
            part(root, Vi * 0.03, Fi, (0.6, 0.95, 1.0), pos=tuple(p), unlit=True)
            glow(root, tuple(p), 0.15, (0.5, 0.8, 1.0, 0.9))
    root.setScale(scale)
    return root


def build_ship(parent):
    """FaceCommander: patchwork warship built from salvaged hulls, brain under a glass dome."""
    root = parent.attachNewNode("ship")
    hull_prof = [(0.0, 2.5), (0.22, 1.95), (0.46, 1.1), (0.58, 0.1), (0.54, -0.9), (0.42, -1.5), (0.3, -1.65)]
    V, F = lathe(hull_prof, 6, "y", phase=math.pi / 6)
    part(root, V, F, GUNMETAL, scale=(1, 1, 0.72), orient="y")
    # salvaged plates in mismatching colours
    rng = np.random.default_rng(7)
    for (px, py, sx, sy, col) in [(0.0, 0.2, 0.5, 0.7, RUST), (0.18, -0.7, 0.35, 0.5, OLIVE),
                                  (-0.2, -0.45, 0.3, 0.6, (0.33, 0.38, 0.52)), (0.0, 1.55, 0.25, 0.4, RUST)]:
        Vb, Fb = box(sx, sy, 0.06)
        part(root, Vb, Fb, col, pos=(px, py, 0.36), hpr=(rng.uniform(-6, 6), 0, 0))
    # wings: right one rusty orange (homage to the 2D original), left one faded olive
    wing = [(0.45, 0.7), (2.05, -0.85), (2.15, -1.35), (0.45, -1.2)]
    for sgn, col in ((1, RUST), (-1, OLIVE)):
        pts = [(sgn * x, y) for x, y in wing]
        if sgn < 0:
            pts = pts[::-1]
        Vw, Fw = prism(pts, 0.09)
        part(root, Vw, Fw, col, hpr=(0, 0, -sgn * 7))
        for k in range(3):  # hazard stripes
            Vs, Fs = box(0.12, 0.42, 0.02)
            part(root, Vs, Fs, (0.95, 0.75, 0.1) if k % 2 == 0 else (0.08, 0.08, 0.08),
                 pos=(sgn * (1.2 + k * 0.14), -0.75 - k * 0.1, 0.08), hpr=(sgn * 30, 0, -sgn * 7))
        # wingtip laser cannon
        Vc, Fc = lathe([(0.07, 0.6), (0.09, 0.0), (0.09, -0.5)], 6, "y")
        part(root, Vc, Fc, DARK, pos=(sgn * 2.1, -0.75, 0.0), orient="y")
        Vt, Ft = icosphere(1)
        part(root, Vt * 0.07, Ft, GREEN_LASER, pos=(sgn * 2.1, -0.12, 0.0), unlit=True)
        glow(root, (sgn * 2.1, -0.1, 0.0), 0.35, (*GREEN_LASER, 0.9))
        # engine nacelle
        Vn, Fn = lathe([(0.17, 0.25), (0.28, -0.15), (0.3, -1.2), (0.25, -1.75)], 8, "y")
        part(root, Vn, Fn, (0.3, 0.32, 0.36), pos=(sgn * 0.68, -0.25, -0.08), orient="y")
        Vd, Fd = lathe([(0.21, 0), (0.0, -0.01)], 8, "y")
        part(root, Vd, Fd, CYAN, pos=(sgn * 0.68, -2.01, -0.08), unlit=True, orient=None, two_sided=True)
        for ln, a in ((1.1, 0.45), (0.65, 0.7)):
            Vf, Ff = lathe([(0.2, 0), (0.0, -ln)], 10, "y")
            part(root, Vf, Ff, (0.35, 0.8, 1.0, a), pos=(sgn * 0.68, -2.02, -0.08), additive=True, orient=None,
                 vcol=lambda p, a=a, ln=ln: (0.4 + 0.6 * (1 + p[1] / ln), 0.85, 1.0, a * (1 + p[1] / ln)))
        glow(root, (sgn * 0.68, -2.1, -0.08), 0.7, (0.4, 0.8, 1.0, 0.9))
        # nuclear rocket under the wing
        Vr, Fr = lathe([(0.0, 0.45), (0.07, 0.3), (0.07, -0.35), (0.05, -0.4)], 6, "y")
        part(root, Vr, Fr, (0.85, 0.85, 0.8), pos=(sgn * 1.15, -0.55, -0.16), orient="y")
        part(root, Vt * 0.06, Ft, (1.0, 0.15, 0.1), pos=(sgn * 1.15, -0.1, -0.16), unlit=True)
    # dorsal fin
    Vf, Ff = prism([(-0.75, 0.25), (-1.55, 0.25), (-1.7, 0.95), (-1.35, 0.95)], 0.06)
    part(root, Vf[:, [2, 0, 1]], Ff, (0.5, 0.52, 0.55), pos=(0, 0, 0.05))
    # cockpit: glass dome with the commander's living brain
    build_brain(root, 0.26, aura=False).setPos(0, 0.95, 0.38)
    glow(root, (0, 0.95, 0.42), 0.7, (1.0, 0.4, 0.7, 0.5))
    Vh, Fh = hemisphere(2)
    part(root, Vh * 0.42, Fh, (0.55, 0.95, 1.0, 0.28), pos=(0, 0.95, 0.27), alpha=True, two_sided=True)
    Vr, Fr = lathe([(0.44, 0.0), (0.44, 0.06)], 12, "z")
    part(root, Vr, Fr, DARK, pos=(0, 0.95, 0.25), orient="z")
    return root


def asteroid_mesh(seed, radius, irregular=0.35, sub=2, base=(0.47, 0.43, 0.39)):
    rng = np.random.default_rng(seed)
    V, F = icosphere(sub)
    d = np.zeros(len(V))
    for _ in range(14):
        dv = rng.normal(size=3)
        dv /= np.linalg.norm(dv)
        amp = rng.uniform(-1, 0.6) * irregular
        w = rng.uniform(0.08, 0.35)
        d += amp * np.exp(-(1 - V @ dv) / w)
    d = np.clip(d, -0.45, 0.6)
    V = V * (1 + d)[:, None] * radius * rng.uniform(0.75, 1.25, size=3)
    cols = []
    for f in F:
        k = 0.85 + 0.6 * d[list(f)].mean() + rng.uniform(-0.07, 0.07)
        cols.append(tuple(np.clip(np.array(base) * k, 0, 1)))
    return V, F, cols, d


def build_asteroid(parent, seed, radius, category=1):
    root = parent.attachNewNode("asteroid")
    if category == 1:
        V, F, cols, _ = asteroid_mesh(seed, radius)
        part(root, V, F, cols)
    else:
        V, F, cols, d = asteroid_mesh(seed, radius, irregular=0.45, base=(0.42, 0.33, 0.3))
        part(root, V, F, cols)
        # glowing fracture lines: it will burst into category-1 fragments when shot
        rng = np.random.default_rng(seed + 99)
        planes = [rng.normal(size=3) for _ in range(2)]
        hot = [f for f in F if any(abs(np.dot(V[list(f)].mean(0) / radius, p / np.linalg.norm(p))) < 0.035
                                   for p in planes)]  # noqa
        part(root, V * 1.01, hot, (1.0, 0.45, 0.1), unlit=True, orient=None, two_sided=True)
        glow(root, (0, 0, 0), radius * 2.2, (1.0, 0.35, 0.05, 0.25))
    return root


CAT_PURPLE = (0.28, 0.16, 0.38)
MAGENTA = (1.0, 0.2, 0.85)
ACID = (0.65, 1.0, 0.15)


def _cat_eye(root, pos, size, slit_color=(0.02, 0.02, 0.02)):
    eye = [(0, 0.5), (0.55, 0.12), (0.55, -0.12), (0, -0.5), (-0.55, -0.12), (-0.55, 0.12)]
    Ve, Fe = prism([(x * size, y * size * 0.55) for x, y in eye], 0.04)
    part(root, Ve, Fe, ACID, pos=pos, unlit=True)
    Vp, Fp = box(0.07 * size, 0.5 * size, 0.05)
    part(root, Vp, Fp, slit_color, pos=(pos[0], pos[1], pos[2] + 0.02), unlit=True)
    glow(root, pos, size * 1.3, (*ACID, 0.6))


def build_fighter(parent):
    """Catlien space fighter. Faces -Y (towards the player); read from above it is a cat's face."""
    root = parent.attachNewNode("fighter")
    head = [(0, -1.15), (0.75, -0.85), (1.05, -0.1), (0.85, 0.65), (0.35, 0.95),
            (-0.35, 0.95), (-0.85, 0.65), (-1.05, -0.1), (-0.75, -0.85)]
    V, F = loft(head, [(0.85, -0.3), (1.0, 0.0), (0.92, 0.18), (0.6, 0.42)])
    body = part(root, V, F, CAT_PURPLE)
    neon_edges(body, (0.9, 0.2, 0.8, 0.35), 1.0)
    for sgn in (1, -1):  # ears at the back edge
        Vp, Fp = pyramid([(sgn * 0.25, 0.55), (sgn * 0.95, 0.35), (sgn * 0.75, 1.0)], (sgn * 0.75, 0.95, 1.05))
        ear = part(root, Vp, Fp, CAT_PURPLE)
        neon_edges(ear, (1.0, 0.25, 0.85, 0.9))
        Vi, Fi = pyramid([(sgn * 0.42, 0.62), (sgn * 0.8, 0.5), (sgn * 0.7, 0.85)], (sgn * 0.72, 0.88, 0.85))
        part(root, Vi * np.array([1, 1, 1]), Fi, MAGENTA, pos=(0, 0, 0.06), unlit=True)
        _cat_eye(root, (sgn * 0.38, -0.12, 0.43), 0.42)
        for k, ang in enumerate((-12, 0, 12)):  # whisker antennas
            Vw, Fw = box(1.3, 0.025, 0.025)
            part(root, Vw, Fw, MAGENTA, pos=(sgn * 1.1, -0.72 + k * 0.08, 0.05), hpr=(sgn * ang, 0, 0), unlit=True)
        Vb, Fb = prism([(sgn * 0.9, 0.2), (sgn * 1.75, 0.95), (sgn * 1.55, 1.15), (sgn * 0.8, 0.6)][::sgn], 0.07)
        blade = part(root, Vb, Fb, (0.2, 0.12, 0.28))
        neon_edges(blade, (1.0, 0.2, 0.85, 0.8))
        glow(root, (sgn * 0.45, 1.0, 0.0), 0.5, (1.0, 0.3, 0.9, 0.9))
    Vn, Fn = pyramid([(-0.12, -0.75), (0.12, -0.75), (0, -0.58)], (0, -0.68, 0.32))
    part(root, Vn, Fn, (1.0, 0.45, 0.7), unlit=True)  # nose
    Vc, Fc = lathe([(0.08, 0), (0.1, -0.45)], 6, "y")
    part(root, Vc, Fc, DARK, pos=(0, -1.05, -0.05), orient="y")
    glow(root, (0, -1.5, -0.05), 0.35, (1.0, 0.2, 0.3, 0.9))
    return root


def mothership_layout(width=14.0):
    """x boundaries of the damage zones (30% / 15% / 10% / 15% / 30%)."""
    w = width
    return [-w / 2, -w / 2 + 0.30 * w, -w / 2 + 0.45 * w, w / 2 - 0.45 * w, w / 2 - 0.30 * w, w / 2]


def build_mothership(parent, width=14.0):
    root = parent.attachNewNode("mothership")
    s = width / 2
    outline = [(0, -0.42), (0.35, -0.38), (0.75, -0.18), (1.0, 0.12), (0.88, 0.38),
               (0.45, 0.5), (-0.45, 0.5), (-0.88, 0.38), (-1.0, 0.12), (-0.75, -0.18), (-0.35, -0.38)]
    poly = [(x * s, y * s) for x, y in outline]
    V, F = loft(poly, [(0.9, -1.0), (1.0, -0.2), (0.96, 0.4), (0.72, 1.1)])
    hull = part(root, V, F, (0.17, 0.11, 0.24))
    neon_edges(hull, (0.85, 0.15, 0.75, 0.55))
    rng = np.random.default_rng(11)
    zones = mothership_layout(width)
    # armour greebles (zone 1, outer) and glowing vents (zone 2)
    for _ in range(70):
        x = rng.uniform(-0.85, 0.85) * s
        y = rng.uniform(-0.15, 0.3) * s
        ax = abs(x)
        if ax < zones[3]:
            continue
        Vb, Fb = box(rng.uniform(0.25, 0.8), rng.uniform(0.25, 0.9), rng.uniform(0.1, 0.4))
        if ax > zones[4]:
            part(root, Vb, Fb, (0.24, 0.17, 0.3), pos=(x, y, 1.1))
        else:
            part(root, Vb, Fb, (1.0, 0.45, 0.1) if rng.random() < 0.4 else (0.3, 0.2, 0.36),
                 pos=(x, y, 1.05), unlit=False)
    for sgn in (1, -1):
        Vp, Fp = pyramid([(sgn * 2.0, 1.2), (sgn * 5.6, 0.9), (sgn * 4.6, 3.4)], (sgn * 4.4, 3.0, 4.2))
        ear = part(root, Vp, Fp, (0.2, 0.13, 0.28), pos=(0, 0, 1.0))
        neon_edges(ear, (1.0, 0.2, 0.8, 0.8))
        Vi, Fi = pyramid([(sgn * 2.8, 1.5), (sgn * 4.9, 1.3), (sgn * 4.3, 2.9)], (sgn * 4.3, 2.7, 3.2))
        part(root, Vi, Fi, MAGENTA, pos=(0, 0, 1.15), unlit=True)
        _cat_eye(root, (sgn * 2.3, -0.4, 1.12), 1.9)
        for k in range(4):  # turrets along the front edge
            Vt, Ft = lathe([(0.25, 0), (0.25, 0.3), (0.12, 0.45)], 6, "z")
            px = sgn * (1.6 + k * 1.15)
            part(root, Vt, Ft, (0.3, 0.22, 0.36), pos=(px, -0.55 * s * (1 - 0.12 * k) + 0.4, 0.4), orient="z")
            glow(root, (px, -0.55 * s * (1 - 0.12 * k), 0.75), 0.35, (1.0, 0.25, 0.3, 0.8))
        glow(root, (sgn * 3.5, 3.2, 0.0), 2.0, (1.0, 0.25, 0.85, 0.7))
    # throne chamber of "the Mother" - zone 3, the weak spot
    Vh, Fh = hemisphere(2)
    part(root, Vh * np.array([0.75, 0.6, 0.55]), Fh, (1.0, 0.25, 0.55), pos=(0, -2.1, 0.95), unlit=True)
    part(root, Vh * np.array([0.95, 0.8, 0.75]), Fh, (0.9, 0.6, 1.0, 0.25), pos=(0, -2.1, 0.92), alpha=True)
    glow(root, (0, -2.1, 1.2), 2.4, (1.0, 0.2, 0.5, 0.8))
    return root


def build_black_hole(parent, r=1.0, cam_facing=True):
    root = parent.attachNewNode("blackhole")
    V, F = icosphere(3)
    part(root, V * r, F, (0, 0, 0), unlit=True)

    def disk_col(p, r0, r1, a0):
        rr = math.hypot(p[0], p[1])
        t = min(max((rr - r0) / (r1 - r0), 0.0), 1.0)
        th = math.atan2(p[1], p[0])
        swirl = 0.55 + 0.45 * math.sin(3 * th + 7 * math.log(rr + 1e-6))
        a = a0 * (1 - t) ** 1.6 * swirl
        return (1.0, 0.85 - 0.55 * t, 0.55 - 0.5 * t, a)

    Vd, Fd = annulus(1.35 * r, 4.2 * r, seg=160, rings=14)
    disk = part(root, Vd, Fd, (1, 1, 1), orient=None, additive=True,
                vcol=lambda p: disk_col(p, 1.35 * r, 4.2 * r, 1.0))
    disk.setP(-72)
    # lensed far side of the disk + photon ring, facing the camera
    halo = root.attachNewNode("halo")
    Vl, Fl = annulus(1.08 * r, 2.3 * r, seg=128, rings=8)
    part(halo, Vl, Fl, (1, 1, 1), orient=None, additive=True,
         vcol=lambda p: disk_col(p, 1.08 * r, 2.3 * r, 0.55)).setP(90)
    Vp, Fp = annulus(1.02 * r, 1.12 * r, seg=128, rings=2)
    part(halo, Vp, Fp, (1.0, 0.9, 0.7, 0.9), orient=None, additive=True).setP(90)
    if cam_facing:
        halo.setBillboardPointEye()
    return root


def build_explosion(parent, t, seed=5, scale=1.0):
    """t in [0, 1]: fireball + debris + expanding shockwave ring in the play plane."""
    root = parent.attachNewNode("explosion")
    rng = np.random.default_rng(seed)
    spread = 0.3 + 2.4 * t ** 0.5
    fade = (1 - t) ** 1.3
    for _ in range(55):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        p = d * spread * rng.uniform(0.0, 1.0)
        hot = max(0.0, 1 - t * 1.6 - np.linalg.norm(p) / 4)
        col = (1.0, 0.45 + 0.5 * hot, 0.1 + 0.6 * hot, 0.75 * fade)
        glow(root, tuple(p), rng.uniform(0.5, 1.6) * (1 + t), col)
    if t < 0.35:
        glow(root, (0, 0, 0), 3.5 * (1 - t), (1, 1, 0.9, 1.0))
    R = 0.8 + 11 * t
    if t > 0.05:
        Vr, Fr = annulus(R * 0.78, R, seg=128, rings=5)

        def ring_col(p):
            rr = math.hypot(p[0], p[1])
            u = (rr - R * 0.78) / (R * 0.22)
            a = math.sin(math.pi * u) ** 2 * (1 - t) * 0.95
            return (0.65 + 0.35 * u, 0.85, 1.0, a)

        part(root, Vr, Fr, (1, 1, 1), orient=None, additive=True, vcol=ring_col)
    Vi, Fi = icosphere(0)
    for _ in range(16):
        d = rng.normal(size=3)
        d[2] *= 0.4
        d /= np.linalg.norm(d)
        p = d * (0.4 + 6.5 * t * rng.uniform(0.6, 1.2))
        V, F, cols, _ = asteroid_mesh(int(rng.integers(1000)), rng.uniform(0.08, 0.22), sub=0)
        part(root, V, F, cols, pos=tuple(p), hpr=tuple(rng.uniform(0, 360, 3)))
        if t < 0.6:
            glow(root, tuple(p), 0.3, (1, 0.6, 0.2, 0.7 * fade))
    root.setScale(scale)
    return root


def build_laser_bolt(parent, pos, color=GREEN_LASER, length=0.9):
    V, F = icosphere(1)
    b = part(parent, V * np.array([0.09, length / 2, 0.09]), F, color, pos=pos, unlit=True)
    glow(parent, pos, 0.55, (*color, 0.8))
    return b


def build_hypno_rings(parent, center, radii, width=0.9):
    root = parent.attachNewNode("hypno")
    for k, R in enumerate(radii):
        V, F = annulus(max(0.01, R - width), R, seg=180, rings=4)

        def col(p, R=R, k=k):
            th = math.atan2(p[1] - 0, p[0])
            rr = math.hypot(p[0], p[1])
            u = (rr - (R - width)) / width
            h = (th / (2 * math.pi) * 3 + k * 0.17) % 1.0
            r, g, b = _hsv(h, 0.75, 1.0)
            return (r, g, b, 0.85 * math.sin(math.pi * min(max(u, 0), 1)) ** 2)

        part(root, V, F, (1, 1, 1), orient=None, additive=True, vcol=col)
    root.setPos(*center)
    return root


def _hsv(h, s, v):
    import colorsys
    return colorsys.hsv_to_rgb(h, s, v)


def build_helmet(parent):
    """AR overlay: life-support helmet with an exposed brain under a glass dome.

    Head-local coordinates: head centre at origin, head half-width ~1, face looks along -Y,
    brow at z~0.35, chin at z~-1.35.
    """
    root = parent.attachNewNode("helmet")
    build_brain(root, 0.68, aura=False).setPos(0, 0.12, 0.95)
    root.find("**/brain").setP(-8)
    Vh, Fh = hemisphere(3)
    part(root, Vh * np.array([1.12, 1.15, 1.2]), Fh, (0.6, 0.95, 1.0, 0.22), pos=(0, 0.1, 0.45),
         alpha=True, two_sided=True)
    glow(root, (0, 0.1, 1.0), 2.4, (0.9, 0.4, 1.0, 0.28))
    # metal head band with rivets and status LEDs
    Vb, Fb = lathe([(1.08, 0.3), (1.16, 0.36), (1.16, 0.56), (1.1, 0.62)], 24, "z")
    band = part(root, Vb, Fb, (0.36, 0.38, 0.43), pos=(0, 0.1, 0), orient="z")
    band.setScale(1, 1.05, 1)
    Vi, Fi = icosphere(1)
    for k in range(-5, 6):
        a = math.radians(-90 + k * 15)
        p = (1.17 * math.cos(a), 0.1 + 1.2 * math.sin(a), 0.46)
        col = (0.3, 1, 0.3) if k % 3 else (1, 0.2, 0.2)
        part(root, Vi * 0.035, Fi, col, pos=p, unlit=True)
        if k % 3 == 0:
            glow(root, p, 0.14, (*col, 0.9))
    for sgn in (1, -1):
        # ear pod with glowing ring
        Vp, Fp = lathe([(0.0, 0.0), (0.3, 0.02), (0.34, 0.2), (0.22, 0.32)], 10, "y")
        pod = part(root, Vp, Fp, (0.3, 0.32, 0.36), orient="y")
        pod.setPos(sgn * 1.02, 0.15, -0.25)
        pod.setH(-sgn * 90)
        Vr, Fr = lathe([(0.26, 0.0), (0.26, 0.04)], 16, "y")
        rr = part(root, Vr, Fr, CYAN, unlit=True, orient="y")
        rr.setPos(sgn * 1.25, 0.15, -0.25)
        rr.setH(-sgn * 90)
        glow(root, (sgn * 1.3, 0.1, -0.25), 0.4, (*CYAN, 0.8))
        # life-support tubes curving down to the collar
        for j, (col, a) in enumerate((((0.25, 0.25, 0.28), 1.0), ((0.4, 1.0, 0.4), 0.55))):
            pts = _bezier([(sgn * 1.2, 0.2 + 0.25 * j, -0.4), (sgn * 1.55, 0.3 + 0.3 * j, -1.0),
                           (sgn * 1.25, 0.25 + 0.3 * j, -1.6), (sgn * 0.85, 0.0 + 0.3 * j, -1.75)], 14)
            for p in pts:
                part(root, Vi * 0.1, Fi, col if j == 0 else (*col, a), pos=tuple(p),
                     unlit=(j == 1), alpha=(j == 1))
    # collar
    Vc, Fc = lathe([(0.75, -1.55), (1.15, -1.7), (1.3, -1.95), (1.0, -2.05)], 20, "z")
    part(root, Vc, Fc, (0.3, 0.32, 0.37), orient="z")
    for k in range(-3, 4):
        a = math.radians(-90 + k * 18)
        Vv, Fv = box(0.18, 0.04, 0.08)
        part(root, Vv, Fv, (1, 0.5, 0.1), pos=(1.2 * math.cos(a), 1.2 * math.sin(a), -1.8),
             hpr=(math.degrees(a) + 90, 0, 0), unlit=True)
    return root


def _bezier(ctrl, n):
    P = np.array(ctrl, float)
    out = []
    for t in np.linspace(0, 1, n):
        out.append((1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t ** 2 * P[2] + t ** 3 * P[3])
    return out
