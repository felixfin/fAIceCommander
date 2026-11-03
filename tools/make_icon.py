"""Renders the window / desktop icon: the FaceCommander ship seen from above on a dark rounded tile
with a pink rim. Writes faicecommander/assets/icon.png and icon.ico (PNG-compressed ICO, 16-256 px).

Run: .venv/Scripts/python tools/make_icon.py
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from panda3d.core import (  # noqa: E402
    AmbientLight, AntialiasAttrib, DirectionalLight, Filename, Material, PNMImage, Point3, loadPrcFileData,
)

loadPrcFileData("", "window-type offscreen\nwin-size 512 512\nframebuffer-multisample 1\nmultisamples 8\n"
                    "framebuffer-alpha 1\nsync-video 0\n")
from direct.showbase.ShowBase import ShowBase  # noqa: E402

from faicecommander.render import models as M  # noqa: E402

ASSETS = ROOT / "faicecommander" / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_ship(path):
    base = ShowBase()
    base.setBackgroundColor(0, 0, 0, 0)
    base.render.setShaderAuto()
    base.render.setAntialias(AntialiasAttrib.MMultisample)
    mat = Material()
    mat.setSpecular((0.3, 0.3, 0.32, 1))
    mat.setShininess(30)
    base.render.setMaterial(mat)
    amb = base.render.attachNewNode(AmbientLight("amb"))
    amb.node().setColor((0.25, 0.25, 0.3, 1))
    key = base.render.attachNewNode(DirectionalLight("key"))
    key.node().setColor((1.25, 1.15, 1.05, 1))
    key.setHpr(-50, -45, 0)
    for light in (amb, key):
        base.render.setLight(light)
    ship = M.build_ship(base.render)
    ship.setH(-30)
    base.camLens.setFov(32)
    base.camera.setPos(0, -5.2, 7.5)
    base.camera.lookAt(Point3(0, 0.1, 0))
    for _ in range(3):
        base.graphicsEngine.renderFrame()
    base.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
    base.destroy()


def compose(ship_png, out_png):
    """Rounded dark tile, pink rim, the ship on top."""
    ship = PNMImage(Filename.fromOsSpecific(str(ship_png)))
    n = 512
    img = PNMImage(n, n, 4)
    r = 0.18 * n
    for y in range(n):
        for x in range(n):
            dx = max(r - x, 0, x - (n - 1 - r))
            dy = max(r - y, 0, y - (n - 1 - r))
            d = (dx * dx + dy * dy) ** 0.5
            inside = max(0.0, min(1.0, r - d + 0.5)) if (dx or dy) else 1.0
            edge = min(x, y, n - 1 - x, n - 1 - y) if not (dx or dy) else r - d
            rim = max(0.0, 1 - abs(edge - 10) / 6)
            v = 0.05 + 0.06 * (1 - y / n)
            col = (v * 0.8 + rim, v * 0.7 + rim * 0.35, v * 1.2 + rim * 0.8)
            sr, sg, sb = ship.getXel(x, y)
            sa = ship.getAlpha(x, y) if ship.hasAlpha() else (1.0 if sr + sg + sb > 0.02 else 0.0)
            img.setXelA(x, y, *(c * (1 - sa) + s * sa for c, s in zip(col, (sr, sg, sb))), inside)
    img.write(Filename.fromOsSpecific(str(out_png)))
    return img


def write_ico(img, path):
    pngs = []
    for size in SIZES:
        small = PNMImage(size, size, 4)
        small.gaussianFilterFrom(1.0, img)
        tmp = path.with_name(f"icon_{size}.png")
        small.write(Filename.fromOsSpecific(str(tmp)))
        pngs.append((size, tmp.read_bytes()))
        tmp.unlink()
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, data = b"", b""
    for size, png in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    path.write_bytes(header + entries + data)


if __name__ == "__main__":
    raw = ASSETS / "icon_render.png"
    render_ship(raw)
    img = compose(raw, ASSETS / "icon.png")
    raw.unlink()
    write_ico(img, ASSETS / "icon.ico")
    print("wrote", ASSETS / "icon.png", "and", ASSETS / "icon.ico")
