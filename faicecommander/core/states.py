"""Game states. Each gets update(dt, face, ctl) every frame while active."""
from ..input.gestures import Calibrator


class State:
    scrolling = False  # does the starfield move (constant thrust)?

    def __init__(self, app):
        self.app = app

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self, dt, face, ctl):
        pass


class TitleState(State):
    def enter(self):
        self.t = 0.0
        self.app.hud.show_game_hud(False)
        self.app.hud.message("fAIceCommander 3D", "Steer with your head · fire with your mouth",
                             "Open your mouth or press SPACE to start")
        self.app.hud.set_warning("Photosensitivity warning: this game contains flashing lights.")

    def update(self, dt, face, ctl):
        self.t += dt
        if self.t > 0.8 and ctl.mouth_pressed or self.t > 12:
            self.app.change(CalibrationState if self.app.tracker_ok else PlayState)

    def exit(self):
        self.app.hud.set_warning("")


class CalibrationState(State):
    STEPS = (("neutral", "Look straight into the camera", "Keep your head upright and your mouth closed", 2.5),
             ("mouth", "Open your mouth wide", "Hold it open", 2.0),
             ("eyes", "Close your eyes", "Keep them closed for 3 seconds", 3.0))

    def enter(self):
        self.cal = Calibrator()
        self.step, self.t = 0, 0.0
        self.app.hud.show_game_hud(False)

    def update(self, dt, face, ctl):
        if self.app.skip_requested():
            self.app.change(PlayState)
            return
        key, title, sub, duration = self.STEPS[self.step]
        if face is not None and face.found:
            self.t += dt
            self.cal.add(key, face)
            warn = ""
        else:
            warn = "No face detected - look into the camera"
        left = max(0.0, duration - self.t)
        self.app.hud.message(f"CALIBRATION {self.step + 1}/3", title, f"{sub} · {left:.1f}")
        self.app.hud.set_warning(warn)
        if self.t >= duration:
            self.step, self.t = self.step + 1, 0.0
            if self.step == len(self.STEPS):
                self.app.gestures.calibrate(self.cal.result())
                self.app.change(PlayState)

    def exit(self):
        self.app.hud.set_warning("")
        self.app.hud.message()


class PlayState(State):
    scrolling = True

    def enter(self):
        self.level = self.app.make_level()
        self.level.start()
        self.app.hud.show_game_hud(True)
        self.app.hud.message(self.level.title, "Reach the next star", "")
        self.banner = 3.0
        self.lost = 0.0
        self.paused = False

    @property
    def halted(self):
        return self.paused or self.lost >= self.app.cfg["controls.face_lost_pause_s"]

    def update(self, dt, face, ctl):
        app = self.app
        if app.pause_toggled():
            self.paused = not self.paused
        face_mode = app.tracker_ok and not app.keyboard_recent()
        self.lost = self.lost + dt if face_mode and not (face and face.found) else 0.0
        if self.halted:
            app.hud.set_warning("PAUSED · press P" if self.paused else "FACE LOST · look into the camera")
            return
        app.hud.set_warning("")
        self.banner -= dt
        if self.banner <= 0:
            app.hud.message()
        for kind, payload in self.level.update(dt, ctl):
            if kind == "hit":
                app.flash.trigger()
        w = app.world
        app.hud.set_weapons(w.weapons.unlocked, w.weapons.selected, w.weapons.nukes)
        app.hud.set_stats(w.ship.hull, w.ship.energy, w.score, self.level.title, self.level.progress)
        if w.ship.hull <= 0:
            w.explode(w.ship.x, w.ship.y, 2.0)
            app.change(GameOverState)
        elif self.level.complete:
            app.change(LevelCompleteState)

    def exit(self):
        self.app.hud.set_warning("")


class _EndState(State):
    title = sub = ""

    def enter(self):
        self.t = 0.0
        self.app.hud.message(self.title, self.sub.format(score=int(self.app.world.score)),
                             "Open your mouth or press SPACE to play again")

    def update(self, dt, face, ctl):
        self.t += dt
        self.app.world.effects = [fx for fx in self.app.world.effects if fx.update(dt)]
        if self.t > 1.5 and ctl.mouth_pressed:
            self.app.restart_level()
            self.app.change(PlayState)


class GameOverState(_EndState):
    title, sub = "GAME OVER", "Score {score}"

    def enter(self):
        self.app.world.ship.node.hide()
        super().enter()

    def exit(self):
        self.app.world.ship.node.show()


class LevelCompleteState(_EndState):
    title, sub = "STAR REACHED", "Score {score} · level 2 arrives in the next milestone"
