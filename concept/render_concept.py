"""Renders the concept-art images for fAIceCommander 3D with Panda3D (offscreen).

Usage: python render_concept.py [shot ...]   (no args = all shots)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from panda3d.core import (
    AmbientLight, AntialiasAttrib, Vec3, DirectionalLight, Filename, OrthographicLens, Point2, Point3,
    loadPrcFileData,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "img")
TMP = os.path.join(OUT, "_tmp.png")
W, H = 1280, 720
os.makedirs(OUT, exist_ok=True)

loadPrcFileData("", f"""
window-type offscreen
win-size {W} {H}
framebuffer-alpha 1
framebuffer-multisample 1
multisamples 8
audio-library-name null
""")

from direct.showbase.ShowBase import ShowBase  # noqa: E402

import models as M  # noqa: E402

base = ShowBase()
base.disableMouse()
base.setBackgroundColor(0, 0, 0, 0)
base.render.setAntialias(AntialiasAttrib.MMultisample)
PERSP = base.cam.node().getLens()

amb = base.render.attachNewNode(AmbientLight("amb"))
amb.node().setColor((0.2, 0.2, 0.27, 1))
key = base.render.attachNewNode(DirectionalLight("key"))
key.node().setColor((1.15, 1.07, 1.0, 1))
key.setHpr(-35, -55, 0)
rim = base.render.attachNewNode(DirectionalLight("rim"))
rim.node().setColor((0.55, 0.4, 1.0, 1))
rim.setHpr(150, -15, 0)
for L in (amb, key, rim):
    base.render.setLight(L)

FONT = "C:/Windows/Fonts/bahnschrift.ttf"
MONO = "C:/Windows/Fonts/consolab.ttf"


def font(size, mono=False):
    return ImageFont.truetype(MONO if mono else FONT, size)


# ---------------------------------------------------------------- rendering helpers

def render(build, cam_pos, look_at, fov=40, ortho=None, up=(0, 0, 1)):
    root = base.render.attachNewNode("shot")
    extra = build(root)
    if ortho:
        lens = OrthographicLens()
        lens.setFilmSize(*ortho)
        base.cam.node().setLens(lens)
    else:
        base.cam.node().setLens(PERSP)
        PERSP.setFov(fov)
        PERSP.setAspectRatio(W / H)
    base.camera.setPos(*cam_pos)
    base.camera.lookAt(Point3(*look_at), Vec3(*up))
    for _ in range(2):
        base.graphicsEngine.renderFrame()
    base.win.saveScreenshot(Filename.fromOsSpecific(TMP))
    labels = {}
    if isinstance(extra, dict):
        for k, p in extra.items():
            labels[k] = project(p)
    root.removeNode()
    img = np.asarray(Image.open(TMP).convert("RGBA"), float) / 255.0
    return img, labels


def project(p):
    p3 = base.cam.getRelativePoint(base.render, Point3(*p))
    p2 = Point2()
    base.cam.node().getLens().project(p3, p2)
    return ((p2.x + 1) / 2 * W, (1 - p2.y) / 2 * H)


def background(seed=1, nebula=1.0, stars=1.0, tint=(0.4, 0.12, 0.5), tint2=(0.05, 0.25, 0.4)):
    rng = np.random.default_rng(seed)
    img = np.zeros((H, W, 3))

    def fbm():
        acc = np.zeros((H, W))
        for octave, amp in ((3, 1), (6, 0.5), (12, 0.25), (24, 0.12), (48, 0.06)):
            small = rng.random((octave, int(octave * W / H) + 1))
            up = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255
            acc += up * amp
        acc -= acc.min()
        return acc / acc.max()

    if nebula:
        n1 = np.clip((fbm() - 0.5) * 2.2, 0, 1) ** 2
        n2 = np.clip((fbm() - 0.55) * 2.5, 0, 1) ** 2
        img += nebula * (n1[..., None] * np.array(tint) * 0.55 + n2[..., None] * np.array(tint2) * 0.5)
    if stars:
        n = int(W * H / 700 * stars)
        ys, xs = rng.integers(0, H, n), rng.integers(0, W, n)
        b = rng.random(n) ** 3
        cols = np.array([[1, 1, 1], [0.8, 0.9, 1], [1, 0.9, 0.8]])[rng.integers(0, 3, n)]
        img[ys, xs] += b[:, None] * cols
        big = rng.random(n) > 0.985
        star_layer = np.zeros_like(img)
        star_layer[ys[big], xs[big]] = 3.0
        star_layer = np.asarray(Image.fromarray(np.uint8(np.clip(star_layer * 80, 0, 255))).filter(
            ImageFilter.GaussianBlur(1.6))) / 255.0
        img += star_layer * 0.9
    return img


def composite(fg, bg):
    """Premultiplied composite: glow (additive, alpha~0) survives, opaque parts cover the bg."""
    return fg[..., :3] + bg * (1 - fg[..., 3:4])


def bloom(arr, thr=0.62, strength=1.0):
    br = np.clip(arr - thr, 0, None) / (1 - thr)
    im = Image.fromarray(np.uint8(np.clip(br * 255, 0, 255)))
    b1 = np.asarray(im.filter(ImageFilter.GaussianBlur(5))) / 255
    b2 = np.asarray(im.filter(ImageFilter.GaussianBlur(18))) / 255
    return arr + strength * (0.45 * b1 + 0.7 * b2)


def retro(arr, scan=0.07, vignette=0.35):
    out = arr.copy()
    out[::3] *= 1 - scan
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    out *= (1 - vignette * np.clip(r - 0.45, 0, None) ** 1.5)[..., None]
    return out


def finish(fg, bg, thr=0.62, strength=1.0, scan=0.07):
    arr = retro(bloom(composite(fg, bg), thr, strength), scan)
    return Image.fromarray(np.uint8(np.clip(arr, 0, 1) * 255))


def caption(img, title, sub=None):
    d = ImageDraw.Draw(img)
    d.text((40, 30), title, font=font(40), fill=(255, 255, 255))
    if sub:
        d.text((42, 80), sub, font=font(22), fill=(170, 200, 230))
    return img


def label(d, xy, text, color=(200, 230, 255), size=22, anchor="mm"):
    d.text(xy, text, font=font(size), fill=color, anchor=anchor)


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path)
    print("wrote", path)


# ---------------------------------------------------------------- shots

def shot_ship():
    def build(r):
        s = M.build_ship(r)
        s.setHpr(25, 0, -12)
    fg, _ = render(build, (-5.5, -8.5, 5.0), (0, -0.2, 0), fov=40)
    img = finish(fg, background(2))
    save(caption(img, "FaceCommander", "boxy salvage gunship · life-support tank · hoses · electronics · nukes"),
         "01_ship.png")


def shot_asteroids():
    def build(r):
        pts = {}
        specs = [(1, 11, 0.45, (-7.2, 0, 0)), (1, 12, 0.8, (-5.0, 0, 0)), (1, 13, 1.2, (-2.2, 0, 0)),
                 (2, 21, 1.45, (1.9, 0, 0)), (2, 22, 1.9, (6.3, 0, 0))]
        for cat, seed, rad, pos in specs:
            a = M.build_asteroid(r, seed, rad, cat)
            a.setPos(*pos)
            a.setHpr(seed * 37, seed * 11, 0)
            pts[f"{cat}_{seed}"] = (pos[0], pos[1], pos[2] - 2.6)
        return pts
    fg, labels = render(build, (0, -17, 5.5), (0, 0, -0.4), fov=50)
    img = finish(fg, background(3))
    d = ImageDraw.Draw(img)
    caption(img, "Asteroids", "procedurally generated · different every run")
    xs = [labels[k][0] for k in labels]
    yb = max(v[1] for v in labels.values())
    label(d, ((xs[0] + xs[2]) / 2, yb + 20), "CATEGORY 1 · 10–30 px · 1 hit", (200, 220, 240), 24)
    label(d, ((xs[3] + xs[4]) / 2, yb + 20), "CATEGORY 2 · 30–50 px · splits apart", (255, 170, 110), 24)
    save(img, "02_asteroids.png")


def shot_fighter():
    def build(r):
        f = M.build_fighter(r)
        f.setHpr(-20, 18, 8)
        lb = r.attachNewNode("bolts")
        M.build_laser_bolt(lb, (0.2, -3.2, 0.05), color=(1.0, 0.25, 0.3), length=0.7)
    fg, _ = render(build, (1.5, -6.5, 7.5), (0, -0.1, 0), fov=40)
    img = finish(fg, background(4, tint=(0.4, 0.04, 0.05), tint2=(0.08, 0.05, 0.12)))
    save(caption(img, "Catlien Raider", "biomech arrowhead · bone mandible guns · ember slit sensors"),
         "03_catlien_fighter.png")


def shot_mothership():
    def build(r):
        m = M.build_mothership(r)
        m.setHpr(0, 0, 0)
    fg, _ = render(build, (0, -19, 13), (0, 0.5, 0), fov=50)
    img = finish(fg, background(5, tint=(0.45, 0.03, 0.04), tint2=(0.06, 0.04, 0.1)))
    save(caption(img, "Catlien Mothership", "final boss · the throne chamber of the Mother stares back"), "04_mothership.png")


def shot_mothership_zones():
    width = 14.0

    def build(r):
        M.build_mothership(r, width)
    fw = 17.0
    fg, _ = render(build, (0, 0, 30), (0, 0, 0), ortho=(fw, fw * H / W), up=(0, 1, 0))
    img = finish(fg, background(5, nebula=0.5))
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    zones = M.mothership_layout(width)
    names = [("ZONE 1", "low", (90, 160, 255)), ("ZONE 2", "medium", (255, 200, 60)),
             ("ZONE 3", "HIGH", (255, 60, 90)), ("ZONE 2", "medium", (255, 200, 60)),
             ("ZONE 1", "low", (90, 160, 255))]
    to_px = lambda x: (x / fw + 0.5) * W
    for i, (n, s, c) in enumerate(names):
        x0, x1 = to_px(zones[i]), to_px(zones[i + 1])
        d.rectangle([x0, 150, x1, H - 110], fill=(*c, 38), outline=(*c, 200), width=2)
        d.text(((x0 + x1) / 2, H - 85), n, font=font(22), fill=(*c, 255), anchor="mm")
        d.text(((x0 + x1) / 2, H - 58), s, font=font(18), fill=(*c, 255), anchor="mm")
        pct = round((zones[i + 1] - zones[i]) / width * 100)
        d.text(((x0 + x1) / 2, 170), f"{pct} %", font=font(18), fill=(*c, 255), anchor="mm")
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    save(caption(img, "Mothership damage zones", "laser 5/10/20 % · beam 10/20/30 %/s · nuke 20/40/60 %"),
         "05_mothership_zones.png")


def shot_brain():
    def build(r):
        b = M.build_brain(r, 1.4)
        b.setHpr(-35, 10, 0)
    fg, _ = render(build, (0, -9.5, 2.6), (0, 0, 0.1), fov=40)
    img = finish(fg, background(6, nebula=0, stars=0))
    save(caption(img, "Boltzmann Brain", "level 4 · forms out of the void · fades after 1–3 s"), "06_boltzmann_brain.png")


def shot_black_hole():
    def build(r):
        M.build_black_hole(r, 1.2)
    fg, _ = render(build, (0, -14, 3.5), (0, 0, 0), fov=40)
    img = finish(fg, background(7, tint=(0.3, 0.12, 0.05)), thr=0.55, strength=1.2)
    save(caption(img, "Black Hole", "levels 6 / 7 · accretion disk + photon ring · pulls the ship in"),
         "07_black_hole.png")


def shot_explosion():
    frames = []
    for t in (0.08, 0.35, 0.7):
        def build(r, t=t):
            M.build_explosion(r, t)
            M.build_asteroid(r, 99, 0.0001)
        fg, _ = render(build, (0, -17, 13), (0, 0, 0), fov=55)
        frames.append(finish(fg, background(8), thr=0.55, strength=1.1))
    strip = Image.new("RGB", (W, H))
    w3 = W // 3
    for i, f in enumerate(frames):
        crop = f.crop(((W - w3) // 2, 0, (W - w3) // 2 + w3, H))
        strip.paste(crop, (i * w3, 0))
    d = ImageDraw.Draw(strip)
    for i, t in enumerate(("t = 0.1 s · flash", "t = 0.5 s · fireball + debris", "t = 1.0 s · shockwave")):
        label(d, (i * w3 + w3 / 2, H - 40), t, size=22)
        if i:
            d.line([(i * w3, 0), (i * w3, H)], fill=(40, 40, 60), width=2)
    caption(strip, "Explosion", "Death-Star-style shockwave ring · the bang plays when the wave reaches the ship")
    save(strip, "08_explosion.png")


def shot_helmet():
    def build(r):
        h = M.build_helmet(r)
        h.setH(18)
        Vh, Fh = M.icosphere(2)  # holographic stand-in head
        head = M.part(r, Vh * np.array([0.95, 1.0, 1.3]), Fh, (0.02, 0.05, 0.08), pos=(0, 0.1, -0.35), unlit=True)
        head.setH(18)
        M.neon_edges(head, (0.3, 0.9, 1.0, 0.5), 1.0)
    fg, _ = render(build, (0, -10.5, 0.2), (0, 0, -0.25), fov=40)
    img = finish(fg, background(9, nebula=0.6))
    save(caption(img, "AR Helmet (webcam overlay)", "exposed brain under glass · status LEDs · sunglasses · cigar"),
         "09_helmet.png")


def helmet_layer(yaw=0.0, roll=0.0):
    """Renders only the helmet with transparent background (for the webcam overlay).

    Returns the cropped RGBA image plus the pixel positions of the eye midpoint and the mouth in it,
    which is what the game does with MediaPipe's head pose: put the helmet's eyes onto the player's.
    """
    def build(r):
        h = M.build_helmet(r)
        h.setHpr(yaw, 0, roll)
        return {"eyes": base.render.getRelativePoint(h, Point3(0, -1.0, M.EYE_Z)),
                "mouth": base.render.getRelativePoint(h, Point3(0, -1.0, M.MOUTH_Z))}
    fg, anchors = render(build, (0, -9.0, 0.0), (0, 0, -0.1), fov=30)
    rgb = fg[..., :3]
    a = np.clip(fg[..., 3:4] + rgb.max(-1, keepdims=True) * 0.6, 0, 1)
    un = np.where(a > 1e-3, rgb / np.maximum(a, 1e-3), 0)
    im = Image.fromarray(np.uint8(np.clip(np.concatenate([un, a], -1), 0, 1) * 255), "RGBA")
    x0, y0, x1, y1 = im.getbbox()
    shift = lambda p: (p[0] - x0, p[1] - y0)
    return im.crop((x0, y0, x1, y1)), shift(anchors["eyes"]), shift(anchors["mouth"])


def webcam_panel(w, h, roll=0.0):
    import cv2
    src = Image.open(os.path.join(HERE, "..", "prompts", "screenshots", "FacecCommander_Screenshot_Ingame.png")).convert("RGB")
    cam = src.crop((292, 672, 532, 806))  # webcam area of the 2D original
    eyes, mouth = (115.5, 65.0), (115.0, 81.0)  # positions of the old landmark dots in that crop
    # remove the old coloured landmark dots
    arr = np.asarray(cam).copy()
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    mask = ((hsv[..., 1] > 140) & (hsv[..., 2] > 120)).astype(np.uint8) * 255
    mask[:, :80] = 0
    mask[:, 160:] = 0
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    cam = Image.fromarray(cv2.inpaint(arr, mask, 3, cv2.INPAINT_TELEA))
    s = h / cam.height
    cam = cam.resize((int(cam.width * s), h), Image.LANCZOS).filter(ImageFilter.SMOOTH)
    # cyberpunk grade
    arr = np.asarray(cam, float) / 255
    lum = arr.mean(-1, keepdims=True)
    arr = np.clip(lum * np.array([0.55, 0.95, 1.0]) * 1.1 + arr * 0.25, 0, 1)
    cam = Image.fromarray(np.uint8(arr * 255)).convert("RGBA")
    helm, h_eyes, h_mouth = helmet_layer(roll=roll)
    k = (mouth[1] - eyes[1]) * s / (h_mouth[1] - h_eyes[1])
    helm = helm.resize((int(helm.width * k), int(helm.height * k)), Image.LANCZOS)
    layer = Image.new("RGBA", cam.size, (0, 0, 0, 0))
    layer.paste(helm, (int(eyes[0] * s - h_eyes[0] * k), int(eyes[1] * s - h_eyes[1] * k)), helm)
    cam = Image.alpha_composite(cam, layer)
    panel = Image.new("RGB", (w, h), (10, 12, 18))
    panel.paste(cam.convert("RGB"), ((w - cam.width) // 2, 0))
    return panel, (w - cam.width) // 2, cam.width


def hud_bar(d, x, y, w, h, frac, col, segs=20):
    d.rectangle([x, y, x + w, y + h], outline=(*col, 255), width=2)
    sw = (w - 4) / segs
    for i in range(int(segs * frac)):
        d.rectangle([x + 3 + i * sw, y + 3, x + 2 + (i + 1) * sw - 2, y + h - 3], fill=(*col, 230))


def draw_hud(img, level_name, score, health, energy, weapon_idx, ammo=3, extra=None):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.text((30, 22), "HULL", font=font(18), fill=(120, 255, 160, 255))
    hud_bar(d, 110, 22, 260, 22, health, (90, 255, 140) if health > 0.35 else (255, 80, 80))
    d.text((30, 54), "ENERGY", font=font(18), fill=(100, 220, 255, 255))
    hud_bar(d, 110, 54, 260, 22, energy, (80, 210, 255))
    d.text((W - 30, 18), f"{score:07d}", font=font(40, True), fill=(255, 240, 180, 255), anchor="ra")
    d.text((W - 30, 66), level_name, font=font(18), fill=(255, 120, 220, 255), anchor="ra")
    weapons = [("LASER", (120, 255, 90)), ("BEAM", (90, 255, 220)), (f"NUKE ×{ammo}", (255, 90, 70)),
               ("SHIELD", (90, 170, 255))]
    x0 = W // 2 - 2 * 130
    for i, (n, c) in enumerate(weapons):
        x = x0 + i * 130
        sel = i == weapon_idx
        d.rounded_rectangle([x + 4, 18, x + 124, 58], 8, outline=(*c, 255 if sel else 90),
                            width=3 if sel else 1, fill=(*c, 55) if sel else (0, 0, 0, 90))
        d.text((x + 64, 38), n, font=font(19), fill=(*c, 255 if sel else 120), anchor="mm")
    if extra:
        extra(d)
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    return img


def draw_control_panel(game, webcam_info, tilt=-0.35, mouth=0.8, eyes_open=True, yaw=0.0, track="NEURAL BREAKS",
                       layers="layers: drums · reese · arp"):
    ph = 250
    panel, cx, cw = webcam_info
    full = Image.new("RGB", (W, H + ph), (8, 9, 14))
    full.paste(game, (0, 0))
    full.paste(panel, (0, H))
    d = ImageDraw.Draw(full)
    d.line([(0, H), (W, H)], fill=(255, 60, 200), width=2)
    # left: gauges
    gx, gy = 30, H + 24
    d.text((gx, gy), "CONTROLS", font=font(18), fill=(255, 120, 220))

    def gauge(y, name, v, lo, hi, col):
        d.text((gx, y), name, font=font(16), fill=(180, 200, 220))
        x0, x1 = gx + 130, gx + 360
        d.line([(x0, y + 10), (x1, y + 10)], fill=(70, 80, 100), width=3)
        d.line([((x0 + x1) / 2, y + 2), ((x0 + x1) / 2, y + 18)], fill=(70, 80, 100), width=2)
        px = x0 + (v - lo) / (hi - lo) * (x1 - x0)
        d.ellipse([px - 7, y + 3, px + 7, y + 17], fill=col)
    gauge(gy + 34, "Tilt", tilt, -1, 1, (120, 255, 160))
    gauge(gy + 68, "Turn", yaw, -1, 1, (255, 200, 80))
    gauge(gy + 102, "Mouth", mouth * 2 - 1, -1, 1, (255, 90, 90))
    d.text((gx, gy + 136), "Eyes", font=font(16), fill=(180, 200, 220))
    d.text((gx + 130, gy + 134), "OPEN" if eyes_open else "CLOSED", font=font(18),
           fill=(120, 255, 160) if eyes_open else (255, 120, 220))
    d.text((gx, gy + 176), "face tracked · 30 fps", font=font(15), fill=(100, 140, 170))
    # right: music + hints
    rx = cx + cw + 30
    d.text((rx, gy), "SOUNDTRACK", font=font(18), fill=(255, 120, 220))
    d.text((rx, gy + 32), track, font=font(20), fill=(220, 230, 255))
    for i, h in enumerate([0.4, 0.9, 0.6, 1.0, 0.7, 0.5, 0.85, 0.3, 0.65, 0.95, 0.55, 0.75]):
        d.rectangle([rx + i * 16, gy + 110 - h * 40, rx + i * 16 + 10, gy + 110], fill=(90, 220, 255))
    d.text((rx, gy + 128), layers, font=font(15), fill=(120, 150, 180))
    d.rectangle([cx, H, cx + cw - 1, H + ph - 1], outline=(255, 60, 200), width=2)
    return full


def shot_ingame_l1():
    def build(r):
        s = M.build_ship(r)
        s.setPos(2.5, -6.0, 0)
        s.setR(14)
        rng = np.random.default_rng(42)
        for i, (x, y, rad) in enumerate([(-7, 9, 0.9), (5.5, 4.5, 0.6), (8.5, 12, 1.2), (-2.5, 13.5, 0.5),
                                         (-9, 1.5, 0.7), (1.5, 17, 1.0)]):
            a = M.build_asteroid(r, 300 + i, rad, 1)
            a.setPos(x, y, 0)
            a.setHpr(*rng.uniform(0, 360, 3))
        for y in (-2.5, 1.0, 4.5):
            M.build_laser_bolt(r, (2.5 + 2.1, y - 4.8 + 3.5, 0))
            M.build_laser_bolt(r, (2.5 - 2.1, y - 5.2 + 3.5, 0))
        e = M.build_explosion(r, 0.42, seed=9)
        e.setPos(-3, 6.5, 0)
    fg, _ = render(build, (0, -27, 19), (0, 2.5, 0), fov=50)
    img = finish(fg, background(11))
    img = draw_hud(img, "LEVEL 1 · ASTEROID BELT", 1250, 0.78, 0.55, 0)
    full = draw_control_panel(img, webcam_panel(W, 250), tilt=0.4, mouth=0.85)
    save(full, "10_ingame_level1.png")


def shot_ingame_l7():
    def build(r):
        m = M.build_mothership(r)
        m.setPos(-1.5, 16.5, 0)
        s = M.build_ship(r)
        s.setPos(-3.0, -6.2, 0)
        s.setR(-10)
        sh = r.attachNewNode("shield")
        Vh, Fh = M.icosphere(2)
        M.part(sh, Vh * np.array([2.6, 2.6, 1.4]), Fh, (0.3, 0.7, 1.0, 0.18), pos=(-3.0, -6.5, 0),
               alpha=True, two_sided=True)
        M.neon_edges(sh.getChild(0), (0.4, 0.8, 1.0, 0.35), 1.0)
        for (x, y) in ((-2.0, 3.5), (0.5, 6.0), (-4.5, 0.0), (3.0, 9.0)):
            M.build_laser_bolt(r, (x, y, 0), color=(1.0, 0.25, 0.4), length=0.6)
        M.build_hypno_rings(r, (-1.5, 14.0, 0.0), [8.5, 10.5, 12.5], width=1.1)
        bh = M.build_black_hole(r, 0.55)
        bh.setPos(6.5, 0.5, 0)
        for i, (x, y, rad) in enumerate([(-9, 6, 0.6), (8.5, 9, 0.7)]):
            M.build_asteroid(r, 700 + i, rad, 1).setPos(x, y, 0)
    fg, _ = render(build, (0, -27, 19), (0, 3.5, 0), fov=52)
    img = finish(fg, background(12, tint=(0.45, 0.03, 0.05), tint2=(0.1, 0.03, 0.15)), thr=0.6)

    def extra(d):
        bx, by, bw = W // 2 - 300, 78, 600
        d.text((W // 2, by), "THE MOTHER", font=font(18), fill=(255, 90, 160, 255), anchor="mm")
        d.rectangle([bx, by + 14, bx + bw, by + 30], outline=(255, 90, 160, 255), width=2)
        d.rectangle([bx + 3, by + 17, bx + 3 + (bw - 6) * 0.62, by + 27], fill=(255, 60, 140, 230))
        d.text((W // 2, H // 2 + 40), "HYPNO PULSE  ·  CLOSE YOUR EYES!  2.4 s", font=font(34),
               fill=(255, 120, 230, 255), anchor="mm")
    img = draw_hud(img, "LEVEL 7 · THE MOTHER", 48210, 0.46, 0.3, 3, ammo=2, extra=extra)
    full = draw_control_panel(img, webcam_panel(W, 250, roll=8), tilt=-0.25, mouth=0.1, yaw=0.0,
                              track="MOTHER OF CATS", eyes_open=True,
                              layers="layers: halftime · wobble · choir")
    save(full, "11_ingame_level7.png")


def splatter(img, seed, spots):
    """Blood and brain matter on the 'screen glass'. spots: [(x, y, size), ...] in pixels."""
    rng = np.random.default_rng(seed)
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for cx, cy, size in spots:
        for _ in range(14):  # main blob: union of circles
            r = size * rng.uniform(0.25, 0.6)
            ox, oy = rng.normal(0, size * 0.35, 2)
            d.ellipse([cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r], fill=(105, 0, 8, 225))
        for _ in range(26):  # flung droplets with streaks
            ang = rng.uniform(0, 2 * np.pi)
            dist = size * rng.uniform(0.9, 2.4)
            px, py = cx + np.cos(ang) * dist, cy + np.sin(ang) * dist
            r = size * rng.uniform(0.03, 0.12)
            d.line([(cx + np.cos(ang) * size * 0.6, cy + np.sin(ang) * size * 0.6), (px, py)],
                   fill=(110, 0, 10, 160), width=max(1, int(r * 0.8)))
            d.ellipse([px - r, py - r, px + r, py + r], fill=(120, 0, 10, 230))
        for _ in range(5):  # drips running down
            x = cx + rng.uniform(-0.6, 0.6) * size
            ln = size * rng.uniform(0.5, 1.8)
            w = size * rng.uniform(0.05, 0.1)
            d.rounded_rectangle([x - w, cy, x + w, cy + ln], radius=int(w), fill=(95, 0, 6, 220))
            d.ellipse([x - w * 1.5, cy + ln - w, x + w * 1.5, cy + ln + w * 2], fill=(95, 0, 6, 230))
        for _ in range(9):  # brain matter lumps
            ox, oy = rng.normal(0, size * 0.45, 2)
            rw, rh = size * rng.uniform(0.07, 0.17), size * rng.uniform(0.05, 0.12)
            col = (225, int(rng.uniform(120, 150)), 145, 245)
            d.ellipse([cx + ox - rw, cy + oy - rh, cx + ox + rw, cy + oy + rh], fill=col, outline=(120, 40, 50, 255))
            d.ellipse([cx + ox - rw * 0.4, cy + oy - rh * 0.6, cx + ox, cy + oy - rh * 0.1], fill=(255, 220, 225, 200))
    ov = ov.filter(ImageFilter.GaussianBlur(0.8))
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))  # wet highlights
    dh = ImageDraw.Draw(hl)
    for cx, cy, size in spots:
        for _ in range(10):
            ox, oy = rng.normal(0, size * 0.4, 2)
            r = size * rng.uniform(0.02, 0.06)
            dh.ellipse([cx + ox - r, cy + oy - r, cx + ox + r * 0.6, cy + oy + r * 0.6], fill=(255, 200, 200, 140))
    out = Image.alpha_composite(img.convert("RGBA"), ov)
    return Image.alpha_composite(out, hl).convert("RGB")


def shot_brain_burst():
    frames = []
    for t in (0.0, 0.25, 0.6):
        def build(r, t=t):
            if t == 0:
                M.build_brain(r, 1.2)
            else:
                M.build_brain_burst(r, t, scale=1.2)
        fg, _ = render(build, (0, -11, 3.0), (0, 0, 0), fov=40)
        frames.append(finish(fg, background(6, nebula=0, stars=0), thr=0.6))
    strip = Image.new("RGB", (W, H))
    w3 = W // 3
    for i, f in enumerate(frames):
        strip.paste(f.crop(((W - w3) // 2, 0, (W - w3) // 2 + w3, H)), (i * w3, 0))
    strip = splatter(strip, 4, [(2 * w3 + 120, 300, 90), (2 * w3 + 330, 520, 55)])
    d = ImageDraw.Draw(strip)
    for i, t in enumerate(("intact", "hit · burst", "splatter on screen, fades in ~3 s")):
        label(d, (i * w3 + w3 / 2, H - 40), t, size=22)
        if i:
            d.line([(i * w3, 0), (i * w3, H)], fill=(40, 30, 40), width=2)
    caption(strip, "Brain Burst", "shot Boltzmann brains explode into blood and brain matter")
    save(strip, "12_brain_burst.png")


def shot_ingame_l4():
    def build(r):
        s = M.build_ship(r)
        s.setPos(-1.5, -6.0, 0)
        s.setR(-8)
        rng = np.random.default_rng(4)
        for (x, y) in ((-7, 10), (4.5, 13), (8, 5), (-4, 3.5), (1.5, 8.5), (-9, 15)):
            b = M.build_brain(r, 0.55)
            b.setPos(x, y, 0.4)
            b.setHpr(*rng.uniform(-40, 40, 3))
        M.build_brain_burst(r, 0.3, scale=0.8).setPos(2.5, 0.5, 0.4)
        for y in (-2.0, 1.5):
            M.build_laser_bolt(r, (-1.5 + 0.88, y, 0))
    fg, _ = render(build, (0, -27, 19), (0, 2.5, 0), fov=50)
    img = finish(fg, background(13, nebula=0, stars=0))
    img = splatter(img, 9, [(980, 260, 85), (1140, 470, 45), (850, 520, 30)])
    img = draw_hud(img, "LEVEL 4 · THE VOID", 9870, 0.64, 0.7, 0)
    full = draw_control_panel(img, webcam_panel(W, 250), tilt=-0.15, mouth=0.9, track="NOTHING ANSWERS",
                              layers="layers: drone · heartbeat · whispers")
    save(full, "13_ingame_level4.png")


SHOTS = {n[5:]: f for n, f in globals().items() if n.startswith("shot_")}

if __name__ == "__main__":
    for name in sys.argv[1:] or SHOTS:
        SHOTS[name]()
    if os.path.exists(TMP):
        os.remove(TMP)
