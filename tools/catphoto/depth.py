"""Estimates the depth of the cut-out cats (step 2 of 2, runs in tools/catphoto/.venv with onnxruntime):
Depth Anything V2 Small (Apache 2.0, ONNX). Writes the finished game assets:

    faicecommander/assets/cats/<name>.png        colour + alpha (head and chest, graded later in-game)
    faicecommander/assets/cats/<name>_depth.png  16-bit relative depth, 1 = nearest
    faicecommander/assets/cats/<name>.json       eye / nose positions in texture coordinates (0..1)

Setup: python -m venv tools/catphoto/.venv; tools/catphoto/.venv/Scripts/pip install onnxruntime numpy
opencv-python-headless. Run: tools/catphoto/.venv/Scripts/python tools/catphoto/depth.py
"""
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / "work"
OUT = ROOT / "faicecommander" / "assets" / "cats"

# eye and nose positions in the cut-out (work/<name>_rgba.png) pixels, read off the photos by hand
FACES = {
    "queen": {"eyes": [(517, 209), (616, 197)], "nose": (572, 272)},
    "raider": {"eyes": [(627, 356), (802, 356)], "nose": (714, 474)},
}


def depth_map(sess, bgr):
    h, w = bgr.shape[:2]
    size = 518  # the model's native input (multiple of 14)
    rgb = cv2.cvtColor(cv2.resize(bgr, (size, size), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
    x = (rgb.astype(np.float32) / 255 - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    d = sess.run(None, {sess.get_inputs()[0].name: x})[0].squeeze()
    return cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)  # relative inverse depth: bigger = nearer


def process(sess, name, face):
    rgba = cv2.imread(str(WORK / f"{name}_rgba.png"), cv2.IMREAD_UNCHANGED)
    bgr, alpha = rgba[..., :3], rgba[..., 3].astype(np.float32) / 255
    # the photo's background is white-ish: estimate depth on the cat in front of neutral grey
    comp = (bgr * alpha[..., None] + 128 * (1 - alpha[..., None])).astype(np.uint8)
    d = depth_map(sess, comp)
    (ex0, ey0), (ex1, ey1) = face["eyes"]
    ed = np.hypot(ex1 - ex0, ey1 - ey0)
    cx, cy = (ex0 + ex1) / 2, (ey0 + ey1) / 2
    # the window: head and chest around the eyes
    x0, x1 = int(max(0, cx - 2.1 * ed)), int(min(rgba.shape[1], cx + 2.1 * ed))
    y0, y1 = int(max(0, cy - 1.9 * ed)), int(min(rgba.shape[0], cy + 3.2 * ed))
    sub = (slice(y0, y1), slice(x0, x1))
    bgr, alpha, d = bgr[sub], alpha[sub], d[sub]
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # an elliptical vignette round the face and a fade into darkness below the chest
    ell = ((xx - (cx - x0)) / (1.75 * ed)) ** 2 + ((yy - (cy - y0 + 0.9 * ed)) / (2.6 * ed)) ** 2
    alpha *= np.clip((1.15 - ell) / 0.35, 0, 1)
    alpha *= np.clip((cy - y0 + 3.0 * ed - yy) / (1.3 * ed), 0, 1)
    # depth: normalise on the cat, smooth out the fur noise
    m = alpha > 0.5
    lo, hi = np.percentile(d[m], 2), np.percentile(d[m], 99.5)
    dn = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    # white sofa behind white fur: the matte cannot tell them apart, the depth can (it is further back)
    alpha *= np.clip((dn - 0.12) / 0.15, 0, 1)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 1.5)
    dn = cv2.bilateralFilter(dn.astype(np.float32), 9, 0.1, 6)
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / f"{name}.png"), np.dstack([bgr, (alpha * 255).astype(np.uint8)]))
    cv2.imwrite(str(OUT / f"{name}_depth.png"), (dn * 65535).astype(np.uint16))

    def uv(p):
        return [(p[0] - x0) / w, 1 - (p[1] - y0) / h]
    meta = {"eyes": [uv(p) for p in face["eyes"]], "nose": uv(face["nose"]), "aspect": w / h,
            "source": f"photos/Cat{name.capitalize()}.jpeg"}
    (OUT / f"{name}.json").write_text(json.dumps(meta, indent=2))
    print(name, "texture", (w, h), "eyes", meta["eyes"])


if __name__ == "__main__":
    sess = ort.InferenceSession(str(HERE / "models" / "depth_anything_v2_small.onnx"), providers=["CPUExecutionProvider"])
    for name, face in FACES.items():
        process(sess, name, face)
