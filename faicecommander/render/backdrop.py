"""Scrolling space backdrop below the play plane: nebula texture plus parallax star layers."""
import numpy as np
from panda3d.core import (
    CardMaker, Geom, GeomNode, GeomPoints, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    RenderModeAttrib, SamplerState, Texture, TextureStage,
)


def _fbm(rng, n, octaves=(4, 8, 16, 32, 64)):
    """Tileable fractal noise: blocky octaves smoothed with wrap-around box blurs."""
    acc = np.zeros((n, n))
    for i, o in enumerate(octaves):
        up = np.kron(rng.random((o, o)), np.ones((n // o, n // o)))
        k = max(1, n // o // 2)
        for _ in range(2):
            for axis in (0, 1):
                up = sum(np.roll(up, s, axis) for s in range(-k, k + 1)) / (2 * k + 1)
        acc += up * 0.5 ** i
    acc -= acc.min()
    return acc / acc.max()


def nebula_texture(seed=1, n=256, tint=(0.4, 0.12, 0.5), tint2=(0.05, 0.25, 0.4)):
    rng = np.random.default_rng(seed)
    a = np.clip((_fbm(rng, n) - 0.5) * 2.2, 0, 1) ** 2
    b = np.clip((_fbm(rng, n) - 0.55) * 2.5, 0, 1) ** 2
    rgb = a[..., None] * np.array(tint) * 0.6 + b[..., None] * np.array(tint2) * 0.55
    tex = Texture("nebula")
    tex.setup2dTexture(n, n, Texture.T_unsigned_byte, Texture.F_rgb)
    tex.setRamImage(np.ascontiguousarray(np.uint8(np.clip(rgb[..., ::-1], 0, 1) * 255)).tobytes())  # Panda wants BGR
    tex.setWrapU(SamplerState.WM_repeat)
    tex.setWrapV(SamplerState.WM_repeat)
    return tex


def star_layer(rng, count, width, period, brightness):
    vd = GeomVertexData("stars", GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vw, cw = GeomVertexWriter(vd, "vertex"), GeomVertexWriter(vd, "color")
    prim = GeomPoints(Geom.UHStatic)
    i = 0
    for copy in range(2):  # two stacked copies so the layer can wrap seamlessly
        r = np.random.default_rng(int(rng.integers(1 << 30)))
        for _ in range(count):
            b = brightness * r.random() ** 2.2
            tint = (1.0, 1.0, 1.0) if r.random() < 0.7 else ((0.8, 0.9, 1.0) if r.random() < 0.5 else (1.0, 0.9, 0.8))
            vw.addData3(r.uniform(-width, width), r.uniform(0, period) + copy * period, 0)
            cw.addData4(tint[0] * b, tint[1] * b, tint[2] * b, 1)
            prim.addVertex(i)
            i += 1
    g = Geom(vd)
    g.addPrimitive(prim)
    node = GeomNode("stars")
    node.addGeom(g)
    return node


class Backdrop:
    def __init__(self, parent, camera, seed=1, void=False):
        self.root = parent.attachNewNode("backdrop")
        self.root.setLightOff(1)
        self.root.setShaderOff(1)
        self.root.setDepthWrite(False)
        self.root.setBin("background", 0)
        rng = np.random.default_rng(seed)
        self.layers = []
        self.nebula = None
        self.neb_offset = 0.0
        if not void:
            # the nebula hangs behind everything, in front of the camera, so it never shows an edge
            cm = CardMaker("nebula")
            cm.setFrame(-1600, 1600, -700, 700)
            self.nebula = camera.attachNewNode(cm.generate())
            self.nebula.setY(1000)
            self.nebula.setTexture(nebula_texture(seed))
            self.nebula.setTexScale(TextureStage.getDefault(), 2.3, 1)
            self.nebula.setLightOff(1)
            self.nebula.setShaderOff(1)
            self.nebula.setDepthWrite(False)
            self.nebula.setDepthTest(False)
            self.nebula.setBin("background", -10)
            for depth, count, size, bright, factor in ((-15, 700, 2.2, 1.0, 1.0), (-35, 1200, 1.6, 0.8, 0.7),
                                                       (-70, 1800, 1.2, 0.6, 0.45)):
                period = 220 + abs(depth) * 2
                np_ = self.root.attachNewNode(star_layer(rng, count, 140 + abs(depth) * 2.2, period, bright))
                np_.setZ(depth)
                np_.setAttrib(RenderModeAttrib.make(RenderModeAttrib.MPoint, size, False))
                self.layers.append((np_, period, factor))
        self.offset = 0.0

    def update(self, dt, speed):
        self.offset += speed * dt
        for np_, period, factor in self.layers:
            np_.setY(-40 - (self.offset * factor) % period)
        if self.nebula is not None:
            self.neb_offset += speed * dt * 0.0012
            self.nebula.setTexOffset(TextureStage.getDefault(), 0, self.neb_offset)

    def set_visible(self, visible):
        """The Void level shows nothing at all."""
        for node in (self.root, self.nebula):
            if node is not None:
                node.show() if visible else node.hide()

    def destroy(self):
        self.root.removeNode()
        if self.nebula is not None:
            self.nebula.removeNode()
