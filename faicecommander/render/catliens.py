"""The Catliens as they appear in the game and cutscenes: the photographed cats (models.build_photo_cat)
in closed space-marine helmets, and - for the Mother in her hall - an armoured gorget and a three-legged
mech undercarriage."""
import math

import numpy as np

from . import models as M

ACCENT = {"queen": (1.0, 0.3, 0.08), "raider": (0.5, 1.0, 0.35)}
GUN = M.paint((0.03, 0.03, 0.035), (0.32, 0.33, 0.36), -1, 4, grime=0.25)
DARK = M.paint((0.015, 0.012, 0.014), (0.16, 0.13, 0.14), -1, 4, grime=0.3)


def face(name, height, detail="close"):
    """Where the face of the photo cat lies: eye centre (cx, ez), eye distance ed, the most forward
    forehead y (fy), a surface(x, z) -> y lookup and the width of the bust near its bottom."""
    import json
    from ..config import ASSETS_DIR
    meta = json.loads((ASSETS_DIR / "cats" / f"{name}.json").read_text())
    X, Y, Z, U, V, a = M.cat_grid(name, height, detail)
    nz, nx = X.shape
    w = height * meta["aspect"]
    (u0, v0), (u1, v1) = meta["eyes"]
    cx = ((u0 + u1) / 2 - 0.5) * w
    ez = (v0 + v1) / 2 * height
    ed = math.hypot((u1 - u0) * w, (v1 - v0) * height)

    def surface(x, z):
        i = int(round(min(max(x / w + 0.5, 0), 1) * (nx - 1)))
        j = int(round(min(max(z / height, 0), 1) * (nz - 1)))
        return float(Y[j, i])
    fy = min(surface(cx + dx * ed, ez + 0.7 * ed) for dx in (-0.5, 0, 0.5))
    row = int(0.06 * (nz - 1))
    cols = np.where(a[row] > 0.5)[0]
    bottom = (float(X[row, cols.min()]), float(X[row, cols.max()])) if len(cols) else (-0.4 * w, 0.4 * w)
    return {"cx": cx, "ez": ez, "ed": ed, "fy": fy, "surface": surface, "bottom": bottom, "height": height}


def _over(np_, sort=35):
    np_.setBin("fixed", sort)  # drawn after the cat relief (bin 30)
    return np_


def helmet_marine(root, f, accent):
    """A closed helmet with an oval face opening, a lit frame, side pods, hoses and a chin guard."""
    cx, ez, ed, fy = f["cx"], f["ez"], f["ed"], f["fy"]
    V, F = M.icosphere(4)
    opening = lambda v: v[1] < -0.15 and (v[0] / 0.6) ** 2 + ((v[2] + 0.12) / 0.74) ** 2 < 1  # noqa: E731
    shell = [F[i] for i in range(len(F)) if not any(opening(V[j]) for j in F[i])]
    _over(M.part(root, V * np.array([1.75 * ed, 1.4 * ed, 1.95 * ed]), shell, (1, 1, 1),
                 pos=(cx, fy + 1.0 * ed, ez - 0.05 * ed), vcol=GUN, two_sided=True))
    ry = fy - 0.1 * ed
    frame = [((cx + 1.1 * ed * math.cos(a)), ry + 0.3 * ed * math.cos(a) ** 2,
              ez - 0.25 * ed + 1.45 * ed * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 48)]
    Vf, Ff = M.tube_mesh(frame, 0.17 * ed, 12)
    _over(M.part(root, Vf, Ff, (1, 1, 1), orient=None, vcol=DARK))
    for k in range(10):
        a = math.radians(30 + k * 12)
        _over(M.glow(root, (cx + 1.1 * ed * math.cos(a), ry - 0.2 * ed, ez - 0.25 * ed + 1.45 * ed * math.sin(a)),
                     0.08 * ed, (*accent, 0.9)), 37)
    for s in (-1, 1):
        Vp, Fp = M.lathe([(0.0, 0.0), (0.45 * ed, 0.05 * ed), (0.5 * ed, 0.35 * ed), (0.3 * ed, 0.5 * ed)], 24, "y")
        pod = _over(M.part(root, Vp, Fp, (1, 1, 1), orient="y", vcol=GUN))
        pod.setPos(cx + s * 1.65 * ed, fy + 0.9 * ed, ez + 0.1 * ed)
        pod.setH(-s * 90)
        _over(M.glow(root, (cx + s * 2.15 * ed, fy + 0.9 * ed, ez + 0.1 * ed), 0.3 * ed, (*accent, 0.7)), 37)
        M.tube(root, [(cx + s * 0.45 * ed, ry, ez - 1.6 * ed), (cx + s * 0.9 * ed, ry - 0.2 * ed, ez - 1.95 * ed),
                      (cx + s * 1.4 * ed, ry + 0.3 * ed, ez - 2.0 * ed), (cx + s * 1.6 * ed, ry + 0.9 * ed, ez - 1.4 * ed)],
               0.07 * ed, (0.08, 0.08, 0.09), band=(*accent,))
    Vg, Fg = M.box(1.0 * ed, 0.3 * ed, 0.18 * ed)
    _over(M.part(root, Vg, Fg, (1, 1, 1), pos=(cx, ry, ez - 1.75 * ed), vcol=DARK, smooth=None))


def gorget(root, f, accent):
    """Layered armour plates round the bottom of the bust: they hide where the photo fades out."""
    x0, x1 = f["bottom"]
    h = f["height"]
    cx = (x0 + x1) / 2
    rx = (x1 - x0) / 2 * 0.98
    front = min(f["surface"](cx + dx * rx, 0.1 * h) for dx in (-0.5, 0.0, 0.5)) - 0.03 * h
    ry = rx * 0.55
    prof = [(1.0, -0.02), (1.0, 0.06), (0.96, 0.08), (0.95, 0.13), (0.9, 0.15), (0.88, 0.2), (0.82, 0.22),
            (0.78, 0.27), (0.7, 0.29), (0.6, 0.3)]
    V, F = M.lathe([(r, z * h / rx) for r, z in prof], 48, "z")
    _over(M.part(root, V * np.array([rx, ry, rx]), F, (1, 1, 1), pos=(cx, front + ry, 0.0), orient=None,
                 vcol=GUN, two_sided=True), 34)
    for zz, r in ((0.035, 1.006), (0.175, 0.886)):  # accent light strips along two plate edges
        Vr, Fr = M.lathe([(r, -0.006 * h / rx), (r, 0.006 * h / rx)], 48, "z")
        _over(M.part(root, Vr * np.array([rx, ry, rx]), Fr, accent, pos=(cx, front + ry, zz * h), orient=None,
                     unlit=True), 35)
    for s in (-1, 1):  # rivets on the shoulder plates
        for k in range(3):
            a = math.radians(-90 + s * (35 + k * 18))
            _over(M.part(root, *M.icosphere(1), (0.45, 0.45, 0.48),
                         pos=(cx + rx * 1.0 * math.cos(a), front + ry + ry * 1.0 * math.sin(a), 0.012 * h),
                         scale=0.012 * h), 35)


def mech_legs(root, hub, floor, accent, size=1.0):
    """A hub with three jointed legs (two forward, one back) standing on z = floor; hub in parent space."""
    metal, dark = (0.2, 0.19, 0.2), (0.08, 0.075, 0.08)
    hub = np.array(hub, float)
    s = size

    def seg(a, b, r, col):
        a, b = np.array(a, float), np.array(b, float)
        M.tube(root, [a, a + (b - a) / 3, a + 2 * (b - a) / 3, b], r * s, col, n=6)

    def ball(p, r, col, unlit=False):
        M.part(root, *M.icosphere(2), col, pos=tuple(p), scale=r * s, unlit=unlit)
    Vh, Fh = M.lathe([(0.0, -0.42), (0.45, -0.36), (0.68, -0.12), (0.72, 0.06), (0.6, 0.26), (0.0, 0.32)], 24, "z")
    M.part(root, Vh * s, Fh, metal, pos=tuple(hub), orient=None)
    Vr, Fr = M.lathe([(0.735, -0.025), (0.735, 0.025)], 24, "z")
    M.part(root, Vr * s, Fr, accent, pos=tuple(hub), orient=None, unlit=True)
    up = np.array([0, 0, 1.0])
    for ang in (-58, 58, 180):
        a = math.radians(ang)
        d = np.array([math.sin(a), -math.cos(a), 0.0])  # -y: towards the viewer
        side = np.array([math.cos(a), math.sin(a), 0.0])
        hip = hub + (d * 0.62 - up * 0.05) * s
        knee = hub + (d * 1.25 + up * 0.3) * s
        ankle = hub + d * 1.6 * s
        ankle[2] = floor + 0.33 * (hub[2] - floor)
        foot = np.array([ankle[0], ankle[1], floor + 0.06 * s])
        ball(hip, 0.15, dark)
        seg(hip, knee, 0.12, metal)
        for k in (-1, 1):  # hydraulics
            seg(hip + (side * 0.12 * k - up * 0.08) * s, knee + (side * 0.12 * k - up * 0.1) * s, 0.035, dark)
        ball(knee, 0.15, dark)
        ball(knee + (d * 0.11 + up * 0.07) * s, 0.035, accent, unlit=True)
        seg(knee, ankle, 0.095, metal)
        seg(knee + d * 0.13 * s, ankle + (d * 0.08 + up * 0.1) * s, 0.05, dark)
        ball(ankle, 0.1, dark)
        seg(ankle, foot, 0.075, metal)
        for t in (-35, 0, 35):  # three claws
            b = math.radians(ang + t)
            cd = np.array([math.sin(b), -math.cos(b), 0.0])
            tip = foot + (cd * 0.34 - up * 0.05) * s
            M.tube(root, [foot, foot + (cd * 0.14 + up * 0.04) * s, foot + cd * 0.26 * s, tip], 0.034 * s, dark, n=6)


def build_catlien(parent, name, height, detail="close", armour=False):
    """A photographed cat in helmet D (detail as in models.build_photo_cat); armour adds the gorget."""
    root = parent.attachNewNode(f"catlien-{name}")
    M.build_photo_cat(root, name, height=height, detail=detail)
    f = face(name, height, detail)
    helmet_marine(root, f, ACCENT[name])
    if armour:
        gorget(root, f, ACCENT[name])
    return root
