"""Face-control logic with synthetic tracker data (no webcam needed)."""
import numpy as np

from faicecommander.config import Config
from faicecommander.input.face_tracker import CHIN, EYE_OUTER_LEFT, EYE_OUTER_RIGHT, FOREHEAD, FaceState
from faicecommander.input.gestures import Calibrator, GestureMapper

CFG = Config.load("config.toml")


class Feed:
    """Produces FaceStates with increasing frame ids and timestamps at 30 fps."""

    def __init__(self):
        self.i = 0

    def __call__(self, tilt=0.0, turn=0.0, jaw=0.02, blink=0.05, found=True):
        self.i += 1
        return FaceState(found=found, timestamp=self.i / 30, tilt_deg=tilt, turn=turn, jaw_open=jaw, blink=blink,
                         frame_id=self.i)


def calibrated():
    feed, cal = Feed(), Calibrator()
    for _ in range(30):
        cal.add("neutral", feed(tilt=2.0, turn=0.05, jaw=0.03, blink=0.08))
    for _ in range(30):
        cal.add("mouth", feed(jaw=0.7))
    for _ in range(30):
        cal.add("eyes", feed(blink=0.85))
    g = GestureMapper(CFG)
    g.calibrate(cal.result())
    return g, feed


def run(g, feed, n, **kw):
    out = []
    for _ in range(n):
        out.append(g.update(feed(**kw), 1 / 30))
    return out


def test_calibration_uses_neutral_pose():
    g, _ = calibrated()
    assert abs(g.cal.tilt - 2.0) < 1e-6
    assert g.cal.jaw_open > g.cal.jaw_closed + 0.5


def test_tilt_steers_analog_with_deadzone():
    g, feed = calibrated()
    assert run(g, feed, 20, tilt=2.0 + 3.0)[-1].steer == 0.0         # inside the dead zone
    half = run(g, feed, 40, tilt=2.0 + 13.0)[-1].steer
    assert 0.4 < half < 0.6                                          # analog
    assert run(g, feed, 40, tilt=2.0 + 40.0)[-1].steer == 1.0        # clamped
    assert run(g, feed, 60, tilt=2.0 - 30.0)[-1].steer == -1.0       # left


def test_laser_fires_once_per_mouth_opening():
    g, feed = calibrated()
    presses = sum(c.mouth_pressed for c in run(g, feed, 30, jaw=0.7))  # mouth held open
    assert presses == 1
    run(g, feed, 10, jaw=0.03)                                         # close
    assert sum(c.mouth_pressed for c in run(g, feed, 10, jaw=0.7)) == 1  # open again -> next pulse


def test_hysteresis_ignores_jitter_around_threshold():
    g, feed = calibrated()
    jaw_open = g.cal.jaw_closed + 0.6 * (g.cal.jaw_open - g.cal.jaw_closed)
    jaw_mid = g.cal.jaw_closed + 0.45 * (g.cal.jaw_open - g.cal.jaw_closed)
    presses = 0
    for k in range(40):
        presses += g.update(feed(jaw=jaw_open if k % 2 else jaw_mid), 1 / 30).mouth_pressed
    assert presses == 1


def test_repeated_frame_does_not_retrigger():
    g, feed = calibrated()
    face = feed(jaw=0.7)
    first = g.update(face, 1 / 60)
    second = g.update(face, 1 / 60)  # game runs faster than the camera: same frame twice
    assert first.mouth_pressed and not second.mouth_pressed and second.mouth_open


def test_turn_switches_weapon_once_and_rearms():
    g, feed = calibrated()
    steps = [c.weapon_step for c in run(g, feed, 30, turn=0.9)]
    assert steps.count(1) == 1 and -1 not in steps
    run(g, feed, 30, turn=0.05)
    steps = [c.weapon_step for c in run(g, feed, 30, turn=-0.9)]
    assert steps.count(-1) == 1


def test_eyes_closed():
    g, feed = calibrated()
    assert not run(g, feed, 5, blink=0.1)[-1].eyes_closed
    assert run(g, feed, 5, blink=0.8)[-1].eyes_closed


def test_lost_face_releases_controls():
    g, feed = calibrated()
    run(g, feed, 5, jaw=0.7, tilt=30)
    ctl = g.update(feed(found=False), 1 / 30)
    assert not ctl.tracked and ctl.steer == 0 and not ctl.mouth_open


def test_helmet_matrix_frontal_face():
    from faicecommander.render.webcam_view import HELMET_EYE_SPAN, WebcamView
    lm = np.zeros((478, 3), np.float32)
    lm[EYE_OUTER_LEFT] = (280, 220, 0)
    lm[EYE_OUTER_RIGHT] = (360, 220, 0)
    lm[FOREHEAD] = (320, 150, 0)
    lm[CHIN] = (320, 330, 0)
    m = WebcamView._helmet_matrix(lm, 640, 480)
    k = 80 / HELMET_EYE_SPAN
    assert np.allclose([m.getCell(0, 0), m.getCell(1, 1), m.getCell(2, 2)], [k, k, k], atol=1e-3)  # upright, facing us
    assert m.getCell(3, 2) > 240 - 220  # helmet centre sits above the eyes


def test_helmet_matrix_follows_roll():
    from faicecommander.render.webcam_view import WebcamView
    lm = np.zeros((478, 3), np.float32)
    lm[EYE_OUTER_LEFT] = (280, 210, 0)   # screen-right eye lower: head tilted to the right
    lm[EYE_OUTER_RIGHT] = (360, 230, 0)
    lm[FOREHEAD] = (330, 150, 0)
    lm[CHIN] = (310, 330, 0)
    m = WebcamView._helmet_matrix(lm, 640, 480)
    assert m.getCell(0, 2) < 0  # helmet x axis points down to the right, like the eye line
