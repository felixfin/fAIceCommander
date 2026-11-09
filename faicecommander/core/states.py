"""Game states. Each gets update(dt, face, ctl) every frame while active; on_escape() handles Esc."""
import math

from ..cutscenes.intro import make_intro
from ..cutscenes.outro import make_outro
from ..game.hypno import PULSE, WARNING
from ..game.levels import DIFFICULTIES, LEVELS
from ..input.gestures import Calibrator

VOID_LAYERS = {"pad": 1.0, "sonar": 0.8}


class State:
    scrolling = False   # does the starfield move (constant thrust)?
    cinematic = False   # a cutscene owns the camera

    def __init__(self, app):
        self.app = app

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self, dt, face, ctl):
        pass

    def on_escape(self):
        self.app.change(MenuState)


# ---------------------------------------------------------------- cutscenes

class _CutsceneState(State):
    cinematic = True
    make = None
    skippable = True  # off for offline renders (tools/trailer): a recorded open mouth must not skip

    def enter(self):
        self.app.hud.message()
        self.app.hud.set_menu([], 0)
        self.app.cinema.show(True)
        self.scene = type(self).make(self.app)
        self.scene.start()
        self.held = 0.0

    def update(self, dt, face, ctl):
        self.held = self.held + dt if ctl.mouth_open else 0.0
        skip = self.app.skip_requested() or (ctl.mouth_pressed and not self.app.tracker_ok) or self.held > 1.2
        if skip and self.skippable:
            self.scene.skip()
        self.scene.update(dt)
        if self.scene.done:
            self.finished()

    def on_escape(self):
        self.scene.skip()

    def finished(self):
        pass

    def exit(self):
        self.scene.finish()
        self.app.cinema.show(False)
        self.app.hypno_alpha = 0.0


class IntroState(_CutsceneState):
    make = staticmethod(make_intro)

    def finished(self):
        app = self.app
        app.change(CalibrationState if app.tracker_ok and not app.calibrated else MenuState)


class OutroState(_CutsceneState):
    make = staticmethod(make_outro)

    def __init__(self, app, preview=False):
        super().__init__(app)
        self.preview = preview  # started with --cutscene outro: just watching, nothing was won

    def finished(self):
        if self.preview:
            self.app.change(MenuState)
            return
        self.app.save.unlock_endless()
        self.app.end_run(victory=True)


# ---------------------------------------------------------------- menus

class LoadingState(State):
    """First start: the sound effects and the menu/intro music are synthesized and the Mother's ship
    is built in the background. Shows a progress bar and a slowly turning ship until that is done."""

    def enter(self):
        app = self.app
        from ..render import models as M
        from ..render.hud import Bar
        self.t = 0.0
        app.hud.show_game_hud(False)
        app.world.root.hide()
        app.backdrop.set_visible(True)
        self.root = app.render.attachNewNode("loading")
        self.ship = M.cached("ship", M.build_ship).getChild(0).copyTo(self.root)
        self.ship.setPos(0, 3.5, 0.5)
        self.ship.setScale(1.4)
        self.bar = Bar(app.hud.center, -0.6, -0.25, 1.2, 0.04, (1, 0.45, 0.85, 1), segments=50)
        from ..cutscenes.prewarm import steps
        self.props = steps()        # intro/outro set pieces: built once per frame here, so cuts never stall
        self.props_total = len(self.props)
        app.hud.message("fAIceCommander 3D", "Preparing the soundtrack (first start only)", "")
        app.hud.title.setZ(0.42)
        app.hud.subtitle.setZ(0.3)
        app.hud.hint.setZ(-0.34)

    @property
    def done(self):
        b = self.app.audio.builder
        return ((b.startup_ready or b.error is not None) and self.app.world.mother_model.model is not None
                and not self.props)

    def update(self, dt, face, ctl):
        self.t += dt
        b = self.app.audio.builder
        mother = 0.0 if self.app.world.mother_model.model is None else 1.0
        if self.props and self.t > 0.2:
            tmp = self.app.hidden.attachNewNode("prewarm")
            self.props.pop(0)(tmp)
            tmp.removeNode()
        sets = 1 - len(self.props) / self.props_total
        self.bar.set(0.75 * b.startup_progress + 0.05 * mother + 0.2 * sets)
        status = b.status or ("building the Mother's ship" if not mother else "")
        if not status and self.props:
            status = "building the intro and outro sets"
        self.app.hud.hint.setText(status or "ready")
        self.ship.setH(self.t * 25)
        self.ship.setR(8 * math.sin(self.t * 0.9))
        if self.done and self.t > 0.3:
            app = self.app
            cutscene = getattr(app.args, "cutscene", None)
            if app.take is not None:
                if app.tracker_ok and not app.calibrated:
                    app.change(CalibrationState)  # calibrate first; the take starts from the menu state
                else:
                    app.take.start()
            elif cutscene == "outro":
                app.change(OutroState(app, preview=True))
            elif cutscene == "intro" or app.cfg.get("display.play_intro", True):
                app.change(IntroState)
            else:
                app.change(MenuState)

    def on_escape(self):
        self.app.userExit()

    def exit(self):
        hud = self.app.hud
        self.root.removeNode()
        self.bar.node.removeNode()
        hud.title.setZ(0.08)
        hud.subtitle.setZ(-0.02)
        hud.hint.setZ(-0.1)
        hud.hint.setText("")
        hud.message()
        self.app.world.root.show()


class CalibrationState(State):
    STEPS = (("neutral", "Look straight into the camera", "Keep your head upright and your mouth closed", 2.5),
             ("mouth", "Open your mouth wide", "Hold it open", 2.0),
             ("eyes", "Close your eyes", "Keep them closed until you hear the tone", 3.0))

    def enter(self):
        self.cal = Calibrator()
        self.step, self.t = 0, 0.0
        self.app.hud.show_game_hud(False)
        self.app.hud.set_menu([], 0)
        self.app.audio.music.play("void", VOID_LAYERS)

    def update(self, dt, face, ctl):
        if self.app.skip_requested():
            self.app.calibrated = True
            if self.app.take is not None and not self.app.take.started:
                self.app.take.start()
            else:
                self.app.change(MenuState)
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
                self.app.calibrated = True
                if self.app.take is not None and not self.app.take.started:
                    self.app.take.start()
                else:
                    self.app.change(MenuState)
            else:
                self.app.audio.sfx.play("beep")

    def exit(self):
        self.app.hud.set_warning("")
        self.app.hud.message()


class MenuState(State):
    """Turn your head (Q/E, arrows) to move, open your mouth (SPACE, Enter) to choose."""

    def enter(self):
        app = self.app
        self.t = 0.0
        self.page = "main"
        self.sel = 1  # MEDIUM
        app.hud.show_game_hud(False)
        app.world.root.hide()
        app.backdrop.set_visible(True)
        app.audio.music.play("void", VOID_LAYERS)
        app.hud.set_warning("")
        self._draw()

    def items(self):
        app = self.app
        if self.page == "practice":
            return [(f"DIFFICULTY · {app.difficulty.upper()}", True, self._cycle_difficulty)] + \
                   [(f"LEVEL {cls.number} · {app.levels_cfg[cls.key]['name'].upper()}", True,
                     lambda i=i: app.start_run("practice", i)) for i, cls in enumerate(LEVELS)] + \
                   [("BACK", True, self._main)]
        return [("EASY · retry the level you fail", True, lambda: app.start_run("easy")),
                ("MEDIUM · tougher, retry the level you fail", True, lambda: app.start_run("medium")),
                ("HARD · much tougher, one life from level 1", True, lambda: app.start_run("hard")),
                ("ENDLESS", app.save.endless_unlocked, lambda: app.start_run("endless")),
                ("PRACTICE A LEVEL", True, self._practice),
                ("HIGHSCORES", True, lambda: app.change(HighscoreState)),
                ("WATCH THE INTRO", True, lambda: app.change(IntroState)),
                ("RECALIBRATE", app.tracker_ok, lambda: app.change(CalibrationState)),
                ("QUIT", True, app.userExit)]

    def _practice(self):
        self.page, self.sel = "practice", 1

    def _cycle_difficulty(self):
        app = self.app
        app.difficulty = DIFFICULTIES[(DIFFICULTIES.index(app.difficulty) + 1) % len(DIFFICULTIES)]

    def _main(self):
        self.page, self.sel = "main", 4

    def _draw(self):
        hint = "Turn your head to choose · open your mouth to start" if self.app.tracker_ok else \
            "Q/E or arrows to choose · SPACE to start"
        self.app.hud.message("fAIceCommander 3D" if self.page == "main" else "PRACTICE", "", hint)
        self.app.hud.title.setZ(0.42)
        self.app.hud.hint.setZ(0.3)
        self.app.hud.set_menu([(label, ok) for label, ok, _ in self.items()], self.sel)

    def update(self, dt, face, ctl):
        self.t += dt
        items = self.items()
        if ctl.weapon_step:
            self.sel = (self.sel + ctl.weapon_step) % len(items)
            self.app.audio.sfx.play("switch")
        if self.t > 0.6 and (ctl.mouth_pressed or self.app.skip_requested()):
            label, ok, action = items[self.sel]
            if ok:
                self.app.audio.sfx.play("beep_high")
                action()
                if self.app.state is not self:
                    return
            else:
                self.app.audio.sfx.play("empty")
        self._draw()

    def on_escape(self):
        if self.page != "main":
            self._main()
        else:
            self.app.userExit()

    def exit(self):
        hud = self.app.hud
        hud.set_menu([], 0)
        hud.title.setZ(0.08)
        hud.hint.setZ(-0.1)
        hud.message()
        self.app.world.root.show()


class HighscoreState(State):
    def enter(self):
        app = self.app
        self.t = 0.0
        app.hud.show_game_hud(False)
        app.world.root.hide()
        app.hud.message("HIGHSCORES", "", "")
        app.hud.title.setZ(0.42)
        cols = []
        for mode in ("easy", "medium", "hard", "endless"):
            rows = [f"{mode.upper()}", ""]
            table = app.save.top(mode)
            rows += [f"{i + 1:2d}. {e['name']:<12} {e['score']:>8d}  {e['level']}" for i, e in enumerate(table)]
            rows += ["-"] if not table else []
            cols.append("\n".join(rows))
        app.hud.set_columns(cols)
        for col in app.hud.columns:
            col.setZ(0.28)
        app.hud.set_warning("Open your mouth or press SPACE to return")

    def update(self, dt, face, ctl):
        self.t += dt
        if self.t > 0.8 and (ctl.mouth_pressed or self.app.skip_requested()):
            self.app.change(MenuState)

    def exit(self):
        hud = self.app.hud
        hud.set_columns([])
        hud.title.setZ(0.08)
        hud.set_warning("")
        hud.message()
        self.app.world.root.show()


class NameEntryState(State):
    """Type your name (keyboard); Enter - or opening your mouth - saves it."""

    def __init__(self, app, mode, score, level):
        super().__init__(app)
        self.mode, self.score, self.level = mode, score, level

    def enter(self):
        app = self.app
        self.name = app.save.last_name
        self.t = 0.0
        app.text_input = True
        app.accept("keystroke", self._key)
        app.accept("backspace", self._backspace)
        app.accept("backspace-repeat", self._backspace)
        app.hud.show_game_hud(False)
        self._draw()

    def _key(self, ch):
        if ch.isalnum() or ch in " -_.":
            if len(self.name) < 12:
                self.name += ch.upper()

    def _backspace(self):
        self.name = self.name[:-1]

    def _draw(self):
        cursor = "_" if int(self.t * 2) % 2 == 0 else " "
        self.app.hud.message("NEW HIGHSCORE", f"{self.mode.upper()} · {int(self.score)} points",
                             f"Your name: {self.name}{cursor}   ·   Enter or open your mouth to save")

    def update(self, dt, face, ctl):
        self.t += dt
        self._draw()
        if self.app.skip_requested() or (self.t > 1.0 and ctl.mouth_pressed and self.app.tracker_ok):
            self.app.save.add(self.mode, self.name, self.score, self.level)
            self.app.audio.sfx.play("chime")
            self.app.change(HighscoreState)

    def on_escape(self):
        self.app.change(MenuState)

    def exit(self):
        app = self.app
        app.text_input = False
        for ev in ("keystroke", "backspace", "backspace-repeat"):
            app.ignore(ev)
        app.hud.message()


# ---------------------------------------------------------------- playing

class PlayState(State):
    BOOMS = ((2.5, "nuke_boom", 1.0), (1.3, "boom_big", 0.9), (0.0, "boom_small", 0.7))
    SIMPLE_SFX = {"empty": ("empty", 1.0), "switch": ("switch", 1.0), "split": ("crack", 1.0),
                  "nuke_launch": ("nuke_launch", 1.0), "metal_hit": ("metal_hit", 0.6),
                  "brain_spawn": ("brain_spawn", 0.22), "hypno_warning": ("siren", 0.9), "frozen": ("freeze", 0.9),
                  "absorbed": ("absorbed", 1.0), "mother_hit": ("metal_hit", 0.5), "bomb": ("nuke_launch", 0.6),
                  "hole_formed": ("absorbed", 0.5), "hole_collapse": ("boom_small", 0.6),
                  "mouse_throw": ("mouse_throw", 0.7), "squeak": ("squeak", 0.8), "belly": ("purr_growl", 1.0),
                  "flak": ("enemy_shot", 0.6), "mother_roar": ("mother_roar", 1.0),
                  "mother_scream": ("mother_scream", 0.9), "hypno_start": ("hypno_scream", 0.9)}
    BANNERS = {"wave": ("", "Another wave of raiders"), "intercepted": ("", "Nuke intercepted!"),
               "mother_phase": None}

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
        self.banner_until = 3.0  # the level title shows for the first seconds
        app.audio.music.play(self.level.music, self._layers(intro=True))

    @property
    def scrolling(self):
        return self.app.world.scroll_mult > 0

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
        if self.t > self.banner_until:
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
        app.hud.set_level_info(self.level.progress_label, self.level.note)
        if w.ship.hull <= 0:
            if w.death_cause == "absorbed":
                w.ship.node.hide()
            else:
                w.explode(w.ship.x, w.ship.y, 2.0)
                audio.sfx.play("boom_big")
            app.change(GameOverState)
        elif self.level.complete:
            app.change(OutroState if self.level.number == 7 else LevelCompleteState)

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
            layers = {"pad": 1.0, "arp": 0.7, "choir": 1.0}
        else:
            layers = {"drums": k, "bass": k, "arp": 0.8 * k, "pad": 0.8, "choir": 1.0,
                      "lead": k if self.level.progress > 0.5 or self.level.number == 7 else 0.0}
        layers["heartbeat"] = 1.0 if low else 0.0
        return layers

    def _on_event(self, ev):
        app, sfx, kind = self.app, self.app.audio.sfx, ev[0]
        if kind in self.SIMPLE_SFX:
            name, vol = self.SIMPLE_SFX[kind]
            sfx.play(name, vol)
        if kind in self.BANNERS:
            title, sub = self.BANNERS[kind] or (f"PHASE {ev[1]}", "She is enraged!" if ev[1] == 3 else "She is angry")
            app.hud.message(title, sub, "")
            self.banner_until = self.t + 2.5
            if kind == "mother_phase":
                app.flash.trigger(0.6, (1.0, 0.2, 0.15))
                app.shake(1.2)
                sfx.play("mother_roar", 1.0)
        if kind == "enemy_shot":  # Catliens yowl when they fire
            if ev[1] == "mother":
                sfx.play("mother_meow", 0.8, rate=0.9 + 0.2 * app.world.rng.random())
            else:
                sfx.play(f"meow_{int(app.world.rng.integers(1, 4))}", 1.0, rate=0.95 + 0.1 * app.world.rng.random())
            sfx.play("enemy_shot", 0.12)
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
        elif kind == "mother_down":
            app.flash.trigger(0.9, (1.0, 0.9, 0.8))
            app.shake(1.6)
            sfx.play("nuke_boom")
            sfx.play("mother_death", 1.0)

    def on_escape(self):
        self.app.end_run()

    def exit(self):
        app = self.app
        app.hud.set_warning("")
        app.hud.set_level_info("NEXT STAR", "")
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
        if self.t > 1.5 and (ctl.mouth_pressed or self.app.skip_requested()):
            self.app.audio.sfx.play("beep_high")
            self.proceed()

    def proceed(self):
        pass


class GameOverState(_EndState):
    title = "GAME OVER"

    def enter(self):
        app, w = self.app, self.app.world
        cause = {"absorbed": "Absorbed by the black hole", "drained": "Drained by the black hole"}.get(
            w.death_cause, "Hull destroyed")
        self.sub = cause + " · score {score}"
        self.retry = app.mode in ("easy", "medium", "practice")
        self.hint = ("Open your mouth or press SPACE to retry this level · Esc ends the run" if self.retry else
                     "Open your mouth or press SPACE to continue")
        w.ship.node.hide()
        w.beam.hide()
        app.audio.sfx.play("game_over")
        app.audio.music.play("void", VOID_LAYERS)
        super().enter()

    def proceed(self):
        if self.retry:
            self.app.restart_level()
            self.app.change(PlayState)
        else:
            self.app.end_run()

    def on_escape(self):
        self.app.end_run()

    def exit(self):
        self.app.world.ship.node.show()


class LevelCompleteState(_EndState):
    title = "STAR REACHED"

    def enter(self):
        app = self.app
        practice = app.mode == "practice"
        self.sub = "Score {score}"
        self.hint = "Open your mouth or press SPACE to " + ("return to the menu" if practice else "jump to the next star")
        app.world.beam.hide()
        app.audio.sfx.play("chime")
        if app.audio.music.current == "void_brains":
            app.audio.music.set_layers({"drone": 0.6, "pad": 1.0})
        else:
            app.audio.music.set_layers({"pad": 1.0, "arp": 0.6})
        super().enter()

    def proceed(self):
        if self.app.mode == "practice":
            self.app.change(MenuState)
        else:
            self.app.level_index += 1
            self.app.change(PlayState)
