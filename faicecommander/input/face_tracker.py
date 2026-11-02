"""Webcam capture + MediaPipe FaceLandmarker in a background thread.

The frame is mirrored *before* detection, so everything downstream (steering, the AR helmet,
the displayed image) lives in the same mirror-image space the player sees.
"""
import math
import threading
import time
from dataclasses import dataclass

import numpy as np

from ..config import ASSETS_DIR

# MediaPipe face mesh landmark indices (as seen in the mirrored image)
EYE_OUTER_LEFT, EYE_OUTER_RIGHT = 33, 263   # screen-left / screen-right eye corners
NOSE_TIP = 1
CHEEK_LEFT, CHEEK_RIGHT = 234, 454
FOREHEAD, CHIN = 10, 152
LIP_UPPER, LIP_LOWER = 13, 14


@dataclass
class FaceState:
    found: bool = False
    timestamp: float = 0.0
    tilt_deg: float = 0.0      # head roll, + = tilted towards screen right
    turn: float = 0.0          # nose offset in half face widths, + = turned towards screen right
    jaw_open: float = 0.0      # blendshape jawOpen, 0..1
    blink: float = 0.0         # mean of eyeBlinkLeft/Right, 0..1
    landmarks: np.ndarray = None  # (478, 3): x, y in pixels of the mirrored frame, depth in pixels
    frame: np.ndarray = None      # mirrored BGR frame
    frame_id: int = 0


class FaceTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = FaceState()
        self.error = None
        self.fps = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        """Opens camera and model. Returns False (and sets .error) if face control is unavailable."""
        try:
            import cv2
            import mediapipe as mp
        except ImportError as e:
            self.error = f"missing package: {e.name}"
            return False
        model = ASSETS_DIR / "face_landmarker.task"
        if not model.exists():
            self.error = "face_landmarker.task not found in assets"
            return False
        cap = cv2.VideoCapture(self.cfg["camera.index"], cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.cfg["camera.index"])
        if not cap.isOpened():
            self.error = "no webcam found"
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg["camera.width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg["camera.height"])
        cap.set(cv2.CAP_PROP_FPS, self.cfg["camera.fps"])
        vision = mp.tasks.vision
        options = vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO, num_faces=1,
            output_face_blendshapes=True, output_facial_transformation_matrixes=False)
        self._landmarker = vision.FaceLandmarker.create_from_options(options)
        self._cap, self._cv2, self._mp = cap, cv2, mp
        self._thread = threading.Thread(target=self._run, name="face-tracker", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._cap.release()
            self._landmarker.close()

    def latest(self):
        with self._lock:
            return self.state

    def _run(self):
        cv2, mp = self._cv2, self._mp
        t0 = time.monotonic()
        last_ts, frame_id, fps_t, fps_n = -1, 0, time.monotonic(), 0
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            frame = cv2.flip(frame, 1)
            ts = int((time.monotonic() - t0) * 1000)
            if ts <= last_ts:
                ts = last_ts + 1
            last_ts = ts
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
            frame_id += 1
            state = self._analyse(result, frame, frame_id)
            with self._lock:
                self.state = state
            fps_n += 1
            now = time.monotonic()
            if now - fps_t >= 1.0:
                self.fps, fps_n, fps_t = fps_n / (now - fps_t), 0, now

    @staticmethod
    def _analyse(result, frame, frame_id):
        h, w = frame.shape[:2]
        if not result.face_landmarks:
            return FaceState(found=False, timestamp=time.monotonic(), frame=frame, frame_id=frame_id)
        lm = np.array([(p.x * w, p.y * h, p.z * w) for p in result.face_landmarks[0]], np.float32)
        l, r = lm[EYE_OUTER_LEFT], lm[EYE_OUTER_RIGHT]
        tilt = math.degrees(math.atan2(r[1] - l[1], r[0] - l[0]))
        cl, cr = lm[CHEEK_LEFT][0], lm[CHEEK_RIGHT][0]
        half = max(abs(cr - cl) / 2, 1.0)
        turn = (lm[NOSE_TIP][0] - (cl + cr) / 2) / half
        bs = {c.category_name: c.score for c in result.face_blendshapes[0]} if result.face_blendshapes else {}
        return FaceState(found=True, timestamp=time.monotonic(), tilt_deg=tilt, turn=turn,
                         jaw_open=bs.get("jawOpen", 0.0),
                         blink=(bs.get("eyeBlinkLeft", 0.0) + bs.get("eyeBlinkRight", 0.0)) / 2,
                         landmarks=lm, frame=frame, frame_id=frame_id)
