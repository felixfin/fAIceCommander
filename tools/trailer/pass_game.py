"""One gameplay render pass: pass_game.py <segment folder> <out dir> <prefix> <t0:t1,...> [finale_at]"""
import sys

from replay import render_game

if __name__ == "__main__":
    folder, out, prefix, ranges = sys.argv[1:5]
    finale = float(sys.argv[5]) if len(sys.argv) > 5 else None
    rs = [tuple(map(float, r.split(":"))) for r in ranges.split(",")]
    print(prefix, "saved", render_game(folder, rs, out, prefix, finale_at=finale), "frames", flush=True)
