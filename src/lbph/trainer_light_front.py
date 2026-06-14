"""
Train LBPH using exactly one image per person: light front.png.
"""

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2 as cv
import numpy as np

from .preprocess import IMG_SIZE, extract_lbph_face, resolve_eye_cascade_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSUME_INPUTS_ARE_CROPPED = True
DEFAULT_IMAGE_NAME = "light_front.jpg"


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str(PROJECT_ROOT.joinpath(candidate))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train LBPH using one image per identity: light front.png."
    )
    parser.add_argument(
        "--dataset-dir",
        default=root_path("data", "lasalle_db1"),
        help="Dataset root containing person folders.",
    )
    parser.add_argument(
        "--image-name",
        default=DEFAULT_IMAGE_NAME,
        help="Exact filename to use per person (default: light front.png).",
    )
    parser.add_argument(
        "--model-output",
        default=root_path("models", "lbph", "trainer_light_front.yml"),
        help="Output path for trained LBPH model.",
    )
    parser.add_argument(
        "--labels-output",
        default=root_path("models", "lbph", "labels_light_front.json"),
        help="Output path for labels JSON.",
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
    return parser.parse_args()


def get_person_dirs(dataset_root: str) -> List[Tuple[str, str]]:
    if not os.path.isdir(dataset_root):
        return []
    out: List[Tuple[str, str]] = []
    for person in sorted(os.listdir(dataset_root)):
        person_path = os.path.join(dataset_root, person)
        if os.path.isdir(person_path):
            out.append((person, person_path))
    return out


def main() -> None:
    args = parse_args()
    args.dataset_dir = resolve_path(args.dataset_dir)
    args.model_output = resolve_path(args.model_output)
    args.labels_output = resolve_path(args.labels_output)
    args.cascade_path = resolve_path(args.cascade_path)
    args.eye_cascade_path = resolve_path(resolve_eye_cascade_path(args.eye_cascade_path))

    print("[INFO] LBPH Light-Front Training")
    print(f"[INFO] Dataset: {args.dataset_dir}")
    print(f"[INFO] Image name: {args.image_name}")

    face_cascade: cv.CascadeClassifier | None = None
    eye_cascade: cv.CascadeClassifier | None = None
    if ASSUME_INPUTS_ARE_CROPPED:
        print("[INFO] Pre-cropped mode: skipping Haar detection.")
    else:
        face_cascade = cv.CascadeClassifier(args.cascade_path)
        if face_cascade.empty():
            raise FileNotFoundError(f"Could not load cascade: {args.cascade_path}")
        if args.align_eyes:
            eye_cascade = cv.CascadeClassifier(args.eye_cascade_path)
            if eye_cascade.empty():
                print("[WARN] Could not load eye cascade. Alignment disabled.")
                eye_cascade = None

    person_dirs = get_person_dirs(args.dataset_dir)
    if not person_dirs:
        raise RuntimeError("No identity folders found.")

    faces: List[np.ndarray] = []
    labels: List[int] = []
    label_map: Dict[str, int] = {}
    skipped = 0

    for person, person_path in person_dirs:
        image_path = os.path.join(person_path, args.image_name)
        if not os.path.isfile(image_path):
            skipped += 1
            continue
        img = cv.imread(image_path)
        if img is None:
            skipped += 1
            continue
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        processed = extract_lbph_face(
            image_gray=gray,
            face_cascade=face_cascade,
            min_face_size=args.min_face_size,
            scale_factor=1.1,
            min_neighbors=5,
            img_size=IMG_SIZE,
            equalization=args.equalization,
            align_eyes=args.align_eyes,
            eye_cascade=eye_cascade,
            downscale_max_side=args.downscale_max_side,
            assume_already_cropped=ASSUME_INPUTS_ARE_CROPPED,
        )
        if processed.face is None:
            skipped += 1
            continue
        label_map[person] = len(label_map)
        faces.append(processed.face)
        labels.append(label_map[person])

    if len(faces) < 2:
        raise RuntimeError("Not enough valid images to train model.")

    print(f"[INFO] Training samples: {len(faces)}")
    print(f"[INFO] Skipped identities: {skipped}")

    recognizer = cv.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8,
    )
    recognizer.train(faces, np.array(labels, dtype=np.int32))

    os.makedirs(os.path.dirname(args.model_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.labels_output), exist_ok=True)
    recognizer.save(args.model_output)
    with open(args.labels_output, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)

    print(f"[OK] Saved model to: {args.model_output}")
    print(f"[OK] Saved labels to: {args.labels_output}")


if __name__ == "__main__":
    main()
