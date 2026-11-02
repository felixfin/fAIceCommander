"""Renders the procedural audio once into a per-user cache (WAV) and reports progress."""
import os
import threading
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from . import sfx_bank, tracks
from .synth import SR

AUDIO_VERSION = "m3-1"  # bump when the synth code changes to re-render the cache


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


def ensure_sfx():
    """Sound effects are quick to make; done synchronously at startup."""
    if all(sfx_path(n).exists() for n in sfx_bank.SFX):
        return
    for name, data in sfx_bank.render_all().items():
        _write(sfx_path(name), data)


class MusicBuilder:
    """Renders missing tracks in a background thread; the game polls .ready(track)."""

    def __init__(self):
        self.done = set()
        self.current = None
        self.error = None
        self._marker = lambda t: cache_dir() / f"music_{t}.done"
        for t in tracks.TRACKS:
            if self._marker(t).exists():
                self.done.add(t)
        self.thread = threading.Thread(target=self._run, name="music-builder", daemon=True)
        self.thread.start()

    @property
    def progress(self):
        return len(self.done) / len(tracks.TRACKS)

    def ready(self, track):
        return track in self.done

    def stems(self, track):
        return sorted(p.stem.split(f"music_{track}_", 1)[1] for p in cache_dir().glob(f"music_{track}_*.wav"))

    def _run(self):
        try:
            for name, fn in tracks.TRACKS.items():
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
