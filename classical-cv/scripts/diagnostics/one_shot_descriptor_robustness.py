#!/usr/bin/env python3
"""Exploratory one-shot LSDB robustness comparison for cheap descriptors.

This is deliberately a diagnostic, non-canonical experiment.  It derives one
gallery and one disjoint probe per identity from the project's existing LSDB
identification manifest, applies the current DL41 transforms to BGR pixels,
runs one shared strict YuNet gate per query, and compares threshold-free 1:N
Rank-1 matching on the identical successful grayscale tile.

No frozen verification/cascade threshold is read or changed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gc
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np
from sklearn.metrics import roc_auc_score


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.accuracy_ratio_hybrid import get_modification_set  # noqa: E402
from src.benchmark.hog_descriptor import STANDARD_HOG  # noqa: E402
from src.benchmark.lpq_descriptor import MULTISCALE_LPQ, STANDARD_LPQ  # noqa: E402
from src.benchmark.ltp_descriptor import LTP_VARIANTS  # noqa: E402
from src.benchmark.modifications import (  # noqa: E402
    DL41_CATEGORY_MAP,
    DL41_TIER_MAP,
    stable_rng,
)
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import IMG_SIZE, normalize_face  # noqa: E402
from src.hybrid.recognizer import detect_sample  # noqa: E402


DEFAULT_SOURCE_MANIFEST = PROJECT_ROOT / "data" / "splits" / "lasalle_db1_ident_split_seed42.json"
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data" / "lasalle_db1_processed"
DEFAULT_OUTPUT = (
    WORKSPACE_ROOT
    / "docs"
    / "experiments"
    / "robustness_variants"
    / "classical_descriptor_smoke_2026-08-13"
)
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "731bcf52fec2046689442f7edb26e6b28d1b99d1fbee053402eb9de3715c47dc"
)
EXPECTED_SELECTION_SHA256 = (
    "b58c4ec07070745e1a7c6e57036cd33722eb6576d78b3bbcbd5cd01c61e794b5"
)
EXPECTED_SELECTED_FILES_SHA256 = (
    "dda5f11a3b74fb4607d75736ff957074ee7639939301bf164886929b2059ae03"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--limit-identities",
        type=int,
        default=0,
        help="Debug only: first N sorted manifest identities (0 = all 28).",
    )
    parser.add_argument(
        "--limit-modifications",
        type=int,
        default=0,
        help="Debug only: first N DL41 variants (0 = all 41).",
    )
    parser.add_argument("--timing-queries", type=int, default=256)
    parser.add_argument("--timing-repeats", type=int, default=3)
    parser.add_argument("--timing-warmup", type=int, default=10)
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonable_level(level: Any) -> Any:
    if isinstance(level, tuple):
        return list(level)
    if isinstance(level, np.generic):
        return level.item()
    return level


def level_text(level: Any) -> str:
    return json.dumps(jsonable_level(level), sort_keys=True, separators=(",", ":"))


def percent(correct: int, total: int) -> float | None:
    return None if total == 0 else 100.0 * correct / total


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args], cwd=WORKSPACE_ROOT, text=True, capture_output=True, check=False
    )
    value = result.stdout.strip()
    return value or None


def cpu_name() -> str:
    value = platform.processor().strip()
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except (OSError, ImportError):
            pass
    return value or "unknown"


@dataclass(frozen=True)
class Selection:
    identity: str
    gallery_relpath: str
    probe_relpath: str
    gallery_path: Path
    probe_path: Path
    gallery_sha256: str
    probe_sha256: str


@dataclass
class Query:
    query_id: str
    identity: str
    probe_relpath: str
    probe_file: str
    transform: str
    level: Any
    category: str
    severity: str
    is_clean: bool
    transformed_sha256: str
    transformed_shape: tuple[int, ...]
    detection_status: str = "pending"
    shared_crop_sha256: str | None = None
    crop_gray: np.ndarray | None = None


class LBPHDescriptor:
    """OpenCV-generated LBPH histograms with native-compatible matching.

    OpenCV does not expose a standalone feature-extraction method.  Reusing a
    one-sample recognizer's ``train`` + ``getHistograms`` yields the exact same
    16,384-bin query histogram that ``predict_collect`` computes internally.
    The distance below reproduces OpenCV's native value to float precision.
    """

    name = "lbph"
    descriptor_length = 8 * 8 * 256
    descriptor_bytes = descriptor_length * np.dtype(np.float32).itemsize
    static_state_bytes = 0

    def __init__(self, identities: list[str], gallery_crops: list[np.ndarray]) -> None:
        self.identities = identities
        self.equalization = SPECS["lbph"].default_equalization
        normalized = [self._normalize(crop) for crop in gallery_crops]
        labels = np.arange(len(normalized), dtype=np.int32)
        self.model = cv.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        self.model.train(normalized, labels)
        self.gallery = [
            np.ascontiguousarray(np.asarray(hist).reshape(-1), dtype=np.float32)
            for hist in self.model.getHistograms()
        ]
        if any(feature.shape != (self.descriptor_length,) for feature in self.gallery):
            raise RuntimeError("Unexpected OpenCV LBPH histogram length")
        self._extractor = cv.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )

    @property
    def params(self) -> dict[str, Any]:
        return {
            "algorithm": "opencv_lbph",
            "radius": 1,
            "neighbors": 8,
            "grid_x": 8,
            "grid_y": 8,
            "intrinsic_preprocessing": self.equalization,
            "preprocessing_implementation": "src.classical_faces.preprocess.normalize_face",
            "distance": "opencv_native_predict_collect_chi_square_equivalent",
            "distance_formula": "2*sum((a-b)^2/(a+b+1e-10))",
            "input_contract": "shared_100x100_raw_grayscale_tile",
            "descriptor_dtype": "float32",
            "descriptor_length": self.descriptor_length,
            "descriptor_bytes": self.descriptor_bytes,
        }

    def _normalize(self, gray: np.ndarray) -> np.ndarray:
        return normalize_face(gray, img_size=IMG_SIZE, equalization=self.equalization)

    def extract(self, gray: np.ndarray) -> np.ndarray:
        normalized = self._normalize(gray)
        self._extractor.train([normalized], np.asarray([0], dtype=np.int32))
        feature = np.ascontiguousarray(
            np.asarray(self._extractor.getHistograms()[0]).reshape(-1), dtype=np.float32
        )
        return feature

    @staticmethod
    def distance(first: np.ndarray, second: np.ndarray) -> float:
        left = np.asarray(first, dtype=np.float64)
        right = np.asarray(second, dtype=np.float64)
        return float(2.0 * np.sum((left - right) ** 2 / (left + right + 1e-10)))

    def native_validation(self, crops: list[np.ndarray]) -> dict[str, Any]:
        max_abs_error = 0.0
        prediction_mismatches = 0
        comparisons = 0
        for crop in crops[: min(10, len(crops))]:
            normalized = self._normalize(crop)
            collector = cv.face.StandardCollector_create()
            self.model.predict_collect(normalized, collector)
            native = np.full(len(self.identities), np.nan, dtype=np.float64)
            for label, distance in collector.getResults(True):
                label_i = int(label)
                native[label_i] = min(native[label_i], float(distance)) if np.isfinite(native[label_i]) else float(distance)
            feature = self.extract(crop)
            manual = np.asarray([self.distance(feature, gallery) for gallery in self.gallery])
            max_abs_error = max(max_abs_error, float(np.max(np.abs(manual - native))))
            prediction_mismatches += int(int(np.argmin(manual)) != int(np.nanargmin(native)))
            comparisons += len(native)
        return {
            "queries_checked": min(10, len(crops)),
            "distances_checked": comparisons,
            "max_absolute_distance_error": max_abs_error,
            "rank1_prediction_mismatches": prediction_mismatches,
        }


@dataclass
class Algorithm:
    name: str
    adapter: Any
    gallery: list[np.ndarray]
    params: dict[str, Any]
    descriptor_bytes: int
    static_state_bytes: int
    serialized_model_bytes: int | None = None


def load_selections(
    source_manifest_path: Path, data_root: Path, limit_identities: int
) -> tuple[list[Selection], dict[str, Any]]:
    source_manifest_path = source_manifest_path.resolve()
    data_root = data_root.resolve()
    if not source_manifest_path.is_file():
        raise FileNotFoundError(source_manifest_path)
    if not data_root.is_dir():
        raise FileNotFoundError(data_root)

    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    identities = sorted(manifest["identities"])
    if limit_identities:
        if limit_identities < 2:
            raise ValueError("--limit-identities must be 0 or >= 2")
        identities = identities[:limit_identities]

    selections: list[Selection] = []
    for identity in identities:
        entry = manifest["identities"][identity]
        gallery_rel = entry.get("gallery")
        probe_rel = entry.get("probe")
        if not probe_rel:
            probes = entry.get("probes") or []
            probe_rel = probes[0] if probes else None
        if not isinstance(gallery_rel, str) or not isinstance(probe_rel, str):
            raise RuntimeError(f"{identity}: source manifest lacks one gallery/probe path")
        if gallery_rel == probe_rel:
            raise RuntimeError(f"{identity}: gallery and probe are not disjoint")
        gallery_path = data_root / Path(gallery_rel)
        probe_path = data_root / Path(probe_rel)
        if not gallery_path.is_file() or not probe_path.is_file():
            raise FileNotFoundError(
                f"{identity}: rebased input missing: {gallery_path} or {probe_path}"
            )
        selections.append(
            Selection(
                identity=identity,
                gallery_relpath=gallery_rel.replace("\\", "/"),
                probe_relpath=probe_rel.replace("\\", "/"),
                gallery_path=gallery_path,
                probe_path=probe_path,
                gallery_sha256=sha256_file(gallery_path),
                probe_sha256=sha256_file(probe_path),
            )
        )

    selection_lines = [
        f"{row.identity}|{row.gallery_relpath}|{row.probe_relpath}" for row in selections
    ]
    binding_lines = [
        line
        for row in selections
        for line in (
            f"gallery|{row.gallery_relpath}|{row.gallery_sha256}",
            f"probe|{row.probe_relpath}|{row.probe_sha256}",
        )
    ]
    derived = {
        "schema": "lsface-lsdb-one-shot-smoke-v1",
        "status": "exploratory_diagnostic_non_canonical",
        "source_manifest": str(source_manifest_path),
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "source_manifest_dataset_root_stale": manifest.get("dataset_root"),
        "source_manifest_triples_sha256": manifest.get("triples_sha256"),
        "rebased_dataset_root": str(data_root),
        "derivation": "sorted identities; existing singular gallery field + existing singular probe field (the first already-used disjoint probe)",
        "selection_sha256": sha256_bytes("\n".join(selection_lines).encode("utf-8")),
        "selected_files_binding_sha256": sha256_bytes(
            "\n".join(binding_lines).encode("utf-8")
        ),
        "counts": {
            "identities": len(selections),
            "gallery_images": len(selections),
            "probe_images": len(selections),
        },
        "identities": {
            row.identity: {
                "gallery": row.gallery_relpath,
                "gallery_sha256": row.gallery_sha256,
                "probe": row.probe_relpath,
                "probe_sha256": row.probe_sha256,
            }
            for row in selections
        },
    }
    if not limit_identities:
        if derived["source_manifest_sha256"] != EXPECTED_SOURCE_MANIFEST_SHA256:
            raise RuntimeError("Source split manifest hash changed; refusing silent protocol drift")
        if derived["selection_sha256"] != EXPECTED_SELECTION_SHA256:
            raise RuntimeError("Derived one-shot selection hash changed")
        if derived["selected_files_binding_sha256"] != EXPECTED_SELECTED_FILES_SHA256:
            raise RuntimeError("Selected LSDB file bytes changed")
    return selections, derived


def build_queries(
    selections: list[Selection], seed: int, limit_modifications: int
) -> tuple[list[Query], dict[str, Any]]:
    modifications, variant_count = get_modification_set("dl41")
    if limit_modifications:
        if limit_modifications < 1:
            raise ValueError("--limit-modifications must be 0 or >= 1")
        modifications = modifications[:limit_modifications]
        variant_count = sum(len(levels) for _name, _fn, levels in modifications)

    queries: list[Query] = []
    stream_digest = hashlib.sha256()
    for selection in selections:
        original = cv.imread(str(selection.probe_path), cv.IMREAD_COLOR)
        if original is None:
            raise RuntimeError(f"Unreadable probe: {selection.probe_path}")
        if original.shape != (100, 100, 3):
            raise RuntimeError(
                f"{selection.probe_path}: expected LSDB processed 100x100 BGR, got {original.shape}"
            )
        clean_hash = sha256_bytes(np.ascontiguousarray(original).tobytes())
        queries.append(
            Query(
                query_id=f"{selection.identity}::clean",
                identity=selection.identity,
                probe_relpath=selection.probe_relpath,
                probe_file=selection.probe_path.name,
                transform="clean",
                level=None,
                category="Clean",
                severity="clean",
                is_clean=True,
                transformed_sha256=clean_hash,
                transformed_shape=tuple(original.shape),
            )
        )
        for transform_name, function, levels in modifications:
            for level in levels:
                rng = stable_rng(
                    seed,
                    selection.identity,
                    selection.probe_path.name,
                    transform_name,
                    level,
                )
                # One transform call only.  This cached array is immediately
                # detected below and is never regenerated per recognizer.
                transformed = function(original, level, rng)
                transformed = np.ascontiguousarray(transformed)
                if transformed.shape != original.shape:
                    raise RuntimeError(
                        f"{selection.identity}/{transform_name}: shape drift "
                        f"{original.shape} -> {transformed.shape}"
                    )
                pixels_hash = sha256_bytes(transformed.tobytes())
                stream_digest.update(selection.identity.encode("utf-8"))
                stream_digest.update(b"\0")
                stream_digest.update(transform_name.encode("utf-8"))
                stream_digest.update(b"\0")
                stream_digest.update(repr(level).encode("utf-8"))
                stream_digest.update(b"\0")
                stream_digest.update(transformed.tobytes())
                query = Query(
                    query_id=f"{selection.identity}::{transform_name}",
                    identity=selection.identity,
                    probe_relpath=selection.probe_relpath,
                    probe_file=selection.probe_path.name,
                    transform=transform_name,
                    level=jsonable_level(level),
                    category=DL41_CATEGORY_MAP[transform_name],
                    severity=DL41_TIER_MAP[transform_name],
                    is_clean=False,
                    transformed_sha256=pixels_hash,
                    transformed_shape=tuple(transformed.shape),
                )
                # Attach only until detection.  Keeping it out of the dataclass
                # prevents accidental recognizer-specific transform calls.
                setattr(query, "_transformed_bgr", transformed)
                queries.append(query)

        # The clean array follows the same one-pass detector path.
        setattr(queries[-variant_count - 1], "_transformed_bgr", original)

    return queries, {
        "modification_set": "dl41",
        "variant_count": variant_count,
        "transformed_stream_sha256": stream_digest.hexdigest(),
        "query_order": "sorted identity; clean; then DL41 declaration order",
        "rng_contract": "stable_rng(seed, identity, probe_basename, transform, level)",
        "transform_input": "BGR probe pixels before grayscale conversion",
    }


def detect_and_cache_queries(queries: list[Query]) -> dict[str, Any]:
    detector = create_face_detector("yunet")
    no_face_by_transform: dict[str, int] = defaultdict(int)
    crop_binding = hashlib.sha256()
    for query in queries:
        transformed = getattr(query, "_transformed_bgr")
        gray = cv.cvtColor(transformed, cv.COLOR_BGR2GRAY)
        sample = detect_sample(
            detector,
            image_bgr=transformed,
            image_gray=gray,
            assume_cropped=True,
        )
        delattr(query, "_transformed_bgr")
        if sample is None:
            query.detection_status = "no_face"
            no_face_by_transform[query.transform] += 1
            continue
        crop = np.ascontiguousarray(sample.face_gray, dtype=np.uint8)
        if crop.shape != (100, 100):
            raise RuntimeError(
                f"{query.query_id}: assume_cropped=True should yield 100x100, got {crop.shape}"
            )
        query.detection_status = "detected"
        query.crop_gray = crop
        query.shared_crop_sha256 = sha256_bytes(crop.tobytes())
        crop_binding.update(query.query_id.encode("utf-8"))
        crop_binding.update(b"\0")
        crop_binding.update(crop.tobytes())
    return {
        "detector": detector.describe(),
        "detector_backend": "yunet",
        "face_selection": "largest detection by area",
        "assume_cropped": True,
        "strict_no_face": True,
        "classical_alignment": "none; successful YuNet gates the whole transformed 100x100 pre-cropped tile",
        "successful_crop_stream_sha256": crop_binding.hexdigest(),
        "no_face_total": sum(no_face_by_transform.values()),
        "no_face_by_transform": dict(sorted(no_face_by_transform.items())),
    }


def load_gallery_crops(selections: list[Selection]) -> tuple[list[np.ndarray], dict[str, Any]]:
    detector = create_face_detector("yunet")
    crops: list[np.ndarray] = []
    binding = hashlib.sha256()
    for selection in selections:
        image = cv.imread(str(selection.gallery_path), cv.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Unreadable gallery image: {selection.gallery_path}")
        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        sample = detect_sample(
            detector, image_bgr=image, image_gray=gray, assume_cropped=True
        )
        if sample is None:
            raise RuntimeError(
                f"Strict one-shot gallery enrollment failed YuNet: {selection.gallery_path}"
            )
        crop = np.ascontiguousarray(sample.face_gray, dtype=np.uint8)
        if crop.shape != (100, 100):
            raise RuntimeError(f"Unexpected gallery crop shape: {crop.shape}")
        crops.append(crop)
        binding.update(selection.identity.encode("utf-8"))
        binding.update(b"\0")
        binding.update(crop.tobytes())
    return crops, {
        "gallery_detector_misses": 0,
        "gallery_crop_stream_sha256": binding.hexdigest(),
        "gallery_policy": "strict YuNet; abort on any miss; assume_cropped=True",
    }


def build_algorithms(
    identities: list[str], gallery_crops: list[np.ndarray], output_dir: Path
) -> tuple[dict[str, Algorithm], dict[str, Any]]:
    lbph = LBPHDescriptor(identities, gallery_crops)
    model_path = output_dir / "lbph_one_shot.yml"
    lbph.model.save(str(model_path))

    algorithms: dict[str, Algorithm] = {
        "lbph": Algorithm(
            name="lbph",
            adapter=lbph,
            gallery=lbph.gallery,
            params=lbph.params,
            descriptor_bytes=lbph.descriptor_bytes,
            static_state_bytes=lbph.static_state_bytes,
            serialized_model_bytes=model_path.stat().st_size,
        )
    }
    candidates = [
        LTP_VARIANTS["ltp"],
        LTP_VARIANTS["tan_triggs_ltp"],
        STANDARD_LPQ,
        MULTISCALE_LPQ,
        STANDARD_HOG,
    ]
    for adapter in candidates:
        gallery = [adapter.extract(crop) for crop in gallery_crops]
        algorithms[adapter.name] = Algorithm(
            name=adapter.name,
            adapter=adapter,
            gallery=gallery,
            params=adapter.params,
            descriptor_bytes=int(adapter.descriptor_bytes),
            static_state_bytes=int(getattr(adapter, "static_state_bytes", 0)),
        )
    native_validation = lbph.native_validation(gallery_crops)
    if native_validation["rank1_prediction_mismatches"] != 0:
        raise RuntimeError("Manual LBPH matcher disagrees with predict_collect")
    if native_validation["max_absolute_distance_error"] > 1e-4:
        raise RuntimeError("Manual LBPH native-distance reproduction drifted")
    return algorithms, native_validation


def score_crop(algorithm: Algorithm, crop: np.ndarray) -> tuple[dict[str, Any], float, float]:
    extract_start = time.perf_counter_ns()
    feature = algorithm.adapter.extract(crop)
    extract_ms = (time.perf_counter_ns() - extract_start) / 1e6
    match_start = time.perf_counter_ns()
    distances = np.asarray(
        [algorithm.adapter.distance(feature, gallery) for gallery in algorithm.gallery],
        dtype=np.float64,
    )
    match_ms = (time.perf_counter_ns() - match_start) / 1e6
    if not np.isfinite(distances).all():
        raise RuntimeError(f"{algorithm.name}: non-finite gallery distance")
    order = np.argsort(distances, kind="stable")
    best_idx, second_idx = int(order[0]), int(order[1])
    best = float(distances[best_idx])
    second = float(distances[second_idx])
    margin = second - best
    return {
        "predicted_index": best_idx,
        "best_score": best,
        "second_score": second,
        "margin": margin,
        "relative_margin": margin / max(abs(best), 1e-12),
    }, extract_ms, match_ms


def evaluate(
    algorithms: dict[str, Algorithm], identities: list[str], queries: list[Query]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    rows: list[dict[str, Any]] = []
    indexed: dict[str, dict[str, dict[str, Any]]] = {
        name: {} for name in algorithms
    }
    for query in queries:
        for algorithm_name, algorithm in algorithms.items():
            row: dict[str, Any] = {
                "query_id": query.query_id,
                "algorithm": algorithm_name,
                "identity": query.identity,
                "expected_identity": query.identity,
                "probe_relpath": query.probe_relpath,
                "probe_file": query.probe_file,
                "transform": query.transform,
                "level": level_text(query.level),
                "category": query.category,
                "severity": query.severity,
                "is_clean": query.is_clean,
                "detection_status": query.detection_status,
                "usable": False,
                "failure_reason": "no_face" if query.crop_gray is None else "",
                "transformed_sha256": query.transformed_sha256,
                "shared_crop_sha256": query.shared_crop_sha256 or "",
                "predicted_identity": "",
                "best_score": None,
                "second_score": None,
                "margin": None,
                "relative_margin": None,
                "correct": False,
            }
            if query.crop_gray is not None:
                try:
                    score, _extract_ms, _match_ms = score_crop(algorithm, query.crop_gray)
                    predicted = identities[score["predicted_index"]]
                    row.update(
                        {
                            "usable": True,
                            "failure_reason": "",
                            "predicted_identity": predicted,
                            "best_score": score["best_score"],
                            "second_score": score["second_score"],
                            "margin": score["margin"],
                            "relative_margin": score["relative_margin"],
                            "correct": predicted == query.identity,
                        }
                    )
                except Exception as exc:  # keep explicit unusable diagnostics
                    row["failure_reason"] = f"descriptor_error:{type(exc).__name__}:{exc}"
            rows.append(row)
            indexed[algorithm_name][query.query_id] = row
    return rows, indexed


def error_auc(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if not row["is_clean"] and row["usable"]]
    labels = np.asarray([not bool(row["correct"]) for row in eligible], dtype=np.int8)
    if len(eligible) == 0 or len(np.unique(labels)) < 2:
        return {
            "scope": "modified_detected_usable_only",
            "n": len(eligible),
            "errors": int(labels.sum()) if len(labels) else 0,
            "best_distance_auc": None,
            "negative_margin_auc": None,
        }
    best_scores = np.asarray([float(row["best_score"]) for row in eligible])
    negative_margins = np.asarray([-float(row["margin"]) for row in eligible])
    return {
        "scope": "modified_detected_usable_only",
        "positive_label": "own Rank-1 error",
        "n": len(eligible),
        "errors": int(labels.sum()),
        "best_distance_auc": float(roc_auc_score(labels, best_scores)),
        "negative_margin_auc": float(roc_auc_score(labels, negative_margins)),
    }


def group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    out: dict[str, Any] = {}
    for value, items in sorted(groups.items()):
        total = len(items)
        correct = sum(bool(item["correct"]) for item in items)
        usable_items = [item for item in items if item["usable"]]
        matcher_correct = sum(bool(item["correct"]) for item in usable_items)
        no_face = sum(item["detection_status"] == "no_face" for item in items)
        unusable = sum(
            item["detection_status"] == "detected" and not item["usable"] for item in items
        )
        out[value] = {
            "strict_correct": correct,
            "strict_total": total,
            "strict_rank1_percent": percent(correct, total),
            "matcher_correct": matcher_correct,
            "matcher_total": len(usable_items),
            "matcher_rank1_percent": percent(matcher_correct, len(usable_items)),
            "no_face": no_face,
            "unusable": unusable,
        }
    return out


def summarize_algorithm(
    algorithm: Algorithm, rows: list[dict[str, Any]], timing: dict[str, Any]
) -> dict[str, Any]:
    clean = [row for row in rows if row["is_clean"]]
    modified = [row for row in rows if not row["is_clean"]]
    detected_modified = [row for row in modified if row["usable"]]
    all_usable = [row for row in rows if row["usable"]]
    return {
        "algorithm": algorithm.name,
        "parameters": algorithm.params,
        "clean": {
            "correct": sum(bool(row["correct"]) for row in clean),
            "total": len(clean),
            "rank1_percent": percent(sum(bool(row["correct"]) for row in clean), len(clean)),
            "no_face": sum(row["detection_status"] == "no_face" for row in clean),
        },
        "all41_strict": {
            "correct": sum(bool(row["correct"]) for row in modified),
            "total": len(modified),
            "rank1_percent": percent(
                sum(bool(row["correct"]) for row in modified), len(modified)
            ),
            "no_face": sum(row["detection_status"] == "no_face" for row in modified),
            "unusable": sum(
                row["detection_status"] == "detected" and not row["usable"]
                for row in modified
            ),
        },
        "all41_matcher_only": {
            "correct": sum(bool(row["correct"]) for row in detected_modified),
            "total": len(detected_modified),
            "rank1_percent": percent(
                sum(bool(row["correct"]) for row in detected_modified),
                len(detected_modified),
            ),
        },
        "all_queries_strict": {
            "correct": sum(bool(row["correct"]) for row in rows),
            "total": len(rows),
            "rank1_percent": percent(sum(bool(row["correct"]) for row in rows), len(rows)),
        },
        "all_queries_matcher_only": {
            "correct": sum(bool(row["correct"]) for row in all_usable),
            "total": len(all_usable),
            "rank1_percent": percent(
                sum(bool(row["correct"]) for row in all_usable), len(all_usable)
            ),
        },
        "by_severity": group_summary(modified, "severity"),
        "by_transform": group_summary(modified, "transform"),
        "by_category": group_summary(modified, "category"),
        "confidence_error_auc": error_auc(rows),
        "descriptor_bytes_per_identity": algorithm.descriptor_bytes,
        "gallery_template_bytes": algorithm.descriptor_bytes * len(algorithm.gallery),
        "static_state_bytes": algorithm.static_state_bytes,
        "serialized_model_bytes": algorithm.serialized_model_bytes,
        "timing": timing,
    }


def paired_outcomes(
    lbph_rows: dict[str, dict[str, Any]],
    candidate_rows: dict[str, dict[str, Any]],
    query_ids: list[str],
) -> dict[str, int]:
    counts = {
        "both_correct": 0,
        "lbph_correct_candidate_wrong": 0,
        "lbph_wrong_candidate_correct": 0,
        "both_wrong": 0,
    }
    for query_id in query_ids:
        lbph_correct = bool(lbph_rows[query_id]["correct"])
        candidate_correct = bool(candidate_rows[query_id]["correct"])
        if lbph_correct and candidate_correct:
            counts["both_correct"] += 1
        elif lbph_correct:
            counts["lbph_correct_candidate_wrong"] += 1
        elif candidate_correct:
            counts["lbph_wrong_candidate_correct"] += 1
        else:
            counts["both_wrong"] += 1
    counts["candidate_only_recoveries"] = counts["lbph_wrong_candidate_correct"]
    counts["lbph_only_losses"] = counts["lbph_correct_candidate_wrong"]
    counts["net_difference"] = (
        counts["candidate_only_recoveries"] - counts["lbph_only_losses"]
    )
    counts["total"] = len(query_ids)
    return counts


def build_paired(
    indexed: dict[str, dict[str, dict[str, Any]]], queries: list[Query]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    modified_ids = [query.query_id for query in queries if not query.is_clean]
    detected_ids = [
        query.query_id
        for query in queries
        if not query.is_clean and query.detection_status == "detected"
    ]
    query_by_id = {query.query_id: query for query in queries}
    output: dict[str, Any] = {}
    flat: list[dict[str, Any]] = []
    per_transform: list[dict[str, Any]] = []
    lbph = indexed["lbph"]
    for candidate in (name for name in indexed if name != "lbph"):
        strict = paired_outcomes(lbph, indexed[candidate], modified_ids)
        matcher_ids = [
            query_id
            for query_id in detected_ids
            if lbph[query_id]["usable"] and indexed[candidate][query_id]["usable"]
        ]
        matcher = paired_outcomes(lbph, indexed[candidate], matcher_ids)
        transform_rows: list[dict[str, Any]] = []
        for transform in sorted({query_by_id[qid].transform for qid in modified_ids}):
            ids = [qid for qid in modified_ids if query_by_id[qid].transform == transform]
            counts = paired_outcomes(lbph, indexed[candidate], ids)
            record = {
                "candidate": candidate,
                "transform": transform,
                "category": query_by_id[ids[0]].category,
                "severity": query_by_id[ids[0]].severity,
                **counts,
            }
            transform_rows.append(record)
            per_transform.append(record)
        output[candidate] = {
            "strict_all41": strict,
            "matcher_only": matcher,
            "by_transform": transform_rows,
            "largest_gains": sorted(
                transform_rows,
                key=lambda row: (row["net_difference"], row["candidate_only_recoveries"]),
                reverse=True,
            )[:5],
            "largest_losses": sorted(
                transform_rows,
                key=lambda row: (row["net_difference"], -row["lbph_only_losses"]),
            )[:5],
        }
        for scope, counts in (("strict_all41", strict), ("matcher_only", matcher)):
            flat.append({"candidate": candidate, "scope": scope, **counts})
    return output, flat, per_transform


def benchmark_timings(
    algorithms: dict[str, Algorithm], queries: list[Query], args: argparse.Namespace
) -> dict[str, dict[str, Any]]:
    successful = [query.crop_gray for query in queries if query.crop_gray is not None]
    if not successful:
        raise RuntimeError("No detected queries available for timing")
    max_queries = min(max(1, args.timing_queries), len(successful))
    indices = np.linspace(0, len(successful) - 1, max_queries, dtype=np.int64)
    timing_crops = [successful[int(index)] for index in indices]
    results: dict[str, dict[str, Any]] = {}
    for name, algorithm in algorithms.items():
        warmup = max(1, args.timing_warmup)
        for i in range(warmup):
            score_crop(algorithm, timing_crops[i % len(timing_crops)])
        gc.collect()
        extraction: list[float] = []
        matching: list[float] = []
        total: list[float] = []
        for _repeat in range(max(1, args.timing_repeats)):
            for crop in timing_crops:
                _score, extract_ms, match_ms = score_crop(algorithm, crop)
                extraction.append(extract_ms)
                matching.append(match_ms)
                total.append(extract_ms + match_ms)
        results[name] = {
            "scope": "warm recognition-only; transformed pixels/detection/I-O excluded",
            "samples": len(total),
            "warmup_queries": warmup,
            "unique_cached_crops": len(timing_crops),
            "repeats": max(1, args.timing_repeats),
            "feature_extraction_ms": {
                "p50": percentile(extraction, 50),
                "p95": percentile(extraction, 95),
                "mean": float(np.mean(extraction)),
            },
            "gallery_matching_ms": {
                "p50": percentile(matching, 50),
                "p95": percentile(matching, 95),
                "mean": float(np.mean(matching)),
            },
            "total_recognition_ms": {
                "p50": percentile(total, 50),
                "p95": percentile(total, 95),
                "mean": float(np.mean(total)),
            },
        }
    return results


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if not rows:
        raise RuntimeError(f"Refusing to write empty CSV: {path}")
    fieldnames = fields or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def algorithm_label(name: str) -> str:
    return {
        "lbph": "LBPH",
        "ltp": "LTP",
        "tan_triggs_ltp": "Tan-Triggs + LTP",
        "lpq_w7": "LPQ (w=7)",
        "lpq_multiscale_w3_5_7": "Multi-scale LPQ (3/5/7)",
        "hog": "HOG + cosine",
    }.get(name, name)


def fmt_pct(value: float | None) -> str:
    return "NA" if value is None else f"{value:.2f}%"


def write_readme(
    path: Path,
    selections: list[Selection],
    summary: dict[str, Any],
    source_manifest: dict[str, Any],
) -> None:
    algorithms = summary["algorithms"]
    lbph_r1 = algorithms["lbph"]["all41_strict"]["rank1_percent"]
    lines = [
        "# Exploratory one-shot classical descriptor robustness smoke test",
        "",
        "> **Exploratory / diagnostic / non-canonical.** Do not cite this directory as canonical evidence, modify manuscript claims from it, or use it to recalibrate frozen thresholds.",
        "",
        "## Objective",
        "",
        "Test whether LTP- or LPQ-family descriptors look competitive enough with a freshly rerun one-shot LBPH baseline under the current 41-modification robustness battery to justify a controlled follow-up as the cascade's cheap first stage.",
        "",
        "## Headline ranking (strict detector + matcher system view)",
        "",
        "| Algorithm | Clean R1 | 41-mod R1 | Delta vs LBPH | Matcher-only R1 | p50 ms | Descriptor bytes | Distance AUC | -Margin AUC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(
        algorithms.values(),
        key=lambda item: item["all41_strict"]["rank1_percent"],
        reverse=True,
    )
    for item in ranked:
        auc = item["confidence_error_auc"]
        delta = item["all41_strict"]["rank1_percent"] - lbph_r1
        lines.append(
            f"| {algorithm_label(item['algorithm'])} | "
            f"{fmt_pct(item['clean']['rank1_percent'])} | "
            f"{fmt_pct(item['all41_strict']['rank1_percent'])} | "
            f"{delta:+.2f} pp | "
            f"{fmt_pct(item['all41_matcher_only']['rank1_percent'])} | "
            f"{item['timing']['total_recognition_ms']['p50']:.3f} | "
            f"{item['descriptor_bytes_per_identity']:,} | "
            f"{auc['best_distance_auc']:.3f} | {auc['negative_margin_auc']:.3f} |"
        )

    protocol = summary["protocol"]
    lines += [
        "",
        "## Protocol",
        "",
        f"- Identities: {protocol['identities']}; exactly one existing manifest gallery and one existing disjoint manifest probe per identity.",
        f"- Queries: {protocol['clean_queries']} clean + {protocol['modified_queries']} modified ({protocol['variant_count']} DL41 variants per probe).",
        "- Transform contract: current `get_modification_set('dl41')`; BGR transform before grayscale; `stable_rng(42, identity, probe basename, transform, level)`; each transformed array generated once.",
        "- Shared pipeline: one YuNet call per gallery/query, default score/NMS settings, largest-face rule, strict no-face failures.",
        "- LSDB crop contract: `assume_cropped=True`; YuNet gates each transformed pre-cropped tile, while every classical matcher receives the same successful full 100x100 grayscale tile. No landmark alignment is applied to the classical input.",
        "- Primary metric: threshold-free closed-set 1:N Rank-1. Frozen LBPH/SFace verification or cascade thresholds are not used.",
        f"- Shared modified-query detector failures: {protocol['modified_no_face']} / {protocol['modified_queries']}; matcher-only denominator: {protocol['modified_detected_queries']}.",
        "- Timing: warm recognition-only time in one process; excludes image I/O, transform generation, and YuNet. Extraction and 28-template gallery matching are timed separately.",
        "",
        "This is a small-scale LSDB analogue of the hard LFW robustness flow, not the older same-image transform-sensitivity test and not a literal raw-LFW crop pipeline.",
        "",
        "## Algorithms and fixed reconnaissance parameters",
        "",
    ]
    for item in algorithms.values():
        lines.append(f"### {algorithm_label(item['algorithm'])}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(item["parameters"], indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")

    lines += [
        "## Exact one-shot image selection",
        "",
        f"Source manifest: `{source_manifest['source_manifest']}` (SHA-256 `{source_manifest['source_manifest_sha256']}`). Its recorded dataset root is stale, so its relative paths were explicitly rebased to `{source_manifest['rebased_dataset_root']}` without resampling.",
        "",
        f"Selection hash: `{source_manifest['selection_sha256']}`. Selected-file binding hash: `{source_manifest['selected_files_binding_sha256']}`.",
        "",
        "| Identity | Gallery | Probe |",
        "|---|---|---|",
    ]
    for row in selections:
        lines.append(
            f"| {row.identity} | `{row.gallery_relpath}` | `{row.probe_relpath}` |"
        )

    env = summary["environment"]
    lines += [
        "",
        "## Environment",
        "",
        f"- OS: {env['platform']}",
        f"- CPU: {env['cpu']} ({env['logical_cpus']} logical CPUs)",
        f"- Python: {env['python']}",
        f"- OpenCV: {env['opencv']}; NumPy: {env['numpy']}; scikit-learn: {env['sklearn']}",
        f"- Git commit: `{env['git_commit']}`; dirty at run: `{env['git_dirty']}`",
        "",
        "## Caveats",
        "",
        "- One gallery image and one probe image per identity make this intentionally harsh and high-variance; the old 10-image LSDB enrollment result is not a comparator.",
        "- LTP/Tan-Triggs+LTP and multi-scale LPQ are same-battery exploratory variants; the best-looking variant is not independently validated.",
        "- Raw distance values are algorithm-specific. No LBPH threshold is transferred to LTP, LPQ, or HOG.",
        "- No-face failures are shared system failures. The matcher-only view excludes them but reports their count separately.",
        "- The optional HOG row is contextual and did not delay the required LBPH/LTP/LPQ comparison.",
        "",
        "## Files",
        "",
        "- `summary.json` / `summary.csv`: headline, grouped, timing, size, and AUC results.",
        "- `per_query_results.csv`: every algorithm/query decision, score, margin, detection status, and shared pixel/crop hashes.",
        "- `paired_lbph_vs_candidate.csv` / `paired_per_transform.csv`: strict and matcher-only paired outcomes.",
        "- `one_shot_manifest.json`: exact paths, file hashes, and split lineage.",
        "- `lbph_one_shot.yml`: freshly trained one-template-per-identity OpenCV LBPH model used by this smoke test.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    selections, derived_manifest = load_selections(
        args.source_manifest, args.data_root, args.limit_identities
    )
    identities = [row.identity for row in selections]
    queries, transform_contract = build_queries(
        selections, args.seed, args.limit_modifications
    )
    detector_contract = detect_and_cache_queries(queries)
    gallery_crops, gallery_contract = load_gallery_crops(selections)
    algorithms, native_validation = build_algorithms(
        identities, gallery_crops, output_dir
    )

    per_query_rows, indexed = evaluate(algorithms, identities, queries)
    timings = benchmark_timings(algorithms, queries, args)
    summaries = {
        name: summarize_algorithm(
            algorithm,
            [row for row in per_query_rows if row["algorithm"] == name],
            timings[name],
        )
        for name, algorithm in algorithms.items()
    }
    paired, paired_flat, paired_per_transform = build_paired(indexed, queries)

    clean_queries = [query for query in queries if query.is_clean]
    modified_queries = [query for query in queries if not query.is_clean]
    modified_no_face = sum(
        query.detection_status == "no_face" for query in modified_queries
    )
    protocol = {
        "status": "exploratory_diagnostic_non_canonical",
        "question": "threshold-free one-shot LSDB 1:N identification under current DL41 transforms",
        "identities": len(identities),
        "gallery_images": len(identities),
        "clean_queries": len(clean_queries),
        "variant_count": transform_contract["variant_count"],
        "modified_queries": len(modified_queries),
        "total_queries": len(queries),
        "modified_no_face": modified_no_face,
        "modified_detected_queries": len(modified_queries) - modified_no_face,
        "seed": args.seed,
        "modification_set": "dl41",
        "thresholds_used": False,
        "source_manifest_sha256": derived_manifest["source_manifest_sha256"],
        "one_shot_selection_sha256": derived_manifest["selection_sha256"],
        "selected_files_binding_sha256": derived_manifest[
            "selected_files_binding_sha256"
        ],
        "transform_contract": transform_contract,
        "detector_contract": detector_contract,
        "gallery_contract": gallery_contract,
        "lbph_native_distance_validation": native_validation,
    }

    full_run = args.limit_identities == 0 and args.limit_modifications == 0
    checks: dict[str, Any] = {
        "same_query_keys_all_algorithms": all(
            set(rows) == set(indexed["lbph"]) for rows in indexed.values()
        ),
        "per_query_row_count": len(per_query_rows),
        "expected_per_query_row_count": len(queries) * len(algorithms),
        "paired_totals_match_denominators": True,
        "paired_net_identity_holds": True,
        "shared_no_face_by_construction": True,
        "full_protocol_count_checks_applied": full_run,
    }
    for candidate, payload in paired.items():
        for scope, expected_total in (
            ("strict_all41", len(modified_queries)),
            ("matcher_only", len(modified_queries) - modified_no_face),
        ):
            checks["paired_totals_match_denominators"] &= (
                payload[scope]["total"] == expected_total
            )
        candidate_correct = summaries[candidate]["all41_strict"]["correct"]
        lbph_correct = summaries["lbph"]["all41_strict"]["correct"]
        checks["paired_net_identity_holds"] &= (
            payload["strict_all41"]["net_difference"]
            == candidate_correct - lbph_correct
        )
    if full_run:
        severity_totals = summaries["lbph"]["by_severity"]
        checks.update(
            {
                "identities_28": len(identities) == 28,
                "variants_41": transform_contract["variant_count"] == 41,
                "clean_queries_28": len(clean_queries) == 28,
                "modified_queries_1148": len(modified_queries) == 1148,
                "light_queries_476": severity_totals["light"]["strict_total"] == 476,
                "medium_queries_364": severity_totals["medium"]["strict_total"] == 364,
                "heavy_queries_308": severity_totals["heavy"]["strict_total"] == 308,
            }
        )
    non_boolean_count_keys = {
        "per_query_row_count",
        "expected_per_query_row_count",
        "full_protocol_count_checks_applied",
    }
    if not all(
        bool(value) for key, value in checks.items() if key not in non_boolean_count_keys
    ):
        raise RuntimeError(f"Protocol validation failed: {checks}")
    if checks["per_query_row_count"] != checks["expected_per_query_row_count"]:
        raise RuntimeError(f"Per-query row count failed: {checks}")

    import sklearn

    environment = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": platform.platform(),
        "cpu": cpu_name(),
        "logical_cpus": os.cpu_count(),
        "python": platform.python_version(),
        "opencv": cv.__version__,
        "numpy": np.__version__,
        "sklearn": sklearn.__version__,
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "git_dirty": bool(git_value("status", "--short")),
        "source_hashes": {
            str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"): sha256_file(path)
            for path in (
                SCRIPT_PATH,
                PROJECT_ROOT / "src" / "benchmark" / "modifications.py",
                PROJECT_ROOT / "src" / "benchmark" / "ltp_descriptor.py",
                PROJECT_ROOT / "src" / "benchmark" / "lpq_descriptor.py",
                PROJECT_ROOT / "src" / "benchmark" / "hog_descriptor.py",
            )
        },
    }
    summary = {
        "schema": "lsface-one-shot-descriptor-robustness-v1",
        "status": "exploratory_diagnostic_non_canonical",
        "protocol": protocol,
        "algorithms": summaries,
        "paired_vs_lbph": paired,
        "environment": environment,
        "validation_checks": checks,
        "wall_seconds": time.perf_counter() - started,
    }

    (output_dir / "one_shot_manifest.json").write_text(
        json.dumps(derived_manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    summary_rows: list[dict[str, Any]] = []
    lbph_r1 = summaries["lbph"]["all41_strict"]["rank1_percent"]
    for item in sorted(
        summaries.values(),
        key=lambda value: value["all41_strict"]["rank1_percent"],
        reverse=True,
    ):
        summary_rows.append(
            {
                "algorithm": item["algorithm"],
                "clean_correct": item["clean"]["correct"],
                "clean_total": item["clean"]["total"],
                "clean_rank1_percent": item["clean"]["rank1_percent"],
                "all41_strict_correct": item["all41_strict"]["correct"],
                "all41_strict_total": item["all41_strict"]["total"],
                "all41_strict_rank1_percent": item["all41_strict"]["rank1_percent"],
                "delta_vs_lbph_percentage_points": item["all41_strict"]["rank1_percent"] - lbph_r1,
                "matcher_only_correct": item["all41_matcher_only"]["correct"],
                "matcher_only_total": item["all41_matcher_only"]["total"],
                "matcher_only_rank1_percent": item["all41_matcher_only"]["rank1_percent"],
                "no_face": item["all41_strict"]["no_face"],
                "unusable": item["all41_strict"]["unusable"],
                "descriptor_bytes_per_identity": item["descriptor_bytes_per_identity"],
                "gallery_template_bytes": item["gallery_template_bytes"],
                "static_state_bytes": item["static_state_bytes"],
                "serialized_model_bytes": item["serialized_model_bytes"],
                "feature_extract_p50_ms": item["timing"]["feature_extraction_ms"]["p50"],
                "feature_extract_p95_ms": item["timing"]["feature_extraction_ms"]["p95"],
                "gallery_match_p50_ms": item["timing"]["gallery_matching_ms"]["p50"],
                "gallery_match_p95_ms": item["timing"]["gallery_matching_ms"]["p95"],
                "total_recognition_p50_ms": item["timing"]["total_recognition_ms"]["p50"],
                "total_recognition_p95_ms": item["timing"]["total_recognition_ms"]["p95"],
                "error_auc_best_distance": item["confidence_error_auc"]["best_distance_auc"],
                "error_auc_negative_margin": item["confidence_error_auc"]["negative_margin_auc"],
                "auc_n": item["confidence_error_auc"]["n"],
            }
        )
    write_csv(output_dir / "summary.csv", summary_rows)
    write_csv(output_dir / "per_query_results.csv", per_query_rows)
    write_csv(output_dir / "paired_lbph_vs_candidate.csv", paired_flat)
    write_csv(output_dir / "paired_per_transform.csv", paired_per_transform)

    grouped_rows: list[dict[str, Any]] = []
    for algorithm_name, item in summaries.items():
        for group_type in ("by_severity", "by_transform", "by_category"):
            for group, values in item[group_type].items():
                grouped_rows.append(
                    {
                        "algorithm": algorithm_name,
                        "group_type": group_type.removeprefix("by_"),
                        "group": group,
                        **values,
                    }
                )
    write_csv(output_dir / "grouped_results.csv", grouped_rows)
    write_readme(output_dir / "README.md", selections, summary, derived_manifest)

    print(json.dumps({
        "output_dir": str(output_dir),
        "identities": len(identities),
        "clean_queries": len(clean_queries),
        "modified_queries": len(modified_queries),
        "modified_no_face": modified_no_face,
        "algorithms": {
            name: {
                "clean_r1": item["clean"]["rank1_percent"],
                "all41_strict_r1": item["all41_strict"]["rank1_percent"],
                "matcher_only_r1": item["all41_matcher_only"]["rank1_percent"],
            }
            for name, item in summaries.items()
        },
        "wall_seconds": summary["wall_seconds"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
