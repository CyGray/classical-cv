"""
Train+evaluate sanity check on the same processed dataset folder.

Goal:
- Train LBPH, Eigenfaces, and Fisherfaces on `lasalle_db1_processed`
- Evaluate on the exact same images used in training
- Report per-algorithm hit rate and average distance
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

try:
    from src.lbph.preprocess import IMG_SIZE, extract_lbph_face
except ModuleNotFoundError:
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.lbph.preprocess import IMG_SIZE, extract_lbph_face


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str(PROJECT_ROOT.joinpath(candidate))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Algo check: train and evaluate on the same processed folder."
    )
    parser.add_argument(
        "--base-data-dir",
        default=root_path("data"),
        help="Base data directory.",
    )
    parser.add_argument(
        "--processed-dir-name",
        default="lasalle_db1_processed",
        help="Processed dataset folder name inside base-data-dir.",
    )
    parser.add_argument(
        "--output-json",
        default=root_path("outputs", "algo_check", "processed_same_folder_summary.json"),
        help="Where to save JSON results.",
    )
    return parser.parse_args()


def is_image_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_EXTENSIONS


@dataclass
class Sample:
    person: str
    label: int
    image_path: str
    face: np.ndarray


def collect_samples(processed_root: str) -> tuple[List[Sample], Dict[str, int]]:
    if not os.path.isdir(processed_root):
        raise FileNotFoundError(f"Processed dataset not found: {processed_root}")

    label_map: Dict[str, int] = {}
    samples: List[Sample] = []

    for person in sorted(os.listdir(processed_root)):
        person_dir = os.path.join(processed_root, person)
        if not os.path.isdir(person_dir):
            continue

        if person not in label_map:
            label_map[person] = len(label_map)
        label_id = label_map[person]

        for image_name in sorted(os.listdir(person_dir)):
            if not is_image_file(image_name):
                continue
            image_path = os.path.join(person_dir, image_name)
            img = cv.imread(image_path)
            if img is None:
                continue

            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            processed = extract_lbph_face(
                image_gray=gray,
                face_cascade=None,
                min_face_size=40,
                scale_factor=1.1,
                min_neighbors=5,
                img_size=IMG_SIZE,
                equalization="equalize",
                align_eyes=False,
                eye_cascade=None,
                downscale_max_side=0,
                assume_already_cropped=True,
            )
            if processed.face is None:
                continue

            samples.append(
                Sample(
                    person=person,
                    label=label_id,
                    image_path=image_path,
                    face=processed.face,
                )
            )

    if not samples:
        raise RuntimeError("No valid processed training samples found.")
    if len(label_map) < 2:
        raise RuntimeError("Need at least 2 identities for Fisherfaces.")
    return samples, label_map


def evaluate_same_samples(
    recognizer,
    samples: List[Sample],
) -> dict:
    correct = 0
    distances: List[float] = []
    per_person_correct: Dict[str, int] = {}
    per_person_total: Dict[str, int] = {}

    for s in samples:
        pred_label, distance = recognizer.predict(s.face)
        is_correct = int(pred_label) == int(s.label)
        correct += int(is_correct)
        distances.append(float(distance))

        per_person_total[s.person] = per_person_total.get(s.person, 0) + 1
        if is_correct:
            per_person_correct[s.person] = per_person_correct.get(s.person, 0) + 1

    total = len(samples)
    hit_rate = (100.0 * correct / total) if total else 0.0
    avg_distance = float(np.mean(np.array(distances, dtype=np.float64))) if distances else 0.0

    person_hit_rate: Dict[str, float] = {}
    for person, count in sorted(per_person_total.items()):
        ok = per_person_correct.get(person, 0)
        person_hit_rate[person] = 100.0 * ok / count if count else 0.0

    return {
        "samples": total,
        "correct": correct,
        "hit_rate_percent": hit_rate,
        "average_distance": avg_distance,
        "min_distance": float(np.min(distances)) if distances else 0.0,
        "max_distance": float(np.max(distances)) if distances else 0.0,
        "per_person_hit_rate_percent": person_hit_rate,
    }


def run_lbph(samples: List[Sample]) -> dict:
    recognizer = cv.face.LBPHFaceRecognizer_create(
        radius=1,
        neighbors=8,
        grid_x=8,
        grid_y=8,
    )
    faces = [s.face for s in samples]
    labels = np.array([s.label for s in samples], dtype=np.int32)
    recognizer.train(faces, labels)
    return evaluate_same_samples(recognizer, samples)


def run_eigenfaces(samples: List[Sample]) -> dict:
    recognizer = cv.face.EigenFaceRecognizer_create()
    faces = [s.face for s in samples]
    labels = np.array([s.label for s in samples], dtype=np.int32)
    recognizer.train(faces, labels)
    return evaluate_same_samples(recognizer, samples)


def run_fisherfaces(samples: List[Sample]) -> dict:
    recognizer = cv.face.FisherFaceRecognizer_create()
    faces = [s.face for s in samples]
    labels = np.array([s.label for s in samples], dtype=np.int32)
    recognizer.train(faces, labels)
    return evaluate_same_samples(recognizer, samples)


def main() -> None:
    args = parse_args()
    args.base_data_dir = resolve_path(args.base_data_dir)
    args.output_json = resolve_path(args.output_json)
    processed_root = os.path.join(args.base_data_dir, args.processed_dir_name)

    print("[INFO] Loading processed dataset...")
    samples, label_map = collect_samples(processed_root)
    print(f"[INFO] Identities: {len(label_map)}")
    print(f"[INFO] Samples: {len(samples)}")

    print("[RUN] LBPH")
    lbph_result = run_lbph(samples)
    print("[RUN] Eigenfaces")
    eigen_result = run_eigenfaces(samples)
    print("[RUN] Fisherfaces")
    fisher_result = run_fisherfaces(samples)

    summary = {
        "dataset": {
            "processed_root": processed_root,
            "identities": len(label_map),
            "samples": len(samples),
        },
        "results": {
            "lbph": lbph_result,
            "eigenfaces": eigen_result,
            "fisherfaces": fisher_result,
        },
        "note": (
            "This is train==test on identical samples. "
            "100% hit rate is expected and does not measure generalization."
        ),
    }

    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n[RESULT] Processed Same-Folder Algo Check")
    for algo in ("lbph", "eigenfaces", "fisherfaces"):
        r = summary["results"][algo]
        print(
            f"{algo:12s} hit={r['hit_rate_percent']:.2f}% "
            f"avg_dist={r['average_distance']:.6f} "
            f"min={r['min_distance']:.6f} max={r['max_distance']:.6f}"
        )
    print(f"[OK] Saved JSON: {args.output_json}")


if __name__ == "__main__":
    main()
