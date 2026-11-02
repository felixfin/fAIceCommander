"""Loads the TOML settings and offers dotted access, e.g. cfg["world.px_per_unit"]."""
import tomllib
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
ASSETS_DIR = PACKAGE_DIR / "assets"


class Config:
    def __init__(self, data):
        self._data = data

    @classmethod
    def load(cls, name):
        with open(DATA_DIR / name, "rb") as f:
            return cls(tomllib.load(f))

    def __getitem__(self, dotted):
        node = self._data
        for key in dotted.split("."):
            node = node[key]
        return Config(node) if isinstance(node, dict) else node

    def dict(self):
        return dict(self._data)

    def get(self, dotted, default=None):
        try:
            return self[dotted]
        except KeyError:
            return default

    def set(self, dotted, value):
        *path, last = dotted.split(".")
        node = self._data
        for key in path:
            node = node.setdefault(key, {})
        node[last] = value


class Units:
    """Converts the px values from the config into world units."""

    def __init__(self, cfg):
        self.ppu = cfg["world.px_per_unit"]

    def __call__(self, px):
        return px / self.ppu
