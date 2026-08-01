"""LBPH independence threshold on the native OpenCV predict() scale, full LFW1,
unidirectional unique pairs.

``src/independence_common.py``'s hand-rolled chi-square (used by
``run_lfw_lbph_streaming_independence.py``) is a **different, non-comparable
scale** from what the deployed recognizer actually computes — see
``docs/READ THIS/FROZEN_THRESHOLDS.md`` ("Matches the canonical 70.6089 LBPH
figure ... native cv.face.LBPHFaceRecognizer::predict_collect() scale - not
the independence_common.py chi-square reimplementation, which is a different,
non-comparable scale"). This script trains a real
``cv.face.LBPHFaceRecognizer`` (same params as ``src/hybrid/independence_test.py``:
radius=1, neighbors=8, grid=8x8) over all LFW1 probes and reads
``predict_collect()`` distances, i.e. the same scale as the deployed
``tau_accept``.

Unidirectional here means the *reported* statistic is the upper-triangle
(i<j) unique cross-identity distances only — matching
``docs/features/SYSTEMATIC_INDEPENDENCE_TEST.md`` §2.1's point that this does
not halve the compute (every query row still costs a full predict_collect
against all N classes), only the reported/kept pair count.

Usage::

    python scripts/archive/run_lfw_lbph_native_predict_independence.py --unique-rank 165
    python scripts/archive/run_lfw_lbph_native_predict_independence.py --max-identities 300  # smoke
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_lfw_independence import select_probes, preprocess_probe  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default=str(PROJECT_ROOT / "data" / "lfw-dataset"))
    parser.add_argument("--cascade-path",
                        default=str(PROJECT_ROOT / "haar" / "haarcascade_frontalface_default.xml"))
    parser.add_argument("--output-json",
                        default=str(PROJECT_ROOT / "outputs" / "independence" / "lbph_lfw1" /
                                    "native_predict_scale.json"))
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--min-face-size", type=int, default=40)
    parser.add_argument("--max-identities", type=int, default=0)
    parser.add_argument("--unique-rank", type=int, default=165,
                        help="1-indexed rank into the sorted unique (i<j) cross-identity "
                             "distances, ascending (165 -> ~10ppm at full LFW1 scale).")
    parser.add_argument("--progress-every", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    face_cascade = cv.CascadeClassifier(args.cascade_path)
    if face_cascade.empty():
        raise FileNotFoundError(f"Could not load cascade: {args.cascade_path}")

    dataset_dir = Path(args.dataset_dir)
    probes = select_probes(dataset_dir, args.max_identities, args.random_seed)
    equalization = SPECS["lbph"].default_equalization

    tiles, names = [], []
    for person, path, _extras in probes:
        tile = preprocess_probe(path, face_cascade, args.min_face_size, equalization)
        if tile is None:
            continue
        tiles.append(tile)
        names.append(person)
    n = len(names)
    print(f"[INFO] {n}/{len(probes)} probes kept (equalization={equalization})", flush=True)
    if n < 2:
        print("[ERROR] Not enough usable probes.")
        return 1

    recognizer = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(tiles, np.arange(n, dtype=np.int32))

    dist = np.full((n, n), np.inf, dtype=np.float64)
    t0 = time.time()
    for i in range(n):
        collector = cv.face.StandardCollector_create()
        recognizer.predict_collect(tiles[i], collector)
        for label, d in collector.getResults(True):
            label = int(label)
            d = float(d)
            if d < dist[i, label]:
                dist[i, label] = d
        if (i + 1) % args.progress_every == 0 or i == n - 1:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (n - i - 1)
            print(f"  [row] {i + 1}/{n} elapsed {elapsed / 60:.1f}m eta {eta / 60:.1f}m", flush=True)

    iu = np.triu_indices(n, k=1)
    unique = np.sort(dist[iu])
    unique_pairs = int(unique.size)

    k = max(1, min(args.unique_rank, unique_pairs))
    idx = k - 1
    threshold = float(unique[idx])
    far_ppm = 1.0e6 * k / unique_pairs
    pair_i, pair_j = int(iu[0][np.argsort(dist[iu])[idx]]), int(iu[1][np.argsort(dist[iu])[idx]])

    result = {
        "dataset": {"path": str(dataset_dir), "total_identities": len(probes), "selected_identities": n},
        "scale": "native cv.face.LBPHFaceRecognizer.predict_collect() (radius=1, neighbors=8, grid=8x8)",
        "unique_pairs": unique_pairs,
        "unique_rank": k,
        "raw_threshold": threshold,
        "realized_far_ppm": far_ppm,
        "boundary_pair": {"query_identity": names[pair_i], "candidate_identity": names[pair_j]},
        "curve": [
            {"unique_rank": r, "raw_threshold": float(unique[r - 1]),
             "realized_far_ppm": 1.0e6 * r / unique_pairs}
            for r in (1, 2, 4, 8, 16, 32, 64, 128, 165, 256, 512, 1024)
            if r <= unique_pairs
        ],
    }
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[SAVE] {args.output_json}")
    print(f"[RESULT] rank={k} unique_pairs={unique_pairs:,} FAR={far_ppm:.2f}ppm "
          f"raw_threshold={threshold:.4f} ({names[pair_i]} vs {names[pair_j]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
