"""In-engine cutscenes: a list of shots, each with its own little 3D scene, camera move and text.

Voice-over is optional: if faicecommander/assets/voice/<line id>.wav exists it is played with the line
(see assets/voice/LINES.txt for the ids and texts); otherwise the line is shown as a typed caption.
"""
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import Filename, TextNode

from ..config import ASSETS_DIR

VOICE_DIR = ASSETS_DIR / "voice"
TYPE_RATE = 38.0  # characters per second


class Line:
    def __init__(self, at, text, line_id=None, style="caption"):
        self.at, self.text, self.id, self.style = at, text, line_id, style


class Shot:
    def __init__(self, duration, build, update=None, lines=()):
        self.duration, self.build, self.update, self.lines = duration, build, update, list(lines)


class Cutscene:
    """Plays shots in order. build(root, ctx) returns state for update(t, dt, state, ctx)."""

    def __init__(self, app, shots, music, layers):
        self.app, self.shots, self.music, self.layers = app, shots, music, layers
        self.t = 0.0
        self.index = -1
        self.root = None
        self.state = None
        self.done = False
        font = app.hud.font
        self.caption = OnscreenText("", parent=app.hud.center, pos=(0, -0.62), scale=0.05, fg=(0.92, 0.94, 1, 1),
                                    font=font, mayChange=True, wordwrap=34, shadow=(0, 0, 0, 1))
        # the big line sits low, below the face in the webcam close-up
        self.card = OnscreenText("", parent=app.hud.center, pos=(0, -0.5), scale=0.085, fg=(1, 0.45, 0.85, 1),
                                 font=font, mayChange=True, wordwrap=22, shadow=(0, 0, 0, 1), align=TextNode.ACenter)
        self.credits = OnscreenText("", parent=app.hud.center, pos=(0, 0.42), scale=0.05, fg=(1, 0.6, 0.9, 1),
                                    font=font, mayChange=True, wordwrap=40, shadow=(0, 0, 0, 1))
        self.voices = {}
        self.played = set()

    @property
    def total(self):
        return sum(s.duration for s in self.shots)

    def start(self):
        app = self.app
        self.saved_cam = (app.camera.getPos(), app.camera.getHpr())
        app.world.root.hide()
        app.hud.show_game_hud(False)
        app.hud.message()
        app.audio.music.play(self.music, self.layers)

    def _voice(self, line_id):
        if line_id not in self.voices:
            path = VOICE_DIR / f"{line_id}.wav"
            self.voices[line_id] = (self.app.loader.loadSfx(Filename.fromOsSpecific(str(path)).getFullpath())
                                    if path.exists() else None)
        return self.voices[line_id]

    def update(self, dt):
        if self.done:
            return
        self.t += dt
        start = 0.0
        for i, shot in enumerate(self.shots):
            if self.t < start + shot.duration:
                break
            start += shot.duration
        else:
            self.finish()
            return
        local = self.t - start
        if i != self.index:
            self._enter(i)
        ctx = self.app
        if shot.update:
            shot.update(local, dt, self.state, ctx)
        self._text(shot, local)

    def _enter(self, i):
        if self.root is not None:
            self.root.removeNode()
        if self.state and "cleanup" in self.state:
            self.state.pop("cleanup")()
        self.index = i
        self.root = self.app.render.attachNewNode(f"shot-{i}")
        self.state = self.shots[i].build(self.root, self.app) or {}

    def _text(self, shot, local):
        caption, card, credits = "", "", ""
        for line in shot.lines:
            if local < line.at:
                continue
            shown = line.text[: int((local - line.at) * TYPE_RATE)] if line.style == "caption" else line.text
            if line.style == "card":
                card = shown
            elif line.style == "credits":
                credits = shown
            else:
                caption = shown
            key = (self.index, line.at)
            if line.id and key not in self.played:
                self.played.add(key)
                voice = self._voice(line.id)
                if voice is not None:
                    voice.play()
        self.caption.setText(caption)
        self.card.setText(card)
        self.credits.setText(credits)

    def skip(self):
        self.finish()

    def finish(self):
        if self.done:
            return
        self.done = True
        if self.root is not None:
            self.root.removeNode()
        if self.state and "cleanup" in self.state:
            self.state["cleanup"]()
        for voice in self.voices.values():
            if voice is not None:
                voice.stop()
        self.caption.destroy()
        self.card.destroy()
        self.credits.destroy()
        app = self.app
        app.camera.setPos(self.saved_cam[0])
        app.camera.setHpr(self.saved_cam[1])
        app.world.root.show()
        app.backdrop.set_visible(True)
        app.webcam_fullscreen(False)
