"""LBPH-only full-LFW independence test through the shared multi-core streaming
pipeline (parallel sweep + distance_histogram/KDE/FAR plots).

``run_lfw_independence.py`` loads LFW probes correctly (raw per-identity images,
Haar-cropped) but does its own single-threaded top-K sweep with no plots.
``src/lbph/independence_test.py`` has the parallel streaming + plotting pipeline
but hardcodes the La Salle DB1 ``light_front.jpg`` probe contract. This wires the
former's probe loader into the latter's streaming pipeline (``src.independence_report
.run_streaming_and_save``) so a full-LFW LBPH run gets both.

Usage::

    python scripts/archive/run_lfw_lbph_streaming_independence.py --error-pair-rank 330
"""

import argparse
import sys
from pathlib import Path

import cv2 as cv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_lfw_independence import select_probes, preprocess_probe  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.variants import lbph_histograms_from_tiles  # noqa: E402
from src.independence_report import add_scaling_args, run_streaming_and_save  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default=str(PROJECT_ROOT / "data" / "lfw-dataset"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "outputs" / "independence" / "lbph_lfw1"))
    parser.add_argument("--cascade-path",
                        default=str(PROJECT_ROOT / "haar" / "haarcascade_frontalface_default.xml"))
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--min-face-size", type=int, default=40)
    parser.add_argument("--target-far-ppm", type=float, default=10.0)
    parser.add_argument("--error-pair-rank", type=int, default=None)
    add_scaling_args(parser)
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
    skipped = 0
    for person, path, _extras in probes:
        tile = preprocess_probe(path, face_cascade, args.min_face_size, equalization)
        if tile is None:
            skipped += 1
            continue
        tiles.append(tile)
        names.append(person)
    print(f"[INFO] {len(names)}/{len(probes)} probes kept ({skipped} skipped, no face/unreadable)")

    features = lbph_histograms_from_tiles(tiles, 250)
    pre_stats = {
        "processed": len(probes), "successful": len(names),
        "skipped_unreadable": 0, "skipped_no_face": skipped, "skipped_too_small": 0,
    }
    return run_streaming_and_save(
        args, names=names, feature_matrix=features, metric="chi2",
        model_label="LBPH", distance_label="chi-square (LBPH histograms)",
        person_dirs=probes, pre_stats=pre_stats, model_key="lbph",
    )


if __name__ == "__main__":
    raise SystemExit(main())
