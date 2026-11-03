"""Renders the procedural audio once into a per-user cache (WAV), in a background thread, and
reports progress for the loading screen: sound effects first, then the menu and intro music, then
the rest of the soundtrack."""
import os
import threading
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from . import sfx_bank, tracks
from .synth import SR

AUDIO_VERSION = "b1-2"  # bump when the synth code changes to re-render the cache


def cache_dir():
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache")
    d = base / "fAIceCommander3D" / "audio" / AUDIO_VERSION
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(path, data):
    """Atomic write; safe when several game instances fill the cache at the same time."""
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        wavfile.write(f, SR, (np.clip(data, -1, 1) * 32767).astype(np.int16))
    try:
        tmp.replace(path)
    except OSError:  # another instance wrote (and may be playing) the same file already
        tmp.unlink(missing_ok=True)
        if not path.exists():
            raise


def sfx_path(name):
    return cache_dir() / f"sfx_{name}.wav"


def stem_path(track, stem):
    return cache_dir() / f"music_{track}_{stem}.wav"


FIRST = ("void", "cinematic")  # menu and intro music: the loading screen waits for these


class MusicBuilder:
    """Renders missing sound effects and tracks in a background thread; the game polls .sfx_ready,
    .ready(track) and the progress values."""

    def __init__(self):
        self.done = set()
        self.current = None
        self.error = None
        self._marker = lambda t: cache_dir() / f"music_{t}.done"
        for t in tracks.TRACKS:
            if self._marker(t).exists():
                self.done.add(t)
        self.sfx_missing = [n for n in sfx_bank.SFX if not sfx_path(n).exists()]
        self.sfx_total = max(1, len(self.sfx_missing))
        self.sfx_done = 0
        self.sfx_ready = not self.sfx_missing
        self.thread = threading.Thread(target=self._run, name="audio-builder", daemon=True)
        self.thread.start()

    @property
    def progress(self):
        return len(self.done) / len(tracks.TRACKS)

    @property
    def startup_progress(self):
        """0..1 for the loading screen: sound effects, then the FIRST tracks."""
        sfx = 1.0 if self.sfx_ready else self.sfx_done / self.sfx_total
        music = sum(1 for t in FIRST if t in self.done) / len(FIRST)
        return 0.3 * sfx + 0.7 * music

    @property
    def startup_ready(self):
        return self.sfx_ready and all(t in self.done for t in FIRST)

    @property
    def status(self):
        if not self.sfx_ready:
            return f"synthesizing sound effects {self.sfx_done}/{self.sfx_total}"
        if self.current:
            return f"composing {tracks.TITLES.get(self.current, self.current)}"
        return ""

    def ready(self, track):
        return track in self.done

    def stems(self, track):
        return sorted(p.stem.split(f"music_{track}_", 1)[1] for p in cache_dir().glob(f"music_{track}_*.wav"))

    def _run(self):
        try:
            for name in self.sfx_missing:
                _write(sfx_path(name), sfx_bank.render(name))
                self.sfx_done += 1
            self.sfx_ready = True
            order = list(FIRST) + [t for t in tracks.TRACKS if t not in FIRST]
            for name in order:
                fn = tracks.TRACKS[name]
                if name in self.done:
                    continue
                self.current = name
                if not self._marker(name).exists():  # another instance may have finished it meanwhile
                    for stem, data in fn().items():
                        _write(stem_path(name, stem), data)
                    self._marker(name).touch()
                self.done.add(name)
            self.current = None
        except Exception as e:  # never take the game down because of music
            self.error = repr(e)
