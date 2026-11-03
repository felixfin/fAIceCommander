"""Procedural models for fAIceCommander 3D.

All geometry is generated in code - no external assets, no licensing issues.
Coordinate system (Panda3D): X right, Y forward (= up the screen), Z up.
"""
import hashlib
import math
import os
from pathlib import Path

import numpy as np
from panda3d.core import (
    ColorBlendAttrib, CardMaker, Filename, Loader, LoaderOptions, Material, Point3, Geom, GeomNode, GeomTriangles,
    GeomVertexData, GeomVertexFormat, GeomVertexWriter, NodePath, PNMImage, Texture, TransparencyAttrib,
)


# ---------------------------------------------------------------- model cache

def _source_hash():
    """Changes whenever the model code changes, so stale cached models are never used."""
    pkg = Path(__file__).resolve().parents[1]
    h = hashlib.md5()
    files = [p for d in ("render", "game/entities", "cutscenes") for p in (pkg / d).glob("*.py")]
    for p in sorted(files):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def _cache_dir():
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache")
    d = base / "fAIceCommander3D" / "models" / _source_hash()
    d.mkdir(parents=True, exist_ok=True)
    return d


_LOADED = {}


def cached(name, build):
    """A model tree built by build(root) - loaded from the per-user cache (.bam) when it is there, and
    kept in memory after that. Building the procedural models takes seconds; loading them milliseconds.
    The result is a template: callers copy it (copyTo) and never change it."""
    if name in _LOADED:
        return _LOADED[name]
    path = _cache_dir() / f"{name}.bam"
    if path.exists():
        node = Loader.getGlobalPtr().loadSync(Filename.fromOsSpecific(str(path)), LoaderOptions(LoaderOptions.LF_no_cache))
        if node is not None:
            root = NodePath(node)
            root.setName(name)
            _LOADED[name] = root
            return root
    root = NodePath(name)
    build(root)
    tmp = path.with_name(f"{name}.{os.getpid()}.tmp")
    if root.writeBamFile(Filename.fromOsSpecific(str(tmp))):
        try:
            tmp.replace(path)
        except OSError:  # another instance was faster
            tmp.unlink(missing_ok=True)
    _LOADED[name] = root
    return root


# ---------------------------------------------------------------- mesh core

class Mesh:
    """Collects triangles; shading is flat or smooth with a crease angle (see node())."""

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

    def node(self, name="mesh", smooth=None):
        """smooth: crease angle in degrees. Corners whose faces meet flatter than this share
        an averaged normal (rounded look); sharper edges stay hard. None = flat shading."""
        tris, fns = [], []
        for pts, cols in self.tris:
            a, b, c = pts
            n = np.cross(b - a, c - a)
            if np.linalg.norm(n) < 1e-12:
                continue
            tris.append((pts, cols))
            fns.append(n)
        fns = np.array(fns) if fns else np.zeros((0, 3))
        units = fns / np.maximum(np.linalg.norm(fns, axis=1, keepdims=True), 1e-12)
        corner_normals = []
        if smooth:
            cos_lim = math.cos(math.radians(smooth))
            groups = {}
            for ti, (pts, _) in enumerate(tris):
                for p in pts:
                    groups.setdefault(tuple(np.round(p, 5)), []).append(ti)
            for ti, (pts, _) in enumerate(tris):
                ns = []
                for p in pts:
                    nb = groups[tuple(np.round(p, 5))]
                    sel = [tj for tj in nb if units[tj] @ units[ti] > cos_lim]
                    n = fns[sel].sum(0)
                    ns.append(n / max(np.linalg.norm(n), 1e-12))
                corner_normals.append(ns)
        else:
            corner_normals = [[u, u, u] for u in units]
        vd = GeomVertexData(name, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        vw, nw, cw = (GeomVertexWriter(vd, c) for c in ("vertex", "normal", "color"))
        prim = GeomTriangles(Geom.UHStatic)
        i = 0
        for ((pts, cols), ns) in zip(tris, corner_normals):
            for p, col, n in zip(pts, cols, ns):
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


SMOOTH = 35.0  # default crease angle: curved surfaces render round, box edges stay crisp


def part(parent, V, F, col, pos=(0, 0, 0), hpr=(0, 0, 0), scale=1, orient="center",
         unlit=False, alpha=False, additive=False, vcol=None, two_sided=False, name="part", smooth=SMOOTH):
    np_ = Mesh().add_mesh(V, F, col, orient=orient, vcol=vcol).node(name, smooth=None if (unlit or additive) else smooth)
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


# rock types: (dark, light, accent) - basalt, iron-rich, carbonaceous, dirty ice
ROCK_TYPES = [((0.13, 0.12, 0.115), (0.42, 0.4, 0.37), (0.6, 0.58, 0.52)),
              ((0.16, 0.08, 0.05), (0.5, 0.3, 0.2), (0.75, 0.45, 0.25)),
              ((0.07, 0.065, 0.07), (0.26, 0.25, 0.26), (0.55, 0.5, 0.42)),
              ((0.2, 0.24, 0.28), (0.55, 0.62, 0.68), (0.8, 0.88, 0.95))]


def asteroid_mesh(seed, radius, irregular=0.45, sub=3, base=None):
    """A lumpy rock with craters (bowls with raised rims), ridges and a rock-type palette.
    base: a ROCK_TYPES entry (or None to pick one by seed). Returns V, F, vcol (per-vertex colour
    function for part(..., vcol=...)) and the displacement."""
    rng = np.random.default_rng(seed)
    V, F = icosphere(sub)
    d = np.zeros(len(V))
    for _ in range(14):  # large lumps and dents
        dv = rng.normal(size=3)
        dv /= np.linalg.norm(dv)
        amp = rng.uniform(-1, 0.6) * irregular
        w = rng.uniform(0.08, 0.35)
        d += amp * np.exp(-(1 - V @ dv) / w)
    for _ in range(22):  # smaller knobs and chips
        dv = rng.normal(size=3)
        dv /= np.linalg.norm(dv)
        d += rng.uniform(-0.12, 0.1) * np.exp(-(1 - V @ dv) / rng.uniform(0.01, 0.05))
    crater = np.zeros(len(V))
    for _ in range(int(rng.integers(4, 9))):  # impact craters
        dv = rng.normal(size=3)
        dv /= np.linalg.norm(dv)
        r = rng.uniform(0.18, 0.5)
        ang = np.arccos(np.clip(V @ dv, -1, 1)) / r
        bowl = np.where(ang < 1, -(1 - ang ** 2), 0.0)
        rim = np.exp(-((ang - 1.05) / 0.18) ** 2) * 0.35
        k = rng.uniform(0.14, 0.24) * r * 2
        d += (bowl + rim) * k
        crater = np.maximum(crater, np.where(ang < 1, 1 - ang, 0.0))
    d += 0.025 * np.sin(V @ rng.normal(size=3) * 9) * np.sin(V @ rng.normal(size=3) * 13)  # fine ridges
    d = np.clip(d, -0.5, 0.6)
    V = V * (1 + d)[:, None] * radius * rng.uniform(0.68, 1.3, size=3)
    lo, hi, accent = map(np.array, base or ROCK_TYPES[seed % len(ROCK_TYPES)])
    vc = {}
    for i, p in enumerate(V):
        t = np.clip(0.5 + 1.5 * d[i] + 0.12 * _noise(p, 3.0 / max(radius, 1e-3)), 0, 1)
        c = (lo + (hi - lo) * t) * (1 - 0.5 * crater[i])        # dark crater floors
        if rng.random() < 0.012:                                # rare mineral glints
            c = c * 0.4 + accent * 0.6
        vc[tuple(np.round(p, 5))] = tuple(np.clip(c, 0, 1))
    return V, F, (lambda p: vc[tuple(np.round(p, 5))]), d


def build_asteroid(parent, seed, radius, category=1):
    root = parent.attachNewNode("asteroid")
    if category == 1:
        V, F, vcol, _ = asteroid_mesh(seed, radius)
        part(root, V, F, (1, 1, 1), vcol=vcol)
    else:
        V, F, vcol, d = asteroid_mesh(seed, radius, irregular=0.55, base=ROCK_TYPES[1])
        part(root, V, F, (1, 1, 1), vcol=vcol)
        # glowing fracture lines: it will burst into category-1 fragments when shot
        rng = np.random.default_rng(seed + 99)
        planes = [rng.normal(size=3) for _ in range(2)]
        hot = [f for f in F if any(abs(np.dot(V[list(f)].mean(0) / radius, p / np.linalg.norm(p))) < 0.035
                                   for p in planes)]  # noqa
        part(root, V * 1.01, hot, (1.0, 0.45, 0.1), unlit=True, orient=None, two_sided=True)
        glow(root, (0, 0, 0), radius * 2.2, (1.0, 0.35, 0.05, 0.25))
    return root


# ---------------------------------------------------------------- rounded primitives

def superellipse(a, n):
    c, s = math.cos(a), math.sin(a)
    return math.copysign(abs(c) ** (2 / n), c), math.copysign(abs(s) ** (2 / n), s)


def _ring_faces(V, centers, seg, closed_caps):
    """Quads between consecutive rings (+ optional fan caps), wound outward."""
    F = []

    def emit(tri, ref):
        a, b, c = (V[i] for i in tri)
        if np.dot(np.cross(b - a, c - a), (a + b + c) / 3 - ref) < 0:
            tri = (tri[0], tri[2], tri[1])
        F.append(tri)

    nr = len(centers)
    for i in range(nr - 1):
        ref = (centers[i] + centers[i + 1]) / 2
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            emit((a, b, b + seg), ref)
            emit((a, b + seg, a + seg), ref)
    if closed_caps:
        c0, c1 = nr * seg, nr * seg + 1
        k = (nr - 1) * seg
        for j in range(seg):
            emit((c0, j, (j + 1) % seg), centers[1])
            emit((c1, k + j, k + (j + 1) % seg), centers[-2])
    return F


def _pad(s):
    return tuple(s) + (0.0, 2.5, 0.0)[len(s) - 3:]


def sweep(sections, seg=28, axis="y"):
    """Rounded hull: superellipse cross-sections placed along an axis.

    sections: [(t, w, h, zoff=0, n=2.5, woff=0), ...]; t = position along the axis, w/h = half width /
    half height (width runs along x for axis "y", along y for axis "x"), n = 2 ellipse ... 4+ rounded box.
    Faces come out wound outward, so pass orient=None to part().
    """
    secs = [_pad(s) for s in sections]

    def xyz(t, v, z):
        return (v, t, z) if axis == "y" else (t, v, z)

    V, centers = [], []
    for (t, w, h, zo, n, wo) in secs:
        for j in range(seg):
            cx, cz = superellipse(2 * math.pi * j / seg, n)
            V.append(xyz(t, wo + w * cx, zo + h * cz))
        centers.append(np.array(xyz(t, wo, zo), float))
    V += [tuple(centers[0]), tuple(centers[-1])]
    V = np.array(V, float)
    return V, _ring_faces(V, centers, seg, True)


def sweep_top(sections, x, y):
    """Height of the upper surface of a y-axis sweep at (x, y); None outside the hull."""
    secs = sorted((_pad(s) for s in sections), key=lambda s: s[0])
    for s0, s1 in zip(secs, secs[1:]):
        if s0[0] <= y <= s1[0]:
            f = (y - s0[0]) / max(s1[0] - s0[0], 1e-9)
            t, w, h, zo, n, wo = (a + (b - a) * f for a, b in zip(s0, s1))
            u = abs((x - wo) / max(w, 1e-9))
            if u >= 0.98:
                return None
            return zo + h * (1 - u ** n) ** (1 / n)
    return None


def tube_mesh(points, radius, seg=8):
    """Smooth hose through the given points (parallel-transport frames)."""
    P = np.array(points, float)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    nrm = np.cross(T[0], ref)
    nrm /= np.linalg.norm(nrm)
    V, centers = [], []
    for p, t in zip(P, T):
        nrm = nrm - t * (nrm @ t)
        nrm /= np.linalg.norm(nrm)
        bi = np.cross(t, nrm)
        for j in range(seg):
            a = 2 * math.pi * j / seg
            V.append(p + radius * (math.cos(a) * nrm + math.sin(a) * bi))
        centers.append(p)
    V += [P[0], P[-1]]
    V = np.array(V, float)
    return V, _ring_faces(V, centers, seg, True)


def tube(root, ctrl, radius, color, n=16, band=None, glowing=False):
    """Hose along a cubic bezier; optional coloured bands."""
    pts = _bezier(ctrl, n)
    color = _rgba(color)
    V, F = tube_mesh(pts, radius, 10)
    part(root, V, F, color, orient=None, unlit=glowing, alpha=color[3] < 1)
    if band is not None:
        for p0, p1 in zip(pts[2::4], pts[3::4]):
            Vb, Fb = tube_mesh([p0, (p0 + p1) / 2, p1], radius * 1.15, 10)
            part(root, Vb, Fb, band, orient=None)
    if glowing:
        for p in pts[::4]:
            glow(root, tuple(p), radius * 5, (color[0], color[1], color[2], 0.45))


def greebles(root, sections, count, rng, pick, size=(0.1, 0.5), height=(0.04, 0.25), offset=(0, 0, 0),
             region=None, palette=((0.1, 0.1, 0.11), (0.14, 0.13, 0.13), (0.07, 0.07, 0.08))):
    """Scatters machinery boxes onto the upper surface of a y-axis sweep (Borg-style surface clutter)."""
    xs = [s[1] + abs(_pad(s)[5]) for s in sections]
    ys = [s[0] for s in sections]
    placed = 0
    for _ in range(count * 6):
        if placed >= count:
            break
        x = rng.uniform(-max(xs), max(xs))
        y = rng.uniform(min(ys), max(ys))
        if region and not region(x, y):
            continue
        z = sweep_top(sections, x, y)
        if z is None:
            continue
        sx, sy = rng.uniform(*size), rng.uniform(*size)
        sz = rng.uniform(*height)
        Vb, Fb = box(sx, sy, sz)
        col = pick(x, y) if pick else palette[rng.integers(len(palette))]
        glowing = len(col) == 5  # 5-tuple marks an emissive part: small lit windows / vents
        if glowing:
            sx, sy, sz = sx * 0.3, sy * 0.3, sz * 0.4
        part(root, Vb, Fb, col[:4], pos=(x + offset[0], y + offset[1], z + offset[2] + sz * 0.3),
             hpr=(rng.choice([0, 90]), 0, 0), smooth=None, unlit=glowing)
        placed += 1


def _noise(p, k=1.0):
    x, y, z = p[0] * k, p[1] * k, p[2] * k
    return (math.sin(7.3 * x + 3.1 * y) * math.sin(5.7 * y - 2.3 * z + 1.3) + math.sin(11.1 * z + 4.7 * x) * 0.5) / 1.5


def paint(lo, hi, z0, z1, grime=0.12, soot_y=None):
    """Vertex colour gradient: dark underside -> lit top, with grime noise and optional engine soot."""
    lo, hi = np.array(lo), np.array(hi)

    def f(p):
        t = min(max((p[2] - z0) / (z1 - z0), 0.0), 1.0) ** 0.8
        c = lo + (hi - lo) * t
        c = c * (1 + grime * _noise(p))
        if soot_y is not None and p[1] < soot_y:
            c = c * max(0.35, 1 - (soot_y - p[1]) * 1.6)
        return tuple(np.clip(c, 0, 1))
    return f


# ---------------------------------------------------------------- FaceCommander

ORANGE_LO, ORANGE_HI = (0.32, 0.11, 0.035), (0.93, 0.47, 0.14)
METAL_LO, METAL_HI = (0.09, 0.09, 0.1), (0.38, 0.38, 0.4)

# a blunt, armoured salvage hull: rounded-box sections, no pointed nose
SHIP_HULL = [(2.02, 0.26, 0.15, 0.04, 3.2), (1.96, 0.46, 0.26, 0.05, 3.8), (1.75, 0.58, 0.33, 0.05, 4.0),
             (1.1, 0.64, 0.36, 0.05, 3.8), (-0.4, 0.68, 0.37, 0.04, 3.6), (-1.2, 0.63, 0.34, 0.02, 3.3),
             (-1.42, 0.53, 0.29, 0.0, 3.0), (-1.48, 0.45, 0.23, 0.0, 2.8)]
SHIP_PROW = 2.02


def build_ship(parent, brain=True):
    """FaceCommander: a blunt, armoured salvage gunship (hull, two gun pods, stubby radiator wings).
    brain=False leaves the cockpit dome empty (the intro builds the commander into it)."""
    root = parent.attachNewNode("ship")
    V, F = sweep(SHIP_HULL, 36)
    part(root, V, F, (1, 1, 1), orient=None, vcol=paint(ORANGE_LO, ORANGE_HI, -0.36, 0.36, soot_y=-1.15))
    top = lambda x, y: sweep_top(SHIP_HULL, x, y)
    # panel seams: thin dark bands hugging the hull
    for y in (1.15, 0.2, -0.75):
        ring = [(x, y, (top(x, y) or 0) + 0.004) for x in np.linspace(-0.6, 0.6, 15) if top(x, y)]
        if len(ring) > 3:
            Vr, Fr = tube_mesh(ring, 0.012, 6)
            part(root, Vr, Fr, (0.18, 0.07, 0.03), orient=None)
    # armour: a front ram bar and a glowing sensor slit across the blunt nose
    Vb, Fb = sweep([(-0.5, 0.06, 0.07, 0, 2.6), (0.5, 0.06, 0.07, 0, 2.6)], 12, "x")
    part(root, Vb, Fb, (1, 1, 1), pos=(0, 2.02, -0.08), orient=None, vcol=paint(METAL_LO, METAL_HI, -0.15, 0.0))
    for x in (-0.38, 0.38):
        Vs, Fs = box(0.08, 0.2, 0.1)
        part(root, Vs, Fs, (0.14, 0.14, 0.15), pos=(x, 1.94, -0.08), smooth=None)
    Vs, Fs = box(0.6, 0.02, 0.035)
    part(root, Vs, Fs, (1.0, 0.75, 0.3), pos=(0, 2.0, 0.1), unlit=True, smooth=None)
    glow(root, (0, 2.05, 0.1), 0.5, (1.0, 0.6, 0.2, 0.5))
    for y, w in ((1.55, 0.52), (1.25, 0.56)):  # bolted armour plates on the upper nose
        for sgn in (1, -1):
            Vp, Fp = box(w * 0.42, 0.22, 0.02)
            part(root, Vp, Fp, (1, 1, 1), pos=(sgn * w * 0.25, y, top(sgn * w * 0.25, y) + 0.005),
                 hpr=(0, 0, -sgn * 14), vcol=paint(ORANGE_LO, ORANGE_HI, -0.2, 0.5, grime=0.3), smooth=None)
    pod = [(1.25, 0.12, 0.13, 0, 3.0), (1.18, 0.2, 0.22, 0, 3.4), (0.6, 0.23, 0.25, 0, 3.2),
           (-1.3, 0.25, 0.26, 0, 3.0), (-1.55, 0.21, 0.22, 0, 2.8), (-1.6, 0.15, 0.16, 0, 2.5)]
    Vi, Fi = icosphere(2)
    for sgn in (1, -1):
        px = sgn * 0.98
        Vp, Fp = sweep(pod, 28)
        part(root, Vp, Fp, (1, 1, 1), pos=(px, 0, -0.08), orient=None,
             vcol=paint(METAL_LO, METAL_HI, -0.25, 0.25, soot_y=-1.3))
        Vy, Fy = sweep([(sgn * 0.5, 0.45, 0.07, 0, 2.5, -0.15), (sgn * 0.85, 0.4, 0.06, 0, 2.5, -0.2)], 20, "x")
        part(root, Vy, Fy, (1, 1, 1), pos=(0, 0, -0.02), orient=None, vcol=paint(METAL_LO, METAL_HI, -0.07, 0.07))
        fin = [(sgn * 1.15, 0.48, 0.08, -0.08, 3.6, -0.55), (sgn * 1.6, 0.44, 0.06, -0.16, 3.6, -0.62),
               (sgn * 1.78, 0.4, 0.05, -0.2, 3.4, -0.66)]  # stubby radiator wing, square tip
        Vf, Ff = sweep(fin, 24, "x")
        part(root, Vf, Ff, (1, 1, 1), orient=None, vcol=paint(ORANGE_LO, ORANGE_HI, -0.33, -0.0, grime=0.18))
        for k in range(3):  # hazard chevrons near the fin root
            Vs, Fs = box(0.09, 0.3, 0.012)
            part(root, Vs, Fs, (0.95, 0.75, 0.1) if k % 2 == 0 else (0.06, 0.06, 0.06),
                 pos=(sgn * (1.3 + k * 0.1), -0.62, -0.06 - k * 0.025), hpr=(sgn * 40, 0, -sgn * 10),
                 smooth=None)
        # laser cannon in the pod nose, green muzzle (2D original)
        Vc, Fc = lathe([(0.0, 0.62), (0.05, 0.6), (0.06, 0.45), (0.06, 0.0), (0.09, -0.05)], 14, "y")
        part(root, Vc, Fc, (0.2, 0.2, 0.22), pos=(px, 1.0, -0.08), orient="y")
        part(root, Vi * 0.06, Fi, GREEN_LASER, pos=(px, 1.62, -0.08), unlit=True)
        glow(root, (px, 1.66, -0.08), 0.38, (*GREEN_LASER, 0.9))
        for j in range(3):  # nuke rack on the pod
            Vr, Fr = lathe([(0.0, 0.34), (0.045, 0.24), (0.05, -0.2), (0.07, -0.26)], 12, "y")
            part(root, Vr, Fr, (0.62, 0.62, 0.58), pos=(px + sgn * (j - 1) * 0.1, -0.5, 0.2), orient="y")
            part(root, Vi * 0.035, Fi, (1, 0.15, 0.1), pos=(px + sgn * (j - 1) * 0.1, -0.15, 0.2), unlit=True)
        for k in range(7):  # radiator fins
            Vb, Fb = box(0.025, 0.07, 0.32)
            part(root, Vb, Fb, (0.2, 0.2, 0.22), pos=(sgn * 1.23, -0.95 + k * 0.12, -0.08), smooth=None)
        # coolant hoses into the pods, plus a glowing coolant line
        for (y0, y1) in ((0.45, 0.25), (-0.35, -0.6)):
            z0 = top(sgn * 0.5, y0)
            tube(root, [(sgn * 0.5, y0, z0), (sgn * 0.7, y0 - 0.05, z0 + 0.2), (sgn * 0.88, y1, 0.36),
                        (sgn * 0.92, y1 - 0.1, 0.15)], 0.04, (0.1, 0.1, 0.11), band=(0.9, 0.7, 0.1))
        z0 = top(sgn * 0.42, -0.95)
        tube(root, [(sgn * 0.42, -0.95, z0), (sgn * 0.62, -1.1, z0 + 0.2), (sgn * 0.82, -1.05, 0.36),
                    (sgn * 0.92, -0.95, 0.15)], 0.035, (0.35, 1.0, 0.45, 0.65), glowing=True)
    # three bell nozzles, heat-tinted, with yellow-white flames
    for x in (-0.3, 0.0, 0.3):
        Vn, Fn = lathe([(0.1, -1.38), (0.13, -1.48), (0.17, -1.62), (0.2, -1.75)], 18, "y")
        part(root, Vn, Fn, (1, 1, 1), pos=(x, 0, 0), orient="y", two_sided=True,
             vcol=lambda p: tuple(np.clip(np.array((0.22, 0.2, 0.22)) + max(0, -p[1] - 1.5) * np.array((0.6, 0.35, 0.9)), 0, 1)))
        Vd, Fd = lathe([(0.15, 0), (0.0, 0.01)], 14, "y")
        part(root, Vd, Fd, (1.0, 0.9, 0.55), pos=(x, -1.6, 0), unlit=True, orient=None, two_sided=True)
        for ln, a in ((1.0, 0.45), (0.55, 0.75)):
            Vf, Ff = lathe([(0.15, 0), (0.0, -ln)], 12, "y")
            part(root, Vf, Ff, (1, 1, 1), pos=(x, -1.62, 0), additive=True, orient=None,
                 vcol=lambda p, a=a, ln=ln: (1.0, 0.85 - 0.3 * (-p[1] / ln), 0.4 - 0.3 * (-p[1] / ln), a * (1 + p[1] / ln)))
        glow(root, (x, -1.75, 0), 0.5, (1.0, 0.8, 0.35, 0.9))
    # cockpit: the commander's brain under a glass dome, fed by a life-support tank
    if brain:
        build_brain(root, 0.24, aura=False).setPos(0, 0.55, 0.47)
        glow(root, (0, 0.55, 0.5), 0.65, (1.0, 0.4, 0.7, 0.4))
    Vh, Fh = hemisphere(3)
    part(root, Vh * np.array([0.36, 0.44, 0.3]), Fh, (0.6, 0.95, 1.0, 0.26), pos=(0, 0.55, 0.37),
         alpha=True, two_sided=True)
    Vr, Fr = lathe([(0.39, 0.0), (0.41, 0.03), (0.39, 0.07)], 24, "z")
    ring = part(root, Vr, Fr, (0.2, 0.2, 0.22), pos=(0, 0.55, 0.34), orient="z")
    ring.setScale(0.92, 1.12, 1)
    zt = top(0, -0.45)
    Vt, Ft = lathe([(0.0, 0.0), (0.11, 0.03), (0.12, 0.2), (0.12, 0.36), (0.11, 0.41), (0.0, 0.44)], 18, "y")
    part(root, Vt, Ft, (0.35, 1.0, 0.45, 0.55), pos=(0.0, -0.62, zt + 0.08), unlit=True, alpha=True, orient="y")
    glow(root, (0.0, -0.42, zt + 0.08), 0.5, (0.35, 1.0, 0.45, 0.55))
    for y in (-0.63, -0.18):
        Vr, Fr = lathe([(0.135, 0.0), (0.14, 0.02), (0.135, 0.04)], 18, "y")
        part(root, Vr, Fr, (0.25, 0.25, 0.27), pos=(0.0, y, zt + 0.08), orient="y")
    for sgn in (1, -1):
        tube(root, [(sgn * 0.08, -0.2, zt + 0.12), (sgn * 0.2, -0.05, zt + 0.25), (sgn * 0.28, 0.15, zt + 0.2),
                    (sgn * 0.28, 0.25, top(0.28, 0.25) + 0.02)], 0.03, (0.16, 0.16, 0.18))
    # electronics rack with LED matrix
    zr = top(0.3, -1.05)
    Vb, Fb = box(0.38, 0.28, 0.1)
    part(root, Vb, Fb, (0.15, 0.15, 0.17), pos=(0.3, -1.05, zr + 0.04), smooth=None)
    rng = np.random.default_rng(3)
    for ix in range(5):
        for iy in range(3):
            col = ((0.3, 1.0, 0.3), (1.0, 0.25, 0.15), (0.3, 0.7, 1.0), (1.0, 0.8, 0.2))[rng.integers(4)]
            part(root, Vi * 0.017, Fi, col, pos=(0.18 + ix * 0.06, -1.13 + iy * 0.075, zr + 0.095), unlit=True)
    # radar dish and antennas
    zd = top(-0.32, 0.95)
    Vd, Fd = lathe([(0.0, 0.0), (0.12, 0.035), (0.19, 0.09)], 20, "z")
    part(root, Vd, Fd, (0.6, 0.6, 0.62), pos=(-0.32, 0.95, zd + 0.06), hpr=(30, 35, 0), orient=None, two_sided=True)
    part(root, Vi * 0.022, Fi, (1, 0.3, 0.2), pos=(-0.3, 0.93, zd + 0.12), unlit=True)
    for k in range(3):
        Vb, Fb = lathe([(0.01, 0), (0.006, 0.3 + k * 0.12)], 6, "z")
        part(root, Vb, Fb, (0.2, 0.2, 0.22), pos=(-0.2 - k * 0.07, -1.2, top(-0.2 - k * 0.07, -1.2)), orient="z")
    return root


# ---------------------------------------------------------------- Catliens

HULL_LO, HULL_HI = (0.035, 0.035, 0.04), (0.2, 0.19, 0.19)
EMBER = (1.0, 0.3, 0.06)
SICK_GREEN = (0.45, 1.0, 0.4)


def hull_paint(z0, z1):
    base = paint(HULL_LO, HULL_HI, z0, z1, grime=0.25)

    def f(p):
        c = np.array(base(p))
        rust = max(0.0, _noise(p, 0.7) - 0.45) * 1.6  # dried-blood rust patches
        return tuple(np.clip(c * (1 - rust) + np.array((0.24, 0.06, 0.04)) * rust, 0, 1))
    return f


def _fur(base, dark, stripes=True, seed=0):
    """Vertex colour for fur: soft noise, darker towards the back, tabby stripes and the forehead 'M'."""
    base, dark = np.array(base), np.array(dark)

    def f(p):
        x, y, z = p
        c = base * (1 + 0.18 * _noise(p, 9.0) + 0.08 * _noise(p, 23.0))
        if stripes:
            band = math.sin(z * 26 + 3 * math.sin(x * 9 + seed)) * math.cos(x * 4)
            c = c * (1 - 0.6 * max(0.0, band - 0.2) / 0.8)
        c = c * (1 - 0.25 * max(0.0, y) / 0.6)
        return tuple(np.clip(c * 0.6 + dark * 0.4 * (1 - min(1.0, max(0.0, -y + 0.2))), 0, 1))
    return f


def build_catlien(parent, scale=1.0, queen=False):
    """A Catlien: a big, realistic cat head and shoulders (armour collar, whisker pads, tall tufted ears,
    almond eyes with slit pupils, whiskers, tabby fur). The queen is black with red eyes. Faces -Y."""
    root = parent.attachNewNode("catlien")
    matte = Material("fur")
    matte.setSpecular((0.05, 0.05, 0.05, 1))
    matte.setShininess(5)
    root.setMaterial(matte, 1)
    if queen:
        fur = _fur((0.07, 0.065, 0.07), (0.02, 0.02, 0.025), stripes=False)
        eye_col, iris = (1.0, 0.12, 0.04), (1.0, 0.25, 0.05)
    else:
        fur = _fur((0.42, 0.34, 0.26), (0.12, 0.09, 0.07), seed=1)
        eye_col, iris = (1.0, 0.75, 0.1), (0.85, 0.65, 0.1)
    light_fur = _fur((0.62, 0.56, 0.48) if not queen else (0.12, 0.11, 0.12), (0.3, 0.27, 0.24), stripes=False)
    V, F = icosphere(3)
    head = root.attachNewNode("head")
    head.setPos(0, 0, 1.05)
    head.setP(-6)
    part(head, V * np.array([0.37, 0.36, 0.33]), F, (1, 1, 1), pos=(0, 0.02, 0.02), vcol=fur)       # cranium
    for sgn in (1, -1):
        part(head, V * np.array([0.17, 0.16, 0.15]), F, (1, 1, 1), pos=(sgn * 0.24, -0.06, -0.1), vcol=fur)  # cheek ruffs
        part(head, V * np.array([0.085, 0.075, 0.07]), F, (1, 1, 1), pos=(sgn * 0.065, -0.33, -0.14),
             vcol=light_fur)                                                                            # whisker pads
    part(head, V * np.array([0.07, 0.06, 0.05]), F, (1, 1, 1), pos=(0, -0.29, -0.22), vcol=light_fur)  # chin
    part(head, V * np.array([0.08, 0.12, 0.06]), F, (1, 1, 1), pos=(0, -0.3, -0.01), vcol=fur)         # bridge of the nose
    nose = [(-0.045, 0.0), (0.045, 0.0), (0.0, -0.045)]
    Vn, Fn = prism(nose, 0.03)
    part(head, Vn[:, [0, 2, 1]], Fn, (0.35, 0.18, 0.2) if not queen else (0.08, 0.05, 0.06),
         pos=(0, -0.4, -0.08), hpr=(0, -30, 0))                                                         # nose leather
    Vm, Fm = tube_mesh([(-0.06, -0.385, -0.2), (0, -0.4, -0.18), (0.06, -0.385, -0.2)], 0.008, 6)
    part(head, Vm, Fm, (0.05, 0.03, 0.03), orient=None)                                                 # mouth line
    for sgn in (1, -1):
        # ears: tall, slightly turned out, fur outside, pink-grey inside, tufts on the tips
        ear = head.attachNewNode("ear")
        ear.setPos(sgn * 0.21, 0.0, 0.24)
        ear.setHpr(sgn * -10, -15, sgn * 25)
        Vp, Fp = pyramid([(-0.14, 0.0), (0.14, 0.0), (0.0, 0.08)], (0.0, 0.02, 0.32))
        part(ear, Vp, Fp, (1, 1, 1), vcol=fur, smooth=None)
        Vi, Fi = pyramid([(-0.075, -0.01), (0.075, -0.01), (0.0, 0.03)], (0.0, -0.005, 0.24))
        part(ear, Vi, Fi, (0.45, 0.3, 0.3) if not queen else (0.15, 0.08, 0.09), pos=(0, -0.015, 0.01), smooth=None)
        Vt, Ft = tube_mesh([(0, 0.02, 0.29), (sgn * 0.01, 0.02, 0.35), (sgn * 0.02, 0.03, 0.4)], 0.008, 5)
        part(ear, Vt, Ft, (0.1, 0.08, 0.07), orient=None)
        # eyes: almond shaped, glowing iris with a vertical slit pupil, dark lid rims
        lens = [(-0.075, 0.0), (-0.03, 0.035), (0.04, 0.04), (0.08, 0.005), (0.035, -0.03), (-0.03, -0.03)]
        Ve, Fe = prism(lens, 0.02)
        Ve = Ve * np.array([1.35, 1.35, 1.0])
        part(head, Ve[:, [0, 2, 1]] * np.array([sgn, 1, 1]), Fe, iris, pos=(sgn * 0.15, -0.3, 0.06),
             hpr=(sgn * -20, 0, -sgn * 12), unlit=True)
        Vs, Fs = box(0.014, 0.03, 0.065)
        part(head, Vs * np.array([1, 1, 1.3]), Fs, (0, 0, 0), pos=(sgn * 0.15, -0.315, 0.06), hpr=(sgn * -20, 0, 0),
             unlit=True)
        Vr, Fr = tube_mesh([(sgn * (0.15 + 0.105 * math.cos(a)), -0.305 - 0.01 * math.cos(a), 0.06 + 0.05 * math.sin(a))
                            for a in np.linspace(0, 2 * math.pi, 14)], 0.008, 5)
        part(head, Vr, Fr, (0.03, 0.025, 0.025), orient=None)
        glow(head, (sgn * 0.15, -0.33, 0.06), 0.22, (*eye_col, 0.7))
        for k in range(4):  # whiskers fanning out from the pads
            a = math.radians(-20 + k * 12)
            Vw, Fw = tube_mesh([(sgn * 0.12, -0.36, -0.15 + 0.012 * k),
                                (sgn * (0.12 + 0.2 * math.cos(a)), -0.37 + 0.05, -0.15 + 0.2 * math.sin(a)),
                                (sgn * (0.12 + 0.42 * math.cos(a)), -0.3, -0.18 + 0.32 * math.sin(a))], 0.0035, 4)
            part(head, Vw, Fw, (0.9, 0.88, 0.84), orient=None)
    # neck fur, shoulders and the armoured collar of the warrior caste
    part(root, V * np.array([0.28, 0.26, 0.3]), F, (1, 1, 1), pos=(0, 0.06, 0.72), vcol=light_fur)
    part(root, V * np.array([0.62, 0.36, 0.28]), F, (1, 1, 1), pos=(0, 0.1, 0.4),
         vcol=paint((0.04, 0.04, 0.05), (0.22, 0.21, 0.22), 0.2, 0.68))
    Vc, Fc = lathe([(0.27, 0.6), (0.31, 0.68), (0.27, 0.76)], 20, "z")
    part(root, Vc, Fc, (0.3, 0.07, 0.05) if not queen else (0.35, 0.28, 0.1), orient="z")
    if queen:
        for k in range(7):  # a jewelled collar instead of a crown
            a = math.radians(-150 + k * 20)
            part(root, V * 0.025, F, (1.0, 0.15, 0.1), pos=(0.3 * math.cos(a), 0.3 * math.sin(a) + 0.05, 0.68),
                 unlit=True)
        Vt, Ft = sweep([(-0.2, 0.9, 0.12, 0, 3), (1.9, 0.6, 0.08, 0, 3)], 16, "y")
        throne = part(root, Vt, Ft, (1, 1, 1), orient=None, vcol=hull_paint(0, 2), name="throne")
        throne.setP(90)
        throne.setPos(0, 0.45, -0.1)
    root.setScale(scale)
    return root


SKIN_TONES = [(0.78, 0.6, 0.5), (0.6, 0.43, 0.32), (0.42, 0.28, 0.2), (0.86, 0.7, 0.6)]


def build_human(parent, female=False, skin=0, collar=(1.0, 0.1, 0.05)):
    """A standing human, about 1.75 units tall, facing -Y: realistic proportions (head, neck, torso with
    shoulders / chest / hips, two-part arms with hands, legs, feet), ragged clothes, hair and a glowing
    slave collar (named "collar"). Men are broad-shouldered with short hair, women narrower with long hair."""
    root = parent.attachNewNode("human")
    tone = np.array(SKIN_TONES[skin % len(SKIN_TONES)])
    skin_col = lambda p: tuple(np.clip(tone * (0.92 + 0.08 * _noise(p, 12.0)), 0, 1))  # noqa: E731
    cloth = paint((0.08, 0.07, 0.06), (0.3, 0.27, 0.22), 0.6, 1.4, grime=0.45)
    hair_col = (0.08, 0.06, 0.05) if skin % 2 else (0.22, 0.14, 0.08)
    V, F = icosphere(3)
    sh = 0.19 if female else 0.23            # half shoulder width
    hip = 0.17 if female else 0.15
    # torso as a sweep along z (x = width, y = depth): hips, waist, chest, shoulders
    torso = [(0.85, hip, 0.13, 0, 2.2), (1.0, hip * 0.82, 0.12, 0, 2.2), (1.15, sh * 0.78, 0.13, 0, 2.2),
             (1.3, sh * 0.92, 0.14, 0, 2.3), (1.42, sh * 0.95, 0.12, 0, 2.4), (1.48, sh * 0.55, 0.08, 0, 2.2)]
    Vt, Ft = sweep([(z, w, d, 0, n) for z, w, d, _, n in torso], 24, "y")
    part(root, Vt[:, [0, 2, 1]], Ft, (1, 1, 1), orient="center", vcol=skin_col)
    for sgn in (1, -1):  # shoulder muscles round off the silhouette
        part(root, V * 0.062, F, (1, 1, 1), pos=(sgn * (sh - 0.03), 0.0, 1.41), vcol=skin_col)
    # ragged clothes: a torn tunic / wrap over the hips (and chest for women)
    rag = [(0.6, hip * 1.12, 0.15, 0, 2.2), (0.9, hip * 1.08, 0.145, 0, 2.2), (1.05, hip * 0.9, 0.135, 0, 2.2)]
    if female:
        rag += [(1.18, sh * 0.86, 0.16, -0.0, 2.2), (1.29, sh * 0.95, 0.19, 0, 2.2), (1.4, sh * 0.97, 0.15, 0, 2.3)]
    Vr, Fr = sweep([(z, w, d, 0, n) for z, w, d, _, n in rag], 24, "y")
    part(root, Vr[:, [0, 2, 1]], Fr, (1, 1, 1), orient="center", vcol=cloth)
    # neck and head: skull, jaw, nose, brow, ears, hair
    Vn, Fn = lathe([(0.055, 1.44), (0.05, 1.52), (0.055, 1.56)], 12, "z")
    part(root, Vn, Fn, (1, 1, 1), orient="z", vcol=skin_col)
    head = root.attachNewNode("head")
    head.setPos(0, 0, 1.64)
    part(head, V * np.array([0.085, 0.1, 0.11]), F, (1, 1, 1), vcol=skin_col)
    part(head, V * np.array([0.065, 0.07, 0.05]), F, (1, 1, 1), pos=(0, -0.03, -0.065), vcol=skin_col)     # jaw
    part(head, V * np.array([0.016, 0.03, 0.03]), F, (1, 1, 1), pos=(0, -0.1, -0.01), vcol=skin_col)      # nose
    part(head, V * np.array([0.07, 0.025, 0.015]), F, (1, 1, 1), pos=(0, -0.085, 0.03), vcol=skin_col)    # brow
    for sgn in (1, -1):
        part(head, V * np.array([0.012, 0.022, 0.03]), F, (1, 1, 1), pos=(sgn * 0.085, 0.0, 0.0), vcol=skin_col)
        part(head, V * 0.012, F, (0.05, 0.04, 0.04), pos=(sgn * 0.032, -0.088, 0.012))                    # eyes
    if female:
        part(head, V * np.array([0.095, 0.11, 0.1]), F, hair_col, pos=(0, 0.015, 0.03))
        Vh, Fh = sweep([(0.05, 0.09, 0.06, 0, 2.2), (-0.15, 0.11, 0.05, 0, 2.2), (-0.32, 0.09, 0.03, 0, 2.0)], 16, "y")
        part(head, Vh[:, [0, 2, 1]], Fh, hair_col, pos=(0, 0.06, 0.0), orient="center")                  # long hair
    else:
        part(head, V * np.array([0.09, 0.105, 0.07]), F, hair_col, pos=(0, 0.01, 0.05))                  # short hair
    # arms: upper arm, forearm, hand; hanging, slightly bent
    for sgn in (1, -1):
        s0 = np.array([sgn * (sh - 0.02), 0.0, 1.4])
        el = s0 + np.array([sgn * 0.05, 0.02, -0.29])
        wr = el + np.array([sgn * 0.01, -0.06, -0.26])
        for a, b, r0, r1 in ((s0, el, 0.05 if not female else 0.042, 0.04), (el, wr, 0.038, 0.03)):
            Va, Fa = tube_mesh([a, (a + b) / 2, b], (r0 + r1) / 2, 10)
            part(root, Va, Fa, (1, 1, 1), orient=None, vcol=skin_col)
        part(root, V * np.array([0.03, 0.02, 0.06]), F, (1, 1, 1), pos=tuple(wr + (0, 0, -0.055)), vcol=skin_col)
    # legs and feet
    for sgn in (1, -1):
        h0 = np.array([sgn * hip * 0.5, 0.0, 0.88])
        kn = np.array([sgn * hip * 0.48, -0.02, 0.48])
        an = np.array([sgn * hip * 0.45, 0.0, 0.07])
        for a, b, r in ((h0, kn, 0.09 if female else 0.085), (kn, an, 0.058)):
            Vl, Fl = tube_mesh([a, (a + b) / 2, b], r, 10)
            part(root, Vl, Fl, (1, 1, 1), orient=None, vcol=skin_col if b[2] < 0.5 else cloth)
        part(root, V * np.array([0.045, 0.1, 0.035]), F, (1, 1, 1), pos=tuple(an + (0, -0.05, -0.04)), vcol=skin_col)
    # the collar
    Vc, Fc = lathe([(0.065, 1.47), (0.07, 1.5), (0.065, 1.53)], 16, "z")
    ring = part(root, Vc, Fc, collar, orient="z", unlit=True, name="collar")
    glow(ring, (0, -0.07, 1.5), 0.16, (*collar, 0.9))
    return root


RAIDER_BODY = [(1.25, 0.55, 0.15, 0.0, 3.0), (0.95, 0.8, 0.25, 0.02, 3.0), (0.4, 0.82, 0.29, 0.03, 3.0),
               (-0.15, 0.55, 0.25, 0.03, 2.8), (-0.55, 0.22, 0.17, 0.04, 2.4), (-0.95, 0.13, 0.12, 0.05, 2.2),
               (-1.25, 0.14, 0.13, 0.05, 2.2), (-1.45, 0.3, 0.21, 0.06, 2.4), (-1.8, 0.34, 0.24, 0.05, 2.5),
               (-2.1, 0.24, 0.17, 0.03, 2.4), (-2.3, 0.04, 0.04, 0.02, 2.0)]


def build_fighter(parent):
    """Catlien raider: a predatory warship - wide engine body, long neck, command pod with a cat pilot."""
    root = parent.attachNewNode("fighter")
    V, F = sweep(RAIDER_BODY, 36)
    part(root, V, F, (1, 1, 1), orient=None, vcol=hull_paint(-0.3, 0.32))
    rng = np.random.default_rng(21)
    greebles(root, RAIDER_BODY, 120, rng, None, size=(0.04, 0.13), height=(0.01, 0.05),
             region=lambda x, y: y > -0.4 or abs(x) < 0.1)
    Vi, Fi = icosphere(2)
    for sgn in (1, -1):
        wing = [(sgn * 0.55, 0.5, 0.07, 0.0, 2.2, 0.55), (sgn * 1.3, 0.36, 0.05, -0.32, 2.2, 0.48),
                (sgn * 2.0, 0.26, 0.04, -0.62, 2.2, 0.28)]
        Vw, Fw = sweep(wing, 24, "x")
        part(root, Vw, Fw, (1, 1, 1), orient=None, vcol=hull_paint(-0.7, 0.07))
        for k in range(4):  # structural ribs on the wing
            x = sgn * (0.75 + k * 0.32)
            Vr, Fr = box(0.04, 0.6 - k * 0.06, 0.05)
            part(root, Vr, Fr, (0.12, 0.11, 0.11), pos=(x, 0.5 - k * 0.03, -0.0 - k * 0.15 + 0.05),
                 hpr=(0, 0, -sgn * 24), smooth=None)
        # wingtip disruptor cannons
        Vc, Fc = lathe([(0.0, 0.45), (0.08, 0.4), (0.09, -0.1), (0.06, -0.85), (0.075, -1.0)], 14, "y")
        part(root, Vc, Fc, (1, 1, 1), pos=(sgn * 2.0, 0.25, -0.62), orient="y", vcol=hull_paint(-0.7, -0.5))
        glow(root, (sgn * 2.0, -0.8, -0.62), 0.32, (*EMBER, 0.85))
        # conduits along the neck
        tube(root, [(sgn * 0.2, 0.1, 0.27), (sgn * 0.12, -0.5, 0.2), (sgn * 0.1, -1.0, 0.17),
                    (sgn * 0.15, -1.4, 0.24)], 0.025, (0.1, 0.09, 0.09))
        # glowing vent slits and engines
        for k in range(4):
            Vs, Fs = box(0.2, 0.025, 0.02)
            part(root, Vs, Fs, EMBER, pos=(sgn * 0.5, 0.25 + k * 0.12, sweep_top(RAIDER_BODY, sgn * 0.5, 0.25 + k * 0.12) + 0.005),
                 unlit=True)
        Vn, Fn = lathe([(0.12, 1.15), (0.16, 1.3), (0.2, 1.42)], 16, "y")
        part(root, Vn, Fn, (0.08, 0.08, 0.09), pos=(sgn * 0.32, 0, 0), orient="y", two_sided=True)
        glow(root, (sgn * 0.32, 1.45, 0), 0.55, (1.0, 0.2, 0.05, 0.9))
    # belly emitter (seen only when the raider rolls over): a ribbed disc with a violet core
    Vd, Fd = lathe([(0.0, -0.26), (0.32, -0.25), (0.38, -0.2)], 28, "z")
    part(root, Vd, Fd, (0.14, 0.1, 0.12), pos=(0, 0.35, 0), orient=None, two_sided=True)
    for k in range(3):
        Vr, Fr = annulus(0.1 + k * 0.08, 0.13 + k * 0.08, 28, 2, z=-0.265)
        part(root, Vr, Fr, (1.0, 0.4, 0.95), pos=(0, 0.35, 0), unlit=True, orient=None, two_sided=True)
    glow(root, (0, 0.35, -0.3), 0.7, (1.0, 0.35, 0.95, 0.8))
    # command pod: red-lit canopy with the Catlien pilot inside
    build_catlien(root, 0.15, queen=False).setPos(0, -1.74, 0.2)
    glow(root, (0, -1.5, 0.36), 0.5, (1.0, 0.08, 0.04, 0.55))  # red backlight: pilot reads as a silhouette
    Vh, Fh = hemisphere(3)
    part(root, Vh * np.array([0.21, 0.32, 0.2]), Fh, (0.9, 0.3, 0.2, 0.16), pos=(0, -1.75, 0.27),
         alpha=True, two_sided=True)
    Vr, Fr = lathe([(1.0, 0.0), (1.06, 0.02), (1.0, 0.045)], 28, "z")  # canopy rim
    part(root, Vr, Fr, (0.07, 0.07, 0.07), pos=(0, -1.75, 0.255), scale=(0.21, 0.32, 1), orient="z")
    return root


def build_tractor_beam(parent):
    """The raider's belly pull: a pink-violet cone along -y, 1 unit long (scaled to the distance)."""
    root = parent.attachNewNode("tractor")
    for r0, r1, a in ((0.18, 0.9, 0.22), (0.08, 0.45, 0.35)):
        V, F = lathe([(r0, 0.0), (r1, -1.0)], 20, "y")
        part(root, V, F, (1, 1, 1), additive=True, orient=None,
             vcol=lambda p, a=a: (1.0, 0.35 + 0.3 * (-p[1]), 0.95, a * (0.35 + 0.65 * (1 + p[1]))))
    for k in range(6):  # rings travelling along the cone read as "pulling"
        y = -(k + 0.5) / 6
        V, F = annulus(0.9 * 0.18 + (0.9 - 0.18) * -y - 0.03, 0.18 + (0.9 - 0.18) * -y, 32, 2)
        part(root, V, F, (1.0, 0.55, 1.0, 0.25), pos=(0, y, 0), hpr=(0, 90, 0), additive=True, orient=None)
    return root


def build_space_mouse(parent):
    """A cybernetic space mouse, about 0.8 units long, nose along +y: grey fur, pink ears, a long tail,
    a red implant eye and a tiny thruster."""
    root = parent.attachNewNode("space-mouse")
    fur = paint((0.18, 0.16, 0.16), (0.55, 0.5, 0.48), -0.15, 0.2, grime=0.3)
    body = [(-0.32, 0.03, 0.03, 0.0, 2.0), (-0.25, 0.15, 0.13, 0.0, 2.0), (-0.05, 0.2, 0.17, 0.02, 2.0),
            (0.15, 0.17, 0.15, 0.03, 2.0), (0.3, 0.1, 0.09, 0.02, 2.0), (0.42, 0.02, 0.02, 0.0, 2.0)]
    V, F = sweep(body, 20)
    part(root, V, F, (1, 1, 1), orient=None, vcol=fur)
    Vi, Fi = icosphere(2)
    for sgn in (1, -1):
        part(root, Vi * np.array([0.09, 0.025, 0.09]), Fi, (0.95, 0.6, 0.62), pos=(sgn * 0.1, 0.2, 0.16))
        part(root, Vi * np.array([0.06, 0.03, 0.06]), Fi, (0.75, 0.35, 0.4), pos=(sgn * 0.1, 0.19, 0.16))
    part(root, Vi * 0.03, Fi, (1.0, 0.08, 0.04), pos=(0.07, 0.33, 0.07), unlit=True)  # implant eye
    glow(root, (0.07, 0.35, 0.07), 0.22, (1.0, 0.1, 0.05, 0.95))
    part(root, Vi * 0.022, Fi, (0.02, 0.02, 0.02), pos=(-0.07, 0.33, 0.07))
    part(root, Vi * 0.025, Fi, (0.95, 0.55, 0.6), pos=(0, 0.43, 0.0))  # nose
    for sgn in (1, -1):  # whiskers
        for k in (-1, 1):
            Vw, Fw = tube_mesh([(sgn * 0.03, 0.4, 0.01 * k), (sgn * 0.15, 0.42, 0.03 * k), (sgn * 0.26, 0.38, 0.05 * k)],
                               0.004, 4)
            part(root, Vw, Fw, (0.85, 0.85, 0.85), orient=None)
    tube(root, [(0, -0.3, 0.0), (0.12, -0.5, 0.05), (-0.12, -0.7, 0.02), (0.05, -0.92, 0.08)], 0.018,
         (0.85, 0.55, 0.55))
    Vt, Ft = lathe([(0.05, -0.18), (0.06, -0.3), (0.04, -0.36)], 12, "y")  # thruster on its back
    part(root, Vt, Ft, (0.2, 0.2, 0.22), pos=(0, 0, 0.16), orient="y")
    glow(root, (0, -0.4, 0.16), 0.3, (0.4, 0.8, 1.0, 0.9))
    return root


def mothership_layout(width=14.0):
    """x boundaries of the damage zones (30% / 15% / 10% / 15% / 30%)."""
    w = width
    return [-w / 2, -w / 2 + 0.30 * w, -w / 2 + 0.45 * w, w / 2 - 0.45 * w, w / 2 - 0.30 * w, w / 2]


def build_mothership(parent, width=14.0):
    """The Mother's dreadnought: an arrowhead of machinery and darkness; she sits behind the bridge glass."""
    root = parent.attachNewNode("mothership")
    s = width / 14.0
    hull = [(5.0, 5.0 * s, 0.95, 0.0, 3.6), (3.6, 7.0 * s, 1.3, 0.1, 3.6), (1.5, 6.6 * s, 1.55, 0.2, 3.3),
            (-0.8, 4.6 * s, 1.45, 0.2, 3.0), (-2.8, 2.4 * s, 1.05, 0.15, 2.7), (-4.3, 0.9 * s, 0.6, 0.1, 2.4),
            (-5.0, 0.12, 0.12, 0.05, 2.0)]
    V, F = sweep(hull, 48)
    part(root, V, F, (1, 1, 1), orient=None, vcol=hull_paint(-1.3, 1.75))
    keel = [(4.6, 3.6 * s, 0.7, -1.2, 3.0), (1.0, 4.6 * s, 0.95, -1.35, 3.0), (-2.5, 1.9 * s, 0.7, -1.0, 2.6),
            (-3.9, 0.4, 0.3, -0.7, 2.2)]
    Vk, Fk = sweep(keel, 40)
    part(root, Vk, Fk, (1, 1, 1), orient=None, vcol=hull_paint(-2.2, -0.6))
    rng = np.random.default_rng(11)
    zones = mothership_layout(width)

    def pick(x, y):
        ax = abs(x)
        if ax < zones[3] + 0.4 and y < 1.5:
            return (0.09, 0.09, 0.1)
        r = rng.random()
        if zones[3] < ax < zones[4] and r < 0.12:
            return (1.0, 0.35, 0.06, 1, 1)  # zone 2: glowing vents (5-tuple = emissive)
        if r < 0.035:
            return (*SICK_GREEN, 1, 1)
        return ((0.08, 0.08, 0.09), (0.13, 0.12, 0.12), (0.18, 0.16, 0.15), (0.11, 0.07, 0.06))[rng.integers(4)]

    greebles(root, hull, 520, rng, pick, size=(0.1, 0.45), height=(0.03, 0.22))
    greebles(root, hull, 400, rng, None, size=(0.03, 0.12), height=(0.02, 0.08))
    for k in range(6):  # long conduits along the hull
        x = (-5.5 + k * 2.2) * s
        if abs(x) < 1.0:
            continue
        pts = [(x * (1 - 0.15 * j / 5), 4.2 - j * 1.4, 0) for j in range(6)]
        pts = [(px, py, (sweep_top(hull, px, py) or 0.3) + 0.05) for px, py, _ in pts if sweep_top(hull, px, py)]
        if len(pts) > 2:
            Vt, Ft = tube_mesh(pts, 0.09, 10)
            part(root, Vt, Ft, (0.1, 0.09, 0.09), orient=None)
    Vi, Fi = icosphere(2)
    for sgn in (1, -1):
        for k in range(5):  # turrets along the leading edges
            y = -3.6 + k * 1.1
            x = sgn * (0.9 + k * 0.85) * s
            z = sweep_top(hull, x, y) or 0.3
            Vt, Ft = lathe([(0.22, 0.0), (0.24, 0.12), (0.16, 0.22)], 14, "z")
            part(root, Vt, Ft, (0.12, 0.11, 0.11), pos=(x, y, z), orient="z")
            Vc, Fc = lathe([(0.04, 0.0), (0.04, -0.55)], 8, "y")
            part(root, Vc, Fc, (0.08, 0.08, 0.08), pos=(x, y, z + 0.13), orient="y")
            glow(root, (x, y - 0.6, z + 0.13), 0.35, (*EMBER, 0.85))
        for k in range(5):  # rear spikes
            x = sgn * (1.5 + k * 1.1) * s
            Vk, Fk = lathe([(0.18, 0.0), (0.0, 1.2 + 0.3 * (k % 2))], 8, "y")
            part(root, Vk, Fk, (1, 1, 1), pos=(x, 4.6 - k * 0.25, 0.3), hpr=(sgn * -8, 12, 0), orient="y",
                 vcol=hull_paint(0, 0.6))
    for k in range(5):  # engine bank
        x = (-2.4 + k * 1.2) * s
        Vn, Fn = lathe([(0.35, 4.9), (0.45, 5.2), (0.55, 5.4)], 18, "y")
        part(root, Vn, Fn, (0.07, 0.07, 0.08), pos=(x, 0, 0), orient="y", two_sided=True)
        glow(root, (x, 5.5, 0), 1.3, (1.0, 0.15, 0.04, 0.85))
    # bridge tower (zone 3) with the Mother behind red glass
    tower = [(1.8, 0.55 * s, 0.4, 1.9, 3.0), (0.2, 0.7 * s, 0.62, 2.05, 3.0), (-0.8, 0.66 * s, 0.55, 2.0, 2.8),
             (-1.3, 0.4 * s, 0.35, 1.9, 2.5)]
    Vt, Ft = sweep(tower, 32)
    part(root, Vt, Ft, (1, 1, 1), orient=None, vcol=hull_paint(1.4, 2.7))
    build_catlien(root, 0.5, queen=True).setPos(0, -1.1, 2.02)
    glow(root, (0, -0.55, 2.45), 1.5, (1.0, 0.06, 0.03, 0.6))  # backlit throne
    Vh, Fh = hemisphere(3)
    part(root, Vh * np.array([0.62 * s, 0.7, 0.85]), Fh, (0.9, 0.3, 0.2, 0.15), pos=(0, -1.25, 2.2),
         alpha=True, two_sided=True)
    Vr, Fr = lathe([(1.0, 0.0), (1.05, 0.03), (1.0, 0.07)], 32, "z")  # bridge window rim
    part(root, Vr, Fr, (0.07, 0.07, 0.07), pos=(0, -1.25, 2.17), scale=(0.62 * s, 0.7, 1), orient="z")
    glow(root, (0, 0, -0.9), 6.0, (0.6, 0.05, 0.03, 0.35))
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
        V, F, vcol, _ = asteroid_mesh(int(rng.integers(1000)), rng.uniform(0.08, 0.22), sub=0)
        part(root, V, F, (1, 1, 1), vcol=vcol, pos=tuple(p), hpr=tuple(rng.uniform(0, 360, 3)))
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
            th = math.atan2(p[1], p[0])
            rr = math.hypot(p[0], p[1])
            u = (rr - (R - width)) / width
            stripe = 0.5 + 0.5 * math.sin(9 * th + 14 * u + k * 1.3)
            r, g, b = (0.55 + 0.45 * stripe, 0.25 + 0.7 * stripe ** 3, 1.0)
            return (r, g, b, 0.85 * math.sin(math.pi * min(max(u, 0), 1)) ** 2)

        part(root, V, F, (1, 1, 1), orient=None, additive=True, vcol=col)
    root.setPos(*center)
    return root


EYE_Z, MOUTH_Z = -0.3, -1.05  # helmet-local eye and mouth height (used for webcam alignment)


def build_helmet(parent):
    """AR overlay: life-support helmet with an exposed brain under a glass dome.

    Head-local coordinates: head centre at origin, head half-width ~1, face looks along -Y,
    eyes at EYE_Z, mouth at MOUTH_Z, chin at z~-1.6.
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
    build_tactical_shades(root)
    # cigar in the corner of the mouth, glowing tip and a wisp of smoke
    cig = root.attachNewNode("cigar")
    Vc, Fc = lathe([(0.0, 0.0), (0.06, -0.02), (0.075, -0.15), (0.075, -0.62), (0.07, -0.7)], 8, "y")
    part(cig, Vc, Fc, (0.42, 0.25, 0.11), orient="y")
    Vr, Fr = lathe([(0.079, -0.12), (0.079, -0.2)], 8, "y")
    part(cig, Vr, Fr, (0.85, 0.65, 0.15), orient="y")
    Vt, Ft = lathe([(0.072, -0.7), (0.06, -0.74), (0.0, -0.76)], 8, "y")
    part(cig, Vt, Ft, (1.0, 0.4, 0.05), orient="y", unlit=True)
    glow(cig, (0, -0.74, 0), 0.25, (1.0, 0.45, 0.1, 0.9)).setName("cigar_glow")
    cig.setPos(0.14, -0.96, MOUTH_Z)
    cig.setHpr(28, -10, 0)
    rng = np.random.default_rng(8)
    tip = root.getRelativePoint(cig, Point3(0, -0.76, 0))
    for k in range(7):
        p = (tip[0] + 0.06 * k + rng.uniform(-0.05, 0.05), tip[1] - 0.02 * k, tip[2] + 0.12 + 0.17 * k)
        glow(root, p, 0.18 + 0.07 * k, (0.75, 0.75, 0.8, 0.22 - 0.025 * k))
    return root


def build_tactical_shades(root):
    """Heavy wraparound shades, space-marine style: big angular mirrored lenses that follow the curve of
    the face, a thick armoured brow bar, side shields and riveted temples. Lenses are named "lens"
    (they glow violet while the eyes are closed)."""
    gun = paint((0.05, 0.05, 0.06), (0.3, 0.31, 0.34), EYE_Z - 0.2, EYE_Z + 0.25, grime=0.15)
    # one lens: a curved plate (columns across x, rows over z), wrapping back towards the temples
    outline_top = lambda u: 0.17 - 0.03 * u ** 2          # noqa: E731  top edge, u -1 (nose) .. 1 (temple)
    outline_bot = lambda u: -0.2 + 0.09 * u ** 2 + 0.05 * u  # noqa: E731
    nu, nv = 12, 6

    def lens_mesh(sgn, inset=0.0, y_off=0.0):
        V, F = [], []
        for i in range(nu + 1):
            u = -1 + 2 * i / nu
            x = sgn * (0.37 + 0.3 * u)
            wrap = 0.24 * max(0.0, u + 0.3) ** 2               # bends back towards the ear
            for j in range(nv + 1):
                v = j / nv
                z = outline_bot(u) + inset + (outline_top(u) - outline_bot(u) - 2 * inset) * v
                V.append((x, -1.0 + wrap + 0.02 * (2 * v - 1) ** 2 + y_off, EYE_Z + z))
        for i in range(nu):
            for j in range(nv):
                a = i * (nv + 1) + j
                F.append((a, a + nv + 1, a + nv + 2, a + 1))
        return np.array(V, float), F

    def mirror(p):
        """Dark amber below, steel blue above, and a diagonal sheen: reads as a mirrored visor."""
        h = min(1.0, max(0.0, (p[2] - EYE_Z + 0.2) / 0.37))
        sheen = max(0.0, 1 - abs((abs(p[0]) * 0.8 + (p[2] - EYE_Z)) - 0.38) / 0.035) * 0.55
        return (0.08 * (1 - h) + 0.12 * h + sheen, 0.04 * (1 - h) + 0.22 * h + sheen, 0.02 * (1 - h) + 0.36 * h + sheen)
    for sgn in (1, -1):
        V, F = lens_mesh(sgn)
        lens = part(root, V, F, (1, 1, 1), orient=None, two_sided=True, vcol=mirror, name="lens")
        lens.setMaterial(Material("mirror"), 1)
        lens.getMaterial().setSpecular((1.4, 1.4, 1.5, 1))
        lens.getMaterial().setShininess(90)
        # frame: a rim around the lens edge (tubes along the outline)
        rim = [(sgn * (0.37 + 0.3 * u), -1.0 + 0.24 * max(0.0, u + 0.3) ** 2 - 0.005, EYE_Z + f(u))
               for f in (outline_top, outline_bot) for u in np.linspace(-1, 1, 14)]
        top, bot = rim[:14], rim[14:]
        for pts, r in ((top, 0.035), (bot, 0.022)):
            Vr, Fr = tube_mesh(pts, r, 8)
            part(root, Vr, Fr, (1, 1, 1), orient=None, vcol=gun)
        Ve, Fe = tube_mesh([top[0], bot[0]], 0.022, 8)
        part(root, Ve, Fe, (1, 1, 1), orient=None, vcol=gun)
        # side shield and armoured temple arm with rivets and a status light
        Vs, Fs = box(0.05, 0.3, 0.3)
        part(root, Vs, Fs, (1, 1, 1), pos=(sgn * 0.69, -0.72, EYE_Z), hpr=(sgn * 12, 0, 0), vcol=gun, smooth=None)
        Va, Fa = box(0.07, 0.9, 0.08)
        part(root, Va, Fa, (1, 1, 1), pos=(sgn * 0.72, -0.3, EYE_Z + 0.06), hpr=(sgn * 6, 0, 0), vcol=gun, smooth=None)
        Vi, Fi = icosphere(1)
        for k in range(3):
            part(root, Vi * 0.018, Fi, (0.6, 0.6, 0.62), pos=(sgn * 0.735, -0.62 + 0.12 * k, EYE_Z + 0.06))
        part(root, Vi * 0.02, Fi, (1.0, 0.2, 0.1), pos=(sgn * 0.735, -0.25, EYE_Z + 0.07), unlit=True)
        glow(root, (sgn * 0.74, -0.25, EYE_Z + 0.07), 0.08, (1.0, 0.2, 0.1, 0.9))
    # brow bar across both lenses and a heavy nose bridge
    brow = [(x, -1.01 + 0.24 * max(0.0, (abs(x) - 0.37) / 0.3 + 0.3) ** 2, EYE_Z + 0.185 - 0.02 * (x / 0.67) ** 2)
            for x in np.linspace(-0.67, 0.67, 21)]
    Vb, Fb = tube_mesh(brow, 0.045, 10)
    part(root, Vb, Fb, (1, 1, 1), orient=None, vcol=gun)
    Vn, Fn = box(0.12, 0.06, 0.09)
    part(root, Vn, Fn, (1, 1, 1), pos=(0, -1.02, EYE_Z + 0.07), vcol=gun, smooth=None)


def _bezier(ctrl, n):
    P = np.array(ctrl, float)
    out = []
    for t in np.linspace(0, 1, n):
        out.append((1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t ** 2 * P[2] + t ** 3 * P[3])
    return out


def build_brain_burst(parent, t, seed=3, scale=1.0):
    """Shot Boltzmann brain: brain chunks, blood droplets and a red mist (t in [0, 1])."""
    root = parent.attachNewNode("brainburst")
    rng = np.random.default_rng(seed)
    Vi, Fi = icosphere(1)
    fade = (1 - t) ** 1.2
    glow(root, (0, 0, 0), 1.5 + 3.5 * t, (0.6, 0.0, 0.02, 0.7 * fade))
    for _ in range(24):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        p = d * (0.2 + 3.2 * t * rng.uniform(0.5, 1.2))
        Vc = Vi * rng.uniform(0.08, 0.22) * (1 + 0.35 * rng.normal(size=(len(Vi), 1)))
        pink = (0.9, rng.uniform(0.4, 0.55), 0.55)
        part(root, Vc, Fi, pink, pos=tuple(p), hpr=tuple(rng.uniform(0, 360, 3)))
    for _ in range(45):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        p = d * (0.3 + 4.2 * t * rng.uniform(0.4, 1.3))
        stretch = 1 + 4 * t
        drop = part(root, Vi * np.array([0.05, 0.05 * stretch, 0.05]), Fi, (0.5, 0.01, 0.03), pos=tuple(p))
        drop.lookAt(root, tuple(p * 2))
        glow(root, tuple(p), 0.22, (0.8, 0.02, 0.03, 0.6 * fade))
    root.setScale(scale)
    return root

