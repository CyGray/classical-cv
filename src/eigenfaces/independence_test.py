"""
Eigenfaces Independence Test: Verify distance distribution and false positive behavior
without comparing images from the same identity.

This test:
1. Selects one image per person from the dataset
2. Trains Eigenfaces model on these selected images
3. Performs N × (N - 1) cross-identity comparisons
4. Collects and analyzes distance statistics
5. Outputs CSV, JSON, and console report
"""

import argparse
import csv
import json
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2 as cv
import numpy as np

from src.independence_common import (
    train_and_extract_features,
    compute_pairwise_distances as common_pairwise_distances,
    aggregate_pairwise_results,
    error_pair_report,
    format_error_pair_report,
)
from src.classical_faces.pipeline import SPECS
from src.lbph.preprocess import IMG_SIZE, extract_lbph_face, resolve_eye_cascade_path, normalize_face

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSUME_INPUTS_ARE_CROPPED = True


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str(PROJECT_ROOT.joinpath(candidate))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Eigenfaces Independence Test: N×(N-1) cross-identity distance analysis."
    )
    parser.add_argument(
        "--dataset-dir",
        default=root_path("data", "lasalle_db1"),
        help="Path to dataset directory containing person folders.",
    )
    parser.add_argument(
        "--output-dir",
        default=root_path("outputs", "eigenfaces", "independence_test"),
        help="Directory to save results (CSV, JSON, reports).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional Eigenfaces distance threshold (normalized 0-100 scale) for false positive analysis.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for reproducible image selection.",
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
        choices=["equalize", "clahe", "tan-triggs"],
        default=SPECS["eigenfaces"].default_equalization,
        help="Face contrast normalization (default = the family's training contract).",
    )
    parser.add_argument(
        "--downscale-max-side",
        type=int,
        default=0,
        help="Downscale for detection if > 0.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations to run (each with different random image selection) for aggregation.",
    )
    parser.add_argument(
        "--target-far-ppm",
        type=float,
        default=10000.0,
        help="Target false-alarm rate (ppm) for the rank-based threshold. "
             "Spec default for La Salle DB1 is 10,000 ppm (the 8th error pair).",
    )
    parser.add_argument(
        "--error-pair-rank",
        type=int,
        default=None,
        help="Explicit k-th error pair (overrides --target-far-ppm). Spec: 8 for La Salle, 331 for LFW.",
    )
    return parser.parse_args()


def is_image_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_EXTENSIONS


def get_person_dirs(dataset_root: str) -> List[Tuple[str, str]]:
    """Gather person directories from dataset root."""
    if not os.path.isdir(dataset_root):
        return []
    
    out: List[Tuple[str, str]] = []
    for person in sorted(os.listdir(dataset_root)):
        person_path = os.path.join(dataset_root, person)
        if os.path.isdir(person_path):
            out.append((person, person_path))
    return out


def select_one_image_per_person(
    person_dirs: List[Tuple[str, str]],
    random_seed: int = 42,
) -> Dict[str, str]:
    """
    Select exactly one image per person randomly.
    """
    selected: Dict[str, str] = {}
    rng = random.Random(random_seed)
    
    for person, person_path in person_dirs:
        image_files = [f for f in sorted(os.listdir(person_path)) if is_image_file(f)]
        if not image_files:
            continue
        # Randomly select one image
        selected_image = rng.choice(image_files)
        selected[person] = os.path.join(person_path, selected_image)
    
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
    raw_distance: float
    distance: float
    
    def is_false_positive(self, threshold: float) -> bool:
        """True if distance <= threshold (incorrectly matches different identity)."""
        return self.distance <= threshold


def preprocess_and_extract_faces(
    selected_images: Dict[str, str],
    face_cascade: cv.CascadeClassifier | None,
    eye_cascade: cv.CascadeClassifier | None,
    min_face_size: int,
    align_eyes: bool,
    equalization: str,
    downscale_max_side: int,
) -> Tuple[Dict[str, np.ndarray], Dict[str, int], PreprocessStats]:
    """
    Preprocess selected images and extract faces.
    Returns: (faces_dict, label_map, stats)
    """
    faces: Dict[str, np.ndarray] = {}
    label_map: Dict[str, int] = {}
    stats = PreprocessStats()
    
    for label_id, (person, image_path) in enumerate(sorted(selected_images.items())):
        label_map[person] = label_id
        stats.processed += 1
        
        img = cv.imread(image_path)
        if img is None:
            stats.skipped_unreadable += 1
            continue
        
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        
        if ASSUME_INPUTS_ARE_CROPPED:
            # Bypass detection and alignment if inputs are already cropped faces
            processed_face = normalize_face(gray, img_size=IMG_SIZE, equalization=equalization)
            faces[person] = processed_face
            stats.successful += 1
            continue

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
        )
        
        if processed.face is None:
            if processed.reason == "image_too_small":
                stats.skipped_too_small += 1
            else:
                stats.skipped_no_face += 1
            continue
        
        faces[person] = processed.face
        stats.successful += 1
    
    return faces, label_map, stats


def compute_pairwise_distances(
    selected_images: Dict[str, str],
    faces: Dict[str, np.ndarray],
    label_map: Dict[str, int],
) -> List[ComparisonRecord]:
    """
    Train a single multi-identity Eigenfaces model on all faces, extract PCA
    projections from the saved model, and compute N×(N-1) pairwise Euclidean
    distances.  All raw distances are then normalised to the [0, 100] scale
    so results are comparable across models.
    """
    identities = sorted(faces.keys())
    n = len(identities)

    feature_matrix, identities_sorted = train_and_extract_features(
        faces, label_map, model_type="eigenfaces",
    )

    records_data = common_pairwise_distances(
        feature_matrix, identities_sorted, model_type="eigenfaces",
    )

    # Attach image paths from selected_images
    records: List[ComparisonRecord] = []
    for rd in records_data:
        records.append(ComparisonRecord(
            query_identity=rd["query_identity"],
            query_image_path=selected_images.get(rd["query_identity"], ""),
            candidate_identity=rd["candidate_identity"],
            candidate_image_path=selected_images.get(rd["candidate_identity"], ""),
            raw_distance=rd["raw_distance"],
            distance=rd["normalized_distance"],
        ))

    return records


@dataclass
class DistanceStats:
    min_distance: float = float('inf')
    max_distance: float = float('-inf')
    mean_distance: float = 0.0
    median_distance: float = 0.0
    std_dev: float = 0.0
    percentiles: Dict[float, float] = field(default_factory=dict)
    count: int = 0


def compute_distance_statistics(distances: List[float]) -> DistanceStats:
    """Compute comprehensive distance statistics."""
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
    
    # Compute percentiles
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        stats.percentiles[p] = float(np.percentile(arr, p))
    
    return stats


def suggest_thresholds(stats: DistanceStats) -> Dict[str, float]:
    """Suggest threshold values based on statistics."""
    suggestions: Dict[str, float] = {}
    
    suggestions["percentile_1"] = stats.percentiles.get(1, stats.min_distance)
    suggestions["percentile_5"] = stats.percentiles.get(5, stats.min_distance)
    suggestions["percentile_10"] = stats.percentiles.get(10, stats.min_distance)
    suggestions["min_distance"] = stats.min_distance
    
    if stats.std_dev > 0:
        suggestions["mean_minus_1std"] = max(
            0.0,
            stats.mean_distance - stats.std_dev
        )
    
    return suggestions


def analyze_false_positives(
    records: List[ComparisonRecord],
    threshold: float,
) -> Dict:
    """Analyze false positives at given threshold."""
    false_positives = [r for r in records if r.is_false_positive(threshold)]
    fp_rate = 100.0 * len(false_positives) / len(records) if records else 0.0
    
    return {
        "threshold": threshold,
        "false_positive_count": len(false_positives),
        "total_comparisons": len(records),
        "false_positive_rate_percent": fp_rate,
    }


def save_csv_results(
    records: List[ComparisonRecord],
    output_path: str,
) -> None:
    """Save all comparison records to CSV with normalized distance."""
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
            writer.writerow({
                "query_identity": record.query_identity,
                "query_image_path": record.query_image_path,
                "candidate_identity": record.candidate_identity,
                "candidate_image_path": record.candidate_image_path,
                "distance_normalized": f"{record.distance:.6f}",
            })
    
    print(f"[SAVE] CSV results: {output_path}")


def save_json_results(
    summary: Dict,
    output_path: str,
) -> None:
    """Save summary report to JSON."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"[SAVE] JSON summary: {output_path}")


def print_report(
    summary: Dict,
    records: List[ComparisonRecord],
) -> None:
    """Print human-readable console report."""
    print("\n" + "="*80)
    print("EIGENFACES INDEPENDENCE TEST REPORT (AGGREGATED)")
    print("="*80)
    
    print("\n[DATASET]")
    dataset_info = summary.get("dataset", {})
    print(f"  Dataset path: {dataset_info.get('path', 'N/A')}")
    print(f"  Total identities discovered: {dataset_info.get('total_identities', 0)}")
    print(f"  Identities selected: {dataset_info.get('selected_identities', 0)}")
    
    print("\n[DISTANCE STATISTICS (Normalized 0-100)]")
    stats_data = summary.get('distance_statistics', {})
    print(f"  Min: {stats_data.get('min_distance', 'N/A'):.4f}")
    print(f"  Max: {stats_data.get('max_distance', 'N/A'):.4f}")
    print(f"  Mean: {stats_data.get('mean_distance', 'N/A'):.4f}")
    print(f"  Median: {stats_data.get('median_distance', 'N/A'):.4f}")
    print(f"  Std Dev: {stats_data.get('std_dev', 'N/A'):.4f}")
    
    print("\n[PERCENTILES (Normalized 0-100)]")
    percentiles = stats_data.get('percentiles', {})
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        value = percentiles.get(p, "N/A")
        if isinstance(value, (int, float)):
            print(f"  {p:3d}th: {value:.4f}")
    
    if "false_positive_analysis" in summary:
        fp = summary['false_positive_analysis']
        print("\n[FALSE POSITIVE ANALYSIS]")
        print(f"  Threshold (normalized): {fp.get('threshold', 'N/A'):.2f}")
        print(f"  False positives: {fp.get('false_positive_count', 0)}")
        print(f"  False positive rate: {fp.get('false_positive_rate_percent', 0.0):.2f}%")
    
    if summary.get("error_pair_thresholds"):
        print()
        print(format_error_pair_report(summary["error_pair_thresholds"]))

    print("\n[TOP 10 CLOSEST CROSS-IDENTITY MATCHES (normalized 0-100)]")
    sorted_records = sorted(records, key=lambda r: r.distance)[:10]
    for idx, record in enumerate(sorted_records, start=1):
        print(
            f"  {idx:2d}. {record.query_identity:20s} vs {record.candidate_identity:20s} "
            f"dist={record.distance:8.4f}"
        )
    
    print("\n" + "="*80)


def run_eigenfaces_independence_test() -> int:
    """Main entry point for independence test."""
    args = parse_args()
    args.dataset_dir = resolve_path(args.dataset_dir)
    args.cascade_path = resolve_path(args.cascade_path)
    args.eye_cascade_path = resolve_path(resolve_eye_cascade_path(args.eye_cascade_path))
    args.output_dir = resolve_path(args.output_dir)
    
    print("[INFO] Eigenfaces Independence Test (Aggregated 10x)")
    print(f"[INFO] Dataset: {args.dataset_dir}")
    
    # Load cascades
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
    
    # Gather person directories
    person_dirs = get_person_dirs(args.dataset_dir)
    if len(person_dirs) < 2:
        print("[ERROR] Need at least 2 identities.")
        return 1
    
    all_runs_records = []
    
    for i in range(args.iterations):
        print(f"\n[ITERATION {i+1}/{args.iterations}]")
        
        # Select one image per person
        selected_images = select_one_image_per_person(person_dirs, args.random_seed + i)
        if len(selected_images) < 2:
            print(f"[WARN] Iteration {i+1}: Not enough images selected.")
            continue
        
        # Preprocess and extract faces
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
            print(f"[WARN] Iteration {i+1}: Not enough faces extracted.")
            continue
        
        # Compute pairwise distances
        records = compute_pairwise_distances(selected_images, faces, label_map)
        
        # Save raw results for this run
        run_dir = os.path.join(args.output_dir, "_raw_runs", f"run_{i+1}")
        save_csv_results(records, os.path.join(run_dir, "comparisons.csv"))
        
        # Store for aggregation
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
    
    if not all_runs_records:
        print("[ERROR] No successful iterations.")
        return 1
    
    # Aggregate results
    print("\n[AGGREGATE] Computing mean distances across iterations...")
    aggregated_records_data = aggregate_pairwise_results(all_runs_records)
    
    records = [
        ComparisonRecord(
            query_identity=rd["query_identity"],
            query_image_path=rd["query_image_path"],
            candidate_identity=rd["candidate_identity"],
            candidate_image_path=rd["candidate_image_path"],
            raw_distance=rd["raw_distance"],
            distance=rd["normalized_distance"],
        )
        for rd in aggregated_records_data
    ]
    
    # Compute statistics
    distances = [r.distance for r in records]
    distance_stats = compute_distance_statistics(distances)
    
    # Build summary
    summary: Dict = {
        "dataset": {
            "path": args.dataset_dir,
            "total_identities": len(person_dirs),
            "selected_identities": len({r["query_identity"] for r in aggregated_records_data}),
        },
        "distance_statistics": {
            "min_distance": distance_stats.min_distance,
            "max_distance": distance_stats.max_distance,
            "mean_distance": distance_stats.mean_distance,
            "median_distance": distance_stats.median_distance,
            "std_dev": distance_stats.std_dev,
            "percentiles": distance_stats.percentiles,
        },
        "suggested_thresholds": suggest_thresholds(distance_stats),
        "error_pair_thresholds": error_pair_report(
            aggregated_records_data,
            target_far_ppm=args.target_far_ppm,
            explicit_rank=args.error_pair_rank,
        ),
        "iterations": args.iterations,
    }
    
    if args.threshold is not None:
        summary["false_positive_analysis"] = analyze_false_positives(records, args.threshold)
    
    # Save final results
    csv_path = os.path.join(args.output_dir, "comparisons.csv")
    json_path = os.path.join(args.output_dir, "summary.json")
    save_csv_results(records, csv_path)
    save_json_results(summary, json_path)
    
    # Print report
    print_report(summary, records)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_eigenfaces_independence_test())
