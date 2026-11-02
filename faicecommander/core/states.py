"""Game states. Each gets update(dt, face, ctl) every frame while active."""
from ..input.gestures import Calibrator

VOID_LAYERS = {"pad": 1.0, "sonar": 0.8}


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
        self.app.audio.music.play("void", VOID_LAYERS)

    def update(self, dt, face, ctl):
        self.t += dt
        if self.t > 0.8 and ctl.mouth_pressed or self.t > 12:
            self.app.audio.sfx.play("beep_high")
            self.app.change(CalibrationState if self.app.tracker_ok else PlayState)

    def exit(self):
        self.app.hud.set_warning("")


class CalibrationState(State):
    STEPS = (("neutral", "Look straight into the camera", "Keep your head upright and your mouth closed", 2.5),
             ("mouth", "Open your mouth wide", "Hold it open", 2.0),
             ("eyes", "Close your eyes", "Keep them closed until you hear the tone", 3.0))

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
                self.app.audio.sfx.play("beep_high")
                self.app.gestures.calibrate(self.cal.result())
                self.app.change(PlayState)
            else:
                self.app.audio.sfx.play("beep")

    def exit(self):
        self.app.hud.set_warning("")
        self.app.hud.message()


class PlayState(State):
    scrolling = True
    BOOMS = ((2.5, "nuke_boom", 1.0), (1.3, "boom_big", 0.9), (0.0, "boom_small", 0.7))

    def enter(self):
        app = self.app
        self.level = app.make_level()
        self.level.start()
        app.hud.show_game_hud(True)
        app.hud.message(self.level.title, self.level.banner, "")
        app.audio.music.play(self.level.music, {"pad": 1.0, "arp": 0.7})
        self.t = 0.0
        self.lost = 0.0
        self.paused = False
        self.low_hull = False

    @property
    def halted(self):
        return self.paused or self.lost >= self.app.cfg["controls.face_lost_pause_s"]

    def update(self, dt, face, ctl):
        app = self.app
        if app.pause_toggled():
            self.paused = not self.paused
        face_mode = app.tracker_ok and not app.keyboard_recent()
        self.lost = self.lost + dt if face_mode and not (face and face.found) else 0.0
        audio, w = app.audio, app.world
        if self.halted:
            app.hud.set_warning("PAUSED · press P" if self.paused else "FACE LOST · look into the camera")
            audio.music.set_duck(0.35)
            audio.sfx.stop_loops()
            return
        app.hud.set_warning("")
        audio.music.set_duck(1.0)
        self.t += dt
        if self.t > 3.0:
            app.hud.message()
        for ev in self.level.update(dt, ctl):
            self._on_event(ev)
        audio.sfx.loop("beam", w.weapons.beam_on, 0.7)
        audio.sfx.loop("shield", w.ship.shield_on, 0.6)
        self._music_layers(w)
        app.hud.set_weapons(w.weapons.unlocked, w.weapons.selected, w.weapons.nukes)
        app.hud.set_stats(w.ship.hull, w.ship.energy, w.score, self.level.title, self.level.progress)
        if w.ship.hull <= 0:
            w.explode(w.ship.x, w.ship.y, 2.0)
            audio.sfx.play("boom_big")
            app.change(GameOverState)
        elif self.level.complete:
            app.change(LevelCompleteState)

    def _music_layers(self, w):
        low = w.ship.hull < 35
        if low and not self.low_hull:
            self.app.audio.sfx.play("alarm")
        self.low_hull = low
        k = 0.65 if low else 1.0
        if self.t < 3.0:
            layers = {"pad": 1.0, "arp": 0.7}
        else:
            layers = {"drums": k, "bass": k, "arp": 0.8 * k, "pad": 0.8, "lead": k if self.level.progress > 0.5 else 0.0}
        layers["heartbeat"] = 1.0 if low else 0.0
        self.app.audio.music.set_layers(layers)

    def _on_event(self, ev):
        app, sfx, kind = self.app, self.app.audio.sfx, ev[0]
        if kind == "laser":
            sfx.play("laser", 0.55, rate=0.95 + 0.1 * app.world.rng.random())
        elif kind in ("empty", "switch", "crack"):
            sfx.play(kind)
        elif kind == "split":
            sfx.play("crack")
        elif kind == "shield":
            sfx.play("shield_on" if ev[1] else "shield_off")
        elif kind == "nuke_launch":
            sfx.play("nuke_launch")
        elif kind == "nuke_boom":  # the light arrives first, the sound with the shockwave
            app.flash.trigger(0.8, (1.0, 0.95, 0.85))
            app.shake(0.9)
        elif kind == "boom":
            for min_size, name, vol in self.BOOMS:
                if ev[1] >= min_size:
                    sfx.play(name, vol * min(1.0, 0.5 + ev[1] * 0.3), rate=0.9 + 0.2 * app.world.rng.random())
                    if name == "nuke_boom":
                        app.shake(1.4)
                    break
        elif kind == "hit":
            sfx.play("thud")
            app.flash.trigger()
            app.shake(0.35)

    def exit(self):
        self.app.hud.set_warning("")
        self.app.audio.sfx.stop_loops()


class _EndState(State):
    title = sub = hint = ""

    def enter(self):
        self.t = 0.0
        self.app.hud.message(self.title, self.sub.format(score=int(self.app.world.score)), self.hint)

    def update(self, dt, face, ctl):
        self.t += dt
        w = self.app.world
        w.effects = [fx for fx in w.effects if fx.update(dt)]
        if self.t > 1.5 and ctl.mouth_pressed:
            self.app.audio.sfx.play("beep_high")
            self.proceed()
            self.app.change(PlayState)

    def proceed(self):
        pass


class GameOverState(_EndState):
    title, sub, hint = "GAME OVER", "Score {score}", "Open your mouth or press SPACE to retry this level"

    def enter(self):
        self.app.world.ship.node.hide()
        self.app.world.beam.hide()
        self.app.audio.sfx.play("game_over")
        self.app.audio.music.play("void", VOID_LAYERS)
        super().enter()

    def proceed(self):
        self.app.restart_level()

    def exit(self):
        self.app.world.ship.node.show()


class LevelCompleteState(_EndState):
    title = "STAR REACHED"

    def enter(self):
        last = self.app.level_index == self.app.level_count - 1
        self.sub = "Score {score}" + (" · levels 3-7 arrive in the next milestones" if last else "")
        self.hint = "Open your mouth or press SPACE to " + ("start over" if last else "jump to the next star")
        self.app.world.beam.hide()
        self.app.audio.sfx.play("chime")
        self.app.audio.music.set_layers({"pad": 1.0, "arp": 0.6})
        super().enter()

    def proceed(self):
        self.app.next_level()
