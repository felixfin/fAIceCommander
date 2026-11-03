"""The trailer's edit decision list: 90 s at 24 fps. Shared by the renderers, the score and the
compositor, so cuts, hits and sound effects line up.

Clip sources:
    ("intro", t)            intro at cutscene time t (see faicecommander/cutscenes/timeline.py)
    ("outro", t)            outro
    ("game", segment, t)    a recorded gameplay segment (recordings/<take>/<segment>) at replay time t
    ("finale", t)           the boss segment replayed with the killing nuke injected (FINALE)
    ("card", text, style)   a title card
    ("black",)
Each clip: (start in the trailer, duration, source, options). Options: speed (< 1 = slow motion),
push (slow zoom-in amount), flash (white flash at the cut), pillar (black bars beside a 4:3 webcam shot).
"""
FPS = 24
LENGTH = 90.0
TAKE = "trailer_take1"
BOSS = "06_level7_try1"
FINALE = {"segment": BOSS, "at": 24.0}  # the nuke that ends her is fired at this replay time

S = {"debris1": "01_level2_try1", "debris2": "01_level2_try2", "hypno": "02_level3_try1",
     "void": "03_level4_try1", "patrol": "04_level5_try1", "holes": "05_level6_try2", "boss": BOSS}

CLIPS = [
    # --- prologue: something in the dark
    (0.0, 3.0, ("black",), {}),
    (3.0, 2.5, ("intro", 3.0), {"push": 0.05}),
    (5.5, 2.0, ("card", "THEY CAME FROM THE DARK", "story"), {}),
    (7.5, 0.5, ("black",), {}),
    # --- worlds burn: fast cuts, flashes
    (8.0, 1.4, ("intro", 9.0), {"flash": True}),
    (9.4, 1.2, ("intro", 13.6), {"flash": True, "push": 0.06}),
    (10.6, 1.0, ("intro", 46.0), {"flash": True}),
    (11.6, 1.2, ("intro", 16.5), {"push": 0.05}),
    (12.8, 0.3, ("black",), {}),
    (13.1, 1.6, ("intro", 32.0), {"push": 0.04}),
    (14.7, 1.1, ("intro", 50.5), {"flash": True}),
    (15.8, 1.0, ("intro", 57.0), {}),
    # --- the slaves
    (16.8, 2.2, ("intro", 20.0), {"push": 0.05}),
    (19.0, 1.8, ("card", "THEY TOOK OUR WORLDS", "story"), {}),
    (20.8, 1.6, ("intro", 24.0), {"flash": True}),
    (22.4, 1.4, ("intro", 27.0), {"push": 0.05}),
    (23.8, 1.8, ("card", "THEY TOOK OUR NAMES", "story"), {}),
    (25.6, 1.6, ("intro", 63.0), {"push": 0.04}),
    (27.2, 0.8, ("black",), {}),
    # --- the Mother
    (28.0, 2.5, ("intro", 34.0), {"push": 0.05}),
    (30.5, 0.6, ("black",), {}),
    (31.1, 2.4, ("intro", 39.75), {"push": 0.08}),
    (33.5, 1.3, ("intro", 51.0), {"flash": True, "speed": 0.5}),
    (34.8, 1.2, ("intro", 53.0), {"speed": 0.5}),
    # --- one survived
    (36.0, 2.0, ("card", "ONE COMMANDER SURVIVED", "story"), {}),
    (38.0, 1.2, ("intro", 58.0), {}),
    (39.2, 1.4, ("intro", 65.0), {"push": 0.04}),
    (40.6, 2.0, ("intro", 76.3), {"flash": True}),
    (42.6, 1.6, ("intro", 83.5), {}),
    (44.2, 0.3, ("black",), {}),
    (44.5, 3.5, ("intro", 92.0), {"push": 0.04, "pillar": True}),
    # --- tension: micro cuts of gameplay over a riser
    (48.0, 0.6, ("game", "debris2", 38.6), {"flash": True}),
    (48.6, 0.6, ("game", "patrol", 4.0), {"flash": True}),
    (49.2, 0.6, ("game", "void", 11.3), {"flash": True}),
    (49.8, 0.6, ("game", "boss", 15.8), {"flash": True}),
    (50.4, 1.6, ("black",), {}),
    # --- the drop
    (52.0, 1.4, ("card", "STEER WITH YOUR HEAD", "feature"), {}),
    (53.4, 2.8, ("game", "debris1", 35.4), {}),
    (56.2, 2.8, ("game", "patrol", 3.6), {"flash": True}),
    (59.0, 1.4, ("card", "FIRE WITH YOUR MOUTH", "feature"), {}),
    (60.4, 2.0, ("game", "void", 19.4), {}),
    (62.4, 1.6, ("game", "void", 33.5), {"flash": True}),
    (64.0, 1.9, ("game", "patrol", 28.0), {"flash": True}),
    (65.9, 1.4, ("card", "CLOSE YOUR EYES - OR DIE", "feature"), {}),
    (67.3, 2.0, ("game", "hypno", 8.6), {}),
    (69.3, 1.6, ("game", "holes", 40.0), {"flash": True}),
    (70.9, 1.6, ("game", "boss", 19.0), {"flash": True}),
    (72.5, 1.4, ("game", "boss", 27.0), {}),
    (73.9, 1.1, ("game", "boss", 16.0), {"flash": True}),
    # --- finale
    (75.0, 3.6, ("finale", 22.8), {}),
    (78.6, 2.2, ("outro", 3.0), {"push": 0.05}),
    (80.8, 1.0, ("outro", 6.0), {"flash": True}),
    (81.8, 1.2, ("black",), {}),
    # --- title
    (83.0, 4.5, ("card", "fAIceCommander 3D", "title"), {}),
    (87.5, 2.5, ("card", "YOUR FACE IS THE WEAPON", "tagline"), {}),
]

VOICE = [(0.8, "trailer_01"), (19.1, "trailer_02"), (23.9, "trailer_03"), (36.2, "trailer_04"),
         (46.0, "trailer_05"), (84.6, "trailer_06")]


def source_ranges(kind, segment=None, pad=0.3):
    """Time ranges (in source time) a renderer has to produce for the given source."""
    out = []
    for _, dur, src, opt in CLIPS:
        if src[0] != kind or (segment is not None and S.get(src[1], src[1]) != segment):
            continue
        t0 = src[-1]
        out.append((max(0.0, t0 - pad), t0 + dur * opt.get("speed", 1.0) + pad))
    return out
