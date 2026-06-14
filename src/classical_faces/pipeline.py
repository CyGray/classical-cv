"""Shared train/evaluate engine for LBPH, Eigenfaces and Fisherfaces.

The three recognizers differ only in a small ``RecognizerSpec`` (the OpenCV
factory, default unknown-threshold, default sweep, and a feature-size formula).
Everything else - preprocessing, dataset gathering, the evaluation loop, the
metrics, and the on-disk report schema - lives here so the pipelines cannot
drift apart again.

Key contract decisions (see ``docs/READ THIS/CLASSICAL_TRACK_AUDIT.md``):

* No full-image fallback. A Haar miss is counted as ``skipped_no_face``; it is
  never silently fed to the recognizer as a whole frame.
* No skip-unseen. Identities absent from the label map are treated as
  impostors (open-set), so the report is honest about both recognition and
  rejection. When every test identity is enrolled (the closed-set
  ``split_lasalle`` loop) the impostor counters are simply zero.
* One report schema with ``hit_rate_percent`` as the primary metric for all
  three, plus the open-set known/unknown/balanced fields and detection +
  footprint blocks.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

import cv2 as cv
import numpy as np

from src.classical_faces.datasets import root_path, sample_image_files
from src.classical_faces.detection import (
    DEFAULT_YUNET_NMS_THRESHOLD,
    DEFAULT_YUNET_SCORE_THRESHOLD,
    VALID_BACKENDS,
    FaceDetector,
    create_face_detector,
    resolve_default_backend,
)
from src.classical_faces.preprocess import (
    IMG_SIZE,
    extract_classical_face,
    resolve_eye_cascade_path,
)
from src.reporting.identity import attach_entity_identity, build_dataset_profile


# --------------------------------------------------------------------------- #
# Recognizer specifications
# --------------------------------------------------------------------------- #
def _lbph_feature_bytes(recognizer) -> int:
    try:
        grid_x = int(recognizer.getGridX())
        grid_y = int(recognizer.getGridY())
        neighbors = int(recognizer.getNeighbors())
        return grid_x * grid_y * (2 ** neighbors) * 4
    except Exception:
        return 8 * 8 * 256 * 4


def _subspace_feature_bytes(recognizer) -> int:
    # Feature vector dimension = number of retained subspace components, which is
    # the number of columns of the eigenvector matrix (Eigen: n_samples,
    # Fisher: n_classes - 1). getEigenValues() stores them on an inconsistent
    # axis between the two recognizers, so read the eigenvectors instead.
    try:
        vectors = recognizer.getEigenVectors()
        if vectors is None:
            return 0
        return int(vectors.shape[1]) * 4
    except Exception:
        return 0


@dataclass(frozen=True)
class RecognizerSpec:
    family: str
    # Factory accepting ``num_components`` (ignored by LBPH; 0 = library default,
    # i.e. all samples for Eigen / classes-1 for Fisher).
    create: Callable[..., "cv.face.BasicFaceRecognizer"]
    default_unknown_threshold: float
    default_threshold_sweep: tuple[float, ...]
    feature_bytes: Callable[[object], int]
    # Per-family contract defaults. Trainer/evaluator/live/benchmark wrappers all
    # read these so the preprocessing + model shape cannot drift between stages.
    default_num_components: int = 0
    default_equalization: str = "equalize"


# Default unknown-thresholds are CALIBRATED values: the deployable threshold at
# the project-spec FAR budget (0.01% = 100 ppm) measured against 13,149 LFW
# impostors on each family's native predict() scale
# (reports/benchmark/tar_at_far.md, 2026-06-10). At that threshold LBPH holds
# TAR 98.21% / FRR 1.79%; Eigen/Fisher fail TAR at any FAR <= 1%.

LBPH_SPEC = RecognizerSpec(
    family="lbph",
    create=lambda num_components=0: cv.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8
    ),
    default_unknown_threshold=73.0,
    default_threshold_sweep=(40, 50, 55, 60, 65, 70, 73, 75, 77, 80, 85, 90, 100, 110),
    feature_bytes=_lbph_feature_bytes,
    # Tan-Triggs illumination normalization: measured on the clean held-out split
    # it lifts LBPH from 96.4% to 100% rank-1 and cuts the EER vs LFW impostors
    # from 3.6% to ~0.07% (see reports/benchmark/classical_config_sweep.md).
    # Eigen/Fisher stay on plain equalization - Tan-Triggs strips the
    # low-frequency content their subspaces rely on.
    default_equalization="tan-triggs",
)

EIGEN_SPEC = RecognizerSpec(
    family="eigenfaces",
    create=lambda num_components=0: cv.face.EigenFaceRecognizer_create(
        num_components=int(num_components)
    ),
    default_unknown_threshold=4308.0,
    default_threshold_sweep=(1000, 2000, 3000, 4000, 4308, 5000, 5283, 6000, 7000, 9000),
    feature_bytes=_subspace_feature_bytes,
)

FISHER_SPEC = RecognizerSpec(
    family="fisherfaces",
    create=lambda num_components=0: cv.face.FisherFaceRecognizer_create(
        num_components=int(num_components)
    ),
    default_unknown_threshold=738.0,
    default_threshold_sweep=(200, 300, 400, 500, 600, 738, 800, 922, 1000, 1500),
    feature_bytes=_subspace_feature_bytes,
)

SPECS: dict[str, RecognizerSpec] = {
    "lbph": LBPH_SPEC,
    "eigenfaces": EIGEN_SPEC,
    "fisherfaces": FISHER_SPEC,
}


# --------------------------------------------------------------------------- #
# Preprocessing configuration + cascade loading
# --------------------------------------------------------------------------- #
@dataclass
class PreprocessConfig:
    assume_cropped: bool = False
    align_eyes: bool = False
    equalization: str = "equalize"
    min_face_size: int = 40
    scale_factor: float = 1.1
    min_neighbors: int = 5
    downscale_max_side: int = 0
    img_size: tuple[int, int] = IMG_SIZE
    # Detection backend for raw / live inputs (ignored under assume_cropped):
    # "haar" (Viola-Jones cascade) or "yunet" (CNN). See src/classical_faces/detection.py.
    detector_backend: str = "haar"
    yunet_model_path: str = ""
    yunet_score_threshold: float = DEFAULT_YUNET_SCORE_THRESHOLD
    yunet_nms_threshold: float = DEFAULT_YUNET_NMS_THRESHOLD


def build_preprocess_config(args: argparse.Namespace) -> PreprocessConfig:
    return PreprocessConfig(
        assume_cropped=bool(getattr(args, "assume_cropped", False)),
        align_eyes=bool(getattr(args, "align_eyes", False)),
        equalization=getattr(args, "equalization", "equalize"),
        min_face_size=int(getattr(args, "min_face_size", 40)),
        scale_factor=float(getattr(args, "scale_factor", 1.1)),
        min_neighbors=int(getattr(args, "min_neighbors", 5)),
        downscale_max_side=int(getattr(args, "downscale_max_side", 0)),
        detector_backend=str(getattr(args, "detector", "haar") or "haar").strip().lower(),
        yunet_model_path=str(getattr(args, "yunet_model_path", "") or ""),
        yunet_score_threshold=float(
            getattr(args, "yunet_score_threshold", DEFAULT_YUNET_SCORE_THRESHOLD)
        ),
        yunet_nms_threshold=float(
            getattr(args, "yunet_nms_threshold", DEFAULT_YUNET_NMS_THRESHOLD)
        ),
    )


def build_detectors(
    *,
    face_cascade_path: str,
    eye_cascade_path: str,
    preprocess: PreprocessConfig,
) -> tuple[FaceDetector | None, cv.CascadeClassifier | None]:
    """Build the face detector (Haar or YuNet) + the optional eye cascade.

    Returns ``(None, eye_cascade)`` under ``assume_cropped``: cropped inputs skip
    detection entirely (the image *is* the face), so the backend choice is moot
    for the clean-split loop. Detection only runs for raw photos and the live
    webcam path -- which is exactly where Haar and YuNet differ.
    """
    detector: FaceDetector | None = None
    if not preprocess.assume_cropped:
        detector = create_face_detector(
            preprocess.detector_backend,
            cascade_path=face_cascade_path,
            yunet_model_path=preprocess.yunet_model_path or None,
            min_face_size=preprocess.min_face_size,
            scale_factor=preprocess.scale_factor,
            min_neighbors=preprocess.min_neighbors,
            downscale_max_side=preprocess.downscale_max_side,
            yunet_score_threshold=preprocess.yunet_score_threshold,
            yunet_nms_threshold=preprocess.yunet_nms_threshold,
        )

    eye_cascade: cv.CascadeClassifier | None = None
    if preprocess.align_eyes:
        resolved = resolve_eye_cascade_path(eye_cascade_path)
        eye_cascade = cv.CascadeClassifier(resolved)
        if eye_cascade.empty():
            print(f"[WARN] Could not load eye cascade at {resolved}. Alignment disabled.")
            eye_cascade = None
    return detector, eye_cascade


# Backward-compatible alias: older imports referenced ``load_cascades``. It now
# returns a (FaceDetector | None, eye_cascade) pair -- the first element is a
# detector object, not a raw cascade.
load_cascades = build_detectors


def _preprocess_image(
    image_gray: np.ndarray,
    *,
    preprocess: PreprocessConfig,
    detector: FaceDetector | None,
    eye_cascade: cv.CascadeClassifier | None,
    image_bgr: np.ndarray | None = None,
):
    return extract_classical_face(
        image_gray=image_gray,
        face_cascade=None,
        min_face_size=preprocess.min_face_size,
        scale_factor=preprocess.scale_factor,
        min_neighbors=preprocess.min_neighbors,
        img_size=preprocess.img_size,
        equalization=preprocess.equalization,
        align_eyes=preprocess.align_eyes,
        eye_cascade=eye_cascade,
        downscale_max_side=preprocess.downscale_max_side,
        assume_already_cropped=preprocess.assume_cropped,
        detector=detector,
        image_bgr=image_bgr,
    )


# --------------------------------------------------------------------------- #
# Stats + metrics (open-set aware, single schema)
# --------------------------------------------------------------------------- #
@dataclass
class Stats:
    total_images: int = 0
    evaluated_images: int = 0
    correct: int = 0
    known_total: int = 0
    known_correct: int = 0
    unknown_total: int = 0
    unknown_correct: int = 0
    predicted_known: int = 0
    predicted_unknown: int = 0
    face_detected: int = 0
    face_aligned: int = 0
    skipped_unreadable: int = 0
    skipped_no_face: int = 0
    skipped_too_small: int = 0


def _rates(stats: Stats) -> dict:
    eval_count = stats.evaluated_images
    overall_acc = (100.0 * stats.correct / eval_count) if eval_count else 0.0
    known_acc = (100.0 * stats.known_correct / stats.known_total) if stats.known_total else 0.0
    unknown_reject = (
        (100.0 * stats.unknown_correct / stats.unknown_total) if stats.unknown_total else 0.0
    )
    balanced = (
        0.5 * (known_acc + unknown_reject) if (stats.known_total and stats.unknown_total) else 0.0
    )
    return {
        "overall_acc": overall_acc,
        "known_acc": known_acc,
        "unknown_reject": unknown_reject,
        "balanced": balanced,
    }


def summarize_bucket(name: str, stats: Stats) -> str:
    r = _rates(stats)
    return (
        f"{name:<20} total={stats.total_images:<6} eval={stats.evaluated_images:<6} "
        f"hit={r['overall_acc']:6.2f}% known={r['known_acc']:6.2f}% "
        f"unk_rej={r['unknown_reject']:6.2f}% bal={r['balanced']:6.2f}% "
        f"detected={stats.face_detected:<6} aligned={stats.face_aligned:<6}"
    )


def bucket_to_dict(name: str, stats: Stats) -> dict:
    r = _rates(stats)
    return {
        "bucket": name,
        "total_images": stats.total_images,
        "evaluated_images": stats.evaluated_images,
        "correct": stats.correct,
        # Primary metric for all three recognizers:
        "hit_rate_percent": r["overall_acc"],
        # Back-compat alias for older LBPH consumers:
        "overall_accuracy_percent": r["overall_acc"],
        "known_total": stats.known_total,
        "known_correct": stats.known_correct,
        "known_accuracy_percent": r["known_acc"],
        "unknown_total": stats.unknown_total,
        "unknown_correct": stats.unknown_correct,
        "unknown_rejection_rate_percent": r["unknown_reject"],
        "balanced_accuracy_percent": r["balanced"],
        "predicted_known": stats.predicted_known,
        "predicted_unknown": stats.predicted_unknown,
        "face_detected": stats.face_detected,
        "face_aligned": stats.face_aligned,
        "skipped_unreadable": stats.skipped_unreadable,
        "skipped_no_face": stats.skipped_no_face,
        "skipped_too_small": stats.skipped_too_small,
    }


def threshold_metrics(records: list[dict], threshold: float) -> dict:
    total = len(records)
    known_total = sum(1 for r in records if r["is_known_truth"])
    unknown_total = total - known_total

    known_correct = 0
    unknown_correct = 0
    overall_correct = 0

    for r in records:
        dist = float(r["distance"])
        best_name = r["best_name"]
        pred = best_name if (best_name != "Unknown" and dist <= threshold) else "Unknown"
        if r["is_known_truth"]:
            if pred == r["truth"]:
                known_correct += 1
                overall_correct += 1
        else:
            if pred == "Unknown":
                unknown_correct += 1
                overall_correct += 1

    known_acc = (100.0 * known_correct / known_total) if known_total else 0.0
    unknown_reject = (100.0 * unknown_correct / unknown_total) if unknown_total else 0.0
    balanced = 0.5 * (known_acc + unknown_reject) if (known_total and unknown_total) else 0.0
    overall_acc = (100.0 * overall_correct / total) if total else 0.0

    return {
        "threshold": threshold,
        "overall_total": total,
        "overall_correct": overall_correct,
        "overall_accuracy_percent": overall_acc,
        "overall_hit_rate_percent": overall_acc,
        "known_total": known_total,
        "known_correct": known_correct,
        "known_accuracy_percent": known_acc,
        "unknown_total": unknown_total,
        "unknown_correct": unknown_correct,
        "unknown_rejection_rate_percent": unknown_reject,
        "balanced_accuracy_percent": balanced,
    }


def compute_threshold_sweep(eval_records: list[dict], thresholds: list[float]) -> list[dict]:
    sweep = []
    buckets = sorted({r["bucket"] for r in eval_records})
    for thr in thresholds:
        overall = threshold_metrics(eval_records, thr)
        by_bucket = {
            bucket: threshold_metrics([r for r in eval_records if r["bucket"] == bucket], thr)
            for bucket in buckets
        }
        sweep.append({**overall, "by_bucket": by_bucket})
    return sweep


def best_sweep_entry(sweep: list[dict]) -> dict | None:
    if not sweep:
        return None
    return max(sweep, key=lambda e: e.get("overall_hit_rate_percent", 0.0))


def rank1_metrics(records: list[dict]) -> dict:
    """Closed-set rank-1 identification accuracy (nearest neighbour, no threshold).

    This is the honest recognition number for a closed-set held-out test (every
    test identity is enrolled, so there are no impostors to reject). It does not
    depend on the unknown-threshold, which only matters in the open-set case.
    """
    known_records = [r for r in records if r["is_known_truth"]]
    total = len(known_records)
    correct = sum(1 for r in known_records if r["best_name"] == r["truth"])
    return {
        "known_total": total,
        "correct": correct,
        "accuracy_percent": (100.0 * correct / total) if total else 0.0,
    }


# --------------------------------------------------------------------------- #
# Progress + footprint helpers
# --------------------------------------------------------------------------- #
def format_seconds(seconds: float) -> str:
    secs = max(0, int(seconds))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def print_progress(processed: int, total: int, start_time: float, status: str) -> None:
    if total <= 0:
        return
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0.0
    remaining = max(0, total - processed)
    eta = remaining / rate if rate > 0 else 0.0
    pct = 100.0 * processed / total
    bar_width = 28
    filled = int(bar_width * processed / total)
    bar = "#" * filled + "-" * (bar_width - filled)
    msg = (
        f"\r[PROGRESS] [{bar}] {processed}/{total} ({pct:6.2f}%) "
        f"| elapsed {format_seconds(elapsed)} | eta {format_seconds(eta)} "
        f"| {rate:6.2f} img/s | {status:<28}"
    )
    sys.stdout.write(msg)
    sys.stdout.flush()


def model_file_bytes(path: str) -> int:
    try:
        return int(os.path.getsize(path))
    except OSError:
        return 0


def _plan_entries(
    entries: list[tuple[str, str, str]],
    *,
    max_images_per_person: int,
    random_seed: int,
    cap_per_bucket: bool,
) -> tuple[list[tuple[str, str, str, list[str]]], int]:
    planned: list[tuple[str, str, str, list[str]]] = []
    used: dict = defaultdict(int)
    total = 0
    for bucket, person, folder in entries:
        if not os.path.isdir(folder):
            continue
        key = (bucket, person) if cap_per_bucket else person
        files = sample_image_files(
            folder,
            max_images=max_images_per_person,
            already_used=used[key],
            bucket=bucket,
            person=person,
            random_seed=random_seed,
        )
        if not files:
            continue
        used[key] += len(files)
        planned.append((bucket, person, folder, files))
        total += len(files)
    return planned, total


# --------------------------------------------------------------------------- #
# Recognizer / label IO
# --------------------------------------------------------------------------- #
def load_recognizer(spec: RecognizerSpec, model_path: str):
    recognizer = spec.create()
    recognizer.read(model_path)
    return recognizer


def load_label_map(labels_path: str) -> tuple[dict, dict, set[str]]:
    with open(labels_path, "r", encoding="utf-8") as f:
        label_map = json.load(f)
    id_to_name = {int(v): k for k, v in label_map.items()}
    known_names = set(label_map.keys())
    return label_map, id_to_name, known_names


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def run_training(
    spec: RecognizerSpec,
    *,
    entries: list[tuple[str, str, str]],
    preprocess: PreprocessConfig,
    detector: FaceDetector | None,
    eye_cascade: cv.CascadeClassifier | None,
    max_images_per_person: int,
    random_seed: int,
    model_output: str,
    labels_output: str,
    progress_interval: int = 25,
    num_components: int | None = None,
) -> dict:
    planned, total_planned = _plan_entries(
        entries,
        max_images_per_person=max_images_per_person,
        random_seed=random_seed,
        cap_per_bucket=False,
    )
    if total_planned == 0:
        raise RuntimeError("No training images found after planning. Check dataset paths.")

    faces: list[np.ndarray] = []
    labels: list[int] = []
    label_map: dict[str, int] = {}
    person_counts: dict[str, int] = defaultdict(int)
    bucket_counts: dict[str, int] = defaultdict(int)
    stats = Stats()

    start_time = time.time()
    processed = 0
    for bucket, person, _folder, files in planned:
        if person not in label_map:
            label_map[person] = len(label_map)
        label_id = label_map[person]

        for image_name in files:
            processed += 1
            stats.total_images += 1
            if processed == 1 or processed % max(1, progress_interval) == 0 or processed == total_planned:
                print_progress(processed, total_planned, start_time, f"load/{person}")

            image_path = os.path.join(_folder, image_name)
            img = cv.imread(image_path)
            if img is None:
                stats.skipped_unreadable += 1
                continue
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            result = _preprocess_image(
                gray,
                preprocess=preprocess,
                detector=detector,
                eye_cascade=eye_cascade,
                image_bgr=img,
            )
            if result.face is None:
                if result.reason == "image_too_small":
                    stats.skipped_too_small += 1
                else:
                    stats.skipped_no_face += 1
                continue

            faces.append(result.face)
            labels.append(label_id)
            stats.face_detected += 1
            if result.used_alignment:
                stats.face_aligned += 1
            person_counts[person] += 1
            bucket_counts[bucket] += 1

    if total_planned > 0:
        print_progress(processed, total_planned, start_time, "done")
        print()

    if not faces:
        raise RuntimeError("No training faces extracted. Cannot train model.")

    resolved_components = (
        spec.default_num_components if num_components is None else int(num_components)
    )
    recognizer = spec.create(num_components=resolved_components)
    train_start = time.time()
    recognizer.train(faces, np.array(labels, dtype=np.int32))
    train_time = time.time() - train_start

    os.makedirs(os.path.dirname(model_output), exist_ok=True)
    os.makedirs(os.path.dirname(labels_output), exist_ok=True)
    recognizer.save(model_output)
    with open(labels_output, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)

    total_time = time.time() - start_time
    return {
        "family": spec.family,
        "identities": len(label_map),
        "used_samples": len(faces),
        "skipped_unreadable": stats.skipped_unreadable,
        "skipped_no_face": stats.skipped_no_face,
        "skipped_too_small": stats.skipped_too_small,
        "face_aligned": stats.face_aligned,
        "person_counts": dict(person_counts),
        "bucket_counts": dict(bucket_counts),
        "train_time_seconds": train_time,
        "total_time_seconds": total_time,
        "model_output": model_output,
        "labels_output": labels_output,
        "model_file_bytes": model_file_bytes(model_output),
        "feature_vector_bytes": spec.feature_bytes(recognizer),
        "num_components": resolved_components,
    }


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def run_evaluation(
    spec: RecognizerSpec,
    *,
    entries: list[tuple[str, str, str]],
    recognizer,
    known_names: set[str],
    id_to_name: dict[int, str],
    preprocess: PreprocessConfig,
    detector: FaceDetector | None,
    eye_cascade: cv.CascadeClassifier | None,
    unknown_threshold: float,
    threshold_sweep: list[float],
    max_images_per_person: int,
    random_seed: int,
    model_path: str,
    labels_path: str,
    dataset_profile: dict,
    model_variant: str,
    run_tag: str = "",
    report_json: str | None = None,
    show_misclassified: int = 15,
    extra_config: dict | None = None,
) -> dict:
    planned, total_planned = _plan_entries(
        entries,
        max_images_per_person=max_images_per_person,
        random_seed=random_seed,
        cap_per_bucket=True,
    )

    per_bucket_stats: dict[str, Stats] = defaultdict(Stats)
    overall = Stats()
    misclassified: list[dict] = []
    eval_records: list[dict] = []

    start_time = time.time()
    processed = 0
    for bucket, person, folder, files in planned:
        bstats = per_bucket_stats[bucket]
        for image_name in files:
            processed += 1
            if processed == 1 or processed % 25 == 0 or processed == total_planned:
                print_progress(processed, total_planned, start_time, f"{bucket}/{person}")

            image_path = os.path.join(folder, image_name)
            bstats.total_images += 1
            overall.total_images += 1

            img = cv.imread(image_path)
            if img is None:
                bstats.skipped_unreadable += 1
                overall.skipped_unreadable += 1
                continue
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            result = _preprocess_image(
                gray,
                preprocess=preprocess,
                detector=detector,
                eye_cascade=eye_cascade,
                image_bgr=img,
            )
            if result.face is None:
                if result.reason == "image_too_small":
                    bstats.skipped_too_small += 1
                    overall.skipped_too_small += 1
                else:
                    bstats.skipped_no_face += 1
                    overall.skipped_no_face += 1
                continue

            bstats.evaluated_images += 1
            overall.evaluated_images += 1
            bstats.face_detected += 1
            overall.face_detected += 1
            if result.used_alignment:
                bstats.face_aligned += 1
                overall.face_aligned += 1

            pred_id, distance = recognizer.predict(result.face)
            pred_name = id_to_name.get(pred_id, "Unknown")
            if distance <= unknown_threshold and pred_name != "Unknown":
                predicted_label = pred_name
                bstats.predicted_known += 1
                overall.predicted_known += 1
            else:
                predicted_label = "Unknown"
                bstats.predicted_unknown += 1
                overall.predicted_unknown += 1

            is_known_truth = person in known_names
            if is_known_truth:
                bstats.known_total += 1
                overall.known_total += 1
                is_correct = predicted_label == person
                if is_correct:
                    bstats.known_correct += 1
                    overall.known_correct += 1
            else:
                bstats.unknown_total += 1
                overall.unknown_total += 1
                is_correct = predicted_label == "Unknown"
                if is_correct:
                    bstats.unknown_correct += 1
                    overall.unknown_correct += 1

            if is_correct:
                bstats.correct += 1
                overall.correct += 1
            elif len(misclassified) < show_misclassified:
                misclassified.append(
                    {
                        "bucket": bucket,
                        "truth": person,
                        "truth_known": is_known_truth,
                        "predicted": predicted_label,
                        "best_name": pred_name,
                        "distance": float(distance),
                        "path": image_path,
                    }
                )

            eval_records.append(
                {
                    "bucket": bucket,
                    "truth": person,
                    "is_known_truth": is_known_truth,
                    "best_name": pred_name,
                    "distance": float(distance),
                }
            )

    elapsed = time.time() - start_time
    if total_planned > 0:
        print_progress(min(processed, total_planned), total_planned, start_time, "done")
        print()

    sweep = compute_threshold_sweep(eval_records, threshold_sweep)
    best = best_sweep_entry(sweep)
    rank1 = rank1_metrics(eval_records)

    detection_total = overall.face_detected + overall.skipped_no_face + overall.skipped_too_small
    detection_rate = (100.0 * overall.face_detected / detection_total) if detection_total else 0.0

    config = {
        "unknown_threshold": unknown_threshold,
        "threshold_sweep": ",".join(
            str(int(t)) if float(t).is_integer() else str(t) for t in threshold_sweep
        ),
        "assume_cropped": preprocess.assume_cropped,
        "align_eyes": preprocess.align_eyes,
        "equalization": preprocess.equalization,
        "min_face_size": preprocess.min_face_size,
        "scale_factor": preprocess.scale_factor,
        "min_neighbors": preprocess.min_neighbors,
        "downscale_max_side": preprocess.downscale_max_side,
        "detector_backend": (preprocess.detector_backend if not preprocess.assume_cropped else "none"),
        "detector_detail": (detector.describe() if detector is not None else "none (assume_cropped)"),
        "max_images_per_person": max_images_per_person,
        "random_seed": random_seed,
    }
    if extra_config:
        config.update(extra_config)

    overall_dict = bucket_to_dict("overall", overall)
    overall_dict["closed_set_rank1_percent"] = rank1["accuracy_percent"]

    report = {
        "model_path": model_path,
        "labels_path": labels_path,
        "unknown_threshold": unknown_threshold,
        "elapsed_seconds": elapsed,
        "config": config,
        "buckets": [
            bucket_to_dict(bucket, per_bucket_stats[bucket])
            for bucket in sorted(per_bucket_stats.keys())
        ],
        "overall": overall_dict,
        "rank1": rank1,
        "threshold_sweep": sweep,
        "best_sweep": best,
        "detection": {
            "detected": overall.face_detected,
            "aligned": overall.face_aligned,
            "skipped_no_face": overall.skipped_no_face,
            "skipped_too_small": overall.skipped_too_small,
            "skipped_unreadable": overall.skipped_unreadable,
            "detection_rate_percent": detection_rate,
            "assume_cropped": preprocess.assume_cropped,
            "detector_backend": (preprocess.detector_backend if not preprocess.assume_cropped else "none"),
            "full_image_fallback_used": 0,
        },
        "footprint": {
            "model_file_bytes": model_file_bytes(model_path),
            "feature_vector_bytes": spec.feature_bytes(recognizer),
        },
        "known_vs_unknown": {
            "known_total": overall.known_total,
            "known_correct": overall.known_correct,
            "known_accuracy_percent": _rates(overall)["known_acc"],
            "unknown_total": overall.unknown_total,
            "unknown_correct": overall.unknown_correct,
            "unknown_rejection_rate_percent": _rates(overall)["unknown_reject"],
            "balanced_accuracy_percent": _rates(overall)["balanced"],
        },
        "sample_misclassifications": misclassified,
        "skipped_reasons": {
            "unreadable": overall.skipped_unreadable,
            "no_face": overall.skipped_no_face,
            "too_small": overall.skipped_too_small,
        },
    }

    attach_entity_identity(
        report=report,
        model_family=spec.family,
        dataset_profile=dataset_profile,
        model_variant=model_variant,
        run_tag=run_tag,
    )

    if report_json:
        os.makedirs(os.path.dirname(report_json), exist_ok=True)
        with open(report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report


def print_eval_summary(spec: RecognizerSpec, report: dict) -> None:
    overall = report["overall"]
    det = report["detection"]
    foot = report["footprint"]
    print(f"\n[RESULT] {spec.family} offline evaluation")
    print(f"[INFO] Model: {report['model_path']}")
    print(f"[INFO] Unknown threshold: {report['unknown_threshold']}")
    print(f"[INFO] Evaluated in: {report['elapsed_seconds']:.2f}s")
    rank1 = report.get("rank1", {})
    print(
        f"[OVERALL] hit_rate@thr={overall['hit_rate_percent']:.2f}% "
        f"rank1(closed-set)={rank1.get('accuracy_percent', 0.0):.2f}% "
        f"evaluated={overall['evaluated_images']} "
        f"known={overall['known_total']} unknown={overall['unknown_total']}"
    )
    print(
        f"[DETECTION] detected={det['detected']} aligned={det['aligned']} "
        f"no_face={det['skipped_no_face']} too_small={det['skipped_too_small']} "
        f"rate={det['detection_rate_percent']:.2f}%"
    )
    best = report.get("best_sweep")
    if best:
        print(
            f"[BEST SWEEP] threshold={best['threshold']} "
            f"hit_rate={best['overall_hit_rate_percent']:.2f}%"
        )
    print(
        f"[FOOTPRINT] model={foot['model_file_bytes']} bytes "
        f"feature_vector={foot['feature_vector_bytes']} bytes"
    )


# --------------------------------------------------------------------------- #
# Shared argparse helpers (keep the per-family wrappers thin)
# --------------------------------------------------------------------------- #
def add_dataset_args(
    parser: argparse.ArgumentParser,
    *,
    default_base: str,
    default_raw: str,
    default_include_raw: bool,
    default_aug_splits: str = "light",
) -> None:
    parser.add_argument("--base-data-dir", default=default_base)
    parser.add_argument("--raw-dir-name", default=default_raw)
    parser.add_argument(
        "--include-raw",
        action=argparse.BooleanOptionalAction,
        default=default_include_raw,
        help="Include the raw/train folder.",
    )
    parser.add_argument("--processed-dir-name", default="lasalle_db1_processed")
    parser.add_argument(
        "--include-processed",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--augmented-dir-name", default="augmented41mods")
    parser.add_argument(
        "--include-augmented",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--aug-splits", default=default_aug_splits)


def add_preprocess_args(
    parser: argparse.ArgumentParser,
    *,
    default_assume_cropped: bool = False,
    default_align_eyes: bool = False,
    default_equalization: str = "equalize",
) -> None:
    parser.add_argument(
        "--assume-cropped",
        action=argparse.BooleanOptionalAction,
        default=default_assume_cropped,
        help="Treat inputs as pre-cropped faces (no Haar detection, no fallback).",
    )
    parser.add_argument(
        "--align-eyes",
        action=argparse.BooleanOptionalAction,
        default=default_align_eyes,
        help="Eye-based alignment before equalize/resize. Off by default for cropped tiles.",
    )
    parser.add_argument(
        "--equalization",
        choices=["equalize", "clahe", "tan-triggs"],
        default=default_equalization,
    )
    parser.add_argument("--min-face-size", type=int, default=40)
    parser.add_argument("--scale-factor", type=float, default=1.1)
    parser.add_argument("--min-neighbors", type=int, default=5)
    parser.add_argument("--downscale-max-side", type=int, default=0)
    parser.add_argument(
        "--cascade-path",
        default=root_path("haar", "haarcascade_frontalface_default.xml"),
    )
    parser.add_argument("--eye-cascade-path", default="")
    # --- Face detector toggle (raw / live inputs only; cropped tiles skip it) ---
    parser.add_argument(
        "--detector",
        choices=list(VALID_BACKENDS),
        default=resolve_default_backend(),
        help="Face detection backend: 'haar' (Viola-Jones cascade) or 'yunet' (CNN). "
        "Default from the FACE_G3_DETECTOR env var, else 'haar'. Ignored under "
        "--assume-cropped (pre-cropped tiles are the face already).",
    )
    parser.add_argument(
        "--yunet-model-path",
        default="",
        help="YuNet ONNX weights (default: models/yunet_mobilefacenet/"
        "face_detection_yunet_2023mar.onnx).",
    )
    parser.add_argument(
        "--yunet-score-threshold", type=float, default=DEFAULT_YUNET_SCORE_THRESHOLD
    )
    parser.add_argument(
        "--yunet-nms-threshold", type=float, default=DEFAULT_YUNET_NMS_THRESHOLD
    )


def selected_aug_splits(args: argparse.Namespace) -> set[str]:
    return {s.strip().lower() for s in args.aug_splits.split(",") if s.strip()}


def parse_threshold_sweep(raw: str, default: tuple[float, ...]) -> list[float]:
    values = [float(x.strip()) for x in raw.split(",") if x.strip()]
    return values if values else list(default)


def dataset_profile_from_args(args: argparse.Namespace) -> dict:
    from src.dataset_layout import infer_target_split_name

    target_split = infer_target_split_name(
        raw_dir=args.raw_dir_name, processed_dir=args.processed_dir_name
    )
    return build_dataset_profile(
        base_data_dir=args.base_data_dir,
        raw_dir_name=args.raw_dir_name,
        include_raw=bool(getattr(args, "include_raw", True)),
        processed_dir_name=args.processed_dir_name,
        include_processed=bool(getattr(args, "include_processed", False)),
        augmented_dir_name=args.augmented_dir_name,
        include_augmented=bool(getattr(args, "include_augmented", False)),
        aug_splits=selected_aug_splits(args),
        target_split=target_split,
    )
