"""Reproducible 12-configuration LBPH descriptor ablation.

The ablation varies radius in {1, 2, 3} and square grid size in
{4, 6, 8, 10}, while holding neighbors=8 and the existing 100x100
Tan-Triggs preprocessing contract fixed.  Every configuration receives its
own threshold calibrated from native OpenCV ``predict_collect`` distances.

This script intentionally writes only to ``outputs/provenance_reruns``.  It
does not modify deployed models, ``thresholds.json``, or canonical results.
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classical_faces.detection import create_face_detector
from src.classical_faces.preprocess import IMG_SIZE, normalize_face
from src.hybrid.recognizer import detect_sample


DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "outputs"
    / "provenance_reruns"
    / "lbph_descriptor_ablation_2026-08-14"
)
DEFAULT_LSDB_TRAIN = WORKSPACE_ROOT / "data" / "lsdb" / "split" / "train"
DEFAULT_LSDB_TEST = WORKSPACE_ROOT / "data" / "lsdb" / "split" / "test"
DEFAULT_LFW_ROOT = PROJECT_ROOT / "data" / "lfw-dataset"
DEFAULT_LFW_MANIFEST = PROJECT_ROOT / "data" / "splits" / "lfw_ident_split_seed42.json"

NEIGHBORS = 8
RADII = (1, 2, 3)
GRIDS = (4, 6, 8, 10)
BASELINE_ID = "r1_n8_g8x8"
EQUALIZATION = "tan-triggs"
LSDB_TARGET_FAR = 0.01058
LFW_TARGET_FAR = 10e-6
LSDB_DEV_POSES = ("down", "front", "left", "right", "up")
LSDB_ILLUMINATIONS = ("dark", "light")
LSDB_LOCKED_CALIBRATION_COUNT = 2


@dataclass(frozen=True)
class LBPHConfig:
    radius: int
    grid: int
    neighbors: int = NEIGHBORS

    @property
    def config_id(self) -> str:
        return f"r{self.radius}_n{self.neighbors}_g{self.grid}x{self.grid}"

    @property
    def feature_bytes_per_template(self) -> int:
        return self.grid * self.grid * (2**self.neighbors) * 4

    def to_dict(self) -> dict[str, int | str]:
        return {
            "config_id": self.config_id,
            "radius": self.radius,
            "neighbors": self.neighbors,
            "grid_x": self.grid,
            "grid_y": self.grid,
            "feature_bytes_per_template": self.feature_bytes_per_template,
        }


ALL_CONFIGS = tuple(LBPHConfig(radius, grid) for radius in RADII for grid in GRIDS)
CONFIG_BY_ID = {config.config_id: config for config in ALL_CONFIGS}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    os.replace(temp, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_strings(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def make_recognizer(config: LBPHConfig):
    return cv.face.LBPHFaceRecognizer_create(
        radius=config.radius,
        neighbors=config.neighbors,
        grid_x=config.grid,
        grid_y=config.grid,
    )


def train_recognizer(
    config: LBPHConfig, faces: Sequence[np.ndarray], labels: Sequence[int]
) -> tuple[Any, float]:
    if not faces or len(faces) != len(labels):
        raise ValueError("LBPH training requires equally sized non-empty faces and labels")
    recognizer = make_recognizer(config)
    started = time.perf_counter()
    recognizer.train(list(faces), np.asarray(labels, dtype=np.int32))
    return recognizer, time.perf_counter() - started


def per_label_scores(recognizer: Any, face: np.ndarray) -> dict[int, float]:
    collector = cv.face.StandardCollector_create()
    recognizer.predict_collect(face, collector)
    scores: dict[int, float] = {}
    for label, distance in collector.getResults(False):
        label_int = int(label)
        distance_float = float(distance)
        previous = scores.get(label_int)
        if previous is None or distance_float < previous:
            scores[label_int] = distance_float
    if not scores:
        label, distance = recognizer.predict(face)
        scores[int(label)] = float(distance)
    return scores


def rank_threshold(distances: np.ndarray, target_far: float) -> dict[str, float | int]:
    if distances.ndim != 1 or distances.size == 0:
        raise ValueError("Threshold calibration requires a non-empty 1-D distance array")
    rank = max(1, math.floor(target_far * int(distances.size)))
    rank = min(rank, int(distances.size))
    threshold = float(np.partition(distances, rank - 1)[rank - 1])
    accepted = int(np.count_nonzero(distances <= threshold))
    return {
        "threshold": threshold,
        "target_far": float(target_far),
        "target_far_ppm": float(target_far * 1_000_000.0),
        "impostor_count": int(distances.size),
        "target_rank": int(rank),
        "accepted_impostors_at_threshold": accepted,
        "realized_far": float(accepted / distances.size),
        "realized_far_ppm": float(accepted / distances.size * 1_000_000.0),
    }


def evaluate_identification(
    recognizer: Any,
    samples: Sequence[tuple[int, np.ndarray]],
    threshold: float,
) -> dict[str, Any]:
    rank1 = 0
    tpir = 0
    verification_true_accept = 0
    genuine_distances: list[float] = []
    nearest_distances: list[float] = []
    elapsed = 0.0
    for truth, face in samples:
        started = time.perf_counter()
        scores = per_label_scores(recognizer, face)
        elapsed += time.perf_counter() - started
        predicted, nearest_distance = min(scores.items(), key=lambda item: item[1])
        genuine_distance = float(scores[truth])
        correct = predicted == truth
        accepted = nearest_distance <= threshold
        rank1 += int(correct)
        tpir += int(correct and accepted)
        verification_true_accept += int(genuine_distance <= threshold)
        genuine_distances.append(genuine_distance)
        nearest_distances.append(float(nearest_distance))
    count = len(samples)
    if count == 0:
        raise ValueError("No identification samples were supplied")
    genuine = np.asarray(genuine_distances, dtype=np.float64)
    nearest = np.asarray(nearest_distances, dtype=np.float64)
    return {
        "probe_count": count,
        "rank1_count": rank1,
        "rank1_percent": 100.0 * rank1 / count,
        "tpir_count": tpir,
        "tpir_percent": 100.0 * tpir / count,
        "verification_true_accept_count": verification_true_accept,
        "verification_tpr_percent": 100.0 * verification_true_accept / count,
        "genuine_distance_median": float(np.median(genuine)),
        "genuine_distance_p90": float(np.quantile(genuine, 0.90)),
        "nearest_distance_median": float(np.median(nearest)),
        "score_seconds": elapsed,
        "mean_score_ms": 1000.0 * elapsed / count,
    }


def read_gray(path: Path) -> np.ndarray:
    image = cv.imread(str(path), cv.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return normalize_face(image, img_size=IMG_SIZE, equalization=EQUALIZATION)


def load_lsdb(
    train_root: Path, test_root: Path
) -> tuple[list[str], dict[str, dict[str, np.ndarray]], dict[str, dict[str, np.ndarray]]]:
    identities = sorted(path.name for path in train_root.iterdir() if path.is_dir())
    if not identities:
        raise FileNotFoundError(f"No LSDB identities found under {train_root}")
    train: dict[str, dict[str, np.ndarray]] = {}
    locked: dict[str, dict[str, np.ndarray]] = {}
    missing: list[str] = []
    for identity in identities:
        train[identity] = {}
        locked[identity] = {}
        for pose in LSDB_DEV_POSES:
            for illumination in LSDB_ILLUMINATIONS:
                name = f"{illumination}_{pose}.jpg"
                path = train_root / identity / name
                if not path.is_file():
                    missing.append(str(path))
                else:
                    train[identity][name] = read_gray(path)
        for illumination in LSDB_ILLUMINATIONS:
            name = f"{illumination}_name.jpg"
            path = test_root / identity / name
            if not path.is_file():
                missing.append(str(path))
            else:
                locked[identity][name] = read_gray(path)
    if missing:
        raise FileNotFoundError("Missing expected LSDB images:\n" + "\n".join(missing[:20]))
    return identities, train, locked


def calibrate_from_labeled_samples(
    recognizer: Any,
    samples: Sequence[tuple[int, np.ndarray]],
    target_far: float,
) -> tuple[dict[str, Any], list[float]]:
    impostors: list[float] = []
    genuine: list[float] = []
    for truth, face in samples:
        scores = per_label_scores(recognizer, face)
        genuine.append(float(scores[truth]))
        impostors.extend(float(distance) for label, distance in scores.items() if label != truth)
    calibration = rank_threshold(np.asarray(impostors, dtype=np.float64), target_far)
    threshold = float(calibration["threshold"])
    calibration.update(
        {
            "genuine_count": len(genuine),
            "genuine_tpr_percent": 100.0 * sum(value <= threshold for value in genuine) / len(genuine),
            "genuine_distance_median": float(np.median(np.asarray(genuine))),
        }
    )
    return calibration, genuine


def run_lsdb_dev_config(
    config: LBPHConfig,
    identities: Sequence[str],
    train_rows: dict[str, dict[str, np.ndarray]],
) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    started = time.perf_counter()
    fold_index = 0
    for evaluation_pose in LSDB_DEV_POSES:
        for evaluation_illumination in LSDB_ILLUMINATIONS:
            calibration_illumination = (
                "light" if evaluation_illumination == "dark" else "dark"
            )
            evaluation_name = f"{evaluation_illumination}_{evaluation_pose}.jpg"
            calibration_name = f"{calibration_illumination}_{evaluation_pose}.jpg"
            fit_faces: list[np.ndarray] = []
            fit_labels: list[int] = []
            calibration_samples: list[tuple[int, np.ndarray]] = []
            evaluation_samples: list[tuple[int, np.ndarray]] = []
            for label, identity in enumerate(identities):
                for name, face in sorted(train_rows[identity].items()):
                    if name == evaluation_name:
                        evaluation_samples.append((label, face))
                    elif name == calibration_name:
                        calibration_samples.append((label, face))
                    else:
                        fit_faces.append(face)
                        fit_labels.append(label)
            recognizer, train_seconds = train_recognizer(config, fit_faces, fit_labels)
            calibration, _ = calibrate_from_labeled_samples(
                recognizer, calibration_samples, LSDB_TARGET_FAR
            )
            evaluation = evaluate_identification(
                recognizer, evaluation_samples, float(calibration["threshold"])
            )
            folds.append(
                {
                    "fold": fold_index,
                    "fit_images_per_identity": 8,
                    "calibration_image": calibration_name,
                    "evaluation_image": evaluation_name,
                    "fit_images": len(fit_faces),
                    "train_seconds": train_seconds,
                    "calibration": calibration,
                    "evaluation": evaluation,
                }
            )
            fold_index += 1
            del recognizer
            gc.collect()
    rank1 = np.asarray([fold["evaluation"]["rank1_percent"] for fold in folds])
    tpir = np.asarray([fold["evaluation"]["tpir_percent"] for fold in folds])
    return {
        **config.to_dict(),
        "dataset": "LSDB-development",
        "protocol": (
            "10-fold paired-view CV; one illumination/pose image evaluates, the "
            "opposite illumination of that pose calibrates, and eight images fit"
        ),
        "folds": folds,
        "mean_rank1_percent": float(rank1.mean()),
        "min_rank1_percent": float(rank1.min()),
        "mean_tpir_percent": float(tpir.mean()),
        "min_tpir_percent": float(tpir.min()),
        "total_seconds": time.perf_counter() - started,
    }


def run_lsdb_locked_config(
    config: LBPHConfig,
    identities: Sequence[str],
    train_rows: dict[str, dict[str, np.ndarray]],
    locked_rows: dict[str, dict[str, np.ndarray]],
) -> dict[str, Any]:
    fit_faces: list[np.ndarray] = []
    fit_labels: list[int] = []
    calibration_samples: list[tuple[int, np.ndarray]] = []
    evaluation_samples: list[tuple[int, np.ndarray]] = []
    calibration_names: list[str] | None = None
    for label, identity in enumerate(identities):
        ordered = sorted(train_rows[identity])
        fit_names = ordered[:-LSDB_LOCKED_CALIBRATION_COUNT]
        current_calibration_names = ordered[-LSDB_LOCKED_CALIBRATION_COUNT:]
        if calibration_names is None:
            calibration_names = current_calibration_names
        elif calibration_names != current_calibration_names:
            raise AssertionError("LSDB identities do not share the stable filename split")
        for name in fit_names:
            fit_faces.append(train_rows[identity][name])
            fit_labels.append(label)
        for name in current_calibration_names:
            calibration_samples.append((label, train_rows[identity][name]))
        for illumination in LSDB_ILLUMINATIONS:
            evaluation_samples.append(
                (label, locked_rows[identity][f"{illumination}_name.jpg"])
            )
    recognizer, train_seconds = train_recognizer(config, fit_faces, fit_labels)
    calibration, _ = calibrate_from_labeled_samples(recognizer, calibration_samples, LSDB_TARGET_FAR)
    evaluation = evaluate_identification(
        recognizer, evaluation_samples, float(calibration["threshold"])
    )
    del recognizer
    gc.collect()
    return {
        **config.to_dict(),
        "dataset": "LSDB-locked-name-views",
        "fit_rule": "first eight lexicographically sorted train filenames",
        "calibration_images": calibration_names,
        "evaluation_pose": "name",
        "fit_images": len(fit_faces),
        "train_seconds": train_seconds,
        "calibration": calibration,
        "evaluation": evaluation,
    }


def stable_order(names: Iterable[str], seed: int, stratum: str) -> list[str]:
    def key(name: str) -> bytes:
        return hashlib.sha256(f"{seed}:{stratum}:{name}".encode("utf-8")).digest()

    return sorted(names, key=key)


def split_stratum(names: Sequence[str], seed: int, stratum: str) -> tuple[list[str], list[str]]:
    ordered = stable_order(names, seed, stratum)
    midpoint = (len(ordered) + 1) // 2
    return ordered[:midpoint], ordered[midpoint:]


def trim_cohort(
    names: Sequence[str],
    probe_names: set[str],
    limit: int,
    seed: int,
    cohort: str,
) -> list[str]:
    if limit <= 0 or len(names) <= limit:
        return sorted(names)
    probes = stable_order((name for name in names if name in probe_names), seed, cohort + ":probe")
    singletons = stable_order((name for name in names if name not in probe_names), seed, cohort + ":singleton")
    probe_quota = max(2, round(limit * len(probes) / len(names)))
    probe_quota = min(probe_quota, len(probes), limit)
    singleton_quota = min(limit - probe_quota, len(singletons))
    if probe_quota + singleton_quota < limit:
        probe_quota = min(len(probes), limit - singleton_quota)
    return sorted(probes[:probe_quota] + singletons[:singleton_quota])


def build_lfw_cohorts(
    manifest: dict[str, Any], max_identities_per_cohort: int
) -> tuple[list[str], list[str]]:
    entries = manifest["identities"]
    probe_identities = sorted(
        name for name, entry in entries.items() if entry.get("probes") or entry.get("probe")
    )
    probe_set = set(probe_identities)
    singleton_identities = sorted(name for name in entries if name not in probe_set)
    seed = int(manifest.get("seed", 42))
    dev_probe, locked_probe = split_stratum(probe_identities, seed, "probe")
    dev_single, locked_single = split_stratum(singleton_identities, seed, "singleton")
    dev = trim_cohort(
        dev_probe + dev_single,
        probe_set,
        max_identities_per_cohort,
        seed,
        "development",
    )
    locked = trim_cohort(
        locked_probe + locked_single,
        probe_set,
        max_identities_per_cohort,
        seed,
        "locked",
    )
    if set(dev) & set(locked):
        raise AssertionError("LFW development and locked identity cohorts overlap")
    return dev, locked


def manifest_probes(entry: dict[str, Any]) -> list[str]:
    probes = entry.get("probes")
    if probes is not None:
        return list(probes)
    probe = entry.get("probe")
    return [probe] if probe else []


def preprocess_lfw_image(detector: Any, path: Path) -> np.ndarray:
    image = cv.imread(str(path), cv.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read LFW image: {path}")
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    sample = detect_sample(
        detector,
        image_bgr=image,
        image_gray=gray,
        assume_cropped=False,
    )
    if sample is None:
        raise RuntimeError(f"YuNet did not detect a face in manifest-selected image: {path}")
    return normalize_face(sample.face_gray, img_size=IMG_SIZE, equalization=EQUALIZATION)


def cache_signature(
    manifest_path: Path,
    lfw_root: Path,
    dev_names: Sequence[str],
    locked_names: Sequence[str],
) -> dict[str, Any]:
    return {
        "manifest_sha256": sha256_file(manifest_path),
        "lfw_root": str(lfw_root.resolve()),
        "dev_identities_sha256": sha256_strings(dev_names),
        "locked_identities_sha256": sha256_strings(locked_names),
        "preprocessing": {
            "detector": "YuNet default weights/settings; largest box; assume_cropped=False",
            "normalization": EQUALIZATION,
            "image_size": list(IMG_SIZE),
        },
    }


def prepare_lfw_cache(
    manifest: dict[str, Any],
    manifest_path: Path,
    lfw_root: Path,
    dev_names: Sequence[str],
    locked_names: Sequence[str],
    output_dir: Path,
    progress_every: int,
) -> dict[str, np.ndarray]:
    cache_dir = output_dir / "cache"
    cache_path = cache_dir / "lfw_preprocessed.npz"
    metadata_path = cache_dir / "lfw_preprocessed.json"
    expected = cache_signature(manifest_path, lfw_root, dev_names, locked_names)
    if cache_path.is_file() and metadata_path.is_file():
        actual = json.loads(metadata_path.read_text(encoding="utf-8"))
        if actual.get("signature") == expected:
            log(f"Loading matching LFW preprocessing cache: {cache_path}")
            with np.load(cache_path, allow_pickle=False) as cached:
                return {key: cached[key] for key in cached.files}

    cache_dir.mkdir(parents=True, exist_ok=True)
    detector = create_face_detector("yunet", min_face_size=40)
    entries = manifest["identities"]
    selected = [("development", name) for name in dev_names] + [
        ("locked", name) for name in locked_names
    ]
    gallery_names: list[str] = []
    gallery_cohorts: list[int] = []
    gallery_faces: list[np.ndarray] = []
    probe_names: list[str] = []
    probe_cohorts: list[int] = []
    probe_faces: list[np.ndarray] = []
    total_images = len(selected) + sum(len(manifest_probes(entries[name])) for _, name in selected)
    completed = 0
    started = time.perf_counter()
    for cohort_name, identity in selected:
        cohort_code = 0 if cohort_name == "development" else 1
        entry = entries[identity]
        gallery_rel = entry.get("gallery")
        if isinstance(gallery_rel, list):
            if len(gallery_rel) != 1:
                raise ValueError("LFW ablation requires one gallery image per identity")
            gallery_rel = gallery_rel[0]
        if not gallery_rel:
            raise ValueError(f"LFW identity has no gallery image: {identity}")
        gallery_faces.append(preprocess_lfw_image(detector, lfw_root / gallery_rel))
        gallery_names.append(identity)
        gallery_cohorts.append(cohort_code)
        completed += 1
        if completed % progress_every == 0 or completed == total_images:
            log(f"LFW preprocessing {completed}/{total_images}")
        for probe_rel in manifest_probes(entry):
            probe_faces.append(preprocess_lfw_image(detector, lfw_root / probe_rel))
            probe_names.append(identity)
            probe_cohorts.append(cohort_code)
            completed += 1
            if completed % progress_every == 0 or completed == total_images:
                log(f"LFW preprocessing {completed}/{total_images}")

    arrays = {
        "gallery_names": np.asarray(gallery_names),
        "gallery_cohorts": np.asarray(gallery_cohorts, dtype=np.uint8),
        "gallery_faces": np.stack(gallery_faces).astype(np.uint8, copy=False),
        "probe_names": np.asarray(probe_names),
        "probe_cohorts": np.asarray(probe_cohorts, dtype=np.uint8),
        "probe_faces": np.stack(probe_faces).astype(np.uint8, copy=False),
    }
    np.savez(cache_path, **arrays)
    atomic_json(
        metadata_path,
        {
            "signature": expected,
            "created_utc": utc_now(),
            "elapsed_seconds": time.perf_counter() - started,
            "gallery_count": len(gallery_faces),
            "probe_count": len(probe_faces),
            "detection_failures": 0,
        },
    )
    return arrays


def lfw_cohort_arrays(
    cache: dict[str, np.ndarray], cohort_code: int
) -> tuple[list[str], list[np.ndarray], list[tuple[int, np.ndarray]]]:
    gallery_mask = cache["gallery_cohorts"] == cohort_code
    gallery_names = [str(value) for value in cache["gallery_names"][gallery_mask]]
    gallery_faces = [face for face in cache["gallery_faces"][gallery_mask]]
    name_to_label = {name: label for label, name in enumerate(gallery_names)}
    probe_mask = cache["probe_cohorts"] == cohort_code
    probe_names = [str(value) for value in cache["probe_names"][probe_mask]]
    probe_faces = cache["probe_faces"][probe_mask]
    probes = [(name_to_label[name], face) for name, face in zip(probe_names, probe_faces)]
    return gallery_names, gallery_faces, probes


def collect_unique_gallery_pairs(
    recognizer: Any,
    gallery_faces: Sequence[np.ndarray],
    config_id: str,
    progress_every: int,
) -> tuple[np.ndarray, float]:
    count = len(gallery_faces)
    pair_count = count * (count - 1) // 2
    distances = np.empty(pair_count, dtype=np.float64)
    offset = 0
    elapsed = 0.0
    for query_label, face in enumerate(gallery_faces):
        started = time.perf_counter()
        scores = per_label_scores(recognizer, face)
        elapsed += time.perf_counter() - started
        expected = count - query_label - 1
        values = [
            distance for label, distance in scores.items() if label > query_label
        ]
        if len(values) != expected:
            raise AssertionError(
                f"{config_id}: expected {expected} upper-triangle scores, got {len(values)}"
            )
        distances[offset : offset + expected] = values
        offset += expected
        completed = query_label + 1
        if completed % progress_every == 0 or completed == count:
            log(f"{config_id} LFW calibration queries {completed}/{count}")
    if offset != pair_count:
        raise AssertionError(f"Filled {offset} of {pair_count} LFW impostor pairs")
    return distances, elapsed


def count_gallery_pair_accepts(
    recognizer: Any,
    gallery_faces: Sequence[np.ndarray],
    threshold: float,
    config_id: str,
    progress_every: int,
) -> tuple[int, int, float]:
    count = len(gallery_faces)
    pair_count = count * (count - 1) // 2
    accepted = 0
    elapsed = 0.0
    for query_label, face in enumerate(gallery_faces):
        started = time.perf_counter()
        scores = per_label_scores(recognizer, face)
        elapsed += time.perf_counter() - started
        accepted += sum(
            1
            for label, distance in scores.items()
            if label > query_label and distance <= threshold
        )
        completed = query_label + 1
        if completed % progress_every == 0 or completed == count:
            log(f"{config_id} locked FAR queries {completed}/{count}")
    return accepted, pair_count, elapsed


def run_lfw_dev_config(
    config: LBPHConfig,
    gallery_names: Sequence[str],
    gallery_faces: Sequence[np.ndarray],
    probes: Sequence[tuple[int, np.ndarray]],
    progress_every: int,
) -> dict[str, Any]:
    recognizer, train_seconds = train_recognizer(
        config, gallery_faces, list(range(len(gallery_faces)))
    )
    impostors, calibration_score_seconds = collect_unique_gallery_pairs(
        recognizer, gallery_faces, config.config_id, progress_every
    )
    calibration = rank_threshold(impostors, LFW_TARGET_FAR)
    calibration["score_seconds"] = calibration_score_seconds
    evaluation = evaluate_identification(
        recognizer, probes, float(calibration["threshold"])
    )
    del impostors
    del recognizer
    gc.collect()
    return {
        **config.to_dict(),
        "dataset": "LFW-development",
        "identity_count": len(gallery_names),
        "probe_count": len(probes),
        "identity_names_sha256": sha256_strings(gallery_names),
        "train_seconds": train_seconds,
        "calibration": calibration,
        "evaluation": evaluation,
        "estimated_gallery_feature_bytes": config.feature_bytes_per_template
        * len(gallery_faces),
    }


def run_lfw_locked_config(
    config: LBPHConfig,
    development_threshold: float,
    gallery_names: Sequence[str],
    gallery_faces: Sequence[np.ndarray],
    probes: Sequence[tuple[int, np.ndarray]],
    progress_every: int,
) -> dict[str, Any]:
    recognizer, train_seconds = train_recognizer(
        config, gallery_faces, list(range(len(gallery_faces)))
    )
    evaluation = evaluate_identification(recognizer, probes, development_threshold)
    accepted, pair_count, far_score_seconds = count_gallery_pair_accepts(
        recognizer,
        gallery_faces,
        development_threshold,
        config.config_id,
        progress_every,
    )
    del recognizer
    gc.collect()
    return {
        **config.to_dict(),
        "dataset": "LFW-locked-identities",
        "identity_count": len(gallery_names),
        "probe_count": len(probes),
        "identity_names_sha256": sha256_strings(gallery_names),
        "threshold_source": "same configuration's LFW development cohort",
        "threshold": development_threshold,
        "train_seconds": train_seconds,
        "evaluation": evaluation,
        "locked_impostor_pair_count": pair_count,
        "locked_false_accept_count": accepted,
        "locked_realized_far": accepted / pair_count,
        "locked_realized_far_ppm": accepted / pair_count * 1_000_000.0,
        "locked_far_score_seconds": far_score_seconds,
        "estimated_gallery_feature_bytes": config.feature_bytes_per_template
        * len(gallery_faces),
    }


def checkpoint_path(output_dir: Path, stage: str, config_id: str) -> Path:
    return output_dir / "checkpoints" / stage / f"{config_id}.json"


def run_or_resume(
    output_dir: Path,
    stage: str,
    config: LBPHConfig,
    resume: bool,
    callback: Any,
) -> dict[str, Any]:
    path = checkpoint_path(output_dir, stage, config.config_id)
    if resume and path.is_file():
        log(f"Resuming {stage} {config.config_id} from {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))
    log(f"Starting {stage} {config.config_id}")
    result = callback()
    atomic_json(path, result)
    log(f"Completed {stage} {config.config_id}")
    return result


def rank_configs(
    lsdb_results: Sequence[dict[str, Any]], lfw_results: Sequence[dict[str, Any]]
) -> tuple[list[str], list[str]]:
    lsdb_ranked = sorted(
        lsdb_results,
        key=lambda row: (
            -row["mean_tpir_percent"],
            -row["mean_rank1_percent"],
            -row["min_tpir_percent"],
            row["feature_bytes_per_template"],
            row["config_id"],
        ),
    )
    lfw_ranked = sorted(
        lfw_results,
        key=lambda row: (
            -row["evaluation"]["tpir_percent"],
            -row["evaluation"]["rank1_percent"],
            row["feature_bytes_per_template"],
            row["config_id"],
        ),
    )
    return (
        [row["config_id"] for row in lsdb_ranked],
        [row["config_id"] for row in lfw_ranked],
    )


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def flatten_lsdb_dev(results: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aggregate: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    for result in results:
        aggregate.append(
            {
                **{key: result[key] for key in CONFIG_BY_ID[result["config_id"]].to_dict()},
                "mean_rank1_percent": result["mean_rank1_percent"],
                "min_rank1_percent": result["min_rank1_percent"],
                "mean_tpir_percent": result["mean_tpir_percent"],
                "min_tpir_percent": result["min_tpir_percent"],
                "total_seconds": result["total_seconds"],
            }
        )
        for fold in result["folds"]:
            folds.append(
                {
                    "config_id": result["config_id"],
                    "fold": fold["fold"],
                    "fit_images_per_identity": fold["fit_images_per_identity"],
                    "calibration_image": fold["calibration_image"],
                    "evaluation_image": fold["evaluation_image"],
                    "threshold": fold["calibration"]["threshold"],
                    "calibration_far_percent": 100.0
                    * fold["calibration"]["realized_far"],
                    "rank1_percent": fold["evaluation"]["rank1_percent"],
                    "tpir_percent": fold["evaluation"]["tpir_percent"],
                    "mean_score_ms": fold["evaluation"]["mean_score_ms"],
                }
            )
    return aggregate, folds


def flatten_lfw_dev(results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                **CONFIG_BY_ID[result["config_id"]].to_dict(),
                "identity_count": result["identity_count"],
                "probe_count": result["probe_count"],
                "threshold": result["calibration"]["threshold"],
                "calibration_far_ppm": result["calibration"]["realized_far_ppm"],
                "rank1_percent": result["evaluation"]["rank1_percent"],
                "tpir_percent": result["evaluation"]["tpir_percent"],
                "verification_tpr_percent": result["evaluation"]["verification_tpr_percent"],
                "genuine_distance_median": result["evaluation"]["genuine_distance_median"],
                "mean_score_ms": result["evaluation"]["mean_score_ms"],
                "train_seconds": result["train_seconds"],
            }
        )
    return rows


def flatten_locked(
    lsdb_results: Sequence[dict[str, Any]], lfw_results: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lsdb_rows = [
        {
            **CONFIG_BY_ID[result["config_id"]].to_dict(),
            "threshold": result["calibration"]["threshold"],
            "calibration_far_percent": 100.0 * result["calibration"]["realized_far"],
            "rank1_percent": result["evaluation"]["rank1_percent"],
            "tpir_percent": result["evaluation"]["tpir_percent"],
            "verification_tpr_percent": result["evaluation"]["verification_tpr_percent"],
            "mean_score_ms": result["evaluation"]["mean_score_ms"],
        }
        for result in lsdb_results
    ]
    lfw_rows = [
        {
            **CONFIG_BY_ID[result["config_id"]].to_dict(),
            "threshold": result["threshold"],
            "locked_far_ppm": result["locked_realized_far_ppm"],
            "rank1_percent": result["evaluation"]["rank1_percent"],
            "tpir_percent": result["evaluation"]["tpir_percent"],
            "verification_tpr_percent": result["evaluation"]["verification_tpr_percent"],
            "mean_score_ms": result["evaluation"]["mean_score_ms"],
        }
        for result in lfw_results
    ]
    return lsdb_rows, lfw_rows


def parse_configs(value: str) -> list[LBPHConfig]:
    if value.strip().lower() == "all":
        return list(ALL_CONFIGS)
    ids = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in ids if item not in CONFIG_BY_ID]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"Unknown configuration(s): {', '.join(unknown)}. Valid: {', '.join(CONFIG_BY_ID)}"
        )
    return [CONFIG_BY_ID[item] for item in ids]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lsdb-train-root", type=Path, default=DEFAULT_LSDB_TRAIN)
    parser.add_argument("--lsdb-test-root", type=Path, default=DEFAULT_LSDB_TEST)
    parser.add_argument("--lfw-root", type=Path, default=DEFAULT_LFW_ROOT)
    parser.add_argument("--lfw-manifest", type=Path, default=DEFAULT_LFW_MANIFEST)
    parser.add_argument(
        "--configs",
        default="all",
        help="Comma-separated configuration IDs or 'all' (default).",
    )
    parser.add_argument(
        "--max-lfw-identities-per-cohort",
        type=int,
        default=0,
        help="Deterministically cap each LFW cohort; 0 uses every identity.",
    )
    parser.add_argument("--progress-every", type=int, default=250)
    parser.add_argument("--skip-lfw", action="store_true")
    parser.add_argument("--skip-locked", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def validate_inputs(args: argparse.Namespace, configs: Sequence[LBPHConfig]) -> None:
    if not hasattr(cv, "face"):
        raise RuntimeError("OpenCV contrib face module is unavailable")
    for path in (args.lsdb_train_root, args.lsdb_test_root):
        if not path.is_dir():
            raise FileNotFoundError(path)
    if not args.skip_lfw:
        if not args.lfw_root.is_dir():
            raise FileNotFoundError(args.lfw_root)
        if not args.lfw_manifest.is_file():
            raise FileNotFoundError(args.lfw_manifest)
    if not configs:
        raise ValueError("No configurations selected")
    if not args.skip_lfw and BASELINE_ID not in {config.config_id for config in configs}:
        log("Warning: baseline config omitted; locked finalists will not include it")


def main() -> None:
    args = parse_args()
    configs = parse_configs(args.configs)
    validate_inputs(args, configs)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_started = time.perf_counter()
    created_utc = utc_now()

    manifest: dict[str, Any] | None = None
    dev_names: list[str] = []
    locked_names: list[str] = []
    if not args.skip_lfw:
        manifest = json.loads(args.lfw_manifest.read_text(encoding="utf-8"))
        dev_names, locked_names = build_lfw_cohorts(
            manifest, args.max_lfw_identities_per_cohort
        )

    provenance = {
        "schema": "lsface-lbph-descriptor-ablation-v1",
        "status": "running",
        "created_utc": created_utc,
        "command": [sys.executable, *sys.argv],
        "script": str(Path(__file__).resolve()),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "git": {
            "commit": git_output("rev-parse", "HEAD"),
            "branch": git_output("branch", "--show-current"),
            "status_porcelain": git_output("status", "--short"),
        },
        "environment": {
            "python": platform.python_version(),
            "opencv": cv.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "configs": [config.to_dict() for config in configs],
        "fixed_contract": {
            "preprocessing": EQUALIZATION,
            "image_size": list(IMG_SIZE),
            "neighbors": NEIGHBORS,
            "distance": "native OpenCV LBPH predict_collect",
            "deployment_files_modified": False,
        },
        "datasets": {
            "lsdb_train_root": str(args.lsdb_train_root.resolve()),
            "lsdb_test_root": str(args.lsdb_test_root.resolve()),
            "lsdb_tree_sha256": sha256_tree(args.lsdb_train_root)
            + ":"
            + sha256_tree(args.lsdb_test_root),
            "lfw_root": None if args.skip_lfw else str(args.lfw_root.resolve()),
            "lfw_manifest": None
            if args.skip_lfw
            else str(args.lfw_manifest.resolve()),
            "lfw_manifest_sha256": None
            if args.skip_lfw
            else sha256_file(args.lfw_manifest),
            "lfw_archive_sha256_from_manifest": None
            if manifest is None
            else manifest.get("archive_sha256"),
            "lfw_development_identities": len(dev_names),
            "lfw_locked_identities": len(locked_names),
            "lfw_development_identities_sha256": sha256_strings(dev_names),
            "lfw_locked_identities_sha256": sha256_strings(locked_names),
        },
        "protocol": {
            "lsdb_development": "Ten paired-view folds over train only; per-fold calibration",
            "lsdb_locked": "Name views from test; baseline and dev-selected finalists only",
            "lsdb_target_far": LSDB_TARGET_FAR,
            "lfw_development": "Identity-disjoint stratified half; gallery-pair calibration and probes",
            "lfw_locked": "Disjoint identity half; threshold frozen from development",
            "lfw_target_far": LFW_TARGET_FAR,
            "selection": "Separate LSDB and LFW development rankings; locked finalists are baseline plus each development winner",
        },
    }
    atomic_json(output_dir / "run_provenance.json", provenance)

    log("Loading and normalizing LSDB")
    identities, lsdb_train, lsdb_locked = load_lsdb(
        args.lsdb_train_root, args.lsdb_test_root
    )
    log(f"LSDB ready: {len(identities)} identities, 280 development + 56 locked images")

    lsdb_dev_results: list[dict[str, Any]] = []
    for config in configs:
        result = run_or_resume(
            output_dir,
            "lsdb_dev",
            config,
            args.resume,
            lambda config=config: run_lsdb_dev_config(config, identities, lsdb_train),
        )
        lsdb_dev_results.append(result)

    lfw_dev_results: list[dict[str, Any]] = []
    lfw_cache: dict[str, np.ndarray] | None = None
    dev_gallery_names: list[str] = []
    dev_gallery_faces: list[np.ndarray] = []
    dev_probes: list[tuple[int, np.ndarray]] = []
    locked_gallery_names: list[str] = []
    locked_gallery_faces: list[np.ndarray] = []
    locked_probes: list[tuple[int, np.ndarray]] = []
    if not args.skip_lfw:
        assert manifest is not None
        lfw_cache = prepare_lfw_cache(
            manifest,
            args.lfw_manifest,
            args.lfw_root,
            dev_names,
            locked_names,
            output_dir,
            args.progress_every,
        )
        dev_gallery_names, dev_gallery_faces, dev_probes = lfw_cohort_arrays(lfw_cache, 0)
        locked_gallery_names, locked_gallery_faces, locked_probes = lfw_cohort_arrays(
            lfw_cache, 1
        )
        log(
            "LFW ready: "
            f"development {len(dev_gallery_names)} identities/{len(dev_probes)} probes; "
            f"locked {len(locked_gallery_names)} identities/{len(locked_probes)} probes"
        )
        for config in configs:
            result = run_or_resume(
                output_dir,
                "lfw_dev",
                config,
                args.resume,
                lambda config=config: run_lfw_dev_config(
                    config,
                    dev_gallery_names,
                    dev_gallery_faces,
                    dev_probes,
                    args.progress_every,
                ),
            )
            lfw_dev_results.append(result)

    if lfw_dev_results:
        lsdb_ranking, lfw_ranking = rank_configs(lsdb_dev_results, lfw_dev_results)
    else:
        lsdb_ranking = [
            row["config_id"]
            for row in sorted(
                lsdb_dev_results,
                key=lambda row: (
                    -row["mean_tpir_percent"],
                    -row["mean_rank1_percent"],
                    row["feature_bytes_per_template"],
                    row["config_id"],
                ),
            )
        ]
        lfw_ranking = []

    selected_ids: list[str] = []
    for config_id in (BASELINE_ID, lsdb_ranking[0], lfw_ranking[0] if lfw_ranking else None):
        if config_id and config_id in CONFIG_BY_ID and config_id not in selected_ids:
            if config_id in {config.config_id for config in configs}:
                selected_ids.append(config_id)

    lsdb_locked_results: list[dict[str, Any]] = []
    lfw_locked_results: list[dict[str, Any]] = []
    if not args.skip_locked:
        for config_id in selected_ids:
            config = CONFIG_BY_ID[config_id]
            result = run_or_resume(
                output_dir,
                "lsdb_locked",
                config,
                args.resume,
                lambda config=config: run_lsdb_locked_config(
                    config, identities, lsdb_train, lsdb_locked
                ),
            )
            lsdb_locked_results.append(result)
        if not args.skip_lfw:
            dev_by_id = {result["config_id"]: result for result in lfw_dev_results}
            for config_id in selected_ids:
                config = CONFIG_BY_ID[config_id]
                threshold = float(dev_by_id[config_id]["calibration"]["threshold"])
                result = run_or_resume(
                    output_dir,
                    "lfw_locked",
                    config,
                    args.resume,
                    lambda config=config, threshold=threshold: run_lfw_locked_config(
                        config,
                        threshold,
                        locked_gallery_names,
                        locked_gallery_faces,
                        locked_probes,
                        args.progress_every,
                    ),
                )
                lfw_locked_results.append(result)

    aggregate_rows, fold_rows = flatten_lsdb_dev(lsdb_dev_results)
    write_csv(
        output_dir / "lsdb_development.csv",
        aggregate_rows,
        [
            "config_id",
            "radius",
            "neighbors",
            "grid_x",
            "grid_y",
            "feature_bytes_per_template",
            "mean_rank1_percent",
            "min_rank1_percent",
            "mean_tpir_percent",
            "min_tpir_percent",
            "total_seconds",
        ],
    )
    write_csv(
        output_dir / "lsdb_development_folds.csv",
        fold_rows,
        [
            "config_id",
            "fold",
            "fit_images_per_identity",
            "calibration_image",
            "evaluation_image",
            "threshold",
            "calibration_far_percent",
            "rank1_percent",
            "tpir_percent",
            "mean_score_ms",
        ],
    )
    if lfw_dev_results:
        write_csv(
            output_dir / "lfw_development.csv",
            flatten_lfw_dev(lfw_dev_results),
            [
                "config_id",
                "radius",
                "neighbors",
                "grid_x",
                "grid_y",
                "feature_bytes_per_template",
                "identity_count",
                "probe_count",
                "threshold",
                "calibration_far_ppm",
                "rank1_percent",
                "tpir_percent",
                "verification_tpr_percent",
                "genuine_distance_median",
                "mean_score_ms",
                "train_seconds",
            ],
        )
    if lsdb_locked_results or lfw_locked_results:
        lsdb_locked_rows, lfw_locked_rows = flatten_locked(
            lsdb_locked_results, lfw_locked_results
        )
        if lsdb_locked_rows:
            write_csv(
                output_dir / "lsdb_locked.csv",
                lsdb_locked_rows,
                [
                    "config_id",
                    "radius",
                    "neighbors",
                    "grid_x",
                    "grid_y",
                    "feature_bytes_per_template",
                    "threshold",
                    "calibration_far_percent",
                    "rank1_percent",
                    "tpir_percent",
                    "verification_tpr_percent",
                    "mean_score_ms",
                ],
            )
        if lfw_locked_rows:
            write_csv(
                output_dir / "lfw_locked.csv",
                lfw_locked_rows,
                [
                    "config_id",
                    "radius",
                    "neighbors",
                    "grid_x",
                    "grid_y",
                    "feature_bytes_per_template",
                    "threshold",
                    "locked_far_ppm",
                    "rank1_percent",
                    "tpir_percent",
                    "verification_tpr_percent",
                    "mean_score_ms",
                ],
            )

    summary = {
        "schema": "lsface-lbph-descriptor-ablation-summary-v1",
        "completed_utc": utc_now(),
        "baseline_config_id": BASELINE_ID,
        "lsdb_development_ranking": lsdb_ranking,
        "lfw_development_ranking": lfw_ranking,
        "selected_for_locked_evaluation": selected_ids,
        "selection_rule": {
            "lsdb": "mean TPIR, mean Rank-1, worst-fold TPIR, smaller descriptor, ID",
            "lfw": "TPIR, Rank-1, smaller descriptor, ID",
        },
        "lsdb_development": lsdb_dev_results,
        "lfw_development": lfw_dev_results,
        "lsdb_locked": lsdb_locked_results,
        "lfw_locked": lfw_locked_results,
        "elapsed_seconds": time.perf_counter() - run_started,
        "governance": {
            "canonical_result": False,
            "deployment_config_changed": False,
            "thresholds_json_changed": False,
            "promotion_requires_review": True,
            "historical_lsdb_test_reuse_caveat": (
                "The name-view test partition predates this run and has appeared in earlier "
                "workspace studies; treat it as a locked comparison within this run, not a "
                "never-observed final test set."
            ),
        },
    }
    atomic_json(output_dir / "summary.json", summary)
    provenance["status"] = "complete"
    provenance["completed_utc"] = summary["completed_utc"]
    provenance["elapsed_seconds"] = summary["elapsed_seconds"]
    provenance["selected_for_locked_evaluation"] = selected_ids
    atomic_json(output_dir / "run_provenance.json", provenance)
    (output_dir / "README.md").write_text(
        "# LBPH descriptor ablation (provenance rerun)\n\n"
        "This directory is a non-canonical working result. It compares radius "
        "{1,2,3} x grid {4,6,8,10}, with neighbors=8, 100x100 Tan-Triggs "
        "preprocessing, native OpenCV distances, and per-configuration calibration.\n\n"
        "`summary.json` contains the full protocol and nested results; the CSV files "
        "are compact review tables. Deployment models and thresholds were not changed.\n",
        encoding="utf-8",
    )
    log(f"Ablation complete: {output_dir}")
    log(f"LSDB development winner: {lsdb_ranking[0]}")
    if lfw_ranking:
        log(f"LFW development winner: {lfw_ranking[0]}")


if __name__ == "__main__":
    main()
