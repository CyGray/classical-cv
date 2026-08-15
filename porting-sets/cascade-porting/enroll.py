#!/usr/bin/env python3
"""Build Raspberry Pi LBPH + SFace artifacts from one central enrollment DB.

Examples:
  python enroll.py --identity Alice --input captures/alice.jpg
  python enroll.py --identity Alice --input captures/alice/
  python enroll.py --input captures/   # captures/<identity>/*.jpg

``enrollment/enrollment.npz`` is pickle-free source-of-truth storage. It has
one accepted image record with BOTH normalized LBPH tile and SFace embedding.
Every update regenerates an LBPH .yml and SFace gallery from those same rows.
The Pi runtime uses ``enrollment/current.json`` automatically.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections import Counter
from pathlib import Path

import cv2 as cv
import numpy as np

from lbph_config import DEPLOYED_PROFILE, SELECTED_PROFILE, make_lbph, resolve_descriptor

ROOT = Path(__file__).resolve().parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DB = ROOT / "enrollment" / "enrollment.npz"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="One image, an identity folder, or folders grouped by identity.")
    parser.add_argument("--identity", help="Required for one image or a folder of one person's images.")
    parser.add_argument("--include-name", help="Only enroll files with this exact name, e.g. light_front.jpg.")
    parser.add_argument("--replace-identity", action="append", default=[], metavar="NAME")
    parser.add_argument("--database", default=str(DB))
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--skip-invalid", action="store_true")
    parser.add_argument("--rebuild-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--descriptor-profile",
        choices=(DEPLOYED_PROFILE, SELECTED_PROFILE),
        default=DEPLOYED_PROFILE,
        help=(
            "LBPH profile to train: deployed r1_n8_g8x8 (default) or selected "
            "candidate r3_n8_g6x6. Selected requires matching calibrated thresholds."
        ),
    )
    return parser.parse_args()


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty() -> dict[str, list]:
    return {"labels": [], "lbph_faces": [], "sface_embeddings": [], "sha256": [], "sources": []}


def load(db: Path) -> dict[str, list]:
    if not db.exists():
        return empty()
    with np.load(db, allow_pickle=False) as raw:
        needed = set(empty())
        if needed - set(raw.files):
            raise RuntimeError(f"Bad central DB; missing: {sorted(needed - set(raw.files))}")
        records = {key: raw[key].tolist() for key in needed}
    validate(records)
    return records


def validate(records: dict[str, list]) -> None:
    if len({len(v) for v in records.values()}) != 1:
        raise RuntimeError("Central DB arrays have different lengths.")
    for tile in records["lbph_faces"]:
        if np.asarray(tile).shape != (100, 100):
            raise RuntimeError("Central DB has invalid LBPH tile shape.")
    for feature in records["sface_embeddings"]:
        if np.asarray(feature).reshape(-1).size != 128:
            raise RuntimeError("Central DB has invalid SFace feature shape.")


def paths(input_path: Path, identity: str | None, include_name: str | None):
    if input_path.is_file():
        if not identity:
            raise ValueError("--identity is required with one image.")
        yield identity, input_path
        return
    if not input_path.is_dir():
        raise FileNotFoundError(input_path)
    if identity:
        for image in sorted(p for p in input_path.rglob("*") if p.suffix.lower() in IMAGE_EXTS and (not include_name or p.name == include_name)):
            yield identity, image
        return
    for person in sorted(p for p in input_path.iterdir() if p.is_dir()):
        for image in sorted(p for p in person.rglob("*") if p.suffix.lower() in IMAGE_EXTS and (not include_name or p.name == include_name)):
            yield person.name, image


def normalize(face_gray: np.ndarray) -> np.ndarray:
    img = cv.resize(face_gray, (100, 100), interpolation=cv.INTER_AREA).astype(np.float32) / 255.0
    alpha, tau, gamma = 0.1, 10.0, 0.2
    img = np.power(img, gamma)
    img = cv.GaussianBlur(img, (0, 0), sigmaX=1.0)
    img = img / np.power(np.mean(np.power(np.abs(img), alpha)), 1.0 / alpha)
    img = img / np.power(np.mean(np.power(np.abs(img), tau)), 1.0 / tau)
    img = tau * np.tanh(img / tau)
    return np.uint8(cv.normalize(img, None, 0, 255, cv.NORM_MINMAX))


def extract(path: Path, detector, sface) -> tuple[np.ndarray, np.ndarray]:
    image = cv.imread(str(path))
    if image is None:
        raise ValueError("unreadable")
    h, w = image.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(image)
    if faces is None or len(faces) != 1:
        raise ValueError("need exactly one YuNet-detected face")
    row = faces[0]
    x, y, bw, bh = (int(v) for v in row[:4])
    x, y = max(0, x), max(0, y)
    bw, bh = min(bw, w - x), min(bh, h - y)
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    face = gray[y : y + bh, x : x + bw]
    if face.size == 0:
        raise ValueError("empty face crop")
    feature = sface.feature(sface.alignCrop(image, row)).reshape(-1).astype(np.float32)
    if feature.size != 128 or not np.isfinite(feature).all():
        raise ValueError("invalid SFace feature")
    return normalize(face), feature


def save_db(db: Path, records: dict[str, list], metadata: dict) -> None:
    validate(records)
    db.parent.mkdir(parents=True, exist_ok=True)
    arrays = {
        "labels": np.asarray(records["labels"], dtype=str),
        "lbph_faces": np.stack(records["lbph_faces"]).astype(np.uint8),
        "sface_embeddings": np.vstack(records["sface_embeddings"]).astype(np.float32),
        "sha256": np.asarray(records["sha256"], dtype=str),
        "sources": np.asarray(records["sources"], dtype=str),
    }
    with tempfile.NamedTemporaryFile(dir=db.parent, suffix=".npz", delete=False) as handle:
        temp = Path(handle.name)
        np.savez_compressed(handle, **arrays)
    os.replace(temp, db)
    (db.with_suffix(".json")).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def build_release(
    records: dict[str, list], db: Path, descriptor_profile: str = DEPLOYED_PROFILE
) -> Path:
    descriptor = resolve_descriptor(descriptor_profile)
    names = sorted(set(records["labels"]))
    labels_map = {name: index for index, name in enumerate(names)}
    release_root = db.parent / "releases"
    release_root.mkdir(parents=True, exist_ok=True)
    final = release_root / f"release-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    staging = Path(tempfile.mkdtemp(dir=release_root, prefix=".pending-"))
    try:
        lbph = make_lbph(descriptor)
        lbph.train([np.asarray(x, dtype=np.uint8) for x in records["lbph_faces"]], np.asarray([labels_map[x] for x in records["labels"]], dtype=np.int32))
        lbph.save(str(staging / "lbph.yml"))
        (staging / "labels.json").write_text(json.dumps(labels_map, indent=2) + "\n", encoding="utf-8")
        matrix = np.vstack(records["sface_embeddings"]).astype(np.float32)
        gallery = {name: matrix[np.asarray(records["labels"]) == name].mean(axis=0, keepdims=True) for name in names}
        np.save(staging / "sface_gallery.npy", gallery, allow_pickle=True)  # Legacy Pi runtime format.
        (staging / "manifest.json").write_text(json.dumps({
            "created_utc": now(),
            "database": str(db),
            "identities": names,
            "samples": len(records["labels"]),
            "parity": "same central rows rebuild both engines",
            "descriptor_id": descriptor.descriptor_id,
            "lbph_descriptor": descriptor.to_dict(),
        }, indent=2) + "\n", encoding="utf-8")
        # Windows refuses os.replace() for directories. Same-parent rename is
        # atomic on the target filesystem while the destination is unique.
        staging.rename(final)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    pointer = db.parent / "current.json"
    with tempfile.NamedTemporaryFile(dir=pointer.parent, suffix=".json", mode="w", encoding="utf-8", delete=False) as handle:
        json.dump({"release": str(final.relative_to(pointer.parent)), "updated_utc": now()}, handle, indent=2)
        temp = Path(handle.name)
    os.replace(temp, pointer)
    return final


def main() -> int:
    options = args()
    if options.rebuild_only == bool(options.input):
        raise ValueError("Provide --input, or use --rebuild-only.")
    db = Path(options.database)
    if not db.is_absolute():
        db = ROOT / db
    records = load(db)
    stats = Counter()
    if not options.rebuild_only:
        yunet_onnx = ROOT / "models" / "face_detection_yunet_2023mar.onnx"
        if not yunet_onnx.exists():
            yunet_onnx = ROOT / "face_detection_yunet_2023mar.onnx"
        sface_onnx = ROOT / "models" / "face_recognition_sface_2021dec.onnx"
        if not sface_onnx.exists():
            sface_onnx = ROOT / "face_recognition_sface_2021dec.onnx"
        detector = cv.FaceDetectorYN.create(str(yunet_onnx), "", (320, 320), 0.9, 0.3, 5000)
        sface = cv.FaceRecognizerSF.create(str(sface_onnx), "")
        replace = set(options.replace_identity)
        incoming = empty()
        existing = dict(zip(records["sha256"], records["labels"]))
        for identity, image in paths(Path(options.input), options.identity, options.include_name):
            fingerprint = digest(image)
            if fingerprint in existing:
                if existing[fingerprint] != identity:
                    raise ValueError(f"{image} already assigned to {existing[fingerprint]!r}")
                if identity not in replace:
                    stats["duplicates"] += 1
                    continue
            try:
                tile, feature = extract(image, detector, sface)
            except ValueError as error:
                print(f"[REJECT] {image}: {error}")
                if not options.skip_invalid:
                    raise RuntimeError("No changes written. Use --skip-invalid to continue.") from error
                continue
            incoming["labels"].append(identity); incoming["lbph_faces"].append(tile)
            incoming["sface_embeddings"].append(feature); incoming["sha256"].append(fingerprint)
            incoming["sources"].append(str(image)); stats["accepted"] += 1
        if replace:
            if replace - set(incoming["labels"]):
                raise RuntimeError("Every --replace-identity needs at least one accepted input image.")
            keep = [i for i, label in enumerate(records["labels"]) if label not in replace]
            records = {key: [value[i] for i in keep] for key, value in records.items()}
        for key in records:
            records[key].extend(incoming[key])
    counts = Counter(records["labels"])
    short = [f"{name}={count}" for name, count in counts.items() if count < options.min_samples]
    if short or len(counts) < 2:
        raise RuntimeError(f"Need 2 identities and {options.min_samples} samples each; short: {', '.join(short)}")
    descriptor = resolve_descriptor(options.descriptor_profile)
    metadata = {
        "updated_utc": now(),
        "identities": len(counts),
        "samples": len(records["labels"]),
        "recipe": "YuNet one-face box crop + Tan-Triggs LBPH + SFace alignCrop",
        "lbph_descriptor": descriptor.to_dict(),
    }
    if options.dry_run:
        print(f"[DRY RUN] {metadata} stats={dict(stats)}")
        return 0
    save_db(db, records, metadata)
    release = build_release(records, db, options.descriptor_profile)
    print(f"[ENROLL] DB={db}\n[ENROLL] active release={release}\n[ENROLL] stats={dict(stats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
