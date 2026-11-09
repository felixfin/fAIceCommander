"""Bakes the realistic humans of the cutscenes from MakeHuman's CC0 base mesh into
faicecommander/assets/humans/bodies.npz - shaped (ethnic / gender targets), posed (linear blend skinning
on the default skeleton) and with the selections the game needs (rags, scalp, braid, joints). The game
only reads the .npz; MakeHuman is a development source, not a dependency.

Source files (CC0, from github.com/makehumancommunity/makehuman, folder makehuman/data) in build/mh/:
    3dobjs/base.obj                         -> base.obj
    targets/macrodetails/<e>-<g>-young.target -> <e>-<g>-young.target  (e: african, caucasian; g: male, female)
    rigs/default.mhskel, rigs/default_weights.mhw

    python tools/humans/bake.py
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MH = ROOT / "build" / "mh"
OUT = ROOT / "faicecommander" / "assets" / "humans" / "bodies.npz"

# bone rotations (axis in MakeHuman space: x = the character's left, y up, z forward; degrees, applied in order)
POSES = {
    "broken": {"upperarm01.L": [((0, 0, 1), -50), ((1, 0, 0), -30)], "upperarm01.R": [((0, 0, 1), 50), ((1, 0, 0), -30)],
               "lowerarm01.L": [((1, 0, 0), -55), ((0, 1, 0), -25)], "lowerarm01.R": [((1, 0, 0), -55), ((0, 1, 0), 25)],
               "spine03": ((1, 0, 0), 14), "spine02": ((1, 0, 0), 8), "neck01": ((1, 0, 0), 18), "head": ((1, 0, 0), 16)},
    "upright": {"upperarm01.L": ((0, 0, 1), -42), "upperarm01.R": ((0, 0, 1), 42),
                "lowerarm01.L": ((1, 0, 0), -12), "lowerarm01.R": ((1, 0, 0), -12)},
    "cheer": {"upperarm01.L": [((0, 0, 1), 95), ((1, 0, 0), -15)], "upperarm01.R": [((0, 0, 1), -95), ((1, 0, 0), -15)],
              "lowerarm01.L": ((0, 0, 1), 25), "lowerarm01.R": ((0, 0, 1), -25), "head": ((1, 0, 0), -12)},
}
BODIES = [(g, e) for g in ("male", "female") for e in ("caucasian", "african")]
HEIGHT = {"male": 1.72, "female": 1.64}
JOINTS = ("neck01____head", "head____head", "eye.L____head", "eye.R____head")


def load_obj():
    V, faces, group = [], [], None
    for line in open(MH / "base.obj"):
        if line.startswith("v "):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("g "):
            group = line.split()[1]
        elif line.startswith("f ") and group == "body":
            faces.append([int(p.split("/")[0]) - 1 for p in line.split()[1:]])
    return np.array(V), faces


def target(V, name):
    V = V.copy()
    for line in open(MH / f"{name}.target"):
        if line[0] in "#\n":
            continue
        i, dx, dy, dz = line.split()
        V[int(i)] += np.array([float(dx), float(dy), float(dz)])
    return V


SKEL = json.load(open(MH / "default.mhskel"))
WEIGHTS = json.load(open(MH / "default_weights.mhw"))["weights"]


def rot(axis, deg):
    x, y, z = np.asarray(axis, float) / np.linalg.norm(axis)
    a = math.radians(deg)
    c, s, C = math.cos(a), math.sin(a), 1 - math.cos(a)
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def pose(V, rotations):
    """Linear blend skinning: each rotation turns a bone about its rest head joint, inherited down the tree."""
    joints = {name: V[idx].mean(0) for name, idx in SKEL["joints"].items()}
    bones = SKEL["bones"]
    order, seen = [], set()

    def visit(b):
        if b in seen:
            return
        if bones[b]["parent"]:
            visit(bones[b]["parent"])
        seen.add(b)
        order.append(b)
    for b in bones:
        visit(b)
    T = {}
    for b in order:
        p = bones[b]["parent"]
        R0, t0 = T[p] if p else (np.eye(3), np.zeros(3))
        if b in rotations:
            spec = rotations[b] if isinstance(rotations[b], list) else [rotations[b]]
            Rl = np.eye(3)
            for axis, deg in spec:
                Rl = rot(axis, deg) @ Rl
            h = joints[bones[b]["head"]]
            T[b] = (R0 @ Rl, R0 @ (h - Rl @ h) + t0)
        else:
            T[b] = (R0, t0)
    out, wsum = np.zeros_like(V), np.zeros(len(V))
    for b, lst in WEIGHTS.items():
        if b not in T:
            continue
        R, t = T[b]
        idx = np.array([v for v, _ in lst])
        w = np.array([x for _, x in lst])[:, None]
        out[idx] += w * (V[idx] @ R.T + t)
        wsum[idx] += w[:, 0]
    ok = wsum > 1e-6
    out[ok] /= wsum[ok, None]
    out[~ok] = V[~ok]
    return out


def to_panda(V, height, rest=None):
    """MakeHuman -> Panda (x right, y away from the viewer, z up), feet at 0, facing -Y; scaled so that
    the rest pose (default: V itself) is the given height."""
    rest = V if rest is None else rest
    P = np.stack([-V[:, 0], -V[:, 2], V[:, 1]], 1)
    P[:, 2] -= P[:, 2].min()
    return P * (height / np.ptp(rest[:, 1]))


def normals(P, T):
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    N = np.zeros_like(P)
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)


def main():
    V0, faces = load_obj()
    used = np.unique([i for f in faces for i in f])
    remap = -np.ones(len(V0), int)
    remap[used] = np.arange(len(used))
    quads = [[int(remap[i]) for i in f] for f in faces]
    tris, owner = [], []  # triangles, and the quad each came from
    for q, f in enumerate(quads):
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
            owner.append(q)
    # x is mirrored on the way to Panda (to_panda), so the winding turns: flip it back (normals outwards)
    T, owner = np.array(tris, np.int32)[:, [0, 2, 1]], np.array(owner)
    limb = np.zeros(len(V0))
    for bone, lst in WEIGHTS.items():
        if any(k in bone for k in ("arm", "hand", "finger", "clavicle", "shoulder", "metacarpal")):
            for v, w in lst:
                limb[v] += w
    limb = limb[used]
    data = {"tris": T}
    for gender, ethnic in BODIES:
        key = f"{gender}_{ethnic}"
        Vr = target(V0, f"{ethnic}-{gender}-young")
        Rf = to_panda(Vr, HEIGHT[gender])  # the rest pose (all vertices, joints are on helper geometry)
        R = Rf[used]                         # selections are made on it
        # rags: hips (and chest for women), a torn hem; never on the arms
        rng = np.random.default_rng(len(key))
        rag = np.zeros(len(T), bool)
        bands = [(0.74, 1.0)] + ([(1.17, 1.33)] if gender == "female" else [])
        for z0, z1 in bands:
            ph = rng.uniform(0, 6.28, 3)
            c = R[T].mean(1)
            a = np.arctan2(c[:, 1], c[:, 0] * 1.6)
            hem = z0 - 0.02 - 0.02 * np.sin(3 * a + ph[0]) - 0.01 * np.sin(7 * a + ph[1]) - 0.005 * np.sin(17 * a + ph[2])
            ok = (c[:, 2] > hem) & (c[:, 2] < z1) & (np.abs(c[:, 0]) < 0.22) & (limb[T].max(1) <= 0.3)
            rag |= ok
        # scalp (women: down to the nape, the hair is tied back into a braid)
        rh = Rf[SKEL["joints"]["head____head"]].mean(0)
        d = R - rh
        on = (d[:, 2] > 0.115) | ((d[:, 2] > 0.07) & (d[:, 1] > -0.06))
        if gender == "female":
            on |= (d[:, 1] > 0.02) & (d[:, 2] > -0.01)
        scalp = on[T].all(1)
        data[f"{key}_rag"] = np.where(rag)[0].astype(np.int32)
        data[f"{key}_scalp"] = np.where(scalp)[0].astype(np.int32)
        nape = np.where((np.abs(R[:, 0]) < 0.02) & (R[:, 2] > rh[2] - 0.01) & (R[:, 2] < rh[2] + 0.04))[0]
        nape = nape[np.argmax(R[nape, 1])]
        for pname, rots in POSES.items():
            Pf = to_panda(pose(Vr, rots), HEIGHT[gender], Vr)
            P = Pf[used]
            vkey = f"{key}_{pname}"
            data[f"{vkey}_P"] = P.astype(np.float32)
            data[f"{vkey}_joints"] = np.array([Pf[SKEL["joints"][n]].mean(0) for n in JOINTS], np.float32)
            if gender == "female":  # the braid falls from the nape along the (bent) back
                anchor = P[nape] + np.array([0, 0.02, 0])
                spine = np.where(np.abs(P[:, 0]) < 0.05)[0]
                pts = [anchor]
                for k in range(1, 13):
                    z = anchor[2] - 0.4 * k / 12
                    near = spine[np.abs(P[spine, 2] - z) < 0.025]
                    y = P[near, 1].max() + 0.012 if len(near) else pts[-1][1]
                    if k <= 2:
                        y = 0.5 * min(y, pts[-1][1]) + 0.5 * pts[-1][1]
                    pts.append(np.array([0.01 * math.sin(k * 0.9), y, z]))
                data[f"{vkey}_braid"] = np.array(pts, np.float32)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, **data)
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1e6:.2f} MB, {len(used)} vertices, {len(T)} triangles")


if __name__ == "__main__":
    main()
