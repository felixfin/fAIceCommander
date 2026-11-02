"""Entry point: python -m faicecommander [--windowed] [--no-camera]"""
import argparse

from panda3d.core import loadPrcFileData


def main():
    parser = argparse.ArgumentParser(prog="faicecommander", description="fAIceCommander 3D")
    parser.add_argument("--windowed", action="store_true", help="start in a window instead of fullscreen")
    parser.add_argument("--no-camera", action="store_true", help="keyboard only, never open the webcam")
    parser.add_argument("--autopilot", type=float, default=0.0, metavar="SECONDS",
                        help="let the game play itself (smoke test)")
    parser.add_argument("--screenshot", metavar="PATH", help="with --autopilot: save a screenshot, then quit")
    parser.add_argument("--offscreen", action="store_true", help="render without a visible window (tests)")
    parser.add_argument("--level", type=int, default=1, help="start at this level (practice; development)")
    args = parser.parse_args()

    from .config import Config
    cfg = Config.load("config.toml")
    levels = Config.load("levels.toml")
    w, h = cfg["display.window_size"]
    loadPrcFileData("", f"""
window-title fAIceCommander 3D
win-size {w} {h}
framebuffer-multisample 1
multisamples 4
sync-video 1
audio-preload-threshold 60000000
{"window-type offscreen" if args.offscreen else ""}
""")
    from .core.app import App
    App(cfg, levels, args).run()


if __name__ == "__main__":
    main()
