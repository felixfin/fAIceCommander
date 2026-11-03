"""Audio facade used by the game: procedural sound effects plus the adaptive soundtrack."""
from .cache import MusicBuilder
from .players import MusicDirector, SfxPlayer


class _SilentSfx:
    """Stands in until the sound effects have been synthesized (first start, loading screen)."""

    def play(self, *args, **kwargs):
        pass

    def loop(self, *args, **kwargs):
        pass

    def stop_loops(self):
        pass


class AudioSystem:
    def __init__(self, base, cfg):
        self.base = base
        self.builder = MusicBuilder()  # renders whatever is missing in the background
        master = cfg["audio.master"]
        self._sfx_volume = master * cfg["audio.sfx"]
        self.sfx = _SilentSfx()
        self.music = MusicDirector(base, self.builder, master * cfg["audio.music"])
        self.muted = False
        self.update(0.0)

    def toggle_mute(self):
        self.muted = not self.muted
        for mgr in self.base.sfxManagerList:
            mgr.setVolume(0.0 if self.muted else 1.0)

    def update(self, dt):
        if isinstance(self.sfx, _SilentSfx) and self.builder.sfx_ready:
            self.sfx = SfxPlayer(self.base, self._sfx_volume)
        self.music.update(dt)
