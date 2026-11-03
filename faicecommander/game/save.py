"""Persistent player data: top-10 highscores per mode, endless unlock, last name used."""
import json
import os
import time
from pathlib import Path

MODES = ("easy", "hard", "endless")
TOP = 10


def default_path():
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return base / "fAIceCommander3D" / "save.json"


class SaveData:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()
        self.data = {"highscores": {m: [] for m in MODES}, "endless_unlocked": False, "last_name": "COMMANDER"}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.update({k: v for k, v in loaded.items() if k in self.data})
            for m in MODES:
                self.data["highscores"].setdefault(m, [])
        except (OSError, ValueError):
            pass  # first start or unreadable file: keep the defaults

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def top(self, mode):
        return self.data["highscores"][mode]

    def qualifies(self, mode, score):
        if mode not in MODES or score <= 0:
            return False
        table = self.top(mode)
        return len(table) < TOP or score > table[-1]["score"]

    def add(self, mode, name, score, level):
        name = (name.strip() or "COMMANDER").upper()[:12]
        entry = {"name": name, "score": int(score), "level": level, "date": time.strftime("%Y-%m-%d")}
        table = sorted(self.top(mode) + [entry], key=lambda e: -e["score"])[:TOP]
        self.data["highscores"][mode] = table
        self.data["last_name"] = name
        self.save()
        return table.index(entry) + 1 if entry in table else None

    @property
    def endless_unlocked(self):
        return self.data["endless_unlocked"]

    def unlock_endless(self):
        self.data["endless_unlocked"] = True
        self.save()

    @property
    def last_name(self):
        return self.data["last_name"]
