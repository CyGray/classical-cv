"""
LBPH Independence Test using only light_front.jpg for each identity.

Purpose:
- Compare every identity against every other identity.
- Since all comparisons are different-person comparisons, any pair accepted
  under a threshold is considered a false positive.
- False Positive Rate (FPR) is computed as:

    FPR = false positives / total inter-identity comparisons

Notes:
- Lower LBPH distance means higher similarity.
- A threshold is required to compute a concrete FPR.
- If no threshold is provided, the script still produces a threshold sweep
  using percentile-based candidate thresholds.
- The script saves both a histogram and a smooth curve plot.
"""

import argparse
import csv
import concurrent.futures
import heapq
import json
import os
import random
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

import cv2 as cv
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]

try:
    from src.independence_common import (
        train_and_extract_features,
        aggregate_pairwise_results,
    )
    from src.lbph.preprocess import IMG_SIZE, extract_lbph_face, resolve_eye_cascade_path
except ModuleNotFoundError:
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.independence_common import (
        train_and_extract_features,
        aggregate_pairwise_results,
    )
    from src.lbph.preprocess import IMG_SIZE, extract_lbph_face, resolve_eye_cascade_path


ASSUME_INPUTS_ARE_CROPPED = True
DEFAULT_IMAGE_NAME = "light_front.jpg"
DEFAULT_OUTPUT_DIR = str(PROJECT_ROOT.joinpath("outputs", "lbph", "independence_test_light_front"))
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
_PAIRWISE_FEATURE_PATH = ""
_PAIRWISE_METRIC = "lbph"
_PAIRWISE_FEATURES: np.ndarray | None = None


def _init_pairwise_worker(feature_path: str, metric: str) -> None:
    global _PAIRWISE_FEATURE_PATH, _PAIRWISE_METRIC, _PAIRWISE_FEATURES
    _PAIRWISE_FEATURE_PATH = feature_path
    _PAIRWISE_METRIC = metric
    _PAIRWISE_FEATURES = np.load(_PAIRWISE_FEATURE_PATH, mmap_mode="r")


def _pairwise_chunk_worker(args: tuple[int, int, int, int, int]) -> dict:
    """
    Compute pairwise distances for row range [start, end) against all N rows.
    Returns chunk metadata and in-memory raw-distance array.
    """
    chunk_idx, start, end, top_k, lbph_block_rows = args
    features = _PAIRWISE_FEATURES
    if features is None:
        raise RuntimeError("Pairwise worker not initialized.")

    n = int(features.shape[0])
    count = sum((n - i - 1) for i in range(start, end))
    eps = 1e-10
    # Block processing avoids allocating a full (N x D) float64 temp matrix.
    out = np.empty(count, dtype=np.float32)

    idx = 0
    local_heap: list[tuple[float, int, int]] = []
    for i in range(start, end):
        fi = features[i]
        if _PAIRWISE_METRIC == "lbph":
            row_dist = np.empty(n, dtype=np.float64)
            for b0 in range(0, n, lbph_block_rows):
                b1 = min(n, b0 + lbph_block_rows)
                blk = features[b0:b1]
                diff_blk = blk - fi
                denom_blk = blk + fi + eps
                row_dist[b0:b1] = 0.5 * np.sum((diff_blk * diff_blk) / denom_blk, axis=1)
        else:
            row_dist = np.linalg.norm(features - fi, axis=1)
        for j in range(i + 1, n):
            d = float(row_dist[j])
            out[idx] = d
            if len(local_heap) < top_k:
                heapq.heappush(local_heap, (-d, i, j))
            elif d < -local_heap[0][0]:
                heapq.heapreplace(local_heap, (-d, i, j))
            idx += 1

    return {
        "chunk_idx": chunk_idx,
        "start": start,
        "end": end,
        "count": count,
        "raw": out,
        "top_heap": local_heap,
    }


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str(PROJECT_ROOT.joinpath(candidate))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LBPH Independence Test using only light_front.jpg."
    )

    parser.add_argument(
        "--dataset-source",
        choices=["lasalle_db1_processed", "lfw-dataset"],
        default="lasalle_db1_processed",
        help="Dataset preset (default: lasalle_db1_processed).",
    )
    parser.add_argument(
        "--dataset-dir",
        default="",
        help="Dataset root containing person folders.",
    )
    parser.add_argument(
        "--image-name",
        default=DEFAULT_IMAGE_NAME,
        help="Exact filename to use per person.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save results.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional LBPH distance threshold on the normalized 0-100 scale.",
    )
    parser.add_argument(
        "--min-face-size",
        type=int,
        default=40,
        help="Minimum detected face width/height.",
    )
    parser.add_argument(
        "--cascade-path",
        default=root_path("haar", "haarcascade_frontalface_default.xml"),
        help="Path to Haar cascade XML.",
    )
    parser.add_argument(
        "--eye-cascade-path",
        default="",
        help="Optional path to Haar eye cascade XML.",
    )
    parser.add_argument(
        "--align-eyes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable classical eye-based alignment.",
    )
    parser.add_argument(
        "--equalization",
        choices=["equalize", "clahe"],
        default="equalize",
        help="Face contrast normalization.",
    )
    parser.add_argument(
        "--downscale-max-side",
        type=int,
        default=0,
        help="Downscale for detection if >0.",
    )
    parser.add_argument(
        "--histogram-bins",
        type=int,
        default=20,
        help="Number of bins used for the histogram.",
    )
    parser.add_argument(
        "--curve-points",
        type=int,
        default=500,
        help="Number of points used to draw the smooth distance curve.",
    )
    parser.add_argument(
        "--curve-bandwidth",
        type=float,
        default=None,
        help=(
            "Optional KDE bandwidth. If omitted, Silverman's rule is used. "
            "Increase for smoother curve, decrease for more detail."
        ),
    )
    parser.add_argument(
        "--max-identities",
        type=int,
        default=0,
        help="Cap number of identities (0 = no cap).",
    )
    parser.add_argument(
        "--lfw-default-max-identities",
        type=int,
        default=0,
        help="Auto-cap for LFW when --max-identities=0 (0 disables auto-cap).",
    )
    parser.add_argument(
        "--max-comparisons",
        type=int,
        default=0,
        help="Safety cap for N*(N-1) comparisons. Set 0 to disable.",
    )
    parser.add_argument(
        "--streaming-threshold",
        type=int,
        default=3_000_000,
        help="Use memory-safe streaming mode when expected comparisons exceed this.",
    )
    parser.add_argument(
        "--segment-count",
        type=int,
        default=1,
        help="Split query identities into this many segments (default: 1).",
    )
    parser.add_argument(
        "--segment-index",
        type=int,
        default=1,
        help="1-based segment index to run (default: 1).",
    )
    parser.add_argument(
        "--write-comparisons-csv",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write full comparisons.csv in streaming mode (very slow for huge runs).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Pairwise comparison worker processes (default: 4).",
    )
    parser.add_argument(
        "--chunk-rows",
        type=int,
        default=64,
        help="Rows per work chunk in streaming mode (default: 64).",
    )
    parser.add_argument(
        "--max-inflight",
        type=int,
        default=32,
        help="Max queued+running chunks in streaming mode (default: 32).",
    )
    parser.add_argument(
        "--lbph-block-rows",
        type=int,
        default=256,
        help="LBPH worker inner block size (default: 256).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of iterations to run for aggregation.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for image selection.",
    )

    return parser.parse_args()


def resolve_dataset_choice(args: argparse.Namespace) -> None:
    if args.dataset_dir:
        return

    # If dataset_source is already provided via CLI (e.g. from main.py),
    # skip the prompt and just resolve the directory.
    cli_args = [arg.split("=")[0] for arg in sys.argv[1:]]
    if "--dataset-source" in cli_args and args.dataset_source:
        choice = "" # Skip prompt
    else:
        print("\nChoose dataset source:")
        print("  1. la salle processed (default)")
        print("  2. lfw-dataset")
        try:
            choice = input("Enter choice [1/2] (default: 1): ").strip()
        except EOFError:
            choice = ""

    if choice == "2":
        args.dataset_source = "lfw-dataset"

    if args.dataset_source == "lfw-dataset":
        args.dataset_dir = root_path("data", "lfw-dataset")
        # LFW usually does not use light_front.jpg; use random valid image per identity.
        if args.image_name == DEFAULT_IMAGE_NAME:
            args.image_name = "__random__"
    else:
        args.dataset_dir = root_path("data", "lasalle_db1_processed")


def resolve_default_output_dir(args: argparse.Namespace) -> None:
    """
    Keep user-provided --output-dir untouched.
    If default output dir is used, place artifacts in dataset-specific subfolders
    with a timestamp to avoid overwriting previous runs.
    """
    if args.output_dir != DEFAULT_OUTPUT_DIR:
        return

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.dataset_source == "lfw-dataset":
        if args.segment_count > 1:
            suffix = f"lfw_seg{args.segment_index}of{args.segment_count}_{timestamp}"
        else:
            suffix = f"lfw_{timestamp}"
    else:
        suffix = f"lasalle_db1_processed_{timestamp}"

    args.output_dir = root_path("outputs", "lbph", "independence_test_light_front", suffix)


def get_person_dirs(dataset_root: str) -> List[Tuple[str, str]]:
    if not os.path.isdir(dataset_root):
        return []

    out: List[Tuple[str, str]] = []
    for person in sorted(os.listdir(dataset_root)):
        person_path = os.path.join(dataset_root, person)
        if os.path.isdir(person_path):
            out.append((person, person_path))

    return out


def select_light_front_images(
    person_dirs: List[Tuple[str, str]],
    image_name: str,
    random_seed: int = 42,
) -> Dict[str, str]:
    selected: Dict[str, str] = {}
    import random
    rng = random.Random(random_seed)

    for person, person_path in person_dirs:
        if image_name in ["__first__", "__random__"]:
            image_files = [
                f
                for f in sorted(os.listdir(person_path))
                if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
            ]
            if image_files:
                if image_name == "__random__":
                    selected[person] = os.path.join(person_path, rng.choice(image_files))
                else:
                    selected[person] = os.path.join(person_path, image_files[0])
            continue

        image_path = os.path.join(person_path, image_name)
        if os.path.isfile(image_path):
            selected[person] = image_path

    return selected


@dataclass
class PreprocessStats:
    processed: int = 0
    successful: int = 0
    skipped_unreadable: int = 0
    skipped_no_face: int = 0
    skipped_too_small: int = 0


@dataclass
class ComparisonRecord:
    query_identity: str
    query_image_path: str
    candidate_identity: str
    candidate_image_path: str
    distance: float
    raw_distance: float = 0.0

    def is_false_positive(self, threshold: float) -> bool:
        return self.distance <= threshold


@dataclass
class DistanceStats:
    min_distance: float = float("inf")
    max_distance: float = float("-inf")
    mean_distance: float = 0.0
    median_distance: float = 0.0
    std_dev: float = 0.0
    percentiles: Dict[float, float] = field(default_factory=dict)
    count: int = 0


def preprocess_and_extract_faces(
    selected_images: Dict[str, str],
    face_cascade: cv.CascadeClassifier | None,
    eye_cascade: cv.CascadeClassifier | None,
    min_face_size: int,
    align_eyes: bool,
    equalization: str,
    downscale_max_side: int,
) -> Tuple[Dict[str, np.ndarray], Dict[str, int], PreprocessStats]:
    faces: Dict[str, np.ndarray] = {}
    label_map: Dict[str, int] = {}
    stats = PreprocessStats()
    start_time = time.time()
    total = len(selected_images)
    progress_interval = 25

    def _format_seconds(seconds: float) -> str:
        secs = max(0, int(seconds))
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _print_progress(current: int, status: str, *, done: bool = False) -> None:
        elapsed = time.time() - start_time
        rate = current / elapsed if elapsed > 0 else 0.0
        remaining = max(0, total - current)
        eta = remaining / rate if rate > 0 else 0.0
        pct = (100.0 * current / total) if total > 0 else 0.0

        bar_width = 24
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "#" * filled + "-" * (bar_width - filled)

        msg = (
            f"\r[PREPROCESS] [{bar}] {current}/{total} ({pct:6.2f}%) "
            f"| elapsed {_format_seconds(elapsed)} | eta {_format_seconds(eta)} "
            f"| {rate:6.2f} img/s | {status:<24}"
        )
        sys.stdout.write(msg)
        if done:
            sys.stdout.write("\n")
        sys.stdout.flush()

    for idx, (person, image_path) in enumerate(sorted(selected_images.items()), start=1):
        label_map[person] = len(label_map)
        stats.processed += 1
        if idx == 1 or idx % progress_interval == 0 or idx == total:
            _print_progress(idx, person)

        img = cv.imread(image_path)
        if img is None:
            stats.skipped_unreadable += 1
            continue

        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

        processed = extract_lbph_face(
            image_gray=gray,
            face_cascade=face_cascade,
            min_face_size=min_face_size,
            scale_factor=1.1,
            min_neighbors=5,
            img_size=IMG_SIZE,
            equalization=equalization,
            align_eyes=align_eyes,
            eye_cascade=eye_cascade,
            downscale_max_side=downscale_max_side,
            assume_already_cropped=ASSUME_INPUTS_ARE_CROPPED,
        )

        if processed.face is None:
            if processed.reason == "image_too_small":
                stats.skipped_too_small += 1
            else:
                stats.skipped_no_face += 1
            continue

        faces[person] = processed.face
        stats.successful += 1

    if total > 0:
        _print_progress(total, "done", done=True)

    return faces, label_map, stats


def compute_pairwise_distances(
    selected_images: Dict[str, str],
    faces: Dict[str, np.ndarray],
    label_map: Dict[str, int],
) -> List[ComparisonRecord]:
    feature_matrix, identities_sorted = train_and_extract_features(
        faces,
        label_map,
        model_type="lbph",
    )

    compare_start = time.time()
    total_identities = len(identities_sorted)

    def _format_seconds(seconds: float) -> str:
        secs = max(0, int(seconds))
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _progress(done: int, total: int) -> None:
        elapsed = time.time() - compare_start
        rate = done / elapsed if elapsed > 0 else 0.0
        remaining = max(0, total - done)
        eta = remaining / rate if rate > 0 else 0.0
        pct = (100.0 * done / total) if total > 0 else 0.0
        bar_width = 24
        filled = int(bar_width * done / total) if total > 0 else 0
        bar = "#" * filled + "-" * (bar_width - filled)
        msg = (
            f"\r[COMPARE]    [{bar}] {done}/{total} ({pct:6.2f}%) "
            f"| elapsed {_format_seconds(elapsed)} | eta {_format_seconds(eta)} "
            f"| {rate:6.2f} row/s"
        )
        sys.stdout.write(msg)
        if done == total:
            sys.stdout.write("\n")
        sys.stdout.flush()

    n = len(identities_sorted)
    raw_distances: List[Tuple[int, int, float]] = []

    # Vectorized row-wise chi-squared distances; faster and less Python overhead.
    eps = 1e-10
    for i in range(n):
        fi = feature_matrix[i]
        diff = fi - feature_matrix
        denom = fi + feature_matrix + eps
        row_dist = 0.5 * np.sum((diff * diff) / denom, axis=1)
        for j in range(n):
            if i == j:
                continue
            raw_distances.append((i, j, float(row_dist[j])))
        _progress(i + 1, n)

    raw_vals = np.array([d for (_, _, d) in raw_distances], dtype=np.float64)
    dmin = float(np.min(raw_vals))
    dmax = float(np.max(raw_vals))
    if dmax > 0:
        norm_vals = 100.0 * raw_vals / dmax
    else:
        norm_vals = np.zeros_like(raw_vals)

    records: List[ComparisonRecord] = []
    for (i, j, raw_d), norm_d in zip(raw_distances, norm_vals):
        records.append(
            ComparisonRecord(
                query_identity=identities_sorted[i],
                query_image_path=selected_images.get(identities_sorted[i], ""),
                candidate_identity=identities_sorted[j],
                candidate_image_path=selected_images.get(identities_sorted[j], ""),
                distance=float(norm_d),
                raw_distance=float(raw_d),
            )
        )

    return records


def compute_distance_statistics(distances: List[float]) -> DistanceStats:
    if not distances:
        return DistanceStats()

    arr = np.array(distances, dtype=np.float64)

    stats = DistanceStats(
        min_distance=float(np.min(arr)),
        max_distance=float(np.max(arr)),
        mean_distance=float(np.mean(arr)),
        median_distance=float(np.median(arr)),
        std_dev=float(np.std(arr)),
        count=len(distances),
    )

    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        stats.percentiles[p] = float(np.percentile(arr, p))

    return stats


def get_candidate_thresholds(stats: DistanceStats) -> Dict[str, float]:
    """
    Candidate thresholds are based on impostor-distance percentiles.

    Since every comparison is between different identities, choosing the 5th
    percentile as the threshold should produce approximately 5% FPR.
    """

    return {
        "p01_threshold": stats.percentiles.get(1, stats.min_distance),
        "p05_threshold": stats.percentiles.get(5, stats.min_distance),
        "p10_threshold": stats.percentiles.get(10, stats.min_distance),
        "p25_threshold": stats.percentiles.get(25, stats.min_distance),
        "mean_minus_1std_threshold": max(
            0.0,
            stats.mean_distance - stats.std_dev,
        ),
    }


def compute_false_positive_rate(
    records: List[ComparisonRecord],
    threshold: float,
) -> Dict:
    total = len(records)
    false_positives = [r for r in records if r.is_false_positive(threshold)]
    false_positive_count = len(false_positives)

    false_positive_rate = false_positive_count / total if total else 0.0

    return {
        "threshold": threshold,
        "false_positive_count": false_positive_count,
        "total_comparisons": total,
        "false_positive_rate": false_positive_rate,
        "false_positive_rate_percent": false_positive_rate * 100.0,
    }


def compute_threshold_sweep(
    records: List[ComparisonRecord],
    candidate_thresholds: Dict[str, float],
) -> List[Dict]:
    sweep: List[Dict] = []

    for label, threshold in candidate_thresholds.items():
        result = compute_false_positive_rate(records, threshold)
        result["label"] = label
        sweep.append(result)

    return sweep


def get_lowest_distance_pairs(
    records: List[ComparisonRecord],
    limit: int = 20,
) -> List[Dict]:
    lowest = sorted(records, key=lambda r: r.distance)[:limit]

    return [
        {
            "query_identity": r.query_identity,
            "candidate_identity": r.candidate_identity,
            "distance": r.distance,
            "query_image_path": r.query_image_path,
            "candidate_image_path": r.candidate_image_path,
        }
        for r in lowest
    ]


def compute_kde_curve(
    values: List[float],
    points: int = 500,
    bandwidth: float | None = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Compute a simple Gaussian KDE curve using NumPy only.

    This avoids requiring scipy while still giving a smooth curve-like graph.
    """

    arr = np.array(values, dtype=np.float64)

    if arr.size == 0:
        return np.array([]), np.array([]), 0.0

    if arr.size == 1:
        x = np.linspace(arr[0] - 1.0, arr[0] + 1.0, points)
        y = np.zeros_like(x)
        y[np.argmin(np.abs(x - arr[0]))] = 1.0
        return x, y, 1.0

    data_min = float(np.min(arr))
    data_max = float(np.max(arr))
    data_std = float(np.std(arr, ddof=1))

    if bandwidth is None:
        # Silverman's rule of thumb.
        bandwidth = 1.06 * data_std * (arr.size ** (-1 / 5))

    if bandwidth <= 0:
        bandwidth = max((data_max - data_min) / 50.0, 1.0)

    padding = bandwidth * 3.0
    x = np.linspace(data_min - padding, data_max + padding, points)

    z = (x[:, None] - arr[None, :]) / bandwidth
    kernels = np.exp(-0.5 * z * z) / np.sqrt(2 * np.pi)
    y = np.mean(kernels, axis=1) / bandwidth

    return x, y, float(bandwidth)


def save_distance_histogram(
    records: List[ComparisonRecord],
    output_path: str,
    threshold: float | None = None,
    bins: int = 20,
) -> None:
    """
    Save a histogram of inter-identity distances.

    The area left of the threshold represents false positives because all
    comparisons are inter-identity comparisons.
    """

    distances = [r.distance for r in records]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    plt.figure(figsize=(10, 6))
    plt.hist(distances, bins=bins, edgecolor="black")

    if threshold is not None:
        plt.axvline(threshold, linestyle="--", linewidth=2)

        ymax = plt.ylim()[1]
        plt.text(
            threshold,
            ymax * 0.95,
            f"Threshold = {threshold:.2f}",
            rotation=90,
            verticalalignment="top",
        )

    plt.title("LBPH Independence Test: Inter-Identity Distance Histogram")
    plt.xlabel("Normalized Distance")
    if distances:
        plt.xlim(min(distances), 100)
    else:
        plt.xlim(0, 100)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def save_distance_curve_plot(
    records: List[ComparisonRecord],
    output_path: str,
    threshold: float | None = None,
    curve_points: int = 500,
    curve_bandwidth: float | None = None,
) -> float:
    """
    Save a curve-style distance distribution plot.

    The area left of the threshold represents false positives because all
    comparisons are inter-identity comparisons.
    """

    distances = [r.distance for r in records]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    x, y, used_bandwidth = compute_kde_curve(
        distances,
        points=curve_points,
        bandwidth=curve_bandwidth,
    )

    plt.figure(figsize=(10, 6))

    if x.size > 0 and y.size > 0:
        plt.plot(x, y, linewidth=2)

        if threshold is not None:
            plt.axvline(threshold, linestyle="--", linewidth=2)

            ymax = plt.ylim()[1]
            plt.text(
                threshold,
                ymax * 0.95,
                f"Threshold = {threshold:.2f}",
                rotation=90,
                verticalalignment="top",
            )

    plt.title("LBPH Independence Test: Inter-Identity Distance Curve")
    plt.xlabel("Normalized Distance")
    plt.ylabel("Estimated Frequency Density")
    if distances:
        plt.xlim(max(0, min(distances) - 5), 100)
    else:
        plt.xlim(0, 100)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()

    return used_bandwidth


def save_csv_results(records: List[ComparisonRecord], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "query_identity",
                "query_image_path",
                "candidate_identity",
                "candidate_image_path",
                "distance_normalized",
            ],
        )

        writer.writeheader()

        for record in records:
            writer.writerow(
                {
                    "query_identity": record.query_identity,
                    "query_image_path": record.query_image_path,
                    "candidate_identity": record.candidate_identity,
                    "candidate_image_path": record.candidate_image_path,
                    "distance_normalized": f"{record.distance:.6f}",
                }
            )


def save_threshold_sweep_csv(sweep: List[Dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "label",
                "threshold",
                "false_positive_count",
                "total_comparisons",
                "false_positive_rate",
                "false_positive_rate_percent",
            ],
        )

        writer.writeheader()

        for row in sweep:
            writer.writerow(
                {
                    "label": row["label"],
                    "threshold": f"{row['threshold']:.6f}",
                    "false_positive_count": row["false_positive_count"],
                    "total_comparisons": row["total_comparisons"],
                    "false_positive_rate": f"{row['false_positive_rate']:.6f}",
                    "false_positive_rate_percent": f"{row['false_positive_rate_percent']:.4f}",
                }
            )


def save_lowest_pairs_csv(lowest_pairs: List[Dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "query_identity",
                "candidate_identity",
                "distance",
                "query_image_path",
                "candidate_image_path",
            ],
        )

        writer.writeheader()

        for row in lowest_pairs:
            writer.writerow(
                {
                    "query_identity": row["query_identity"],
                    "candidate_identity": row["candidate_identity"],
                    "distance": f"{row['distance']:.6f}",
                    "query_image_path": row["query_image_path"],
                    "candidate_image_path": row["candidate_image_path"],
                }
            )


def save_json_results(summary: Dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def print_report(summary: Dict) -> None:
    print("\nLBPH LIGHT-FRONT INDEPENDENCE TEST REPORT")

    dataset_info = summary.get("dataset", {})
    comparison_info = summary.get("comparison", {})
    stats_data = summary.get("distance_statistics", {})

    print(f"Dataset: {dataset_info.get('path', 'N/A')}")
    print(f"Total identities: {dataset_info.get('total_identities', 0)}")
    print(f"Selected identities: {dataset_info.get('selected_identities', 0)}")
    print(f"Skipped identities: {dataset_info.get('skipped_identities', 0)}")

    expected = comparison_info.get("expected_comparisons", 0)
    actual = comparison_info.get("actual_comparisons", 0)
    match = "(ok)" if expected == actual else "(MISMATCH)"

    print(f"\nComparisons: expected {expected}, actual {actual} {match}")

    print("\nDistance Statistics")
    print(
        "Normalized 0-100 stats: "
        f"min={stats_data.get('min_distance', 0):.4f} "
        f"max={stats_data.get('max_distance', 0):.4f} "
        f"mean={stats_data.get('mean_distance', 0):.4f} "
        f"median={stats_data.get('median_distance', 0):.4f} "
        f"std={stats_data.get('std_dev', 0):.4f}"
    )

    print("\nFalse Positive Rate Sweep")
    print(
        f"{'Label':<28} "
        f"{'Threshold':>12} "
        f"{'FP Count':>10} "
        f"{'Total':>10} "
        f"{'FPR %':>10}"
    )
    print("-" * 76)

    for row in summary.get("threshold_sweep", []):
        print(
            f"{row['label']:<28} "
            f"{row['threshold']:>12.4f} "
            f"{row['false_positive_count']:>10} "
            f"{row['total_comparisons']:>10} "
            f"{row['false_positive_rate_percent']:>9.4f}%"
        )

    provided_threshold_result = summary.get("provided_threshold_fpr")
    if provided_threshold_result:
        print("\nProvided Threshold FPR")
        print(
            f"Threshold: {provided_threshold_result['threshold']:.4f}\n"
            f"False positives: "
            f"{provided_threshold_result['false_positive_count']} / "
            f"{provided_threshold_result['total_comparisons']}\n"
            f"False positive rate: "
            f"{provided_threshold_result['false_positive_rate_percent']:.4f}%"
        )

    plots = summary.get("plots", {})
    if plots:
        print("\nPlots")
        print(f"Distance histogram: {plots.get('distance_histogram', 'N/A')}")
        print(f"Distance curve plot: {plots.get('distance_curve_plot', 'N/A')}")
        print(f"KDE bandwidth used: {plots.get('kde_bandwidth_used', 'N/A')}")

    print(f"\n[INFO] Results saved to: {summary.get('output_dir', 'N/A')}")


def try_merge_segment_outputs(args: argparse.Namespace) -> None:
    if args.segment_count <= 1 or args.segment_index != args.segment_count:
        return
    if args.dataset_source != "lfw-dataset":
        return

    base_dir = Path(DEFAULT_OUTPUT_DIR)
    seg_summaries: List[Dict] = []
    for idx in range(1, args.segment_count + 1):
        seg_dir = base_dir / f"lfw_seg{idx}of{args.segment_count}"
        seg_summary_path = seg_dir / "summary.json"
        if not seg_summary_path.exists():
            print(f"[WARN] Missing segment summary: {seg_summary_path}")
            return
        with seg_summary_path.open("r", encoding="utf-8") as f:
            seg_summaries.append(json.load(f))

    merged_dir = base_dir / "lfw_merged"
    merged_dir.mkdir(parents=True, exist_ok=True)

    total_comparisons = sum(
        int(s.get("comparison", {}).get("actual_comparisons", 0))
        for s in seg_summaries
    )
    expected_comparisons = sum(
        int(s.get("comparison", {}).get("expected_comparisons", 0))
        for s in seg_summaries
    )

    # Merge threshold sweep by label (sum FP counts).
    sweep_by_label: Dict[str, Dict] = {}
    for s in seg_summaries:
        for row in s.get("threshold_sweep", []):
            label = str(row.get("label", ""))
            if not label:
                continue
            item = sweep_by_label.setdefault(
                label,
                {
                    "label": label,
                    "threshold": float(row.get("threshold", 0.0)),
                    "false_positive_count": 0,
                },
            )
            item["false_positive_count"] += int(row.get("false_positive_count", 0))

    merged_sweep: List[Dict] = []
    for label in sorted(sweep_by_label.keys()):
        item = sweep_by_label[label]
        fp = int(item["false_positive_count"])
        fpr = (fp / total_comparisons) if total_comparisons else 0.0
        merged_sweep.append(
            {
                "label": label,
                "threshold": float(item["threshold"]),
                "false_positive_count": fp,
                "total_comparisons": total_comparisons,
                "false_positive_rate": fpr,
                "false_positive_rate_percent": fpr * 100.0,
            }
        )

    # Merge lowest pairs from all segments, keep global top-20.
    all_pairs: List[Dict] = []
    for s in seg_summaries:
        for row in s.get("lowest_distance_pairs", []):
            all_pairs.append(row)
    all_pairs_sorted = sorted(all_pairs, key=lambda x: float(x.get("distance", 1e12)))[:20]

    # Write merged CSV artifacts.
    merged_sweep_csv = merged_dir / "threshold_sweep.csv"
    save_threshold_sweep_csv(merged_sweep, str(merged_sweep_csv))
    merged_lowest_csv = merged_dir / "lowest_distance_pairs.csv"
    save_lowest_pairs_csv(all_pairs_sorted, str(merged_lowest_csv))

    base_summary = seg_summaries[-1]
    merged_summary = {
        **base_summary,
        "output_dir": str(merged_dir),
        "comparison": {
            "expected_comparisons": expected_comparisons,
            "actual_comparisons": total_comparisons,
            "note": (
                f"Merged from {args.segment_count} LFW segments "
                "(unique-pair segmented run)."
            ),
            "segment_index": None,
            "segment_count": args.segment_count,
            "merged": True,
        },
        "threshold_sweep": merged_sweep,
        "lowest_distance_pairs": all_pairs_sorted,
    }
    merged_summary.setdefault("saved_files", {})
    merged_summary["saved_files"]["threshold_sweep_csv"] = str(merged_sweep_csv)
    merged_summary["saved_files"]["lowest_distance_pairs_csv"] = str(merged_lowest_csv)
    merged_summary["saved_files"]["summary_json"] = str(merged_dir / "summary.json")
    # comparisons.csv is intentionally not merged.
    merged_summary["saved_files"]["comparisons_csv"] = ""
    merged_summary["saved_files"]["comparisons_note"] = (
        "Segmented comparisons.csv files remain in each segment folder."
    )

    merged_json = merged_dir / "summary.json"
    save_json_results(merged_summary, str(merged_json))
    print(f"[OK] Merged segment outputs -> {merged_dir}")


def run_lbph_independence_test_light_front() -> int:
    args = parse_args()
    resolve_dataset_choice(args)

    args.segment_count = max(1, int(args.segment_count))
    args.segment_index = max(1, int(args.segment_index))
    args.workers = max(1, int(args.workers))
    args.chunk_rows = max(1, int(args.chunk_rows))
    args.max_inflight = max(args.workers, int(args.max_inflight))
    args.lbph_block_rows = max(32, int(args.lbph_block_rows))

    # LFW fast profile defaults (only when user did not override from CLI).
    if args.dataset_source == "lfw-dataset":
        cli = " ".join(sys.argv[1:])
        if "--chunk-rows" not in cli:
            args.chunk_rows = 96
        if "--max-inflight" not in cli:
            args.max_inflight = max(args.max_inflight, args.workers * 12)
        if "--lbph-block-rows" not in cli:
            args.lbph_block_rows = 384
    if args.segment_index > args.segment_count:
        print("[ERROR] --segment-index cannot be greater than --segment-count.")
        return 1
    resolve_default_output_dir(args)

    args.dataset_dir = resolve_path(args.dataset_dir)
    args.cascade_path = resolve_path(args.cascade_path)
    args.eye_cascade_path = resolve_path(resolve_eye_cascade_path(args.eye_cascade_path))
    args.output_dir = resolve_path(args.output_dir)

    face_cascade: cv.CascadeClassifier | None = None
    eye_cascade: cv.CascadeClassifier | None = None

    if not ASSUME_INPUTS_ARE_CROPPED:
        face_cascade = cv.CascadeClassifier(args.cascade_path)
        if face_cascade.empty():
            raise FileNotFoundError(f"Could not load cascade: {args.cascade_path}")

        if args.align_eyes:
            eye_cascade = cv.CascadeClassifier(args.eye_cascade_path)
            if eye_cascade.empty():
                eye_cascade = None

    person_dirs = get_person_dirs(args.dataset_dir)
    if not person_dirs:
        print("[ERROR] No identities found.")
        return 1

    all_runs_records = []
    first_run_summary = {}

    for iteration in range(args.iterations):
        print(f"\n[ITERATION {iteration+1}/{args.iterations}]")
        selected_images = select_light_front_images(
            person_dirs, args.image_name, args.random_seed + iteration
        )

        if args.max_identities > 0 and len(selected_images) > args.max_identities:
            kept = dict(sorted(selected_images.items())[: args.max_identities])
            if iteration == 0:
                print(
                    f"[INFO] Applying --max-identities={args.max_identities}: "
                    f"{len(selected_images)} -> {len(kept)} identities"
                )
            selected_images = kept
        elif (
            args.dataset_source == "lfw-dataset"
            and args.max_identities <= 0
            and args.lfw_default_max_identities > 0
            and len(selected_images) > args.lfw_default_max_identities
        ):
            kept = dict(sorted(selected_images.items())[: args.lfw_default_max_identities])
            if iteration == 0:
                print(
                    f"[INFO] Auto-cap for LFW: {len(selected_images)} -> {len(kept)} identities "
                    f"(use --max-identities to override)"
                )
            selected_images = kept

        if len(selected_images) < 2:
            print(f"[WARN] Iteration {iteration+1}: Not enough identities.")
            continue

        faces, label_map, preprocess_stats = preprocess_and_extract_faces(
            selected_images,
            face_cascade,
            eye_cascade,
            args.min_face_size,
            args.align_eyes,
            args.equalization,
            args.downscale_max_side,
        )

        if len(faces) < 2:
            print(f"[WARN] Iteration {iteration+1}: Not enough faces extracted.")
            continue

        expected_comparisons = (len(faces) * (len(faces) - 1)) // 2
        if args.max_comparisons > 0 and expected_comparisons > args.max_comparisons:
            print(
                f"[ERROR] Iteration {iteration+1} blocked by --max-comparisons safety cap."
            )
            continue

        if expected_comparisons > args.streaming_threshold:
            if iteration == 0:
                print(
                    f"[INFO] Large run detected ({expected_comparisons:,} comparisons). "
                    "Using memory-safe streaming mode."
                )
            # Streaming mode currently doesn't support easy aggregation in-place.
            # We'll run it once for now or implement a multi-run streaming aggregator if needed.
            # For simplicity, we fallback to streaming for the first iteration only if large.
            if args.iterations > 1:
                print("[WARN] Multiple iterations not yet supported in streaming mode. Running once.")
            return run_lbph_independence_test_light_front_streaming(
                args=args,
                person_dirs=person_dirs,
                selected_images=selected_images,
                faces=faces,
                label_map=label_map,
                preprocess_stats=preprocess_stats,
            )

        records = compute_pairwise_distances(selected_images, faces, label_map)
        
        # Save raw results
        run_dir = os.path.join(args.output_dir, "_raw_runs", f"run_{iteration+1}")
        save_csv_results(records, os.path.join(run_dir, "comparisons.csv"))
        
        all_runs_records.append([
            {
                "query_identity": r.query_identity,
                "query_image_path": r.query_image_path,
                "candidate_identity": r.candidate_identity,
                "candidate_image_path": r.candidate_image_path,
                "raw_distance": r.raw_distance,
            }
            for r in records
        ])
        
        if iteration == 0:
            first_run_summary = {
                "dataset": {
                    "path": args.dataset_dir,
                    "total_identities": len(person_dirs),
                    "selected_identities": len(faces),
                    "skipped_identities": len(person_dirs) - len(faces),
                },
                "preprocessing": {
                    "processed": preprocess_stats.processed,
                    "successful": preprocess_stats.successful,
                    "skipped_unreadable": preprocess_stats.skipped_unreadable,
                    "skipped_no_face": preprocess_stats.skipped_no_face,
                    "skipped_too_small": preprocess_stats.skipped_too_small,
                }
            }

    if not all_runs_records:
        print("[ERROR] No successful iterations.")
        return 1

    print("\n[AGGREGATE] Computing mean distances...")
    aggregated_data = aggregate_pairwise_results(all_runs_records)
    
    records = [
        ComparisonRecord(
            query_identity=rd["query_identity"],
            query_image_path=rd["query_image_path"],
            candidate_identity=rd["candidate_identity"],
            candidate_image_path=rd["candidate_image_path"],
            distance=rd["normalized_distance"],
            raw_distance=rd["raw_distance"],
        )
        for rd in aggregated_data
    ]

    distances = [r.distance for r in records]
    distance_stats = compute_distance_statistics(distances)

    candidate_thresholds = get_candidate_thresholds(distance_stats)
    threshold_sweep = compute_threshold_sweep(records, candidate_thresholds)
    lowest_pairs = get_lowest_distance_pairs(records, limit=20)

    os.makedirs(args.output_dir, exist_ok=True)

    csv_path = os.path.join(args.output_dir, "comparisons.csv")
    threshold_sweep_csv_path = os.path.join(args.output_dir, "threshold_sweep.csv")
    lowest_pairs_csv_path = os.path.join(args.output_dir, "lowest_distance_pairs.csv")
    histogram_path = os.path.join(args.output_dir, "distance_histogram.png")
    curve_plot_path = os.path.join(args.output_dir, "distance_curve_plot.png")
    json_path = os.path.join(args.output_dir, "summary.json")

    save_csv_results(records, csv_path)
    save_threshold_sweep_csv(threshold_sweep, threshold_sweep_csv_path)
    save_lowest_pairs_csv(lowest_pairs, lowest_pairs_csv_path)

    plot_threshold = args.threshold if args.threshold is not None else candidate_thresholds.get("p05_threshold")
    save_distance_histogram(
        records,
        histogram_path,
        threshold=plot_threshold,
        bins=args.histogram_bins,
    )

    used_bandwidth = save_distance_curve_plot(
        records,
        curve_plot_path,
        threshold=plot_threshold,
        curve_points=args.curve_points,
        curve_bandwidth=args.curve_bandwidth,
    )

    summary: Dict = {
        "output_dir": args.output_dir,
        "dataset": first_run_summary.get("dataset", {}),
        "preprocessing": first_run_summary.get("preprocessing", {}),
        "comparison": {
            "expected_comparisons": (len(records)), # approximate
            "actual_comparisons": len(records),
            "note": (
                "This test uses ordered comparisons, so A vs B and B vs A "
                "are both counted. Results aggregated from multiple runs."
            ),
        },
        "distance_statistics": {
            "min_distance": distance_stats.min_distance,
            "max_distance": distance_stats.max_distance,
            "mean_distance": distance_stats.mean_distance,
            "median_distance": distance_stats.median_distance,
            "std_dev": distance_stats.std_dev,
            "percentiles": distance_stats.percentiles,
        },
        "candidate_thresholds": candidate_thresholds,
        "threshold_sweep": threshold_sweep,
        "lowest_distance_pairs": lowest_pairs,
        "plots": {
            "distance_histogram": histogram_path,
            "distance_curve_plot": curve_plot_path,
            "kde_bandwidth_used": used_bandwidth,
        },
        "saved_files": {
            "comparisons_csv": csv_path,
            "threshold_sweep_csv": threshold_sweep_csv_path,
            "lowest_distance_pairs_csv": lowest_pairs_csv_path,
            "summary_json": json_path,
            "distance_histogram": histogram_path,
            "distance_curve_plot": curve_plot_path,
        },
        "iterations": args.iterations,
    }

    if args.threshold is not None:
        summary["provided_threshold_fpr"] = compute_false_positive_rate(
            records,
            args.threshold,
        )

    save_json_results(summary, json_path)
    try_merge_segment_outputs(args)
    print_report(summary)

    return 0


def run_lbph_independence_test_light_front_streaming(
    args: argparse.Namespace,
    person_dirs: List[Tuple[str, str]],
    selected_images: Dict[str, str],
    faces: Dict[str, np.ndarray],
    label_map: Dict[str, int],
    preprocess_stats: PreprocessStats,
) -> int:
    feature_matrix, identities_sorted = train_and_extract_features(
        faces,
        label_map,
        model_type="lbph",
    )
    n = len(identities_sorted)
    seg_size = (n + args.segment_count - 1) // args.segment_count
    seg_start = (args.segment_index - 1) * seg_size
    seg_end = min(n, seg_start + seg_size)
    if seg_start >= n:
        print("[ERROR] Segment start is out of range for selected identities.")
        return 1
    seg_rows = seg_end - seg_start
    total = sum((n - i - 1) for i in range(seg_start, seg_end))
    eps = 1e-10

    os.makedirs(args.output_dir, exist_ok=True)
    csv_path = os.path.join(args.output_dir, "comparisons.csv")
    threshold_sweep_csv_path = os.path.join(args.output_dir, "threshold_sweep.csv")
    lowest_pairs_csv_path = os.path.join(args.output_dir, "lowest_distance_pairs.csv")
    histogram_path = os.path.join(args.output_dir, "distance_histogram.png")
    curve_plot_path = os.path.join(args.output_dir, "distance_curve_plot.png")
    json_path = os.path.join(args.output_dir, "summary.json")

    tmp = tempfile.NamedTemporaryFile(
        prefix=f"lbph_raw_seg{args.segment_index}of{args.segment_count}_",
        suffix=".dat",
        delete=False,
    )
    tmp_path = tmp.name
    tmp.close()

    raw_mm = np.memmap(tmp_path, dtype=np.float32, mode="w+", shape=(total,))
    k = 0
    compare_start = time.time()
    lowest_heap: List[Tuple[float, int, int]] = []

    def _fmt(seconds: float) -> str:
        secs = max(0, int(seconds))
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    print(
        f"[INFO] Segment {args.segment_index}/{args.segment_count}: "
        f"query rows {seg_start + 1}-{seg_end} of {n} (rows={seg_rows}, comparisons={total:,})"
    )

    if args.workers == 1:
        for i in range(seg_start, seg_end):
            fi = feature_matrix[i]
            diff = fi - feature_matrix
            denom = fi + feature_matrix + eps
            row_dist = 0.5 * np.sum((diff * diff) / denom, axis=1)
            for j in range(n):
                if i == j:
                    continue
                d = float(row_dist[j])
                raw_mm[k] = d
                if len(lowest_heap) < 20:
                    heapq.heappush(lowest_heap, (-d, i, j))
                elif d < -lowest_heap[0][0]:
                    heapq.heapreplace(lowest_heap, (-d, i, j))
                k += 1
            done = (i - seg_start) + 1
            elapsed = time.time() - compare_start
            pairs_done = int((done / max(1, seg_rows)) * total)
            rate = pairs_done / elapsed if elapsed > 0 else 0.0
            eta = (total - pairs_done) / rate if rate > 0 else 0.0
            bar_w = 24
            filled = int(bar_w * done / seg_rows)
            bar = "#" * filled + "-" * (bar_w - filled)
            sys.stdout.write(
                f"\r[COMPARE]    [{bar}] {done}/{seg_rows} ({100.0*done/seg_rows:6.2f}%) "
                f"| elapsed {_fmt(elapsed)} | eta {_fmt(eta)} | {rate:8.0f} pair/s"
            )
            sys.stdout.flush()
        sys.stdout.write("\n")
    else:
        feat_tmp = tempfile.NamedTemporaryFile(prefix="lbph_features_", suffix=".npy", delete=False)
        feat_path = feat_tmp.name
        feat_tmp.close()
        np.save(feat_path, feature_matrix.astype(np.float64, copy=False))
        del feature_matrix

        # Keep chunks fairly small so progress updates appear frequently.
        chunk_rows = max(1, int(args.chunk_rows))
        tasks: list[tuple[int, int, int, int]] = []
        row_cursor = seg_start
        chunk_idx = 0
        while row_cursor < seg_end:
            end = min(seg_end, row_cursor + chunk_rows)
            tasks.append((chunk_idx, row_cursor, end, 20, int(args.lbph_block_rows)))
            row_cursor = end
            chunk_idx += 1

        completed_rows = 0
        completed_rows_any = 0
        write_idx = 0
        chunk_results: dict[int, dict] = {}
        pending_idx = 0
        try:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=args.workers,
                initializer=_init_pairwise_worker,
                initargs=(feat_path, "lbph"),
            ) as ex:
                max_inflight = max(2, int(args.max_inflight))
                task_iter = iter(tasks)
                future_set = set()
                for _ in range(min(max_inflight, len(tasks))):
                    try:
                        future_set.add(ex.submit(_pairwise_chunk_worker, next(task_iter)))
                    except StopIteration:
                        break

                last_heartbeat = 0.0
                while future_set:
                    done_set, future_set = concurrent.futures.wait(
                        future_set,
                        timeout=1.0,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    now = time.time()
                    if not done_set:
                        if now - last_heartbeat >= 1.0:
                            elapsed_any = now - compare_start
                            pairs_done_any = int((completed_rows_any / max(1, seg_rows)) * total)
                            rate_any = pairs_done_any / elapsed_any if elapsed_any > 0 else 0.0
                            eta_any = (total - pairs_done_any) / rate_any if rate_any > 0 else 0.0
                            bar_w = 24
                            filled_any = int(bar_w * completed_rows_any / seg_rows)
                            bar_any = "#" * filled_any + "-" * (bar_w - filled_any)
                            sys.stdout.write(
                                f"\r[COMPARE]    [{bar_any}] {completed_rows_any}/{seg_rows} ({100.0*completed_rows_any/seg_rows:6.2f}%) "
                                f"| elapsed {_fmt(elapsed_any)} | eta {_fmt(eta_any)} | {rate_any:8.0f} pair/s"
                            )
                            sys.stdout.flush()
                            last_heartbeat = now
                        continue
                    for future in done_set:
                        res = future.result()
                        completed_rows_any += int(res["end"]) - int(res["start"])
                        elapsed_any = now - compare_start
                        pairs_done_any = int((completed_rows_any / max(1, seg_rows)) * total)
                        rate_any = pairs_done_any / elapsed_any if elapsed_any > 0 else 0.0
                        eta_any = (total - pairs_done_any) / rate_any if rate_any > 0 else 0.0
                        bar_w = 24
                        filled_any = int(bar_w * completed_rows_any / seg_rows)
                        bar_any = "#" * filled_any + "-" * (bar_w - filled_any)
                        sys.stdout.write(
                            f"\r[COMPARE]    [{bar_any}] {completed_rows_any}/{seg_rows} ({100.0*completed_rows_any/seg_rows:6.2f}%) "
                            f"| elapsed {_fmt(elapsed_any)} | eta {_fmt(eta_any)} | {rate_any:8.0f} pair/s"
                        )
                        sys.stdout.flush()
                        chunk_results[int(res["chunk_idx"])] = res
                        while pending_idx in chunk_results:
                            cur = chunk_results.pop(pending_idx)
                            cvals = np.asarray(cur["raw"], dtype=np.float32)
                            ccount = int(cvals.shape[0])
                            raw_mm[write_idx: write_idx + ccount] = cvals
                            write_idx += ccount
                            for item in cur["top_heap"]:
                                neg_d, ii, jj = item
                                d = -float(neg_d)
                                if len(lowest_heap) < 20:
                                    heapq.heappush(lowest_heap, (-d, int(ii), int(jj)))
                                elif d < -lowest_heap[0][0]:
                                    heapq.heapreplace(lowest_heap, (-d, int(ii), int(jj)))
                            completed_rows += int(cur["end"]) - int(cur["start"])
                            pending_idx += 1
                        try:
                            future_set.add(ex.submit(_pairwise_chunk_worker, next(task_iter)))
                        except StopIteration:
                            pass
                        last_heartbeat = now
            sys.stdout.write("\n")
        finally:
            try:
                os.unlink(feat_path)
            except Exception:
                pass

    raw_vals = np.asarray(raw_mm)
    raw_min = float(np.min(raw_vals))
    raw_max = float(np.max(raw_vals))
    raw_mean = float(np.mean(raw_vals))
    raw_std = float(np.std(raw_vals))
    raw_median = float(np.median(raw_vals))
    raw_pcts = np.percentile(raw_vals, [1, 5, 10, 25, 50, 75, 90, 95, 99]).astype(np.float64)

    if raw_max > 0:
        scale = 100.0 / raw_max
    else:
        scale = 0.0

    def norm_d(raw_d: float) -> float:
        if scale <= 0.0:
            return 0.0
        return float(raw_d * scale)

    distance_stats = DistanceStats(
        min_distance=norm_d(raw_min),
        max_distance=norm_d(raw_max),
        mean_distance=norm_d(raw_mean),
        median_distance=norm_d(raw_median),
        std_dev=float(raw_std * scale),
        percentiles={
            1: norm_d(float(raw_pcts[0])),
            5: norm_d(float(raw_pcts[1])),
            10: norm_d(float(raw_pcts[2])),
            25: norm_d(float(raw_pcts[3])),
            50: norm_d(float(raw_pcts[4])),
            75: norm_d(float(raw_pcts[5])),
            90: norm_d(float(raw_pcts[6])),
            95: norm_d(float(raw_pcts[7])),
            99: norm_d(float(raw_pcts[8])),
        },
        count=total,
    )

    candidate_thresholds = get_candidate_thresholds(distance_stats)
    counts = {name: 0 for name in candidate_thresholds}
    provided_count = 0

    norm_vals = np.asarray(raw_mm * scale if scale > 0 else np.zeros_like(raw_mm), dtype=np.float32)
    for name, thr in candidate_thresholds.items():
        counts[name] = int(np.sum(norm_vals <= thr))
    if args.threshold is not None:
        provided_count = int(np.sum(norm_vals <= args.threshold))

    if args.write_comparisons_csv:
        write_start = time.time()
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "query_identity",
                    "query_image_path",
                    "candidate_identity",
                    "candidate_image_path",
                    "distance_normalized",
                ],
            )
            writer.writeheader()
            idx = 0
            for i in range(seg_start, seg_end):
                qi = identities_sorted[i]
                qpath = selected_images.get(qi, "")
                for j in range(n):
                    if i == j:
                        continue
                    cj = identities_sorted[j]
                    cpath = selected_images.get(cj, "")
                    writer.writerow(
                        {
                            "query_identity": qi,
                            "query_image_path": qpath,
                            "candidate_identity": cj,
                            "candidate_image_path": cpath,
                            "distance_normalized": f"{float(norm_vals[idx]):.6f}",
                        }
                    )
                    idx += 1
                done = (i - seg_start) + 1
                elapsed = time.time() - write_start
                pairs_done = int((done / max(1, seg_rows)) * total)
                rate = pairs_done / elapsed if elapsed > 0 else 0.0
                eta = (total - pairs_done) / rate if rate > 0 else 0.0
                bar_w = 24
                filled = int(bar_w * done / seg_rows)
                bar = "#" * filled + "-" * (bar_w - filled)
                sys.stdout.write(
                    f"\r[WRITE]      [{bar}] {done}/{seg_rows} ({100.0*done/seg_rows:6.2f}%) "
                    f"| elapsed {_fmt(elapsed)} | eta {_fmt(eta)} | {rate:8.0f} pair/s"
                )
                sys.stdout.flush()
        sys.stdout.write("\n")
    else:
        csv_path = ""
        print("[INFO] Skipped full comparisons.csv for speed. Use --write-comparisons-csv to enable.")

    threshold_sweep: List[Dict] = []
    for name, thr in candidate_thresholds.items():
        fp = counts[name]
        fpr = fp / total if total else 0.0
        threshold_sweep.append(
            {
                "label": name,
                "threshold": thr,
                "false_positive_count": fp,
                "total_comparisons": total,
                "false_positive_rate": fpr,
                "false_positive_rate_percent": fpr * 100.0,
            }
        )
    save_threshold_sweep_csv(threshold_sweep, threshold_sweep_csv_path)

    lowest_pairs = []
    for neg_d, i, j in sorted(lowest_heap, key=lambda x: -x[0]):
        raw_d = -neg_d
        lowest_pairs.append(
            {
                "query_identity": identities_sorted[i],
                "candidate_identity": identities_sorted[j],
                "distance": norm_d(raw_d),
                "query_image_path": selected_images.get(identities_sorted[i], ""),
                "candidate_image_path": selected_images.get(identities_sorted[j], ""),
            }
        )
    save_lowest_pairs_csv(lowest_pairs, lowest_pairs_csv_path)

    # Build light-weight records only for plotting.
    plot_sample = min(total, 1_000_000)
    if plot_sample < total:
        step = max(1, total // plot_sample)
        plot_distances = [float(norm_vals[i]) for i in range(0, total, step)]
    else:
        plot_distances = [float(v) for v in norm_vals]
    plot_records = [
        ComparisonRecord("", "", "", "", d) for d in plot_distances
    ]
    plot_threshold = args.threshold if args.threshold is not None else candidate_thresholds.get("p05_threshold")
    save_distance_histogram(plot_records, histogram_path, threshold=plot_threshold, bins=args.histogram_bins)
    used_bandwidth = save_distance_curve_plot(
        plot_records,
        curve_plot_path,
        threshold=plot_threshold,
        curve_points=args.curve_points,
        curve_bandwidth=args.curve_bandwidth,
    )

    summary: Dict = {
        "output_dir": args.output_dir,
        "dataset": {
            "path": args.dataset_dir,
            "total_identities": len(person_dirs),
            "selected_identities": len(faces),
            "skipped_identities": len(person_dirs) - len(faces),
        },
        "preprocessing": {
            "processed": preprocess_stats.processed,
            "successful": preprocess_stats.successful,
            "skipped_unreadable": preprocess_stats.skipped_unreadable,
            "skipped_no_face": preprocess_stats.skipped_no_face,
            "skipped_too_small": preprocess_stats.skipped_too_small,
        },
        "comparison": {
            "expected_comparisons": total,
            "actual_comparisons": total,
            "note": "Streaming mode enabled for large run.",
            "segment_index": args.segment_index,
            "segment_count": args.segment_count,
            "segment_query_start_1based": seg_start + 1,
            "segment_query_end_1based": seg_end,
            "segment_rows": seg_rows,
        },
        "distance_statistics": {
            "min_distance": distance_stats.min_distance,
            "max_distance": distance_stats.max_distance,
            "mean_distance": distance_stats.mean_distance,
            "median_distance": distance_stats.median_distance,
            "std_dev": distance_stats.std_dev,
            "percentiles": distance_stats.percentiles,
        },
        "candidate_thresholds": candidate_thresholds,
        "threshold_sweep": threshold_sweep,
        "lowest_distance_pairs": lowest_pairs,
        "plots": {
            "distance_histogram": histogram_path,
            "distance_curve_plot": curve_plot_path,
            "kde_bandwidth_used": used_bandwidth,
            "plot_note": "Plots may use sampled distances in very large runs.",
        },
        "saved_files": {
            "comparisons_csv": csv_path,
            "threshold_sweep_csv": threshold_sweep_csv_path,
            "lowest_distance_pairs_csv": lowest_pairs_csv_path,
            "summary_json": json_path,
            "distance_histogram": histogram_path,
            "distance_curve_plot": curve_plot_path,
        },
    }

    if args.threshold is not None:
        fpr = provided_count / total if total else 0.0
        summary["provided_threshold_fpr"] = {
            "threshold": args.threshold,
            "false_positive_count": provided_count,
            "total_comparisons": total,
            "false_positive_rate": fpr,
            "false_positive_rate_percent": fpr * 100.0,
        }

    save_json_results(summary, json_path)
    try_merge_segment_outputs(args)
    print_report(summary)

    try:
        del norm_vals
        del raw_mm
        os.unlink(tmp_path)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(run_lbph_independence_test_light_front())




