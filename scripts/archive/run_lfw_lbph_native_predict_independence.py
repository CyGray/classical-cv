"""LBPH independence threshold on the native OpenCV predict() scale, full LFW1,
unidirectional unique pairs — YuNet detector.

Replaces the original Haar-based version (2026-07-28). Detection now uses
YuNet (``create_face_detector("yunet")``), the same detector the deployed
hybrid pipeline actually uses end-to-end. Haar was skipping 46/5,749 LFW1
identities and producing different Tan-Triggs-normalized tiles, making the
resulting threshold incomparable to what the production recognizer sees.

``src/independence_common.py``'s hand-rolled chi-square (used by
``run_lfw_lbph_streaming_independence.py``) is a **different, non-comparable
scale** from what the deployed recognizer actually computes. This script trains
a real ``cv.face.LBPHFaceRecognizer`` (same params as
``src/hybrid/independence_test.py``: radius=1, neighbors=8, grid=8x8) over all
LFW1 probes and reads ``predict_collect()`` distances, i.e. the same scale as
the deployed ``tau_accept``.

Unidirectional here means the *reported* statistic is the upper-triangle (i<j)
unique cross-identity distances only — matching
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
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "pipeline"))

from run_lfw_independence import select_probes  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import IMG_SIZE, normalize_face  # noqa: E402
from src.hybrid.recognizer import detect_sample  # noqa: E402


def preprocess_probe_yunet(
    path: str,
    detector,
    equalization: str,
) -> np.ndarray | None:
    """Detect face with YuNet and return the Tan-Triggs-normalized LBPH tile.

    Mirrors exactly what LBPHAdapter._normalize(sample) does at runtime:
      1. YuNet detects the largest face box.
      2. face_gray = gray ROI of that box.
      3. normalize_face(face_gray, IMG_SIZE, equalization).

    Returns None if YuNet finds no face.
    """
    img = cv.imread(path)
    if img is None:
        return None
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    sample = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=False)
    if sample is None:
        return None
    return normalize_face(sample.face_gray, img_size=IMG_SIZE, equalization=equalization)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default=str(PROJECT_ROOT / "data" / "lfw-dataset"))
    parser.add_argument(
        "--output-json",
        default=str(
            PROJECT_ROOT / "reports" / "independence" / "lbph_lfw1" / "native_predict_scale_yunet.json"
        ),
    )
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--max-identities", type=int, default=0)
    parser.add_argument(
        "--unique-rank",
        type=int,
        default=165,
        help="1-indexed rank into the sorted unique (i<j) cross-identity "
             "distances, ascending (165 -> ~10ppm at full LFW1 scale).",
    )
    parser.add_argument("--progress-every", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    detector = create_face_detector("yunet")
    equalization = SPECS["lbph"].default_equalization

    dataset_dir = Path(args.dataset_dir)
    probes = select_probes(dataset_dir, args.max_identities, args.random_seed)

    tiles, names = [], []
    skipped = 0
    for person, path, _extras in probes:
        tile = preprocess_probe_yunet(path, detector, equalization)
        if tile is None:
            skipped += 1
            continue
        tiles.append(tile)
        names.append(person)

    n = len(names)
    print(
        f"[INFO] {n}/{len(probes)} probes kept, {skipped} skipped by YuNet "
        f"(equalization={equalization})",
        flush=True,
    )
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
            print(
                f"  [row] {i + 1}/{n} elapsed {elapsed / 60:.1f}m eta {eta / 60:.1f}m",
                flush=True,
            )

    # Filter to cross-identity pairs only (same-identity distances are irrelevant).
    for i in range(n):
        for j in range(n):
            if names[i] == names[j]:
                dist[i, j] = np.inf

    iu = np.triu_indices(n, k=1)
    raw_dists = dist[iu]
    # Exclude inf (same identity or detection failure diagonals).
    valid_mask = np.isfinite(raw_dists)
    unique = np.sort(raw_dists[valid_mask])
    unique_pairs = int(unique.size)

    k = max(1, min(args.unique_rank, unique_pairs))
    idx = k - 1
    threshold = float(unique[idx])
    far_ppm = 1.0e6 * k / unique_pairs

    # Recover boundary pair indices for provenance.
    argsorted = np.argsort(raw_dists)
    # Find the idx-th finite entry in argsorted.
    finite_count = 0
    boundary_flat = None
    for ai in argsorted:
        if np.isfinite(raw_dists[ai]):
            if finite_count == idx:
                boundary_flat = ai
                break
            finite_count += 1
    if boundary_flat is not None:
        pair_i = int(iu[0][boundary_flat])
        pair_j = int(iu[1][boundary_flat])
        boundary = {"query_identity": names[pair_i], "candidate_identity": names[pair_j]}
    else:
        boundary = {}

    result = {
        "detector": "yunet",
        "dataset": {
            "path": str(dataset_dir),
            "total_identities": len(probes),
            "selected_identities": n,
            "skipped_by_detector": skipped,
        },
        "scale": "native cv.face.LBPHFaceRecognizer.predict_collect() (radius=1, neighbors=8, grid=8x8)",
        "unique_pairs": unique_pairs,
        "unique_rank": k,
        "raw_threshold": threshold,
        "realized_far_ppm": far_ppm,
        "boundary_pair": boundary,
        "curve": [
            {
                "unique_rank": r,
                "raw_threshold": float(unique[r - 1]),
                "realized_far_ppm": 1.0e6 * r / unique_pairs,
            }
            for r in (1, 2, 4, 8, 16, 32, 64, 128, 165, 256, 512, 1024)
            if r <= unique_pairs
        ],
    }
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[SAVE] {args.output_json}")
    print(
        f"[RESULT] rank={k} unique_pairs={unique_pairs:,} FAR={far_ppm:.2f}ppm "
        f"raw_threshold={threshold:.4f} ({boundary.get('query_identity', '?')} vs "
        f"{boundary.get('candidate_identity', '?')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
