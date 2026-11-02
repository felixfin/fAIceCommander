"""Playback through Panda3D: pooled one-shot effects, effect loops and the adaptive music director."""
from panda3d.core import AudioSound, Filename

from . import cache, sfx_bank, tracks

POOL_SIZES = {"laser": 6, "boom_small": 5, "boom_big": 3, "thud": 3, "crack": 3, "switch": 2, "empty": 2}
LOOPS = {"beam": "beam_loop", "shield": "shield_loop"}


def _load(base, path):
    return base.loader.loadSfx(Filename.fromOsSpecific(str(path)).getFullpath())


class SfxPlayer:
    def __init__(self, base, volume):
        self.volume = volume
        self.pools, self.next = {}, {}
        for name in sfx_bank.SFX:
            if name in LOOPS.values():
                continue
            self.pools[name] = [_load(base, cache.sfx_path(name)) for _ in range(POOL_SIZES.get(name, 1))]
            self.next[name] = 0
        self.loops = {}
        for key, name in LOOPS.items():
            s = _load(base, cache.sfx_path(name))
            s.setLoop(True)
            self.loops[key] = [s, False]

    def play(self, name, volume=1.0, rate=1.0):
        pool = self.pools[name]
        s = pool[self.next[name]]
        self.next[name] = (self.next[name] + 1) % len(pool)
        s.stop()
        s.setVolume(volume * self.volume)
        s.setPlayRate(rate)
        s.play()

    def loop(self, key, on, volume=1.0):
        entry = self.loops[key]
        sound, playing = entry
        if on:
            sound.setVolume(volume * self.volume)
            if not playing:
                sound.play()
        elif playing:
            sound.stop()
        entry[1] = on

    def stop_loops(self):
        for key in self.loops:
            self.loop(key, False)


class MusicDirector:
    """Keeps every stem of the current track playing in sync and fades layers by target volume."""

    def __init__(self, base, builder, volume, fade_s=1.5):
        self.base, self.builder = base, builder
        self.volume, self.fade_s = volume, fade_s
        self.loaded = {}          # track -> {stem: AudioSound}
        self.levels = {}          # (track, stem) -> current volume
        self.current = None
        self.wanted = None
        self.layers = {}
        self.duck = 1.0
        self._duck_target = 1.0

    @property
    def title(self):
        return tracks.TITLES.get(self.current, "") if self.current else ""

    def play(self, track, layers):
        if track == self.current:
            self.set_layers(layers)
        else:
            self.wanted = track
            self.layers = dict(layers)

    def set_layers(self, layers):
        self.layers = dict(layers)

    def set_duck(self, factor):
        self._duck_target = factor

    def _load(self, track):
        if track not in self.loaded:
            sounds = {}
            for stem in self.builder.stems(track):
                s = _load(self.base, cache.stem_path(track, stem))
                s.setLoop(True)
                s.setVolume(0)
                sounds[stem] = s
            self.loaded[track] = sounds
        return self.loaded[track]

    def update(self, dt):
        if self.wanted and self.builder.ready(self.wanted):
            stems = self._load(self.wanted)
            for s in stems.values():  # start all stems together so they stay in sync
                s.setTime(0)
                s.play()
            self.current, self.wanted = self.wanted, None
        self.duck += (self._duck_target - self.duck) * min(1.0, dt * 3)
        step = dt / self.fade_s
        for track, stems in self.loaded.items():
            active = False
            for stem, sound in stems.items():
                target = self.layers.get(stem, 0.0) * self.duck if track == self.current else 0.0
                cur = self.levels.get((track, stem), 0.0)
                cur = min(target, cur + step) if cur < target else max(target, cur - step)
                self.levels[(track, stem)] = cur
                sound.setVolume(cur * self.volume)
                active = active or cur > 0.001
            if track != self.current and not active:
                for sound in stems.values():
                    if sound.status() == AudioSound.PLAYING:
                        sound.stop()
