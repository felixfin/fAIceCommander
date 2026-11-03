"""Renders every source the trailer's EDL needs into build/trailer/frames (skips passes already done).
Each pass runs in its own process (one Panda3D window per process).

Run: .venv/Scripts/python tools/trailer/render_all.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import edl  # noqa: E402

FRAMES = ROOT / "build" / "trailer" / "frames"
REC = ROOT / "recordings" / edl.TAKE
FACE = REC / edl.S["debris2"]   # the face in the webcam close-ups of the cutscenes


def passes():
    out = []
    for seq in ("intro", "outro"):
        out.append((seq, ["cinematics.py", seq, str(FRAMES), str(FACE),
                          ",".join(f"{a:.2f}:{b:.2f}" for a, b in edl.source_ranges(seq))]))
    for name, seg in edl.S.items():
        ranges = edl.source_ranges("game", seg)
        if ranges:
            out.append((name, ["pass_game.py", str(REC / seg), str(FRAMES), name,
                               ",".join(f"{a:.2f}:{b:.2f}" for a, b in ranges)]))
    out.append(("finale", ["pass_game.py", str(REC / edl.FINALE["segment"]), str(FRAMES), "finale",
                           ",".join(f"{a:.2f}:{b:.2f}" for a, b in edl.source_ranges("finale")),
                           str(edl.FINALE["at"])]))
    return out


if __name__ == "__main__":
    only = set(sys.argv[1:])
    FRAMES.mkdir(parents=True, exist_ok=True)
    for name, cmd in passes():
        if (only and name not in only) or (not only and (FRAMES / f"{name}_sfx.json").exists()):
            continue
        print("rendering", name, flush=True)
        subprocess.run([sys.executable, str(HERE / cmd[0]), *cmd[1:]], cwd=ROOT, check=True)
    print("all passes done", flush=True)
