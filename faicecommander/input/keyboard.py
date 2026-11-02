"""Keyboard fallback (development, testing, playing without a webcam).

Left/Right or A/D steer, Space = open mouth, Q/E = previous/next weapon, C = close eyes.
"""
from panda3d.core import KeyboardButton

from .gestures import Controls


class KeyboardControls:
    def __init__(self, base):
        self.base = base
        self._space = False
        self._steps = []
        for key, step in (("q", -1), ("e", 1)):
            base.accept(key, self._steps.append, [step])

    def _down(self, *keys):
        watcher = self.base.mouseWatcherNode
        return watcher is not None and any(watcher.isButtonDown(k) for k in keys)

    def update(self):
        """Returns Controls if any control key is in use this frame, else None."""
        left = self._down(KeyboardButton.left(), KeyboardButton.asciiKey("a"))
        right = self._down(KeyboardButton.right(), KeyboardButton.asciiKey("d"))
        space = self._down(KeyboardButton.space())
        eyes = self._down(KeyboardButton.asciiKey("c"))
        step = self._steps.pop(0) if self._steps else 0
        pressed = space and not self._space
        self._space = space
        if not (left or right or space or eyes or step):
            return None
        ctl = Controls(steer=float(right) - float(left), mouth_open=space, mouth_pressed=pressed,
                       weapon_step=step, eyes_closed=eyes, tracked=True)
        ctl.tilt_gauge, ctl.mouth_gauge, ctl.eyes_gauge, ctl.turn_gauge = ctl.steer, float(space), float(eyes), float(step)
        return ctl
