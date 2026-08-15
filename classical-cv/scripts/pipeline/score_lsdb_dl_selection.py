#!/usr/bin/env python3
"""Fresh same-split LSDB selection for archived DL candidate definitions.

The deprecated DL team's *selection* candidate list is SFace, ArcFace, and
FaceNet.  MobileNetV2 remains an archived source-code extra, not a selection
candidate.  This script rebuilds the three recoverable model runtimes,
enrols eight fit images per identity, calibrates each model independently on
two disjoint images per identity, then tests two untouched images per
identity.

Historical ``features/lasalledb1-*.npy`` files are audit inputs only.  They
have no held-out vectors or per-image pixel hashes, so this script never uses
them to calculate a fresh metric.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np


SCRIPT_PATH = Path(__file__).resolve()
CLASSICAL_ROOT = SCRIPT_PATH.parents[2]
WORKSPACE_ROOT = SCRIPT_PATH.parents[3]

DEFAULT_DATA_ROOT = WORKSPACE_ROOT / "data" / "lsdb" / "split"
DEFAULT_ARCHIVE_FEATURE_ROOT = WORKSPACE_ROOT / "deep-learning" / "features"
DEFAULT_YUNET = WORKSPACE_ROOT / "deep-learning" / "archive" / "models" / "face_detection_yunet_2023mar.onnx"
DEFAULT_SFACE = WORKSPACE_ROOT / "deep-learning" / "archive" / "models" / "face_recognition_sface_2021dec.onnx"

SELECTION_MODELS = ("sface", "arcface", "facenet")
NON_SELECTION_ARCHIVED_MODELS = ("mobilenet",)
MODEL_DIMS = {"sface": 128, "arcface": 512, "facenet": 512, "mobilenet": 1280}
MODEL_SCORE_METRICS = {
    "sface": "Euclidean L2 after unit normalization (lower is more similar)",
    "arcface": "1 - cosine similarity after unit normalization (lower is more similar)",
    "facenet": "Legacy raw-vector Euclidean L2 (lower is more similar)",
}
UNIT_NORMALIZED_MODELS = {"sface", "arcface"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class Sample:
    identity: str
    split: str
    path: Path
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class PreparedSample:
    sample: Sample
    face_bgr: np.ndarray
    face_sha256: str
    detection_score: float


@dataclass(frozen=True)
class EmbeddedSample:
    prepared: PreparedSample
    feature: np.ndarray


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_versions(names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not-installed"
    return result


def resolve_path(value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (WORKSPACE_ROOT / value).resolve()


def provenance_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=WORKSPACE_ROOT, text=True,
        capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else f"unavailable: {result.stderr.strip()}"


def sample_json(sample: Sample) -> dict[str, Any]:
    return {
        "identity": sample.identity,
        "split": sample.split,
        "path": str(sample.path),
        "relative_path": sample.relative_path,
        "sha256": sample.sha256,
    }


def dataset_tree_sha256(samples: list[Sample]) -> str:
    digest = hashlib.sha256()
    for sample in sorted(samples, key=lambda item: item.relative_path):
        digest.update(sample.relative_path.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(sample.sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def normalized_legacy_name(filename: str) -> str:
    """Map only legacy ``__orig`` spelling; never infer matching pixels."""
    return filename.replace("__orig", "")


def train_and_calibration(data_root: Path, expected_calibration_per_identity: int) -> tuple[list[Sample], list[Sample]]:
    train_root = data_root / "train"
    identities = sorted(path for path in train_root.iterdir() if path.is_dir())
    if not identities:
        raise RuntimeError(f"No identity folders under {train_root}")

    fit: list[Sample] = []
    calibration: list[Sample] = []
    for identity_dir in identities:
        images = sorted(
            path for path in identity_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if len(images) <= expected_calibration_per_identity:
            raise RuntimeError(f"{identity_dir.name}: need more than {expected_calibration_per_identity} train images")
        fit_paths, calibration_paths = images[:-expected_calibration_per_identity], images[-expected_calibration_per_identity:]
        for split, paths, sink in (("fit", fit_paths, fit), ("calibration", calibration_paths, calibration)):
            for path in paths:
                sink.append(Sample(
                    identity=identity_dir.name,
                    split=split,
                    path=path,
                    relative_path=path.relative_to(data_root).as_posix(),
                    sha256=sha256_file(path),
                ))
    return fit, calibration


def held_out_test(data_root: Path) -> list[Sample]:
    test_root = data_root / "test"
    if not test_root.is_dir():
        raise RuntimeError(f"Missing test root: {test_root}")
    samples: list[Sample] = []
    for identity_dir in sorted(path for path in test_root.iterdir() if path.is_dir()):
        for path in sorted(item for item in identity_dir.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS):
            samples.append(Sample(
                identity=identity_dir.name,
                split="test",
                path=path,
                relative_path=path.relative_to(data_root).as_posix(),
                sha256=sha256_file(path),
            ))
    return samples


def validate_split(
    fit: list[Sample], calibration: list[Sample], test: list[Sample],
    expected_identities: int, expected_fit_per_identity: int,
    expected_calibration_per_identity: int, expected_test_per_identity: int,
) -> list[str]:
    identities = sorted({sample.identity for sample in fit})
    all_identities = {sample.identity for sample in fit + calibration + test}
    if len(identities) != expected_identities or set(identities) != all_identities:
        raise RuntimeError(f"Expected {expected_identities} shared identities; found {len(identities)}")
    for identity in identities:
        counts = (
            sum(sample.identity == identity for sample in fit),
            sum(sample.identity == identity for sample in calibration),
            sum(sample.identity == identity for sample in test),
        )
        expected = (expected_fit_per_identity, expected_calibration_per_identity, expected_test_per_identity)
        if counts != expected:
            raise RuntimeError(f"{identity}: expected fit/calibration/test {expected}, found {counts}")
    paths = [sample.path.resolve() for sample in fit + calibration + test]
    if len(set(paths)) != len(paths):
        raise RuntimeError("Split leakage: one source path belongs to more than one cohort")
    return identities


def normalize_brightness(bgr_face: np.ndarray) -> np.ndarray:
    """Exact LAB-CLAHE preprocessing from deprecated ``feature_extract.py``."""
    lab = cv.cvtColor(bgr_face, cv.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv.split(lab)
    lightness = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
    return cv.cvtColor(cv.merge((lightness, a_channel, b_channel)), cv.COLOR_LAB2BGR)


def prepared_face_sha256(face_bgr: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(face_bgr)
    shape = np.asarray(contiguous.shape, dtype=np.int32).tobytes()
    return sha256_bytes(shape + contiguous.tobytes())


def prepare_samples(samples: list[Sample], detector: cv.FaceDetectorYN, recognizer: cv.FaceRecognizerSF) -> list[PreparedSample]:
    prepared: list[PreparedSample] = []
    failures: list[str] = []
    for index, sample in enumerate(samples, 1):
        image = cv.imread(str(sample.path))
        if image is None:
            failures.append(f"unreadable: {sample.relative_path}")
            continue
        detector.setInputSize((image.shape[1], image.shape[0]))
        ok, faces = detector.detect(image)
        if not ok or faces is None or len(faces) == 0:
            failures.append(f"no_yunet_face: {sample.relative_path}")
            continue
        row = faces[int(np.argmax(faces[:, 2] * faces[:, 3]))]
        face = normalize_brightness(recognizer.alignCrop(image, row))
        if face.size == 0 or not np.isfinite(face).all():
            failures.append(f"invalid_aligned_face: {sample.relative_path}")
            continue
        prepared.append(PreparedSample(
            sample=sample,
            face_bgr=face,
            face_sha256=prepared_face_sha256(face),
            detection_score=float(row[14]),
        ))
        if index % 50 == 0 or index == len(samples):
            print(f"[PREPARE] {index}/{len(samples)}", flush=True)
    if failures:
        raise RuntimeError(
            "DL trio campaign invalid: every planned record must prepare. "
            + "; ".join(failures[:10])
            + (" ..." if len(failures) > 10 else "")
        )
    return prepared


class SFaceExtractor:
    name = "sface"

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.recognizer = cv.FaceRecognizerSF.create(str(model_path), "")

    def extract(self, face_bgr: np.ndarray) -> np.ndarray:
        return self.recognizer.feature(face_bgr).reshape(-1)

    def provenance(self) -> dict[str, Any]:
        return {
            "implementation": "OpenCV FaceRecognizerSF.feature",
            "weight_path": provenance_path(self.model_path),
            "weight_sha256": sha256_file(self.model_path),
        }


class ArcFaceExtractor:
    name = "arcface"
    weight_source_url = "https://github.com/serengil/deepface_models/releases/download/v1.0/arcface_weights.h5"

    def __init__(self, deepface_home: Path) -> None:
        # Must precede the lazy DeepFace import: the package resolves this path at import/use time.
        os.environ["DEEPFACE_HOME"] = str(deepface_home)
        from deepface import DeepFace  # pylint: disable=import-outside-toplevel

        self.deepface_home = deepface_home
        self.deepface = DeepFace
        self.deepface.build_model(model_name="ArcFace")
        self.weight_path = deepface_home / ".deepface" / "weights" / "arcface_weights.h5"
        if not self.weight_path.is_file():
            raise FileNotFoundError(f"ArcFace weight was not materialized: {self.weight_path}")

    def extract(self, face_bgr: np.ndarray) -> np.ndarray:
        result = self.deepface.represent(
            img_path=face_bgr,
            model_name="ArcFace",
            detector_backend="skip",
            enforce_detection=False,
        )
        if not result or "embedding" not in result[0]:
            raise RuntimeError("DeepFace ArcFace returned no embedding")
        return np.asarray(result[0]["embedding"], dtype=np.float32).reshape(-1)

    def provenance(self) -> dict[str, Any]:
        return {
            "implementation": "DeepFace.represent(model_name='ArcFace', detector_backend='skip', enforce_detection=False)",
            "weight_source_url": self.weight_source_url,
            "weight_path": provenance_path(self.weight_path),
            "weight_sha256": sha256_file(self.weight_path),
        }


class FaceNetExtractor:
    name = "facenet"

    def __init__(self, cache_folder: Path) -> None:
        from keras_facenet import FaceNet  # pylint: disable=import-outside-toplevel

        self.cache_folder = cache_folder
        self.facenet = FaceNet(cache_folder=str(cache_folder))
        metadata = self.facenet.metadata
        self.weight_path = cache_folder / metadata["dir_name"] / metadata["keras_weights_filename"]
        if not self.weight_path.is_file():
            raise FileNotFoundError(f"FaceNet weight was not materialized: {self.weight_path}")

    def extract(self, face_bgr: np.ndarray) -> np.ndarray:
        rgb_face = cv.cvtColor(face_bgr, cv.COLOR_BGR2RGB)
        return self.facenet.embeddings(np.expand_dims(rgb_face, axis=0))[0]

    def provenance(self) -> dict[str, Any]:
        return {
            "implementation": "keras_facenet.FaceNet.embeddings after BGR-to-RGB conversion",
            "weight_source_url": self.facenet.metadata["keras_weights_url"],
            "weight_path": provenance_path(self.weight_path),
            "weight_sha256": sha256_file(self.weight_path),
        }


def normalize_feature(model_name: str, feature: np.ndarray) -> np.ndarray:
    vector = np.asarray(feature, dtype=np.float32).reshape(-1)
    if vector.size != MODEL_DIMS[model_name] or not np.isfinite(vector).all():
        raise RuntimeError(f"{model_name}: expected finite {MODEL_DIMS[model_name]}-D feature, got {vector.size}")
    if model_name not in UNIT_NORMALIZED_MODELS:
        return vector
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise RuntimeError(f"{model_name}: zero-norm feature")
    return vector / norm


def extract_model_features(model_name: str, extractor: Any, prepared: list[PreparedSample]) -> list[EmbeddedSample]:
    entries: list[EmbeddedSample] = []
    failures: list[str] = []
    for index, item in enumerate(prepared, 1):
        try:
            feature = normalize_feature(model_name, extractor.extract(item.face_bgr))
        except Exception as exc:  # every cohort record is mandatory
            failures.append(f"{item.sample.relative_path}: {type(exc).__name__}: {exc}")
            continue
        entries.append(EmbeddedSample(prepared=item, feature=feature))
        if index % 50 == 0 or index == len(prepared):
            print(f"[EMBED:{model_name}] {index}/{len(prepared)}", flush=True)
    if failures:
        raise RuntimeError(
            f"{model_name} campaign invalid: every planned record must embed. "
            + "; ".join(failures[:5])
            + (" ..." if len(failures) > 5 else "")
        )
    return entries


def build_gallery(
    model_name: str, fit: list[EmbeddedSample], identities: list[str], expected_fit_per_identity: int,
) -> dict[str, np.ndarray]:
    gallery: dict[str, np.ndarray] = {}
    for identity in identities:
        vectors = [item.feature for item in fit if item.prepared.sample.identity == identity]
        if len(vectors) != expected_fit_per_identity:
            raise RuntimeError(f"{model_name}/{identity}: expected {expected_fit_per_identity} enrolment vectors, found {len(vectors)}")
        centroid = np.mean(np.vstack(vectors), axis=0).astype(np.float32)
        if not np.isfinite(centroid).all():
            raise RuntimeError(f"{model_name}/{identity}: invalid gallery template")
        if model_name in UNIT_NORMALIZED_MODELS:
            norm = float(np.linalg.norm(centroid))
            if norm == 0.0:
                raise RuntimeError(f"{model_name}/{identity}: zero-norm gallery template")
            centroid = centroid / norm
        gallery[identity] = centroid
    return gallery


def score_against_templates(model_name: str, query: np.ndarray, templates: np.ndarray) -> np.ndarray:
    if model_name == "arcface":
        return 1.0 - (templates @ query.reshape(-1))
    return np.linalg.norm(templates - query.reshape(1, -1), axis=1)


def pair_score_rows(model_name: str, queries: list[EmbeddedSample], gallery: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    labels = sorted(gallery)
    templates = np.vstack([gallery[label] for label in labels])
    rows: list[dict[str, Any]] = []
    for query in queries:
        scores = score_against_templates(model_name, query.feature, templates)
        for label, score in zip(labels, scores):
            rows.append({
                "model": model_name,
                "score_metric": MODEL_SCORE_METRICS[model_name],
                "query_identity": query.prepared.sample.identity,
                "query_relative_path": query.prepared.sample.relative_path,
                "query_sha256": query.prepared.sample.sha256,
                "query_preprocessed_face_sha256": query.prepared.face_sha256,
                "gallery_identity": label,
                "score": float(score),
                "is_genuine": bool(label == query.prepared.sample.identity),
            })
    return rows


def write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"No rows to write: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_embeddings(path: Path, model_name: str, entries: list[EmbeddedSample]) -> None:
    np.savez_compressed(
        path,
        model=np.asarray([model_name], dtype="U32"),
        identities=np.asarray([entry.prepared.sample.identity for entry in entries], dtype="U128"),
        splits=np.asarray([entry.prepared.sample.split for entry in entries], dtype="U16"),
        relative_paths=np.asarray([entry.prepared.sample.relative_path for entry in entries], dtype="U256"),
        image_sha256=np.asarray([entry.prepared.sample.sha256 for entry in entries], dtype="U64"),
        preprocessed_face_sha256=np.asarray([entry.prepared.face_sha256 for entry in entries], dtype="U64"),
        detection_scores=np.asarray([entry.prepared.detection_score for entry in entries], dtype=np.float32),
        embeddings=np.vstack([entry.feature for entry in entries]).astype(np.float32),
    )


def write_embedding_records(path: Path, model_name: str, entries: list[EmbeddedSample]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index, entry in enumerate(entries):
            handle.write(json.dumps({
                "embedding_index": index,
                "model": model_name,
                "identity": entry.prepared.sample.identity,
                "split": entry.prepared.sample.split,
                "relative_path": entry.prepared.sample.relative_path,
                "image_sha256": entry.prepared.sample.sha256,
                "preprocessed_face_sha256": entry.prepared.face_sha256,
                "detection_score": entry.prepared.detection_score,
                "embedding_file": f"embeddings_{model_name}.npz",
                "embedding_dtype": "float32",
                "embedding_dimension": int(entry.feature.size),
                "embedding_normalization": "L2 unit" if model_name in UNIT_NORMALIZED_MODELS else "legacy raw vector",
            }, sort_keys=True) + "\n")


def test_decisions(model_name: str, test_rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    by_query: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in test_rows:
        by_query.setdefault((row["query_identity"], row["query_relative_path"]), []).append(row)
    decisions: list[dict[str, Any]] = []
    for (identity, relative_path), rows in sorted(by_query.items()):
        scores = np.asarray([float(row["score"]) for row in rows], dtype=np.float64)
        best_score = float(np.min(scores))
        exact_best = [row for row in rows if float(row["score"]) == best_score]
        predicted = exact_best[0]["gallery_identity"]
        true_row = next(row for row in rows if row["gallery_identity"] == identity)
        strict_rank1 = len(exact_best) == 1 and predicted == identity
        accepted = float(true_row["score"]) <= threshold
        decisions.append({
            "model": model_name,
            "score_metric": MODEL_SCORE_METRICS[model_name],
            "query_identity": identity,
            "query_relative_path": relative_path,
            "query_sha256": true_row["query_sha256"],
            "predicted_identity": predicted,
            "best_score": best_score,
            "genuine_score": float(true_row["score"]),
            "best_score_ties": len(exact_best),
            "strict_rank1_correct": bool(strict_rank1),
            "accepted_at_calibration_threshold": bool(accepted),
            "tar_hit": bool(strict_rank1 and accepted),
        })
    return decisions


def archived_feature_inventory(archive_root: Path, fit: list[Sample], test: list[Sample]) -> dict[str, Any]:
    expected_fit = {(sample.identity, sample.path.name) for sample in fit}
    expected_test = {(sample.identity, sample.path.name) for sample in test}
    models: dict[str, Any] = {}
    for model in SELECTION_MODELS + NON_SELECTION_ARCHIVED_MODELS:
        path = archive_root / f"lasalledb1-{model}.npy"
        if not path.exists():
            models[model] = {"status": "feature_file_missing", "path": str(path)}
            continue
        try:
            data = np.load(path, allow_pickle=True).item()
            rows = {
                (identity, normalized_legacy_name(str(filename)))
                for identity, entry in data.items()
                for filename in entry["filenames"]
            }
            dimensions = sorted({
                int(np.asarray(vector).reshape(-1).size)
                for entry in data.values()
                for vector in np.asarray(entry["embeddings"])
            })
        except Exception as exc:
            models[model] = {
                "status": "feature_file_unreadable",
                "path": str(path),
                "sha256": sha256_file(path),
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        models[model] = {
            "selection_candidate": model in SELECTION_MODELS,
            "status": "archive_train_vectors_only_no_held_out_metric" if model in SELECTION_MODELS else "nonselection_archived_extra",
            "feature_path": provenance_path(path),
            "feature_sha256": sha256_file(path),
            "archived_records": len(rows),
            "embedding_dimensions": dimensions,
            "fit_identifier_matches_after_legacy_name_normalization": len(rows & expected_fit),
            "fit_identifier_records_expected": len(expected_fit),
            "test_identifier_matches": len(rows & expected_test),
            "test_identifier_records_expected": len(expected_test),
            "pixel_hash_binding_present": False,
        }
    return {
        "purpose": "Audit only. Archived vectors are never used for fresh trio metrics.",
        "selection_candidates": list(SELECTION_MODELS),
        "nonselection_archived_extras": list(NON_SELECTION_ARCHIVED_MODELS),
        "legacy_filename_normalization": "remove '__orig' before matching current train identifiers; this does not establish pixel equality",
        "models": models,
    }


def archive_similarity_diagnostic(model_name: str, archive_root: Path, fit: list[EmbeddedSample]) -> dict[str, Any]:
    path = archive_root / f"lasalledb1-{model_name}.npy"
    if not path.is_file():
        return {"status": "archive_file_missing"}
    data = np.load(path, allow_pickle=True).item()
    old_by_key: dict[tuple[str, str], np.ndarray] = {}
    for identity, entry in data.items():
        for filename, vector in zip(entry["filenames"], entry["embeddings"]):
            old_by_key[(identity, normalized_legacy_name(str(filename)))] = np.asarray(vector, dtype=np.float32).reshape(-1)
    cosines: list[float] = []
    for entry in fit:
        key = (entry.prepared.sample.identity, entry.prepared.sample.path.name)
        archived = old_by_key.get(key)
        if archived is None or archived.size != entry.feature.size:
            continue
        fresh = entry.feature.reshape(-1)
        denominator = float(np.linalg.norm(fresh) * np.linalg.norm(archived))
        if denominator > 0.0:
            cosines.append(float(np.dot(fresh, archived) / denominator))
    if not cosines:
        return {"status": "no_identifier_overlap"}
    values = np.asarray(cosines, dtype=np.float64)
    return {
        "status": "diagnostic_only_no_pixel_hash_binding",
        "identifier_overlap": int(values.size),
        "expected_fit_records": len(fit),
        "cosine_similarity_min": float(values.min()),
        "cosine_similarity_median": float(np.median(values)),
        "cosine_similarity_max": float(values.max()),
        "interpretation": "Not an equivalence check: archive inputs lack per-image pixel hashes and historical source pixels are unavailable.",
    }


def score_model(
    model_name: str,
    extractor: Any,
    prepared: list[PreparedSample],
    identities: list[str],
    expected_fit_per_identity: int,
    expected_calibration_per_identity: int,
    far_percent: float,
    output_dir: Path,
    archive_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    entries = extract_model_features(model_name, extractor, prepared)
    by_split = {
        split: [entry for entry in entries if entry.prepared.sample.split == split]
        for split in ("fit", "calibration", "test")
    }
    gallery = build_gallery(model_name, by_split["fit"], identities, expected_fit_per_identity)
    calibration_rows = pair_score_rows(model_name, by_split["calibration"], gallery)
    test_rows = pair_score_rows(model_name, by_split["test"], gallery)

    expected_pair_rows = len(identities) * len(identities) * expected_calibration_per_identity
    expected_impostor_rows = len(identities) * (len(identities) - 1) * expected_calibration_per_identity
    if len(calibration_rows) != expected_pair_rows:
        raise RuntimeError(f"{model_name}: expected {expected_pair_rows} calibration score rows, got {len(calibration_rows)}")
    impostor_scores = sorted(float(row["score"]) for row in calibration_rows if not row["is_genuine"])
    genuine_scores = [float(row["score"]) for row in calibration_rows if row["is_genuine"]]
    if len(impostor_scores) != expected_impostor_rows:
        raise RuntimeError(f"{model_name}: expected {expected_impostor_rows} calibration impostor scores, got {len(impostor_scores)}")
    rank = max(1, int(np.floor(far_percent / 100.0 * len(impostor_scores))))
    threshold = float(impostor_scores[rank - 1])
    calibration_accepts = sum(score <= threshold for score in genuine_scores)
    realized_far = sum(score <= threshold for score in impostor_scores) / len(impostor_scores)
    threshold_ties = sum(score == threshold for score in impostor_scores)
    decisions = test_decisions(model_name, test_rows, threshold)
    if len(decisions) != len(by_split["test"]):
        raise RuntimeError(f"{model_name}: expected {len(by_split['test'])} test decisions, got {len(decisions)}")

    embedding_path = output_dir / f"embeddings_{model_name}.npz"
    records_path = output_dir / f"embedding_records_{model_name}.jsonl"
    gallery_path = output_dir / f"gallery_templates_{model_name}.npz"
    gallery_manifest_path = output_dir / f"gallery_manifest_{model_name}.json"
    calibration_path = output_dir / f"calibration_scores_{model_name}.csv"
    test_path = output_dir / f"test_scores_{model_name}.csv"
    decisions_path = output_dir / f"test_decisions_{model_name}.csv"
    archive_diag_path = output_dir / f"archive_similarity_{model_name}.json"

    write_embeddings(embedding_path, model_name, entries)
    write_embedding_records(records_path, model_name, entries)
    np.savez_compressed(
        gallery_path,
        identities=np.asarray(identities, dtype="U128"),
        templates=np.vstack([gallery[identity] for identity in identities]).astype(np.float32),
    )
    json_dump(gallery_manifest_path, {
        "model": model_name,
        "template_rule": "mean of eight fit vectors per identity, then L2-normalize centroid" if model_name in UNIT_NORMALIZED_MODELS else "mean of eight raw fit vectors per identity",
        "identities": identities,
        "fit_records": len(by_split["fit"]),
        "feature_dimension": MODEL_DIMS[model_name],
        "feature_vector_bytes": MODEL_DIMS[model_name] * 4,
        "score_metric": MODEL_SCORE_METRICS[model_name],
    })
    write_rows_csv(calibration_path, calibration_rows)
    write_rows_csv(test_path, test_rows)
    write_rows_csv(decisions_path, decisions)
    json_dump(archive_diag_path, archive_similarity_diagnostic(model_name, archive_root, by_split["fit"]))

    family = {
        "status": "fresh_same_split",
        "score_metric": MODEL_SCORE_METRICS[model_name],
        "threshold": threshold,
        "calibration_error_rank": rank,
        "calibration_threshold_ties": threshold_ties,
        "calibration_realized_far_percent": 100.0 * realized_far,
        "calibration_tar_percent": 100.0 * calibration_accepts / len(genuine_scores),
        "test_n": len(decisions),
        "test_rank1_percent": 100.0 * sum(row["strict_rank1_correct"] for row in decisions) / len(decisions),
        "test_tar_percent": 100.0 * sum(row["tar_hit"] for row in decisions) / len(decisions),
        "test_rank1_tie_count": sum(int(row["best_score_ties"]) > 1 for row in decisions),
        "feature_dimension": MODEL_DIMS[model_name],
        "feature_vector_bytes": MODEL_DIMS[model_name] * 4,
        "enrollment_templates": len(gallery),
        "archive_similarity_diagnostic": archive_diag_path.name,
    }
    return family, [
        embedding_path.name, records_path.name, gallery_path.name, gallery_manifest_path.name,
        calibration_path.name, test_path.name, decisions_path.name, archive_diag_path.name,
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--yunet-model", type=Path, default=DEFAULT_YUNET)
    parser.add_argument("--sface-model", type=Path, default=DEFAULT_SFACE)
    parser.add_argument("--archive-feature-root", type=Path, default=DEFAULT_ARCHIVE_FEATURE_ROOT)
    parser.add_argument("--deepface-home", type=Path, default=Path(os.environ.get("DEEPFACE_HOME", Path.home())))
    parser.add_argument("--facenet-cache", type=Path, default=Path.home() / ".keras-facenet")
    parser.add_argument("--detector-score-threshold", type=float, default=0.5,
                        help="Frozen for this fresh campaign; 0.6 misses one current fit image.")
    parser.add_argument("--far-percent", type=float, default=1.058)
    parser.add_argument("--expected-identities", type=int, default=28)
    parser.add_argument("--expected-fit-per-identity", type=int, default=8)
    parser.add_argument("--expected-calibration-per-identity", type=int, default=2)
    parser.add_argument("--expected-test-per-identity", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_root = resolve_path(args.data_root)
    output_dir = resolve_path(args.output_dir)
    yunet_model = resolve_path(args.yunet_model)
    sface_model = resolve_path(args.sface_model)
    archive_root = resolve_path(args.archive_feature_root)
    deepface_home = resolve_path(args.deepface_home)
    facenet_cache = resolve_path(args.facenet_cache)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {output_dir}")
    for path, label in ((data_root, "data root"), (yunet_model, "YuNet model"), (sface_model, "SFace model"), (archive_root, "archive feature root")):
        if not path.exists():
            raise SystemExit(f"Missing {label}: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    fit_samples, calibration_samples = train_and_calibration(data_root, args.expected_calibration_per_identity)
    test_samples = held_out_test(data_root)
    identities = validate_split(
        fit_samples, calibration_samples, test_samples,
        args.expected_identities, args.expected_fit_per_identity,
        args.expected_calibration_per_identity, args.expected_test_per_identity,
    )
    all_samples = fit_samples + calibration_samples + test_samples
    split_manifest_path = output_dir / "split_manifest.json"
    json_dump(split_manifest_path, {
        "data_root": str(data_root),
        "identity_count": len(identities),
        "cohorts": {
            "fit": [sample_json(sample) for sample in fit_samples],
            "calibration": [sample_json(sample) for sample in calibration_samples],
            "test": [sample_json(sample) for sample in test_samples],
        },
    })

    detector = cv.FaceDetectorYN.create(str(yunet_model), "", (320, 320), args.detector_score_threshold)
    sface_aligner = cv.FaceRecognizerSF.create(str(sface_model), "")
    prepared = prepare_samples(all_samples, detector, sface_aligner)

    extractors: dict[str, Any] = {
        "sface": SFaceExtractor(sface_model),
        "arcface": ArcFaceExtractor(deepface_home),
        "facenet": FaceNetExtractor(facenet_cache),
    }
    families: dict[str, dict[str, Any]] = {}
    artifact_names = ["split_manifest.json"]
    for model_name in SELECTION_MODELS:
        family, names = score_model(
            model_name, extractors[model_name], prepared, identities,
            args.expected_fit_per_identity, args.expected_calibration_per_identity,
            args.far_percent, output_dir, archive_root,
        )
        families[model_name] = family
        artifact_names.extend(names)

    inventory_path = output_dir / "archived_candidate_inventory.json"
    json_dump(inventory_path, archived_feature_inventory(archive_root, fit_samples, test_samples))
    artifact_names.append(inventory_path.name)

    selection_order = sorted(
        SELECTION_MODELS,
        key=lambda name: (
            -float(families[name]["test_tar_percent"]),
            -float(families[name]["test_rank1_percent"]),
            int(families[name]["feature_vector_bytes"]),
            name,
        ),
    )
    summary_path = output_dir / "summary.json"
    json_dump(summary_path, {
        "status": "fresh_same_split_dl_trio_campaign",
        "selection_candidates": list(SELECTION_MODELS),
        "protocol": {
            "dataset": "root data/lsdb/split",
            "fit_images": len(fit_samples),
            "calibration_images": len(calibration_samples),
            "test_images": len(test_samples),
            "identities": len(identities),
            "calibration_impostor_scores_per_model": len(identities) * (len(identities) - 1) * args.expected_calibration_per_identity,
            "target_far_percent": args.far_percent,
            "threshold_source": "LSDB calibration cross-identity scores only, independently per model",
            "selection_note": "Fresh DL-only same-split comparison. It neither changes frozen LFW thresholds nor compares deep and classical model families as one accuracy contest.",
        },
        "selection_rule": "Rank held-out TAR, then held-out Rank-1, then smaller float32 feature vector; lexical model name only if still tied.",
        "selection_order": selection_order,
        "selected_model": selection_order[0],
        "families": families,
    })
    artifact_names.append(summary_path.name)

    source_git_commit = git_text("rev-parse", "HEAD")
    provenance_path_file = output_dir / "run_provenance.json"
    json_dump(provenance_path_file, {
        "run_name": output_dir.name,
        "source_output_dir": output_dir.relative_to(WORKSPACE_ROOT).as_posix(),
        "source_script": SCRIPT_PATH.relative_to(WORKSPACE_ROOT).as_posix(),
        "source_script_sha256": sha256_file(SCRIPT_PATH),
        "source_git_commit": source_git_commit,
        "source_git_commit_at": git_text("log", "-1", "--format=%cI"),
        "git_commit": source_git_commit,
        "git_status_porcelain": git_text("status", "--porcelain"),
        "argv": sys.argv,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "opencv": cv.__version__,
            "packages": package_versions(["tensorflow", "keras", "tf-keras", "deepface", "keras-facenet", "scipy", "opencv-python"]),
        },
        "models": {
            "yunet": {"path": provenance_path(yunet_model), "sha256": sha256_file(yunet_model)},
            **{name: extractors[name].provenance() for name in SELECTION_MODELS},
        },
        "preprocessing": {
            "detector": "YuNet largest-face detection",
            "detector_score_threshold": args.detector_score_threshold,
            "alignment": "FaceRecognizerSF.alignCrop",
            "brightness": "LAB CLAHE clipLimit=2.0, tileGridSize=(8,8)",
            "feature": {
                "sface": "FaceRecognizerSF.feature then float32 L2 normalization",
                "arcface": "DeepFace.represent with detector_backend='skip' then float32 L2 normalization",
                "facenet": "keras_facenet.FaceNet after BGR-to-RGB; raw-vector score preserved",
            },
            "gallery": "mean of eight fit vectors per identity; unit-model centroids normalized after mean",
            "no_face_policy": "fail run; no silently skipped cohort records",
        },
        "split_manifest": {
            "path": split_manifest_path.name,
            "sha256": sha256_file(split_manifest_path),
            "data_tree_sha256": dataset_tree_sha256(all_samples),
        },
        "counts": {
            "fit": len(fit_samples),
            "calibration": len(calibration_samples),
            "test": len(test_samples),
            "prepared": len(prepared),
            "calibration_score_rows_per_model": len(identities) * len(identities) * args.expected_calibration_per_identity,
            "calibration_impostor_scores_per_model": len(identities) * (len(identities) - 1) * args.expected_calibration_per_identity,
            "test_score_rows_per_model": len(test_samples) * len(identities),
        },
        "archive_boundary": "Archived DL feature files are audit-only: no held-out vectors and no per-image pixel-hash binding. Fresh trio metrics use only newly extracted current split pixels.",
    })
    artifact_names.append(provenance_path_file.name)
    hashes_path = output_dir / "artifact_hashes.json"
    json_dump(hashes_path, {"artifacts": {name: sha256_file(output_dir / name) for name in artifact_names}})

    print("[OK] DL trio selection order: " + " > ".join(selection_order))
    for name in SELECTION_MODELS:
        family = families[name]
        print(
            f"[OK] {name}: threshold={family['threshold']:.8f} "
            f"FAR={family['calibration_realized_far_percent']:.4f}% "
            f"TAR={family['test_tar_percent']:.2f}% Rank-1={family['test_rank1_percent']:.2f}%"
        )
    print(f"[OK] Raw artifacts: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
