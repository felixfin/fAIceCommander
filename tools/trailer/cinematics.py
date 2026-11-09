"""Renders the intro / outro for the trailer: offscreen at 1080p, fixed time steps (sub-sampled so
slow motion is possible), no captions, no control panel; the webcam close-ups show a recorded face.
Only frames inside the requested time ranges are saved. Sound effects are logged with their time.

    render(sequence, ranges, out_dir, face_folder, step=1/48)
        sequence: "intro" or "outro"; ranges: [(t0, t1), ...] in cutscene seconds
        -> out_dir/<sequence>_<frame>.jpg named by cutscene time in 1/1000 s, plus sfx.json
"""
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from replay import ReplayTracker, SfxLog, setup_panda  # noqa: E402


def render(sequence, ranges, out_dir, face_folder, step=1 / 48, size=(1920, 1080)):
    setup_panda(size)
    from panda3d.core import ClockObject, Filename, PNMImage
    from faicecommander.config import Config
    from faicecommander.core import app as appmod, states
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tracker = ReplayTracker(Path(face_folder))
    cfg, lv = Config.load("config.toml"), Config.load("levels.toml")
    cfg.set("display.play_intro", False)
    args = types.SimpleNamespace(no_camera=True, windowed=True, offscreen=True, autopilot=0.0, screenshot=None,
                                 level=1, cutscene=None, tracker=tracker)
    app = appmod.App(cfg, lv, args)
    while isinstance(app.state, states.LoadingState):
        app.taskMgr.step()
    app.no_captions = True
    app.calibrated = True
    app.panel_visible = False
    app.layout()
    clock = ClockObject.getGlobalClock()
    clock.setMode(ClockObject.MNonRealTime)
    app.change(states.IntroState if sequence == "intro" else states.OutroState(app, preview=True))
    app.state.skippable = False
    scene = app.state.scene
    log = SfxLog(app.audio, lambda: scene.t)
    end = max(t1 for _, t1 in ranges)
    k = saved = 0
    img = PNMImage()
    while not scene.done and scene.t < end:
        tracker.loop_seek(k // 2)  # the camera ran at ~30 fps, the cutscene steps at 48
        clock.setDt(step)
        app.taskMgr.step()
        k += 1
        t = scene.t
        if any(t0 <= t <= t1 for t0, t1 in ranges):
            app.win.getScreenshot(img)
            img.write(Filename.fromOsSpecific(str(out_dir / f"{sequence}_{int(round(t * 1000)):07d}.jpg")))
            saved += 1
    (out_dir / f"{sequence}_sfx.json").write_text(json.dumps(log.entries), encoding="utf-8")
    tracker.stop()
    app.destroy()
    return saved


if __name__ == "__main__":
    seq, out, face = sys.argv[1], sys.argv[2], sys.argv[3]
    ranges = [tuple(map(float, r.split(":"))) for r in sys.argv[4].split(",")]
    print("saved", render(seq, ranges, out, face), "frames")
