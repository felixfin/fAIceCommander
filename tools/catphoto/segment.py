"""Cuts the cats out of the photos (step 1 of 2, runs in the game's .venv):
MediaPipe DeepLab v3 finds the "cat" class, OpenCV GrabCut refines the edge, a soft matte is feathered.

    photos/<Name>.jpeg -> tools/catphoto/work/<name>_rgba.png (cropped to the cat, straight alpha)

Run: .venv/Scripts/python tools/catphoto/segment.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / "work"
CAT_CLASS = 8  # Pascal VOC "cat"
PHOTOS = {"queen": "CatQueen.jpeg", "raider": "CatRaider.jpeg"}


def deeplab_mask(rgb):
    import mediapipe as mp
    v = mp.tasks.vision
    seg = v.ImageSegmenter.create_from_options(v.ImageSegmenterOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(HERE / "models" / "deeplab_v3.tflite")),
        output_category_mask=True))
    res = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    cat = res.category_mask.numpy_view()
    seg.close()
    return (cat == CAT_CLASS).astype(np.uint8)


def cut(name, path):
    bgr = cv2.imread(str(path))
    h, w = bgr.shape[:2]
    coarse = deeplab_mask(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    coarse = cv2.resize(coarse, (w, h), interpolation=cv2.INTER_NEAREST)
    # keep the biggest blob only (the cat)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(coarse)
    if n > 1:
        coarse = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    # GrabCut seeded by the coarse mask: sure inside, probable band, sure outside
    gc = np.full((h, w), cv2.GC_BGD, np.uint8)
    grow = cv2.dilate(coarse, np.ones((61, 61), np.uint8))
    shrink = cv2.erode(coarse, np.ones((41, 41), np.uint8))
    gc[grow > 0] = cv2.GC_PR_BGD
    gc[coarse > 0] = cv2.GC_PR_FGD
    gc[shrink > 0] = cv2.GC_FGD
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, gc, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
    mask = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n > 1:
        mask = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    alpha = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 2.5)  # soft, fur-like edge
    ys, xs = np.where(mask > 0)
    pad = 40
    x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + pad)
    rgba = np.dstack([bgr, (alpha * 255).astype(np.uint8)])[y0:y1, x0:x1]
    WORK.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(WORK / f"{name}_rgba.png"), rgba)
    (WORK / f"{name}_crop.txt").write_text(f"{x0} {y0} {x1} {y1}\n")
    print(name, "cut out", rgba.shape, "crop", (x0, y0, x1, y1), "cat pixels", int(mask.sum()))


if __name__ == "__main__":
    for name, file in PHOTOS.items():
        if len(sys.argv) > 1 and name not in sys.argv[1:]:
            continue
        cut(name, ROOT / "photos" / file)
