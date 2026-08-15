"""LBPH impostor-distance FAR sweep, full LFW1, native predict_collect() scale.

Same computation as scripts/archive/run_lfw_lbph_native_predict_independence.py
(YuNet detection, same LBPHFaceRecognizer params, unidirectional unique
cross-identity pairs) but reports thresholds at MULTIPLE target FAR
checkpoints instead of a single rank, because the deployed tau_accept
(rank-165, ~10ppm) answers only "what's the tightest bar" and says nothing
about what looser, still-defensible FAR targets would buy back in TAR.

This script only computes the IMPOSTOR side (cross-identity distances). It
does not touch genuine pairs - see far_sweep_tar_report.py for combining
these thresholds with the genuine distances already logged in
outputs/benchmark/accuracy_ratio_verification_full_pairs.csv.

Usage::

    python scripts/far_sweep_impostor_thresholds.py
    python scripts/far_sweep_impostor_thresholds.py --max-identities 300  # smoke
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "pipeline"))

from run_lfw_independence import select_probes  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import IMG_SIZE, normalize_face  # noqa: E402
from src.hybrid.recognizer import detect_sample  # noqa: E402
from src.independence_common import (  # noqa: E402
    create_lbph_recognizer_for_config,
    lbph_config_metadata,
    lbph_native_scale,
    resolve_lbph_config,
)

DEFAULT_TARGET_FAR_PPM = [10.0, 100.0, 1000.0, 10000.0, 50000.0, 100000.0]


def preprocess_probe_yunet(path: str, detector, equalization: str) -> np.ndarray | None:
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
        default=str(PROJECT_ROOT / "reports" / "independence" / "lbph_lfw1" / "far_sweep.json"),
    )
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--max-identities", type=int, default=0)
    parser.add_argument(
        "--lbph-config",
        default=None,
        help="LBPH descriptor config ID/alias (default: active deployed config; "
             "e.g. r3_n8_g6x6 or selected).",
    )
    parser.add_argument(
        "--target-far-ppm",
        type=float,
        nargs="+",
        default=DEFAULT_TARGET_FAR_PPM,
        help="FAR checkpoints in ppm to sweep (default: 10, 100, 1000, 10000=1%%, "
             "50000=5%%, 100000=10%%).",
    )
    parser.add_argument("--progress-every", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    descriptor_config = resolve_lbph_config(args.lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)
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

    recognizer = create_lbph_recognizer_for_config(descriptor_config)
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

    for i in range(n):
        for j in range(n):
            if names[i] == names[j]:
                dist[i, j] = np.inf

    iu = np.triu_indices(n, k=1)
    raw_dists = dist[iu]
    valid_mask = np.isfinite(raw_dists)
    unique = np.sort(raw_dists[valid_mask])
    unique_pairs = int(unique.size)

    sweep = []
    for target_ppm in args.target_far_ppm:
        k = max(1, min(round(target_ppm / 1.0e6 * unique_pairs), unique_pairs))
        threshold = float(unique[k - 1])
        realized_ppm = 1.0e6 * k / unique_pairs
        sweep.append(
            {
                "target_far_ppm": target_ppm,
                "unique_rank": k,
                "raw_threshold": threshold,
                "realized_far_ppm": realized_ppm,
                "realized_far_percent": realized_ppm / 1.0e4,
            }
        )

    result = {
        "detector": "yunet",
        "dataset": {
            "path": str(dataset_dir),
            "total_identities": len(probes),
            "selected_identities": n,
            "skipped_by_detector": skipped,
        },
        "lbph_config": descriptor_metadata,
        "scale": lbph_native_scale(descriptor_config),
        "unique_pairs": unique_pairs,
        "sweep": sweep,
    }
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[SAVE] {args.output_json}")
    for row in sweep:
        print(
            f"[RESULT] target={row['target_far_ppm']:.0f}ppm rank={row['unique_rank']} "
            f"realized={row['realized_far_ppm']:.2f}ppm threshold={row['raw_threshold']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
