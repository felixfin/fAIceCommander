"""Realistic humans for the cutscenes: MakeHuman (CC0) bodies baked by tools/humans/bake.py into
assets/humans/bodies.npz (shaped, posed, with rag / scalp selections), dressed here with skin colour,
grime, eyes, hair, rags and a slave collar."""

import math

import numpy as np
from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat, GeomVertexData, GeomVertexFormat, InternalName, Material,
    NodePath,
)

from . import models as M

# skin tones and the body each is shaped on
TONES = [((0.78, 0.6, 0.5), "caucasian"), ((0.42, 0.28, 0.2), "african"), ((0.6, 0.43, 0.32), "caucasian"),
         ((0.86, 0.7, 0.6), "caucasian"), ((0.33, 0.22, 0.16), "african")]
POSES = ("broken", "upright", "cheer")
_DATA = None


def _data():
    global _DATA
    if _DATA is None:
        from ..config import ASSETS_DIR
        with np.load(ASSETS_DIR / "humans" / "bodies.npz") as z:
            _DATA = {k: z[k] for k in z.files}
    return _DATA


def _format():
    arr = GeomVertexArrayFormat()
    arr.addColumn(InternalName.getVertex(), 3, Geom.NT_float32, Geom.C_point)
    arr.addColumn(InternalName.getNormal(), 3, Geom.NT_float32, Geom.C_normal)
    arr.addColumn(InternalName.getColor(), 4, Geom.NT_float32, Geom.C_color)
    return GeomVertexFormat.registerFormat(GeomVertexFormat(arr))


_FORMAT = None


def noise3(P, k, seed):
    """Cheap smooth 3D noise in [-1, 1] at points P (sum of random plane waves)."""
    rng = np.random.default_rng(seed)
    acc = np.zeros(len(P))
    for _ in range(6):
        acc += np.sin(P @ rng.normal(size=3) * k + rng.uniform(0, 6.3))
    return acc / 6


def normals(P, T):
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    N = np.zeros_like(P)
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)


def mesh_node(name, P, N, T, colors):
    """A smooth vertex-coloured triangle mesh (float colours: the packed default format bands them)."""
    global _FORMAT
    if _FORMAT is None:
        _FORMAT = _format()
    vd = GeomVertexData(name, _FORMAT, Geom.UHStatic)
    vd.uncleanSetNumRows(len(P))
    arr = np.concatenate([P, N, colors, np.ones((len(P), 1))], 1).astype(np.float32)
    vd.modifyArray(0).modifyHandle().copyDataFrom(arr.tobytes())
    prim = GeomTriangles(Geom.UHStatic)
    prim.setIndexType(Geom.NT_uint32)
    handle = prim.modifyVertices()
    handle.uncleanSetNumRows(len(T) * 3)
    handle.modifyHandle().copyDataFrom(np.ascontiguousarray(T, np.uint32).tobytes())
    g = Geom(vd)
    g.addPrimitive(prim)
    gn = GeomNode(name)
    gn.addGeom(g)
    return NodePath(gn)


def build_human(parent, female=False, tone=0, pose="broken", collar="slave", dirt=0.3, seed=1,
                rags=(0.24, 0.2, 0.15)):
    """A realistic man or woman, facing -Y, feet at 0. tone: index into TONES; pose: broken (bowed, arms
    pulled in), upright, cheer (arms up); collar: "slave" (metal with a red light), "dead" (plain metal)
    or None. The collar is a child node named "collar" at the origin (so it can be dropped with setZ)."""
    d = _data()
    col, ethnic = TONES[tone % len(TONES)]
    key = f"{'female' if female else 'male'}_{ethnic}"
    T = d["tris"]
    P = d[f"{key}_{pose}_P"].astype(np.float64)
    neck, head, eye_l, eye_r = d[f"{key}_{pose}_joints"]
    N = normals(P, T)
    root = parent.attachNewNode("human")
    # skin: tone with blotchy variation, grime, dirty feet
    shade = 1 + 0.07 * noise3(P, 40, seed) + 0.03 * noise3(P, 140, seed + 1) \
        - dirt * np.clip(noise3(P, 18, seed + 2), 0, 1)
    skin = np.clip(np.array(col)[None] * shade[:, None], 0, 1)
    skin[P[:, 2] < 0.08] *= 0.55
    body = mesh_node("body", P, N, T, skin)
    body.reparentTo(root)
    mat = Material("skin")
    mat.setSpecular((0.12, 0.1, 0.1, 1))
    mat.setShininess(12)
    body.setMaterial(mat, 1)
    Vi, Fi = M.icosphere(2)
    for e in (eye_l, eye_r):  # the body mesh has sockets only
        M.part(root, Vi, Fi, (0.62, 0.58, 0.52), pos=tuple(e), scale=0.0115)
        M.part(root, Vi, Fi, (0.12, 0.08, 0.05), pos=(e[0], e[1] - 0.009, e[2]), scale=(0.0055, 0.004, 0.0055))
    # rags: a grimy cloth shell just above the skin
    cloth = np.clip(np.array(rags)[None] * (0.75 + 0.3 * noise3(P, 60, seed + 9)[:, None]), 0, 1)
    r = mesh_node("rags", P + N * 0.008, N, T[d[f"{key}_rag"]], cloth)
    r.reparentTo(root)
    r.setTwoSided(True)
    # hair: a cap over the scalp; women wear it tied back in a braid
    hc = np.array((0.07, 0.05, 0.04) if ethnic == "african" or seed % 2 else (0.25, 0.16, 0.09))
    hcol = np.clip(hc[None] * (0.85 + 0.3 * noise3(P, 90, seed + 3)[:, None]), 0, 1)
    mesh_node("hair", P + N * (0.009 if female else 0.005), N, T[d[f"{key}_scalp"]], hcol).reparentTo(root)
    if female:
        pts = d[f"{key}_{pose}_braid"].astype(np.float64)
        for k in range(len(pts) - 1):  # plaited, tapering
            rr = 0.024 * (1 - 0.5 * k / (len(pts) - 1))
            p0, p1 = pts[k], pts[k + 1]
            for side in (-1, 1):
                off = np.array([side * rr * 0.5, 0, 0])
                M.tube(root, [p0 - off, p0 * 0.67 + p1 * 0.33 + off, p0 * 0.33 + p1 * 0.67 + off, p1 - off],
                       rr * 0.75, tuple(hc * (0.9 + 0.12 * side)), n=6)
        M.part(root, *M.icosphere(1), (0.2, 0.15, 0.1), pos=tuple(pts[-1]), scale=0.014)
    if collar:
        ring = root.attachNewNode("collar")  # stays at the origin: callers drop it with setZ
        axis = np.array(head) - np.array(neck)
        axis /= np.linalg.norm(axis)
        band = ring.attachNewNode("band")  # round the neck, tilted with it
        band.setPos(*(np.array(neck) + axis * 0.045))
        band.setP(math.degrees(math.atan2(-axis[1], axis[2])))
        Vr, Fr = M.lathe([(0.062, -0.017), (0.069, 0.0), (0.062, 0.017)], 24, "z")
        M.part(band, Vr, Fr, (0.16, 0.15, 0.15), orient="z")
        if collar == "slave":
            for y in (-0.071, 0.071):
                M.part(band, Vi, Fi, (1.0, 0.1, 0.05), pos=(0, y, 0), scale=0.008, unlit=True)
    return root


def neck(female, tone, pose):
    """The neck joint of a body (where leashes attach), in the model's own space."""
    key = f"{'female' if female else 'male'}_{TONES[tone % len(TONES)][1]}"
    return tuple(float(v) for v in _data()[f"{key}_{pose}_joints"][0])


def build_stasis_tube(parent, female, tone, h=0.0, seed=11):
    """A glass tube of green fluid with a human floating in it (upright, hoses from above), about 2.2 high."""
    root = parent.attachNewNode("stasis")
    p = build_human(root, female, tone, "upright", collar=None, dirt=0.1, seed=seed, rags=(0.14, 0.18, 0.15))
    p.setPos(0, 0, 0.08)
    p.setH(h)
    p.setColorScale(0.75, 0.95, 0.9, 1)
    V, F = M.lathe([(0.36, 0.0), (0.36, 2.05)], 40, "z")
    glass = M.part(root, V, F, (0.4, 1.0, 0.7, 0.13), pos=(0, 0, -0.05), orient=None, alpha=True, two_sided=True)
    glass.setBin("transparent", 20)
    for z in (-0.08, 2.0):
        Vr, Fr = M.lathe([(0.4, 0.0), (0.42, 0.06), (0.42, 0.14), (0.38, 0.18)], 40, "z")
        M.part(root, Vr, Fr, (1, 1, 1), pos=(0, 0, z), orient="z", vcol=M.paint((0.05, 0.05, 0.06), (0.35, 0.36, 0.38), -0.1, 0.2))
    for k in range(5):
        M.glow(root, (0, -0.1, 0.3 + k * 0.38), 0.7, (0.3, 1.0, 0.6, 0.18))
    for s in (-1, 1):
        M.tube(root, [(s * 0.08, 0, 1.55), (s * 0.15, 0, 1.8), (s * 0.1, 0, 2.0), (s * 0.1, 0, 2.3)], 0.015, (0.1, 0.1, 0.1))
    return root
