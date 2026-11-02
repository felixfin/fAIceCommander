"""Audio facade used by the game: procedural sound effects plus the adaptive soundtrack."""
from .cache import MusicBuilder, ensure_sfx
from .players import MusicDirector, SfxPlayer


class AudioSystem:
    def __init__(self, base, cfg):
        ensure_sfx()
        self.builder = MusicBuilder()
        master = cfg["audio.master"]
        self.sfx = SfxPlayer(base, master * cfg["audio.sfx"])
        self.music = MusicDirector(base, self.builder, master * cfg["audio.music"])
        self.muted = False
        self.base = base

    def toggle_mute(self):
        self.muted = not self.muted
        for mgr in self.base.sfxManagerList:
            mgr.setVolume(0.0 if self.muted else 1.0)

    def update(self, dt):
        self.music.update(dt)
