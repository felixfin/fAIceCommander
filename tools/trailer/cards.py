"""Renders the trailer's title cards as white-on-black 1920x1080 images in the game's font
(build/trailer/cards/<slug>.png). Colour, glow, zoom and glitch are added by the compositor.

Run: .venv/Scripts/python tools/trailer/cards.py
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import edl  # noqa: E402

OUT = ROOT / "build" / "trailer" / "cards"
SCALE = {"story": 0.11, "feature": 0.12, "title": 0.24, "tagline": 0.08}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def render():
    from panda3d.core import Filename, TextNode, loadPrcFileData
    loadPrcFileData("", "window-type offscreen\nwin-size 1920 1080\nsync-video 0\nframebuffer-multisample 1\n"
                        "multisamples 8\naudio-library-name null\n")
    from direct.gui.OnscreenText import OnscreenText
    from direct.showbase.ShowBase import ShowBase
    from faicecommander.config import ASSETS_DIR
    base = ShowBase()
    base.setBackgroundColor(0, 0, 0, 1)
    font = base.loader.loadFont(Filename.fromOsSpecific(str(ASSETS_DIR / "fonts" / "ChakraPetch-SemiBold.ttf")).getFullpath())
    font.setPixelsPerUnit(200)
    OUT.mkdir(parents=True, exist_ok=True)
    cards = {(src[1], src[2]) for _, _, src, _ in edl.CLIPS if src[0] == "card"}
    for text, style in sorted(cards):
        spaced = " ".join(text) if style in ("story", "tagline") else text  # trailer letter spacing
        t = OnscreenText(spaced, pos=(0, -SCALE[style] * 0.35), scale=SCALE[style], fg=(1, 1, 1, 1), font=font,
                         align=TextNode.ACenter)
        for _ in range(2):
            base.graphicsEngine.renderFrame()
        base.win.saveScreenshot(Filename.fromOsSpecific(str(OUT / f"{slug(text)}.png")))
        t.destroy()
        print("card", text)
    base.destroy()


if __name__ == "__main__":
    render()
