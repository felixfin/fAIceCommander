"""Mirrored webcam image with the AR life-support helmet anchored to the player's face.

The helmet pose is built directly from 3D face landmarks (eye corners, forehead, chin), so it
stays independent of MediaPipe's camera conventions: x right, y down, depth away from the camera.
"""
import numpy as np
from panda3d.core import (
    AmbientLight, Camera, CardMaker, DirectionalLight, LMatrix4f, Material, NodePath, OrthographicLens,
    Texture,
)

from ..input.face_tracker import CHIN, EYE_OUTER_LEFT, EYE_OUTER_RIGHT, FOREHEAD
from . import models as M

HELMET_EYE_SPAN = 0.95  # distance between the outer eye corners in helmet units


class WebcamView:
    def __init__(self, base):
        self.base = base
        self.scene = NodePath("webcam-scene")
        self.scene.setShaderAuto()
        mat = Material()
        mat.setSpecular((0.4, 0.4, 0.45, 1))
        mat.setShininess(30)
        self.scene.setMaterial(mat)
        amb = self.scene.attachNewNode(AmbientLight("amb"))
        amb.node().setColor((0.35, 0.35, 0.4, 1))
        key = self.scene.attachNewNode(DirectionalLight("key"))
        key.node().setColor((1.0, 0.97, 0.92, 1))
        key.setHpr(-25, -35, 0)
        for light in (amb, key):
            self.scene.setLight(light)
        self.size = (640, 480)
        self.lens = OrthographicLens()
        self.lens.setFilmSize(*self.size)
        self.lens.setNearFar(-3000, 6000)
        cam = Camera("webcam-cam", self.lens)
        self.cam = self.scene.attachNewNode(cam)
        self.region = base.win.makeDisplayRegion(0.4, 0.6, 0.0, 0.2)
        self.region.setSort(20)
        self.region.setCamera(self.cam)
        self.region.setClearColorActive(True)
        self.region.setClearColor((0.02, 0.03, 0.05, 1))
        self.region.setClearDepthActive(True)
        self.tex = Texture("webcam")
        self.tex.setup2dTexture(*self.size, Texture.T_unsigned_byte, Texture.F_rgb)
        cm = CardMaker("webcam-card")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        self.card = self.scene.attachNewNode(cm.generate())
        self.card.setTexture(self.tex)
        self.card.setLightOff(1)
        self.card.setY(5000)
        self.card.setScale(self.size[0], 1, self.size[1])
        self.card.setColorScale(0.75, 0.95, 1.0, 1)  # cool cyberpunk grade
        self.card.hide()
        self.helmet = M.build_helmet(self.scene)
        self.helmet.hide()
        self.cigar = self.helmet.find("**/cigar")
        self.cigar_rest = self.cigar.getPos()
        self.cigar_glow = self.helmet.find("**/cigar_glow")
        self.lenses = self.helmet.findAllMatches("**/lens")
        self._frame_id = -1

    def set_rect(self, left, right, bottom, top):
        self.region.setDimensions(left, right, bottom, top)

    def _ensure_size(self, w, h):
        if (w, h) != self.size:
            self.size = (w, h)
            self.lens.setFilmSize(w, h)
            self.tex.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgb)
            self.card.setScale(w, 1, h)

    def update(self, face, controls):
        if face is None or face.frame is None:
            self.card.hide()
            self.helmet.hide()
            return
        h, w = face.frame.shape[:2]
        self._ensure_size(w, h)
        if face.frame_id != self._frame_id:
            self._frame_id = face.frame_id
            self.tex.setRamImage(np.ascontiguousarray(face.frame[::-1]).tobytes())  # BGR, bottom-up
        self.card.show()
        if not face.found or face.landmarks is None:
            self.helmet.hide()
            return
        self.helmet.show()
        self.helmet.setMat(self._helmet_matrix(face.landmarks, w, h))
        jaw = controls.mouth_gauge if controls else 0.0
        self.cigar.setPos(self.cigar_rest + (0, 0, -0.28 * jaw))
        self.cigar_glow.setScale(0.25 * (1 + 1.5 * jaw))
        closed = controls.eyes_closed if controls else False
        for lens in self.lenses:
            if closed:
                lens.setColorScale(12.0, 5.0, 25.0, 1)  # violet glow: hypno protection active
                lens.setLightOff(1)
            else:
                lens.clearColorScale()
                lens.clearLight()

    @staticmethod
    def _helmet_matrix(lm, w, h):
        def P(i):
            x, y, z = lm[i]
            return np.array([x - w / 2, z, h / 2 - y], float)

        l, r = P(EYE_OUTER_LEFT), P(EYE_OUTER_RIGHT)
        xa = r - l
        span = np.linalg.norm(xa)
        xa /= max(span, 1e-6)
        up = P(FOREHEAD) - P(CHIN)
        za = up - xa * (up @ xa)
        za /= max(np.linalg.norm(za), 1e-6)
        ya = np.cross(za, xa)
        k = span / HELMET_EYE_SPAN
        eye_mid = (l + r) / 2
        pos = eye_mid - (-1.0 * ya * k + M.EYE_Z * za * k)
        pos[1] = min(pos[1], 0.0)  # keep it in front of the webcam card
        X, Y, Z = xa * k, ya * k, za * k
        return LMatrix4f(X[0], X[1], X[2], 0, Y[0], Y[1], Y[2], 0, Z[0], Z[1], Z[2], 0, pos[0], pos[1], pos[2], 1)
