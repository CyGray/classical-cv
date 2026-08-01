"""What FAR do the *deployed* thresholds realize on the deployment-faithful
(YuNet-cropped) LBPH distance distribution?

Same probe pipeline as scripts/archive/run_lfw_lbph_native_predict_independence.py
(YuNet, assume_cropped=False, native predict_collect). Instead of "rank -> value",
this answers "value -> rank/FAR" for the values currently in thresholds.json,
and dumps a percentile grid so the tail can be read without another 28-min run.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2 as cv
import numpy as np

ROOT = Path(r"C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\classical-cv")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "pipeline"))

from run_lfw_independence import select_probes  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import IMG_SIZE, normalize_face  # noqa: E402
from src.hybrid.recognizer import detect_sample  # noqa: E402

OUT = Path(sys.argv[1])
QUERY_VALUES = [float(v) for v in sys.argv[2:]] or [77.7693, 88.4927, 67.0084, 76.85]


def main() -> int:
    detector = create_face_detector("yunet")
    equalization = SPECS["lbph"].default_equalization
    probes = select_probes(ROOT / "data" / "lfw-dataset", 0, 42)

    tiles, names = [], []
    for person, path, _ in probes:
        img = cv.imread(path)
        if img is None:
            continue
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        s = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=False)
        if s is None:
            continue
        tiles.append(normalize_face(s.face_gray, img_size=IMG_SIZE, equalization=equalization))
        names.append(person)

    n = len(names)
    print(f"[INFO] {n}/{len(probes)} probes kept", flush=True)

    rec = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    rec.train(tiles, np.arange(n, dtype=np.int32))

    dist = np.full((n, n), np.inf, dtype=np.float64)
    t0 = time.time()
    for i in range(n):
        col = cv.face.StandardCollector_create()
        rec.predict_collect(tiles[i], col)
        for label, d in col.getResults(True):
            label = int(label)
            if float(d) < dist[i, label]:
                dist[i, label] = float(d)
        if (i + 1) % 500 == 0:
            print(f"  [row] {i+1}/{n} {(time.time()-t0)/60:.1f}m", flush=True)

    names_arr = np.asarray(names)
    same = names_arr[:, None] == names_arr[None, :]
    dist[same] = np.inf

    iu = np.triu_indices(n, k=1)
    vals = dist[iu]
    vals = np.sort(vals[np.isfinite(vals)])
    total = int(vals.size)

    result = {
        "identities": n,
        "unique_pairs": total,
        "scale": "native predict_collect, YuNet, assume_cropped=False",
        "deployed_threshold_far": [],
        "percentiles": [],
    }
    for v in QUERY_VALUES:
        rank = int(np.searchsorted(vals, v, side="right"))
        result["deployed_threshold_far"].append({
            "threshold": v,
            "pairs_at_or_below": rank,
            "realized_far_ppm": 1.0e6 * rank / total,
            "realized_far_pct": 100.0 * rank / total,
        })
    for p in [0.001, 0.01, 0.1, 0.5, 1, 2, 5, 10, 25, 50]:
        idx = max(0, min(total - 1, int(round(p / 100.0 * total)) - 1))
        result["percentiles"].append({"far_pct": p, "threshold": float(vals[idx])})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[SAVE] {OUT}")
    for r in result["deployed_threshold_far"]:
        print(f"  {r['threshold']:.4f} -> {r['realized_far_pct']:.4f}% "
              f"({r['realized_far_ppm']:.2f} ppm, {r['pairs_at_or_below']:,} pairs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
