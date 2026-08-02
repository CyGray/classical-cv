"""Build the hybrid's SFace gallery from the same crop set LBPH trained on.

The hybrid holds **two galleries for one identity set**: the LBPH ``.yml`` model
(already trained on the clean split) and the SFace embedding gallery built here.
Both come from the *same* aligned crops, so this script asserts the two label
sets are equal (PLAN §10 "two galleries, one identity set" / Phase 4.2). If they
disagree the hybrid would silently describe two different identity universes.

For each training image: YuNet detects -> ``alignCrop`` 112x112 -> ``feature``;
per-identity embeddings are averaged into the gallery and saved to
``models/sface/gallery.npy`` + ``models/sface/labels.json`` (mirroring the DL
``features-*.npy`` dict format so the existing tooling reads it).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2 as cv

from src.classical_faces.detection import create_face_detector
from src.hybrid.recognizer import (
    DEFAULT_LBPH_LABELS,
    DEFAULT_SFACE_GALLERY,
    DEFAULT_SFACE_LABELS,
    detect_sample,
)
from src.sface.recognizer import SFaceGallery, SFaceRecognizer, default_sface_model_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(value: str) -> str:
    p = Path(value)
    return str(p) if p.is_absolute() else str(PROJECT_ROOT / p)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enroll the hybrid SFace gallery.")
    p.add_argument("--data-dir", default=root_path("data", "split_lasalle", "train"))
    p.add_argument("--sface-model", default=default_sface_model_path())
    p.add_argument("--gallery-output", default=DEFAULT_SFACE_GALLERY)
    p.add_argument("--labels-output", default=DEFAULT_SFACE_LABELS)
    p.add_argument(
        "--lbph-labels",
        default=DEFAULT_LBPH_LABELS,
        help="LBPH labels JSON for the two-gallery consistency assertion.",
    )
    p.add_argument(
        "--assume-cropped",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Treat inputs as pre-cropped face tiles (clean split). Detection still "
        "runs so alignCrop can use YuNet landmarks; on a miss it falls back to resize.",
    )
    p.add_argument("--yunet-score-threshold", type=float, default=0.6)
    p.add_argument(
        "--strict-consistency",
        action="store_true",
        help="Exit non-zero if the SFace and LBPH label sets differ.",
    )
    return p.parse_args()


def iter_identity_images(data_dir: Path):
    for person_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        files = sorted(f for f in person_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
        if files:
            yield person_dir.name, files


def main() -> int:
    args = parse_args()
    data_dir = Path(resolve_path(args.data_dir))
    if not data_dir.exists():
        raise FileNotFoundError(f"Training data dir not found: {data_dir}")

    detector = create_face_detector(
        "yunet",
        yunet_score_threshold=args.yunet_score_threshold,
    )
    recognizer = SFaceRecognizer(args.sface_model)
    print(f"[INFO] Detector: {detector.describe()}")
    print(f"[INFO] SFace: {Path(args.sface_model).name}")

    samples: dict[str, list] = {}
    n_images = 0
    n_embedded = 0
    n_fallback = 0
    start = time.time()
    for person, files in iter_identity_images(data_dir):
        for img_path in files:
            n_images += 1
            image_bgr = cv.imread(str(img_path))
            if image_bgr is None:
                print(f"[WARN] Unreadable: {img_path}")
                continue
            gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
            sample = detect_sample(
                detector,
                image_bgr=image_bgr,
                image_gray=gray,
                assume_cropped=args.assume_cropped,
            )
            if sample is None or sample.yunet_row is None:
                # No detection: align-free fallback so the identity still enrolls.
                feature = recognizer.feature_from_crop(image_bgr)
                n_fallback += 1
            else:
                feature = recognizer.feature_from_row(sample.image_bgr, sample.yunet_row)
            samples.setdefault(person, []).append(feature)
            n_embedded += 1

    if not samples:
        raise RuntimeError("No embeddings produced; check the data dir.")

    gallery = SFaceGallery.from_samples(recognizer, samples)
    gallery_out = resolve_path(args.gallery_output)
    labels_out = resolve_path(args.labels_output)
    gallery.save(gallery_out, labels_out)

    elapsed = time.time() - start
    print(
        f"\n[ENROLL] identities={len(gallery.labels)} images={n_images} "
        f"embedded={n_embedded} (align-free fallback={n_fallback}) in {elapsed:.1f}s"
    )
    print(f"[ENROLL] gallery: {gallery_out}  ({sum(len(v) for v in samples.values())} crops)")
    print(f"[ENROLL] labels : {labels_out}")

    # Two-gallery consistency (PLAN §10 / Phase 4.2).
    lbph_labels_path = Path(resolve_path(args.lbph_labels))
    if lbph_labels_path.exists():
        with lbph_labels_path.open("r", encoding="utf-8") as f:
            lbph_labels = set(json.load(f).keys())
        sface_labels = set(gallery.labels)
        if lbph_labels == sface_labels:
            print(f"[CHECK] two-gallery consistency PASS ({len(sface_labels)} identities match)")
        else:
            only_lbph = sorted(lbph_labels - sface_labels)
            only_sface = sorted(sface_labels - lbph_labels)
            print("[CHECK] two-gallery consistency FAIL (label sets differ):")
            if only_lbph:
                print(f"         only in LBPH : {only_lbph}")
            if only_sface:
                print(f"         only in SFace: {only_sface}")
            if args.strict_consistency:
                return 1
    else:
        print(f"[WARN] LBPH labels not found at {lbph_labels_path}; skipped consistency check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
