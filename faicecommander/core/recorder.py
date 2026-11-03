"""Trailer takes: a guided recording session (python -m faicecommander --record NAME).

The session plays a fixed list of short segments (practice runs of chosen levels). For every frame it
stores what is needed to replay the segment exactly and re-render it in high quality later
(tools/trailer): the time step, the controls, whether the game was halted, the face landmarks (for the
AR helmet) and - whenever the camera delivers a new picture - the webcam image and the person mask.

Everything is seeded per segment, so the game logic runs identically in the replay.

    recordings/<take>/<NN>_<level>_<attempt>/
        meta.json    segment, seed, difficulty, frame count, outcome
        frames.npz   per game frame: dt, controls, halted, face found / frame index, landmarks
        cam.avi      webcam frames (MJPG), one per new camera frame
        mask.avi     person masks (MJPG, grey), same frames
"""
import json
import random
import time
from pathlib import Path

import numpy as np

# (level index, difficulty, length in s, extra setup) - what the trailer needs
SEGMENTS = [
    {"level": 1, "difficulty": "medium", "seconds": 60, "title": "Debris Field: laser, beam, nukes"},
    {"level": 2, "difficulty": "medium", "seconds": 55, "title": "Hypno Nebula: close your eyes!",
     "pulse_first_s": 6},
    {"level": 3, "difficulty": "medium", "seconds": 45, "title": "The Void: shoot the brains"},
    {"level": 4, "difficulty": "medium", "seconds": 75, "title": "Patrol: Catlien raiders"},
    {"level": 5, "difficulty": "medium", "seconds": 60, "title": "Event Horizon: black holes"},
    {"level": 6, "difficulty": "easy", "seconds": 150, "title": "The Mother: finish her!", "mother_health": 40},
]
CONTROL_FIELDS = ("steer", "mouth_open", "mouth_pressed", "weapon_step", "eyes_closed", "tracked",
                  "tilt_gauge", "turn_gauge", "mouth_gauge", "eyes_gauge")


def seed_for(index, attempt):
    return 7000 + index * 100 + attempt


def apply_segment(app, seg, seed):
    """Seeds everything and starts the segment's level - used by the recorder and by the replay."""
    app.world.rng = np.random.default_rng(seed)
    np.random.seed(seed)
    random.seed(seed)
    if "pulse_first_s" in seg:
        app.levels_override = {"pulse_first_s": seg["pulse_first_s"]}
    else:
        app.levels_override = {}
    app.start_run("practice", seg["level"], seg["difficulty"])
    level = app.state.level
    if "mother_health" in seg and getattr(level, "mother", None) is not None:
        level.mother.health = float(seg["mother_health"])
    return level


class SegmentWriter:
    def __init__(self, folder):
        import cv2
        self.cv2 = cv2
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.rows = {k: [] for k in CONTROL_FIELDS + ("dt", "halted", "found", "cam_index", "elapsed", "score",
                                                       "ship_x")}
        self.landmarks = []
        self.cam = self.mask = None
        self.cam_frames = 0
        self.last_frame_id = None

    def _open(self, w, h):
        fourcc = self.cv2.VideoWriter_fourcc(*"MJPG")
        self.cam = self.cv2.VideoWriter(str(self.folder / "cam.avi"), fourcc, 30, (w, h))
        self.mask = self.cv2.VideoWriter(str(self.folder / "mask.avi"), fourcc, 30, (w, h))

    def add(self, dt, face, ctl, halted, elapsed, score, ship_x):
        for k in CONTROL_FIELDS:
            self.rows[k].append(float(getattr(ctl, k)))
        self.rows["dt"].append(dt)
        self.rows["halted"].append(float(halted))
        self.rows["elapsed"].append(elapsed)
        self.rows["score"].append(score)      # these two let the replay check that it runs identically
        self.rows["ship_x"].append(ship_x)
        found = face is not None and face.found and face.landmarks is not None
        self.rows["found"].append(float(found))
        self.landmarks.append(face.landmarks.astype(np.float32) if found else np.zeros((478, 3), np.float32))
        if face is not None and face.frame is not None and face.frame_id != self.last_frame_id:
            self.last_frame_id = face.frame_id
            h, w = face.frame.shape[:2]
            if self.cam is None:
                self._open(w, h)
            self.cam.write(face.frame)
            m = face.mask if face.mask is not None else np.full((h, w), 255, np.uint8)
            self.mask.write(self.cv2.cvtColor(m, self.cv2.COLOR_GRAY2BGR))
            self.cam_frames += 1
        self.rows["cam_index"].append(float(self.cam_frames - 1))

    def close(self, meta):
        if self.cam is not None:
            self.cam.release()
            self.mask.release()
        np.savez_compressed(self.folder / "frames.npz", landmarks=np.array(self.landmarks, np.float16),
                            **{k: np.array(v, np.float32) for k, v in self.rows.items()})
        meta = dict(meta, frames=len(self.rows["dt"]), cam_frames=self.cam_frames)
        (self.folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


class RecordSession:
    """Drives the take: segment by segment, automatic retry after a game over, N = next, R = retry."""

    def __init__(self, app, name):
        self.app, self.name = app, name
        self.root = Path.cwd() / "recordings" / name
        self.index, self.attempt = 0, 0
        self.writer = None
        self.wait = 0.0
        self.t = 0.0
        self.started = False
        self.done = False
        self._next = self._retry = False
        app.accept("n", self._flag, ["_next"])
        app.accept("r", self._flag, ["_retry"])

    def _flag(self, name):
        if not self.app.text_input:
            setattr(self, name, True)

    @property
    def segment(self):
        return SEGMENTS[self.index]

    def start(self):
        self.started = True
        self._begin()
        self.skip_once = True  # started from inside another state's update: this frame was not simulated

    def _begin(self):
        seg = self.segment
        seed = seed_for(self.index, self.attempt)
        folder = self.root / f"{self.index + 1:02d}_level{seg['level'] + 1}_try{self.attempt + 1}"
        self.writer = SegmentWriter(folder)
        self.meta = {"take": self.name, "segment": self.index, "attempt": self.attempt, "seed": seed, **seg,
                     "recorded": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.t = 0.0
        self.wait = 0.0
        apply_segment(self.app, seg, seed)
        self.play = self.app.state

    def _end(self, outcome, advance):
        self.writer.close(dict(self.meta, outcome=outcome, seconds_played=round(self.t, 2)))
        self.writer = None
        if advance:
            self.index, self.attempt = self.index + 1, 0
        else:
            self.attempt += 1
        if self.index >= len(SEGMENTS):
            from .states import MenuState
            self.done = True
            self.app.change(MenuState)
            self.app.hud.set_warning(f"TAKE COMPLETE - saved to recordings/{self.name} - Esc quits")
            return
        self._begin()

    def stop(self):
        """Esc / window closed: keep what was recorded of the current segment."""
        if self.writer is not None:
            self.writer.close(dict(self.meta, outcome="stopped", seconds_played=round(self.t, 2)))
            self.writer = None

    def frame(self, dt, face, ctl):
        """Called once per frame after the state update."""
        if not self.started or self.done:
            return
        if getattr(self, "skip_once", False):
            self.skip_once = False
            return
        from .states import PlayState
        state = self.app.state
        playing = isinstance(state, PlayState)
        if playing and state is not self.play:  # the player retried by themselves after a game over
            self._end("died", advance=False)
            return
        if playing:
            self.t += dt
            w = self.app.world
            self.writer.add(dt, face, ctl, state.halted, state.level.elapsed, w.score, w.ship.x)
            seg = self.segment
            self.app.hud.set_level_info(
                f"● REC {self.index + 1}/{len(SEGMENTS)}",
                f"{seg['title']} · {int(self.t)} / {seg['seconds']} s · N next · R retry")
        if self._retry:
            self._retry = False
            self._end("retry", advance=False)
        elif self._next or (playing and self.t >= self.segment["seconds"]):
            self._next = False
            self._end("time", advance=True)
        elif not playing:  # game over or level complete: keep the clip, then go on
            self.wait += dt
            if self.wait > 2.5:
                won = type(state).__name__ in ("LevelCompleteState", "OutroState", "HighscoreState", "MenuState")
                self._end("won" if won else "died", advance=won)
