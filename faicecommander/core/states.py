"""Game states. Each gets update(dt, face, ctl) every frame while active."""
from ..game.hypno import PULSE, WARNING
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
    SIMPLE_SFX = {"empty": ("empty", 1.0), "switch": ("switch", 1.0), "split": ("crack", 1.0),
                  "nuke_launch": ("nuke_launch", 1.0), "enemy_shot": ("enemy_shot", 0.5),
                  "metal_hit": ("metal_hit", 0.6), "brain_spawn": ("brain_spawn", 0.22),
                  "hypno_warning": ("siren", 0.9), "frozen": ("freeze", 0.9), "absorbed": ("absorbed", 1.0)}

    def enter(self):
        app = self.app
        self.level = app.make_level()
        self.level.start()
        app.backdrop.set_visible(not self.level.void)
        app.splatter.clear()
        app.hud.show_game_hud(True)
        app.hud.message(self.level.title, self.level.banner, "")
        self.t = 0.0
        self.lost = 0.0
        self.paused = False
        self.low_hull = False
        app.audio.music.play(self.level.music, self._layers(intro=True))

    @property
    def halted(self):
        return self.paused or self.lost >= self.app.cfg["controls.face_lost_pause_s"]

    def update(self, dt, face, ctl):
        app = self.app
        if app.pause_toggled():
            self.paused = not self.paused
        face_mode = app.tracker_ok and not app.keyboard_recent()
        hyp = self.level.hypno
        self.lost = self.lost + dt if face_mode and not (face and face.found) else 0.0
        audio, w = app.audio, app.world
        if self.halted:
            app.hud.set_warning("PAUSED · press P" if self.paused else "FACE LOST · look into the camera")
            audio.music.set_duck(0.35)
            audio.sfx.stop_loops()
            return
        app.hud.set_warning("")
        self.t += dt
        if self.t > 3.0:
            app.hud.message()
        for ev in self.level.update(dt, ctl):
            self._on_event(ev)
        self._hypno(hyp)
        audio.sfx.loop("beam", w.weapons.beam_on, 0.7)
        audio.sfx.loop("shield", w.ship.shield_on, 0.6)
        audio.sfx.loop("blackhole", w.hole_proximity > 0.02, 0.2 + 0.8 * w.hole_proximity)
        audio.music.set_rate(1.0 - 0.2 * w.hole_proximity)  # the music sinks as you near the event horizon
        audio.music.set_layers(self._layers())
        app.hud.set_weapons(w.weapons.unlocked, w.weapons.selected, w.weapons.nukes)
        app.hud.set_stats(w.ship.hull, w.ship.energy, w.score, self.level.title, self.level.progress)
        if w.ship.hull <= 0:
            if w.death_cause == "absorbed":
                w.ship.node.hide()
            else:
                w.explode(w.ship.x, w.ship.y, 2.0)
                audio.sfx.play("boom_big")
            app.change(GameOverState)
        elif self.level.complete:
            app.change(LevelCompleteState)

    def _hypno(self, hyp):
        app = self.app
        if hyp is None:
            app.hypno_alpha = 0.0
            app.audio.music.set_duck(1.0)
            return
        app.hypno_alpha = hyp.overlay_alpha(self.t)
        app.audio.sfx.loop("hypno", hyp.active, 0.5)
        app.audio.music.set_duck(0.22 if hyp.active else 1.0)  # quiet, so the sonar is clear
        if hyp.phase == WARNING:
            app.hud.message("HYPNO PULSE", "Close your eyes!", f"{hyp.remaining:.1f}")
        elif hyp.phase == PULSE:
            if hyp.frozen:
                app.hud.message("FROZEN", "You opened your eyes", f"thawing in {hyp.remaining:.1f} s")
            else:
                app.hud.message("", "Keep your eyes closed · listen to the sonar", f"{hyp.remaining:.1f} s")
        elif hyp.since_end < 1.5:
            app.hud.message("", "Open your eyes", "")

    def _layers(self, intro=False):
        w = self.app.world
        low = w.ship.hull < 35
        if low and not self.low_hull and not intro:
            self.app.audio.sfx.play("alarm")
        self.low_hull = low
        k = 0.65 if low else 1.0
        if self.level.music == "void_brains":
            layers = {"drone": 1.0, "pad": 0.8, "pulse": 0.0 if intro else k, "whispers": 0.0 if intro else 0.9}
        elif intro or self.t < 3.0:
            layers = {"pad": 1.0, "arp": 0.7}
        else:
            layers = {"drums": k, "bass": k, "arp": 0.8 * k, "pad": 0.8,
                      "lead": k if self.level.progress > 0.5 else 0.0}
        layers["heartbeat"] = 1.0 if low else 0.0
        return layers

    def _on_event(self, ev):
        app, sfx, kind = self.app, self.app.audio.sfx, ev[0]
        if kind in self.SIMPLE_SFX:
            name, vol = self.SIMPLE_SFX[kind]
            sfx.play(name, vol)
        elif kind == "laser":
            sfx.play("laser", 0.55, rate=0.95 + 0.1 * app.world.rng.random())
        elif kind == "shield":
            sfx.play("shield_on" if ev[1] else "shield_off")
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
        elif kind == "kill" and ev[1].kind == "brain":
            sfx.play("splat", 0.8, rate=0.9 + 0.2 * app.world.rng.random())
        elif kind == "splatter":
            app.splatter.add(app.render, ev[1], app.world.rng)
            sfx.play("splat", 1.0, rate=0.8)
        elif kind == "hypno_end":
            sfx.play("beep_high")
        elif kind == "sonar":
            sfx.play(ev[1], 0.9, rate=ev[2])

    def exit(self):
        app = self.app
        app.hud.set_warning("")
        app.audio.sfx.stop_loops()
        app.audio.music.set_rate(1.0)
        app.audio.music.set_duck(1.0)
        app.hypno_alpha = 0.0
        app.world.ship.frozen = False


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
    title, hint = "GAME OVER", "Open your mouth or press SPACE to retry this level"

    def enter(self):
        w = self.app.world
        cause = "Absorbed by the black hole" if w.death_cause == "absorbed" else "Hull destroyed"
        self.sub = cause + " · score {score}"
        w.ship.node.hide()
        w.beam.hide()
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
        self.sub = "Score {score}" + (" · level 7 arrives in the next milestone" if last else "")
        self.hint = "Open your mouth or press SPACE to " + ("start over" if last else "jump to the next star")
        self.app.world.beam.hide()
        self.app.audio.sfx.play("chime")
        if self.app.audio.music.current == "void_brains":
            self.app.audio.music.set_layers({"drone": 0.6, "pad": 1.0})
        else:
            self.app.audio.music.set_layers({"pad": 1.0, "arp": 0.6})
        super().enter()

    def proceed(self):
        self.app.next_level()
