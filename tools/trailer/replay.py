"""Replays a recorded trailer take segment (recordings/<take>/<segment>/) exactly and renders it.

The game runs offscreen with the recorded time steps and controls; a ReplayTracker feeds the recorded
webcam frames, person masks and face landmarks to the webcam panel (helmet, shades, cigar, cockpit).

    analyze(folder)                -> per-frame times and the game events (for picking highlights)
    render(folder, ranges, out)    -> PNG frames for the given time ranges, at 1920x1080
"""
import json
import sys
import time
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def setup_panda(size, quality=True):
    from panda3d.core import loadPrcFileData
    w, h = size
    loadPrcFileData("", f"window-type offscreen\nwin-size {w} {h}\nsync-video 0\naudio-library-name null\n"
                        "textures-power-2 none\n"
                        + ("framebuffer-multisample 1\nmultisamples 8\n" if quality else ""))


class SfxLog:
    """Wraps the game's sound player: every effect that is played (and every loop switched on/off) is
    logged with its time, so the trailer's sound mix can use the game's own sounds in sync."""

    def __init__(self, audio, clock):
        self.entries, self.clock = [], clock
        sfx = audio.sfx
        play, loop = sfx.play, sfx.loop
        self.loops = {}

        def logged_play(name, volume=1.0, rate=1.0):
            self.entries.append(("play", self.clock(), name, volume, rate))
            play(name, volume, rate)

        def logged_loop(key, on, volume=1.0):
            if on != self.loops.get(key, False):
                self.entries.append(("loop", self.clock(), key, volume if on else 0.0, 1.0))
                self.loops[key] = on
            loop(key, on, volume)
        sfx.play, sfx.loop = logged_play, logged_loop


class ReplayTracker:
    """Stands in for FaceTracker: serves the recorded face state of the current replay frame."""

    def __init__(self, folder):
        import cv2
        self.cv2 = cv2
        self.f = np.load(folder / "frames.npz")
        self.cam = cv2.VideoCapture(str(folder / "cam.avi"))
        self.maskv = cv2.VideoCapture(str(folder / "mask.avi"))
        self.pos = -1
        self.frame = self.mask = None
        self.state = None
        self.fps, self.error = 30.0, None

    def start(self):
        return True

    def stop(self):
        self.cam.release()
        self.maskv.release()

    def latest(self):
        return self.state

    def loop_seek(self, i):
        """For cutscenes: plays the recorded face forwards and starts over at the end."""
        n = len(self.f["dt"])
        if i % n == 0 and i:
            self.cam.set(self.cv2.CAP_PROP_POS_FRAMES, 0)
            self.maskv.set(self.cv2.CAP_PROP_POS_FRAMES, 0)
            self.pos = -1
        self.seek(i % n)

    def seek(self, i):
        from faicecommander.input.face_tracker import FaceState
        idx = int(self.f["cam_index"][i])
        while self.pos < idx:  # the camera index only ever grows: read forward
            ok, fr = self.cam.read()
            okm, mk = self.maskv.read()
            if not ok:
                break
            self.frame, self.mask = fr, mk[..., 0].copy()
            self.pos += 1
        found = bool(self.f["found"][i])
        self.state = FaceState(found=found, timestamp=float(i), frame=self.frame, mask=self.mask, frame_id=idx,
                               landmarks=self.f["landmarks"][i].astype(np.float32) if found else None,
                               jaw_open=float(self.f["mouth_gauge"][i]), blink=float(self.f["eyes_gauge"][i]))


class RecordedControls:
    """Autopilot hook: returns the recorded Controls of the current frame."""

    def __init__(self, f):
        from faicecommander.core.recorder import CONTROL_FIELDS
        from faicecommander.input.gestures import Controls
        self.f, self.fields, self.Controls, self.i = f, CONTROL_FIELDS, Controls, 0

    def update(self, dt, world, hypno=None):
        f, i = self.f, self.i
        kw = {}
        for k in self.fields:
            v = f[k][i]
            kw[k] = bool(v) if k in ("mouth_open", "mouth_pressed", "eyes_closed", "tracked") else \
                int(v) if k == "weapon_step" else float(v)
        return self.Controls(**kw)


class Replay:
    def __init__(self, folder, size=(1920, 1080), quality=True):
        setup_panda(size, quality)
        from panda3d.core import ClockObject
        from faicecommander.config import Config
        from faicecommander.core import app as appmod, states
        self.folder = Path(folder)
        self.meta = json.loads((self.folder / "meta.json").read_text(encoding="utf-8"))
        self.tracker = ReplayTracker(self.folder)
        self.f = self.tracker.f
        cfg, lv = Config.load("config.toml"), Config.load("levels.toml")
        cfg.set("display.play_intro", False)
        if quality:  # a little more glow than the live game
            cfg.set("display.bloom", True)
        args = types.SimpleNamespace(no_camera=True, windowed=True, offscreen=True, autopilot=0.0, screenshot=None,
                                     level=1, cutscene=None, tracker=self.tracker)
        self.app = appmod.App(cfg, lv, args)
        self.states = states
        while isinstance(self.app.state, states.LoadingState):
            self.app.taskMgr.step()
        self.app.calibrated = True
        self.clock = ClockObject.getGlobalClock()
        self.clock.setMode(ClockObject.MNonRealTime)
        from faicecommander.core.recorder import apply_segment
        self.controls = RecordedControls(self.f)
        self.app.autopilot = self.controls
        apply_segment(self.app, self.meta, self.meta["seed"])
        self.events = []
        play = self.app.state
        original = play._on_event

        def logged(ev, _orig=original):  # remember what happened, for picking highlights
            self.events.append((self.i, self.t, ev[0], ev[1].kind if ev[0] == "kill" else None))
            _orig(ev)
        play._on_event = logged
        self.i, self.t = 0, 0.0
        self.sfx = SfxLog(self.app.audio, lambda: self.t)

    @property
    def frames(self):
        return len(self.f["dt"])

    def step(self):
        """Advances one recorded frame. Returns False when the recording (or the level) is over.
        Past the end of the recording (finale) the last frame's controls are held."""
        if not isinstance(self.app.state, self.states.PlayState):
            return False
        over = self.i >= self.frames
        k = min(self.i, self.frames - 1)
        dt = float(self.f["dt"][k])
        self.tracker.seek(k)
        self.controls.i = k
        if over:
            self.clock.setDt(dt)
            self.app.taskMgr.step()
            self.t += dt
            self.i += 1
            return False
        self.clock.setDt(dt)
        self.app.taskMgr.step()
        self.drift = abs(self.app.world.score - float(self.f["score"][self.i]))
        self.t += dt
        self.i += 1
        return True

    def screenshot(self, path):
        from panda3d.core import Filename
        self.app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))

    def close(self):
        self.tracker.stop()
        self.app.destroy()


def analyze(folder):
    r = Replay(folder, size=(640, 360), quality=False)
    worst, times = 0.0, []
    while r.step():
        worst = max(worst, r.drift)
        times.append(r.t)
    out = {"segment": Path(folder).name, "frames": r.i, "seconds": r.t, "max_score_drift": worst,
           "events": r.events, "level": r.meta["level"], "sfx": r.sfx.entries}
    r.close()
    return out


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    t0 = time.time()
    res = analyze(folder)
    kinds = {}
    for _, _, k, extra in res["events"]:
        kinds[k if not extra else f"{k}:{extra}"] = kinds.get(k if not extra else f"{k}:{extra}", 0) + 1
    print(json.dumps({k: v for k, v in res.items() if k != "events"}), round(time.time() - t0, 1), "s")
    print(sorted(kinds.items(), key=lambda kv: -kv[1]))
    (folder / "analysis.json").write_text(json.dumps(res), encoding="utf-8")


def render_game(folder, ranges, out_dir, prefix, finale_at=None, size=(1920, 1080)):
    """Replays a segment at full quality and saves the frames inside ranges (replay seconds) as
    <prefix>_<ms>.jpg, plus <prefix>_sfx.json. finale_at: inject the nuke that kills the Mother."""
    from panda3d.core import Filename, PNMImage
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = Replay(folder, size=size, quality=True)
    end = max(t1 for _, t1 in ranges)
    img = PNMImage()
    saved, injected = 0, False
    while r.t < end:
        if finale_at is not None and not injected and r.t >= finale_at:
            injected = True
            w, lvl = r.app.world, r.app.state.level
            m = lvl.mother
            m.health = min(m.health, 4.0)
            w.fire_nuke(m.x, (m.front_y(m.x) or m.y) - 0.6)  # right under her hull: it cannot miss
            for n in w.nukes:
                lvl.seen_nukes.add(id(n))  # no point defence for this one
        if injected:
            r.app.world.ship.hull = 100.0  # the commander survives the finale
        if not r.step() and not injected:
            break
        if injected and not isinstance(r.app.state, r.states.PlayState):
            break
        if any(t0 <= r.t <= t1 for t0, t1 in ranges):
            r.app.win.getScreenshot(img)
            img.write(Filename.fromOsSpecific(str(out_dir / f"{prefix}_{int(round(r.t * 1000)):07d}.jpg")))
            saved += 1
    (out_dir / f"{prefix}_sfx.json").write_text(json.dumps(r.sfx.entries), encoding="utf-8")
    r.close()
    return saved
