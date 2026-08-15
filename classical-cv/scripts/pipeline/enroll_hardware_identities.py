#!/usr/bin/env python3
"""Enroll hardware-captured identities into one source database for LBPH + SFace.

Input layout::

    captures/
      Alice Cruz/
        001.jpg
        002.jpg
        003.jpg
      Ben Reyes/
        001.jpg

The central ``.npz`` contains one record per accepted source image:
``label``, normalized LBPH tile, SFace embedding, source name, and SHA-256.
It is intentionally the source of truth.  Every run rebuilds a fresh OpenCV
LBPH ``.yml`` and SFace mean-gallery ``.npy`` from exactly those same records.
``.npz`` is used instead of a pickled dict ``.npy`` so hardware can load it
with ``allow_pickle=False``.

The script never changes thresholds.  Deploy the printed release directory as
one bundle; do not mix its ``lbph.yml`` or ``sface_gallery.npy`` with another
release.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

IMAGE_EXTS = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
SCHEMA_VERSION = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        help="Folder containing one subfolder per identity. Required unless --rebuild-only.",
    )
    parser.add_argument(
        "--database",
        default="models/hardware/enrollment.npz",
        help="Central, append-only enrollment source database (.npz).",
    )
    parser.add_argument(
        "--lbph-config", default="deployed",
        help="LBPH descriptor alias/ID (deployed, selected, or rN_nN_gNxN).",
    )
    parser.add_argument(
        "--release-root",
        default="models/hardware/releases",
        help="Where immutable deployable LBPH + SFace bundles are written.",
    )
    parser.add_argument(
        "--sface-model",
        default="models/sface/face_recognition_sface_2021dec.onnx",
    )
    parser.add_argument("--assume-cropped", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--yunet-score-threshold", type=float, default=0.6)
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Accept an image YuNet cannot detect. Uses full image for LBPH and resize fallback for SFace.",
    )
    parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Continue when an input photo is rejected. Default aborts without changing central database.",
    )
    parser.add_argument(
        "--min-samples-per-identity",
        type=int,
        default=3,
        help="Reject completed enrollment if any identity has fewer samples (default: 3).",
    )
    parser.add_argument(
        "--replace-identity",
        action="append",
        default=[],
        metavar="NAME",
        help="Replace existing samples for NAME with accepted files supplied this run. Repeatable.",
    )
    parser.add_argument(
        "--rebuild-only",
        action="store_true",
        help="Make a new release from existing central database without reading images.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate/process input but write nothing.")
    return parser.parse_args()


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_records() -> dict[str, list]:
    return {
        "labels": [], "lbph_faces": [], "sface_embeddings": [], "sources": [], "sha256": [],
        "fallback": [],
    }


def load_records(database: Path) -> dict[str, list]:
    if not database.exists():
        return empty_records()
    with np.load(database, allow_pickle=False) as raw:
        required = {"labels", "lbph_faces", "sface_embeddings", "sources", "sha256", "fallback"}
        missing = required - set(raw.files)
        if missing:
            raise ValueError(f"Unsupported enrollment database; missing arrays: {sorted(missing)}")
        records = {key: raw[key].tolist() for key in required}
    validate_records(records)
    return records


def validate_records(records: dict[str, list]) -> None:
    sizes = {key: len(value) for key, value in records.items()}
    if len(set(sizes.values())) != 1:
        raise ValueError(f"Enrollment database arrays have different lengths: {sizes}")
    for face in records["lbph_faces"]:
        if np.asarray(face).shape != (100, 100):
            raise ValueError("Enrollment database contains an LBPH tile not shaped (100, 100).")
    for feature in records["sface_embeddings"]:
        if np.asarray(feature).reshape(-1).size != 128:
            raise ValueError("Enrollment database contains an SFace embedding not sized 128.")


def arrays_from_records(records: dict[str, list]) -> dict[str, np.ndarray]:
    validate_records(records)
    if not records["labels"]:
        raise RuntimeError("No enrolled samples remain in central database.")
    return {
        "labels": np.asarray(records["labels"], dtype=str),
        "lbph_faces": np.stack(records["lbph_faces"]).astype(np.uint8),
        "sface_embeddings": np.vstack(records["sface_embeddings"]).astype(np.float32),
        "sources": np.asarray(records["sources"], dtype=str),
        "sha256": np.asarray(records["sha256"], dtype=str),
        "fallback": np.asarray(records["fallback"], dtype=bool),
    }


def load_metadata(database: Path) -> dict | None:
    metadata_path = database.with_suffix(".json")
    if not database.exists():
        return None
    if not metadata_path.exists():
        raise RuntimeError(f"Central database metadata missing: {metadata_path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def save_database(database: Path, records: dict[str, list], metadata: dict) -> None:
    arrays = arrays_from_records(records)
    database.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = database.with_suffix(".json")
    with tempfile.NamedTemporaryFile(dir=database.parent, suffix=".npz", delete=False) as handle:
        temp_database = Path(handle.name)
        np.savez_compressed(handle, **arrays)
    with tempfile.NamedTemporaryFile(
        dir=metadata_path.parent, suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as handle:
        temp_metadata = Path(handle.name)
        json.dump(metadata, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp_database, database)
    os.replace(temp_metadata, metadata_path)


def iter_capture_files(input_dir: Path):
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    people = sorted(path for path in input_dir.iterdir() if path.is_dir())
    if not people:
        raise RuntimeError("Input directory needs one subfolder per identity.")
    for person_dir in people:
        files = sorted(path for path in person_dir.rglob("*") if path.suffix.lower() in IMAGE_EXTS)
        if not files:
            print(f"[WARN] No supported image files for {person_dir.name}; skipped.")
            continue
        for image_path in files:
            yield person_dir.name, image_path


def process_capture(
    image_path: Path,
    *,
    detector,
    sface,
    assume_cropped: bool,
    allow_fallback: bool,
):
    import cv2 as cv
    from src.classical_faces.pipeline import SPECS
    from src.classical_faces.preprocess import IMG_SIZE, normalize_face
    from src.hybrid.recognizer import make_sample

    image_bgr = cv.imread(str(image_path))
    if image_bgr is None:
        raise ValueError("unreadable image")
    gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
    detections = detector.detect(gray, image_bgr)
    if len(detections) > 1:
        raise ValueError("YuNet found multiple faces; use a photo containing exactly one person")
    if not detections:
        if not allow_fallback:
            raise ValueError("YuNet found no face (use --allow-fallback only for known cropped tiles)")
        face_gray = gray
        feature = sface.feature_from_crop(image_bgr)
        fallback = True
    else:
        sample = make_sample(
            detections[0], image_bgr=image_bgr, image_gray=gray, assume_cropped=assume_cropped
        )
        face_gray = sample.face_gray
        feature = (
            sface.feature_from_row(sample.image_bgr, sample.yunet_row)
            if sample.yunet_row is not None
            else sface.feature_from_crop(sample.image_bgr)
        )
        fallback = sample.yunet_row is None
    face = normalize_face(
        face_gray, img_size=IMG_SIZE, equalization=SPECS["lbph"].default_equalization
    )
    feature = np.asarray(feature, dtype=np.float32).reshape(-1)
    if face.shape != (100, 100) or feature.size != 128:
        raise ValueError(f"unexpected feature shapes: LBPH={face.shape}, SFace={feature.shape}")
    return face, feature, fallback


def update_records(
    args: argparse.Namespace,
    records: dict[str, list],
    input_dir: Path,
    descriptor_metadata: dict,
) -> tuple[dict, dict, dict]:
    from src.classical_faces.detection import create_face_detector
    from src.sface.recognizer import SFaceRecognizer

    detector = create_face_detector("yunet", yunet_score_threshold=args.yunet_score_threshold)
    sface_model = resolve(args.sface_model)
    sface = SFaceRecognizer(str(sface_model))
    import cv2 as cv
    recipe = {
        "detector": "yunet",
        "yunet_model_sha256": sha256_file(Path(detector.model_path)),
        "yunet_score_threshold": args.yunet_score_threshold,
        "assume_cropped": args.assume_cropped,
        "allow_fallback": args.allow_fallback,
        "sface_model_sha256": sha256_file(sface_model),
        "opencv_version": cv.__version__,
        "lbph": descriptor_metadata,
        "lbph_normalization": "normalize_face(100x100, configured lbph equalization)",
        "sface": "YuNet alignCrop then 128D feature; resize fallback only when allowed",
    }
    replace = set(args.replace_identity)
    incoming = empty_records()
    existing_fingerprints = dict(zip(records["sha256"], records["labels"]))
    seen_incoming: dict[str, str] = {}
    stats = Counter()
    for identity, image_path in iter_capture_files(input_dir):
        fingerprint = sha256_file(image_path)
        known_identity = existing_fingerprints.get(fingerprint)
        if known_identity is not None:
            if known_identity != identity:
                raise ValueError(
                    f"{image_path} already belongs to {known_identity!r} in central database, not {identity!r}."
                )
            if identity not in replace:
                stats["duplicates"] += 1
                continue
        if fingerprint in seen_incoming:
            if seen_incoming[fingerprint] != identity:
                raise ValueError(
                    f"{image_path} duplicates a capture assigned to {seen_incoming[fingerprint]!r}, "
                    f"not {identity!r}."
                )
            stats["duplicates"] += 1
            continue
        try:
            face, feature, fallback = process_capture(
                image_path,
                detector=detector,
                sface=sface,
                assume_cropped=args.assume_cropped,
                allow_fallback=args.allow_fallback,
            )
        except ValueError as exc:
            stats["rejected"] += 1
            print(f"[REJECT] {image_path}: {exc}")
            if not args.skip_invalid:
                raise RuntimeError("Enrollment aborted; use --skip-invalid to omit rejected photos.") from exc
            continue
        incoming["labels"].append(identity)
        incoming["lbph_faces"].append(face)
        incoming["sface_embeddings"].append(feature)
        incoming["sources"].append(str(image_path.relative_to(input_dir)))
        incoming["sha256"].append(fingerprint)
        incoming["fallback"].append(fallback)
        seen_incoming[fingerprint] = identity
        stats["accepted"] += 1
        stats["fallbacks"] += int(fallback)

    if replace:
        no_replacement = replace - set(incoming["labels"])
        if no_replacement:
            raise RuntimeError(f"Requested replacement has no accepted new samples: {sorted(no_replacement)}")
        keep = [idx for idx, label in enumerate(records["labels"]) if label not in replace]
        records = {key: [values[idx] for idx in keep] for key, values in records.items()}
    for key in records:
        records[key].extend(incoming[key])
    validate_records(records)
    return records, dict(stats), recipe


def ensure_sample_minimum(records: dict[str, list], minimum: int) -> None:
    if minimum < 1:
        raise ValueError("--min-samples-per-identity must be at least 1")
    counts = Counter(records["labels"])
    short = {name: count for name, count in sorted(counts.items()) if count < minimum}
    if short:
        joined = ", ".join(f"{name}={count}" for name, count in short.items())
        raise RuntimeError(f"Need at least {minimum} samples per identity; short: {joined}")
    if len(counts) < 2:
        raise RuntimeError("Need at least two identities before training LBPH.")


def build_release(
    records: dict[str, list],
    release_root: Path,
    database: Path,
    metadata: dict,
    lbph_config,
) -> Path:
    from src.sface.recognizer import SFaceGallery
    from src.independence_common import create_lbph_recognizer_for_config, lbph_config_metadata

    arrays = arrays_from_records(records)
    names = sorted(set(records["labels"]))
    label_map = {name: index for index, name in enumerate(names)}
    labels = np.asarray([label_map[name] for name in records["labels"]], dtype=np.int32)
    descriptor_metadata = lbph_config_metadata(lbph_config)
    release_root.mkdir(parents=True, exist_ok=True)
    release_name = (
        f"release-{descriptor_metadata['id']}-"
        f"{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    )
    final_path = release_root / release_name
    temporary_path = Path(tempfile.mkdtemp(dir=release_root, prefix=".pending-"))
    try:
        lbph = create_lbph_recognizer_for_config(lbph_config)
        lbph.train([face for face in arrays["lbph_faces"]], labels)
        lbph_name = f"lbph_{descriptor_metadata['id']}.yml"
        labels_name = f"labels_{descriptor_metadata['id']}.json"
        manifest_name = f"manifest_{descriptor_metadata['id']}.json"
        lbph.save(str(temporary_path / lbph_name))
        (temporary_path / labels_name).write_text(json.dumps(label_map, indent=2) + "\n", encoding="utf-8")
        grouped = {
            name: arrays["sface_embeddings"][arrays["labels"] == name].mean(axis=0, keepdims=True)
            for name in names
        }
        SFaceGallery(grouped).save(
            str(temporary_path / "sface_gallery.npy"), str(temporary_path / "sface_labels.json")
        )
        release_manifest = {
            "schema_version": SCHEMA_VERSION,
            "created_utc": utc_now(),
            "central_database": str(database),
            "identities": len(names),
            "samples": len(records["labels"]),
            "label_set": names,
            "lbph": {"model": lbph_name, "labels": labels_name, **descriptor_metadata},
            "sface": {"gallery": "sface_gallery.npy", "labels": "sface_labels.json", "embedding_dim": 128},
            "parity": {"same_central_sample_count": len(records["labels"]), "same_label_set": True},
            "enrollment_metadata": metadata,
        }
        (temporary_path / manifest_name).write_text(
            json.dumps(release_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary_path, final_path)
    except Exception:
        shutil.rmtree(temporary_path, ignore_errors=True)
        raise
    return final_path


def main() -> int:
    args = parse_args()
    if args.rebuild_only and args.input_dir:
        raise ValueError("Use either --rebuild-only or --input-dir, not both.")
    if not args.rebuild_only and not args.input_dir:
        raise ValueError("--input-dir is required unless --rebuild-only is used.")
    database = resolve(args.database)
    from src.independence_common import lbph_config_metadata, resolve_lbph_config

    descriptor_config = resolve_lbph_config(args.lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)
    stored_metadata = load_metadata(database)
    records = load_records(database)
    stats: dict[str, int] = {}
    if not args.rebuild_only:
        records, stats, recipe = update_records(
            args, records, resolve(args.input_dir), descriptor_metadata
        )
        old_recipe = (stored_metadata or {}).get("recipe") or {}
        old_capture_recipe = {k: v for k, v in old_recipe.items() if k != "lbph"}
        new_capture_recipe = {k: v for k, v in recipe.items() if k != "lbph"}
        if records["labels"] and stored_metadata and old_capture_recipe != new_capture_recipe:
            raise RuntimeError(
                "Incoming photos use a different extraction recipe/model from central database. "
                "Re-enroll all identities into a new database instead of mixing them."
            )
    else:
        recipe = (stored_metadata or {}).get("recipe")
        if recipe is None:
            raise RuntimeError("Cannot rebuild: central database has no extraction recipe metadata.")
        recipe = dict(recipe)
        recipe["lbph"] = descriptor_metadata
    ensure_sample_minimum(records, args.min_samples_per_identity)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "updated_utc": utc_now(),
        "identities": len(set(records["labels"])),
        "samples": len(records["labels"]),
        "recipe": recipe,
        "fallback_samples": int(np.count_nonzero(np.asarray(records["fallback"], dtype=bool))),
    }
    if args.dry_run:
        print(f"[DRY RUN] identities={metadata['identities']} samples={metadata['samples']} stats={stats}")
        return 0
    # Central DB is committed before its dependent release. If release creation is interrupted,
    # rerun with --rebuild-only; no incoming files need to be reprocessed.
    save_database(database, records, metadata)
    release = build_release(
        records, resolve(args.release_root), database, metadata, descriptor_config
    )
    print(f"[ENROLL] central database: {database}")
    print(f"[ENROLL] metadata        : {database.with_suffix('.json')}")
    print(f"[ENROLL] release bundle  : {release}")
    print(f"[ENROLL] identities={metadata['identities']} samples={metadata['samples']} stats={stats}")
    print("[DEPLOY] Read the descriptor-specific manifest in the release directory; "
          "it names the matching LBPH and SFace artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
