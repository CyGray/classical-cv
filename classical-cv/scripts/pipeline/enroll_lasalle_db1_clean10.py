#!/usr/bin/env python3
"""Multi-shot LBPH + single-shot SFace enrollment for the La Salle DB1
"clean10" identification run -- the ``docs/reports/DATASET_MATRIX.md``-optimal
training composition (10 gallery images/identity: 5 light_* + 5 dark_*
poses), rebuilt from ``data/lasalle_db1_processed`` since ``data/split_lasalle``
has rotted (verified 2026-08-02).

Modeled on ``enroll_lasalle_db1.py`` / ``ensure_lfw2_enrollment`` (same LBPH
hyperparameters radius=1/neighbors=8/grid_x=8/grid_y=8, same YuNet + SFace
path), with two deliberate differences:

1. **label_map is pre-built from the full sorted identity list before the
   enrollment loop**, not incrementally via ``label_map[person] = len(label_map)``
   inside the loop. That incremental pattern (present in both
   ``enroll_lasalle_db1.py`` and ``run_lfw2_robustness.py``) silently
   corrupts multi-shot enrollment: on a repeated-person iteration it
   reassigns the person's label to a NEW index while earlier LBPH templates
   for that same person keep their OLD (now orphaned) label, since the
   label was already baked into ``labels.append(...)`` before the
   reassignment. It's invisible in every existing caller because they only
   ever enroll one image per person; do not copy this script's gallery loop
   back into a single-shot enrollment path (harmless there, but the wrong
   pattern to propagate).
2. **SFace stays single-shot even though LBPH is multi-shot.** SFace's
   gallery dict has always overwritten per-person on repeated entries
   (last-wins) -- rather than let "whichever image happens to load last"
   pick the SFace reference image, this script fixes it explicitly and
   deterministically to ``light_front`` for every identity (a canonical,
   well-lit frontal pose), so the SFace/Cascade numbers from this run
   differ from the old 1-gallery run for a STATED, interpretable reason
   (deterministic light_front vs seeded-random pose) rather than silent
   gallery-image-choice noise. Only LBPH old-vs-new is a like-for-like
   comparison; see the README this feeds.

Usage:
    python scripts/pipeline/enroll_lasalle_db1_clean10.py
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

ENROLL_DIR = PROJECT_ROOT / "models" / "lasalle_db1_clean10"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "splits" / "lasalle_db1_ident_split_clean10_seed42.json"
SFACE_REFERENCE_POSE = "light_front.jpg"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split-manifest", default=str(DEFAULT_MANIFEST))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--lbph-assume-cropped", choices=["true", "false"], default="true",
                    help="La Salle DB1 processed tiles are pre-cropped 100x100 faces -> true (default).")
    p.add_argument("--force", action="store_true", help="Re-enroll even if a matching cache exists.")
    return p.parse_args()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_lasalle_db1_clean10_enrollment(
    split_manifest_path: str,
    seed: int,
    assume_cropped: bool,
    force: bool = False,
) -> dict[str, str]:
    import cv2 as cv
    import numpy as np
    from src.benchmark.accuracy_ratio_hybrid import load_gallery_from_manifest, load_split_manifest
    from src.classical_faces.detection import create_face_detector
    from src.classical_faces.pipeline import SPECS
    from src.classical_faces.preprocess import IMG_SIZE, normalize_face
    from src.hybrid.recognizer import detect_sample
    from src.sface.recognizer import SFaceGallery, SFaceRecognizer, default_sface_model_path

    split_manifest_sha = _sha256_file(Path(split_manifest_path))
    crop_token = "_cropped" if assume_cropped else "_boxcrop"

    paths = {
        "lbph_model": ENROLL_DIR / f"lbph_seed{seed}_manifest{split_manifest_sha[:12]}{crop_token}.yml",
        "lbph_labels": ENROLL_DIR / f"lbph_labels_seed{seed}_manifest{split_manifest_sha[:12]}{crop_token}.json",
        "sface_gallery": ENROLL_DIR / f"sface_gallery_seed{seed}_manifest{split_manifest_sha[:12]}{crop_token}.npy",
        "sface_labels": ENROLL_DIR / f"sface_labels_seed{seed}_manifest{split_manifest_sha[:12]}{crop_token}.json",
    }
    cache_manifest_path = ENROLL_DIR / f"manifest_seed{seed}_manifest{split_manifest_sha[:12]}{crop_token}.json"
    if not force and cache_manifest_path.exists() and all(p.exists() for p in paths.values()):
        cached = json.loads(cache_manifest_path.read_text(encoding="utf-8"))
        if (cached.get("split_manifest_sha256") == split_manifest_sha
                and cached.get("seed") == seed
                and cached.get("assume_cropped", False) == assume_cropped):
            print(f"[ENROLL] Reusing cached La Salle DB1 clean10 enrollment "
                  f"({cached['identities']} identities) in {ENROLL_DIR}")
            return {k: str(v) for k, v in paths.items()}
        print("[ENROLL] Cached manifest does not match seed/split-manifest/crop-mode; re-enrolling.")

    split_manifest = load_split_manifest(split_manifest_path)
    selection = load_gallery_from_manifest(split_manifest)  # 28*10 = 280 (person, path) rows
    if not selection:
        raise RuntimeError(f"No gallery images found in split manifest {split_manifest_path}")

    persons = sorted({person for person, _ in selection})
    label_map: dict[str, int] = {person: idx for idx, person in enumerate(persons)}

    print(f"[ENROLL] Enrolling {len(selection)} La Salle DB1 gallery images "
          f"across {len(persons)} identities (multi-shot LBPH, assume_cropped={assume_cropped})...")

    detector = create_face_detector("yunet")
    sface = SFaceRecognizer(default_sface_model_path())
    equalization = SPECS["lbph"].default_equalization

    faces: list = []
    labels: list = []
    embeddings: dict[str, list] = {}
    yunet_misses = 0
    for i, (person, path) in enumerate(selection, 1):
        img = cv.imread(path)
        if img is None:
            print(f"[WARN] Could not read {path}; skipping.")
            continue
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=assume_cropped)
        if sample is None:
            face_gray = gray
            feature = sface.feature_from_crop(img)
            yunet_misses += 1
        else:
            face_gray = sample.face_gray
            feature = (
                sface.feature_from_row(sample.image_bgr, sample.yunet_row)
                if sample.yunet_row is not None
                else sface.feature_from_crop(sample.image_bgr)
            )
        faces.append(normalize_face(face_gray, img_size=IMG_SIZE, equalization=equalization))
        labels.append(label_map[person])
        if Path(path).name == SFACE_REFERENCE_POSE:
            embeddings[person] = [feature]  # deterministic single-shot SFace reference

    missing_sface = sorted(set(persons) - set(embeddings))
    if missing_sface:
        raise RuntimeError(f"No '{SFACE_REFERENCE_POSE}' embedding captured for: {missing_sface}")

    if len(faces) < 2:
        raise RuntimeError("Not enough valid La Salle DB1 images to enroll.")

    print(f"[ENROLL] Training LBPH on {len(faces)} faces "
          f"({len(faces) / len(persons):.1f} templates/identity)...")
    recognizer = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(faces, np.array(labels, dtype=np.int32))

    ENROLL_DIR.mkdir(parents=True, exist_ok=True)
    recognizer.save(str(paths["lbph_model"]))
    paths["lbph_labels"].write_text(json.dumps(label_map, indent=2), encoding="utf-8")
    SFaceGallery.from_samples(sface, embeddings).save(
        str(paths["sface_gallery"]), str(paths["sface_labels"])
    )
    cache_manifest_path.write_text(json.dumps({
        "dataset": "lasalle_db1_processed",
        "recipe": "dataset_matrix_clean10 (10 gallery imgs/id: 5 light_* + 5 dark_*)",
        "sface_reference_pose": SFACE_REFERENCE_POSE,
        "split_manifest_path": split_manifest_path,
        "split_manifest_sha256": split_manifest_sha,
        "seed": seed,
        "identities": len(label_map),
        "lbph_templates": len(faces),
        "assume_cropped": assume_cropped,
        "equalization": equalization,
        "yunet_misses_whole_tile_fallback": yunet_misses,
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2), encoding="utf-8")
    print(f"[ENROLL] Done. Cached in {ENROLL_DIR} (YuNet misses: {yunet_misses})")
    return {k: str(v) for k, v in paths.items()}


def main() -> int:
    args = parse_args()
    paths = ensure_lasalle_db1_clean10_enrollment(
        args.split_manifest, args.seed,
        assume_cropped=(args.lbph_assume_cropped == "true"),
        force=args.force,
    )
    for k, v in paths.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
