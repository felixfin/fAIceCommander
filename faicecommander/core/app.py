"""Application shell: window and display regions, lights, input sources, state machine."""
import math
import random
import time

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight, AntialiasAttrib, DirectionalLight, Filename, Material, Point2, Point3, WindowProperties,
)

from ..audio import AudioSystem
from ..game.levels import LEVELS
from ..game.world import World
from ..input.face_tracker import FaceTracker
from ..input.gestures import Controls, GestureMapper
from ..input.keyboard import KeyboardControls
from ..render.backdrop import Backdrop
from ..render.effects import ScreenFlash
from ..render.hud import Hud
from ..render.webcam_view import WebcamView
from .states import TitleState

GAME_VFOV = 44.0


class App(ShowBase):
    def __init__(self, cfg, levels_cfg, args):
        ShowBase.__init__(self)
        self.cfg, self.levels_cfg, self.args = cfg, levels_cfg, args
        self.disableMouse()
        self.setBackgroundColor(0.02, 0.025, 0.04, 1)
        self.win.setClearColor((0.02, 0.025, 0.04, 1))
        self.panel_visible = True
        self._setup_scene()
        self.tracker = FaceTracker(cfg)
        self.tracker_ok = (not args.no_camera) and self.tracker.start()
        self.gestures = GestureMapper(cfg)
        self.keyboard = KeyboardControls(self)
        self._last_keyboard = -99.0
        self._pause = self._skip = False
        self.webcam = WebcamView(self)
        self.hud = Hud(self)
        self.flash = ScreenFlash(self.render2d)
        self.backdrop = Backdrop(self.render, self.camera, seed=3)
        self.world = World(self, cfg)
        self.audio = AudioSystem(self, cfg)
        self.level_count = len(LEVELS)
        self.level_index = max(0, min(self.level_count - 1, getattr(args, "level", 1) - 1))
        self.level_start_score = 0.0
        self.shake_amount = 0.0
        self.cam_base = self.camera.getPos()
        self.autopilot = Autopilot() if args.autopilot else None
        self.accept("f2", self.toggle_panel)
        self.accept("f11", self.toggle_fullscreen)
        self.accept("escape", self.userExit)
        self.accept("p", self._flag, ["_pause"])
        self.accept("enter", self._flag, ["_skip"])
        self.accept("m", self.audio.toggle_mute)
        self.accept("window-event", self.on_window_event)
        if cfg["display.fullscreen"] and not args.windowed and not args.offscreen:
            self.toggle_fullscreen(force=True)
        self.layout()
        self.state = None
        self.change(TitleState)
        self.taskMgr.add(self.update, "update")
        self._t0 = time.monotonic()

    # ------------------------------------------------------------ setup

    def _setup_scene(self):
        self.render.setAntialias(AntialiasAttrib.MMultisample)
        self.render.setShaderAuto()
        mat = Material("hull")
        mat.setSpecular((0.32, 0.32, 0.35, 1))
        mat.setShininess(28)
        self.render.setMaterial(mat)
        amb = self.render.attachNewNode(AmbientLight("amb"))
        amb.node().setColor((0.2, 0.2, 0.27, 1))
        key = self.render.attachNewNode(DirectionalLight("key"))
        key.node().setColor((1.15, 1.07, 1.0, 1))
        key.setHpr(-35, -55, 0)
        rim = self.render.attachNewNode(DirectionalLight("rim"))
        rim.node().setColor((0.55, 0.4, 1.0, 1))
        rim.setHpr(150, -15, 0)
        for light in (amb, key, rim):
            self.render.setLight(light)
        self.camera.setPos(0, -15.0, 18.0)
        self.camera.lookAt(Point3(0, 3.5, 0))
        self.filters = None
        if self.cfg["display.bloom"]:
            try:
                from direct.filter.CommonFilters import CommonFilters
                self.filters = CommonFilters(self.win, self.cam)
                if not self.filters.setBloom(blend=(0.3, 0.4, 0.3, 0.0), mintrigger=0.55, maxtrigger=1.0,
                                             desat=0.1, intensity=1.1, size="medium"):
                    self.filters = None
            except Exception:  # bloom is cosmetic; never block the game on it
                self.filters = None

    # ------------------------------------------------------------ layout

    def panel_frac(self):
        return self.cfg["display.panel_height"] if self.panel_visible else 0.0

    def layout(self):
        w, h = self.win.getXSize(), self.win.getYSize()
        if w <= 0 or h <= 0:
            return
        pf = self.panel_frac()
        self.camNode.getDisplayRegion(0).setDimensions(0, 1, pf, 1)
        aspect = w / max(1.0, h * (1 - pf))
        hfov = math.degrees(2 * math.atan(math.tan(math.radians(GAME_VFOV / 2)) * aspect))
        self.camLens.setFov(hfov, GAME_VFOV)
        if self.filters is not None:
            for region in self.win.getDisplayRegions():
                if region.getCamera() == self.cam and region is not self.camNode.getDisplayRegion(0):
                    region.setDimensions(0, 1, pf, 1)
        cam_w = (pf * h * 4 / 3) / w
        if pf > 0:
            self.webcam.set_rect(0.5 - cam_w / 2, 0.5 + cam_w / 2, 0.0, pf)
        self.webcam.region.setActive(pf > 0 and self.tracker_ok)
        self.hud.layout(pf, self.panel_visible)
        self.hud.cam_note.setText("" if self.tracker_ok else "WEBCAM OFF\nkeyboard mode")
        self.flash.fit(-1 + 2 * pf)
        top = self._plane_y(1.0)
        bottom = self._plane_y(-1.0)
        self.world.set_bounds(top if top is not None else 22.0, bottom if bottom is not None else -14.0)

    def _plane_y(self, screen_y):
        """y where the screen's vertical centre line at screen_y (-1..1) meets the play plane."""
        near, far = Point3(), Point3()
        if not self.camLens.extrude(Point2(0, screen_y), near, far):
            return None
        a = self.render.getRelativePoint(self.cam, near)
        b = self.render.getRelativePoint(self.cam, far)
        if abs(b.z - a.z) < 1e-6:
            return None
        t = -a.z / (b.z - a.z)
        return a.y + (b.y - a.y) * t

    def on_window_event(self, win):
        self.windowEvent(win)
        if win == self.win:
            self.layout()

    def toggle_panel(self):
        self.panel_visible = not self.panel_visible
        self.layout()

    def toggle_fullscreen(self, force=None):
        props = WindowProperties()
        full = (not self.win.getProperties().getFullscreen()) if force is None else force
        props.setFullscreen(full)
        if full:
            props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        else:
            props.setSize(*self.cfg["display.window_size"])
        self.win.requestProperties(props)

    # ------------------------------------------------------------ state machine & helpers

    def change(self, state_cls):
        if self.state is not None:
            self.state.exit()
        self.state = state_cls(self)
        self.state.enter()

    def make_level(self):
        cls = LEVELS[self.level_index]
        self.level_start_score = self.world.score
        return cls(self.world, self.levels_cfg[cls.key])

    def restart_level(self):
        """Easy mode: retry the current level with the score it started with."""
        self.world.score = self.level_start_score

    def next_level(self):
        self.level_index += 1
        if self.level_index >= self.level_count:  # end of the content so far: start over
            self.level_index = 0
            self.world.score = 0.0

    def shake(self, amount):
        self.shake_amount = max(self.shake_amount, amount)

    def _flag(self, name):
        setattr(self, name, True)

    def pause_toggled(self):
        flag, self._pause = self._pause, False
        return flag

    def skip_requested(self):
        flag, self._skip = self._skip, False
        return flag

    def keyboard_recent(self):
        return time.monotonic() - self._last_keyboard < 3.0

    # ------------------------------------------------------------ frame

    def update(self, task):
        dt = min(self.clock.getDt(), 0.05)
        face = self.tracker.latest() if self.tracker_ok else None
        ctl = self.gestures.update(face, dt) if face is not None else Controls()
        kb = self.keyboard.update()
        if kb is not None:
            ctl = kb
            self._last_keyboard = time.monotonic()
        if self.autopilot:
            ctl = self.autopilot.update(dt, self.world)
        self.state.update(dt, face, ctl)
        self.webcam.update(face, ctl)
        self.hud.set_gauges(ctl)
        if self.tracker_ok:
            self.hud.set_status(f"FACE TRACKING · camera {self.tracker.fps:.0f} fps\n"
                                f"{'face locked' if face and face.found else 'searching for a face'}")
        else:
            why = self.tracker.error or "disabled"
            self.hud.set_status(f"KEYBOARD MODE ({why})\nA/D steer · SPACE mouth · Q/E weapon · C eyes")
        self.hud.set_track(self.audio.music.title, self.audio.builder.progress, self.audio.muted)
        self.flash.update(dt)
        self.audio.update(dt)
        self.shake_amount = max(0.0, self.shake_amount - dt * 2.5)
        s = self.shake_amount ** 2 * 0.35
        self.camera.setPos(self.cam_base + (random.uniform(-s, s), random.uniform(-s, s), random.uniform(-s, s)))
        moving = self.state.scrolling and not getattr(self.state, "halted", False)
        self.backdrop.update(dt, self.world.scroll if moving else self.world.scroll * 0.15)
        if self.args.screenshot and time.monotonic() - self._t0 > self.args.autopilot:
            self.win.saveScreenshot(Filename.fromOsSpecific(self.args.screenshot))
            self.userExit()
        return task.cont

    def userExit(self):
        self.tracker.stop()
        super().userExit()


class Autopilot:
    """Plays by itself for automated smoke tests: chases the nearest asteroid and fires."""

    def __init__(self):
        self.t = 0.0
        self.mouth = False

    def update(self, dt, world):
        self.t += dt
        ship = world.ship
        targets = [a for a in world.asteroids if a.y > ship.y]
        steer = 0.0
        if targets:
            a = min(targets, key=lambda a: a.y)
            steer = max(-1.0, min(1.0, (a.x - ship.x) * 0.8))
        was = self.mouth
        self.mouth = (self.t % 0.5) < 0.25
        step = 1 if int(self.t / 3) != int((self.t - dt) / 3) else 0  # cycle through the weapons
        ctl = Controls(steer=steer, mouth_open=self.mouth, mouth_pressed=self.mouth and not was, weapon_step=step,
                       tracked=True)
        ctl.tilt_gauge, ctl.mouth_gauge = steer, float(self.mouth)
        return ctl
