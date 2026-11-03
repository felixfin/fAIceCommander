"""Turns raw face measurements into game controls: calibration, smoothing, hysteresis, edge triggers."""
import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Controls:
    steer: float = 0.0          # -1 (left) .. 1 (right), analog
    mouth_open: bool = False
    mouth_pressed: bool = False  # mouth just opened (one laser pulse, one nuke, shield toggle)
    weapon_step: int = 0         # -1 previous / +1 next weapon, only on the frame of the switch
    eyes_closed: bool = False
    tracked: bool = False        # a face (or the keyboard) is currently controlling the ship
    # normalized values for the panel gauges
    tilt_gauge: float = 0.0
    turn_gauge: float = 0.0
    mouth_gauge: float = 0.0
    eyes_gauge: float = 0.0


class OneEuroFilter:
    """Low lag smoothing for noisy tracking signals (Casiez et al. 2012)."""

    def __init__(self, min_cutoff=1.2, beta=0.05, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x = self.dx = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, dt):
        if self.x is None or dt <= 0:
            self.x, self.dx = x, 0.0
            return x
        dx = (x - self.x) / dt
        self.dx += self._alpha(self.d_cutoff, dt) * (dx - self.dx)
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        self.x += self._alpha(cutoff, dt) * (x - self.x)
        return self.x


@dataclass
class Calibration:
    tilt: float = 0.0
    turn: float = 0.0
    jaw_closed: float = 0.05
    jaw_open: float = 0.55
    blink_open: float = 0.1
    blink_closed: float = 0.75


class Calibrator:
    """Collects samples during the three calibration steps (neutral, mouth open, eyes closed)."""

    STEPS = ("neutral", "mouth", "eyes")

    def __init__(self):
        self.samples = {k: [] for k in self.STEPS}

    def add(self, step, face):
        self.samples[step].append((face.tilt_deg, face.turn, face.jaw_open, face.blink))

    def count(self, step):
        return len(self.samples[step])

    def result(self, fallback=None):
        cal = fallback or Calibration()
        n = np.array(self.samples["neutral"]) if self.samples["neutral"] else None
        if n is not None:
            cal.tilt, cal.turn = float(np.median(n[:, 0])), float(np.median(n[:, 1]))
            cal.jaw_closed = float(np.percentile(n[:, 2], 90))
            cal.blink_open = float(np.percentile(n[:, 3], 90))
        if self.samples["mouth"]:
            cal.jaw_open = max(float(np.percentile(np.array(self.samples["mouth"])[:, 2], 80)), cal.jaw_closed + 0.15)
        if self.samples["eyes"]:
            cal.blink_closed = max(float(np.percentile(np.array(self.samples["eyes"])[:, 3], 80)), cal.blink_open + 0.2)
        return cal


class GestureMapper:
    def __init__(self, cfg):
        c = cfg["controls"]
        self.deadzone, self.full = c["tilt_deadzone_deg"], c["tilt_full_deg"]
        self.turn_thr, self.turn_rearm, self.turn_lockout = c["turn_threshold"], c["turn_rearm"], c["turn_lockout_s"]
        self.turn_hold = c.get("turn_hold_s", 0.0)
        self.turn_tilt_penalty = c.get("turn_tilt_penalty", 0.0)
        self._turn_held = 0.0
        self.mouth_on, self.mouth_off = c["mouth_open_ratio"], c["mouth_close_ratio"]
        self.eyes_thr = c["eyes_closed_ratio"]
        self.cal = Calibration()
        self._tilt_f, self._turn_f = OneEuroFilter(1.5, 0.04), OneEuroFilter(1.5, 0.3)
        self._mouth_open = False
        self._turn_armed = True
        self._turn_cool = 0.0
        self._last_ts = None

    def calibrate(self, cal):
        self.cal = cal

    def update(self, face, dt):
        ctl = Controls()
        self._turn_cool = max(0.0, self._turn_cool - dt)
        if not face.found:
            self._mouth_open = False
            return ctl
        fdt = dt if self._last_ts is None else max(face.timestamp - self._last_ts, 1e-3)
        self._last_ts = face.timestamp
        cal = self.cal
        tilt = self._tilt_f(face.tilt_deg - cal.tilt, fdt)
        turn = self._turn_f(face.turn - cal.turn, fdt)
        mag = max(0.0, abs(tilt) - self.deadzone) / (self.full - self.deadzone)
        ctl.steer = math.copysign(min(mag, 1.0), tilt) if mag > 0 else 0.0
        mouth = (face.jaw_open - cal.jaw_closed) / max(cal.jaw_open - cal.jaw_closed, 1e-3)
        was_open = self._mouth_open
        if not was_open and mouth > self.mouth_on:
            self._mouth_open = True
        elif was_open and mouth < self.mouth_off:
            self._mouth_open = False
        ctl.mouth_open = self._mouth_open
        ctl.mouth_pressed = self._mouth_open and not was_open
        eyes = (face.blink - cal.blink_open) / max(cal.blink_closed - cal.blink_open, 1e-3)
        ctl.eyes_closed = eyes > self.eyes_thr
        # tilting to steer drags the nose sideways a little: demand a clearer turn while tilted
        thr = self.turn_thr * (1 + self.turn_tilt_penalty * min(1.0, abs(tilt) / self.full))
        if abs(turn) > thr:
            self._turn_held += fdt
        else:
            self._turn_held = 0.0
        if self._turn_armed and self._turn_cool <= 0 and abs(turn) > thr and self._turn_held >= self.turn_hold:
            ctl.weapon_step = 1 if turn > 0 else -1
            self._turn_armed = False
            self._turn_cool = self.turn_lockout
        elif abs(turn) < self.turn_rearm:
            self._turn_armed = True
        ctl.tracked = True
        ctl.tilt_gauge = max(-1.0, min(1.0, tilt / self.full))
        ctl.turn_gauge = max(-1.0, min(1.0, turn / (self.turn_thr * 1.3)))
        ctl.mouth_gauge = max(0.0, min(1.0, mouth))
        ctl.eyes_gauge = max(0.0, min(1.0, eyes))
        return ctl
