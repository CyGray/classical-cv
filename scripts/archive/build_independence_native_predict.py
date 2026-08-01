#!/usr/bin/env python3
"""Native predict_collect() independence run for Eigenfaces + Fisherfaces (LSDB1).

LBPH's native-scale rank-8 threshold already exists (`src/hybrid/independence_test.py`
trains a real `cv.face.LBPHFaceRecognizer` and reads `predict_collect()` distances -
see `reports/independence/hybrid/lsdb1_fixed/summary.json`'s `lbph_rank_thresholds`
and `comparisons.csv`'s `mean_lbph_distance` column). That is the canonical LBPH
number (70.6089 raw, rank 8/756) - it is NOT the same scale as
`independence_common.py`'s hand-rolled `chi_squared_distance` reimplementation
(17.65), which is a from-scratch chi-square over extracted histograms, not what
OpenCV's C++ `LBPHFaceRecognizer::predict` actually computes. The "cross-model"
comparison table built on that reimplementation is retired - it produced an
implausibly small LBPH threshold and is not comparable to the deployed
`tau_accept` (73.04, same predict-scale as the real 70.6089).

This script gives Eigenfaces and Fisherfaces the same treatment: train the real
`cv.face.EigenFaceRecognizer` / `FisherFaceRecognizer` as an N-class classifier
(one label per identity, `light_front.jpg` deterministic probe - Fisherfaces gets
extra sorted images per identity for LDA within-class scatter, same as
`src/fisherfaces/independence_test.py`), then read `predict_collect()` (native
OpenCV Euclidean distance in PCA/LDA space) for every ordered cross-identity pair,
instead of the custom `euclidean_distance` reimplementation. Rank-8 threshold
computed the same rank rule as everything else in this project.

Usage:
    python scripts/archive/build_independence_native_predict.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2 as cv  # noqa: E402
import numpy as np  # noqa: E402

from src.independence_common import error_pair_report  # noqa: E402

DATASET_DIR = PROJECT_ROOT / "data" / "lasalle_db1_processed"

MODELS = [
    ("eigenfaces", "src.eigenfaces.independence_test"),
    ("fisherfaces", "src.fisherfaces.independence_test"),
]


def _load_module(dotted: str):
    import importlib
    return importlib.import_module(dotted)


def build_eigenfaces_records() -> tuple[list[dict], dict]:
    mod = _load_module("src.eigenfaces.independence_test")
    person_dirs = mod.get_person_dirs(str(DATASET_DIR))
    selected = mod.select_one_image_per_person(person_dirs, random_seed=42)
    faces, label_map, _ = mod.preprocess_and_extract_faces(
        selected, None, None, min_face_size=40, align_eyes=True,
        equalization="tan-triggs", downscale_max_side=0,
    )
    identities = sorted(faces.keys())
    n = len(identities)
    faces_list = [faces[p] for p in identities]
    labels = np.array([label_map[p] for p in identities], dtype=np.int32)

    num_comp = min(n - 1, 50)
    recognizer = cv.face.EigenFaceRecognizer_create(num_components=num_comp, threshold=1e9)
    recognizer.train(faces_list, labels)

    return _predict_collect_pairs(recognizer, faces_list, identities, label_map), {
        "num_components": num_comp,
    }


def build_fisherfaces_records() -> tuple[list[dict], dict]:
    mod = _load_module("src.fisherfaces.independence_test")
    person_dirs = mod.get_person_dirs(str(DATASET_DIR))
    selected = mod.select_images_per_person(person_dirs, random_seed=42, images_per_identity=2)
    faces, label_map, _ = mod.preprocess_and_extract_faces(
        selected, None, None, min_face_size=40, align_eyes=True,
        equalization="tan-triggs", downscale_max_side=0,
    )
    identities = sorted(faces.keys())
    n = len(identities)

    train_faces: list[np.ndarray] = []
    train_labels: list[int] = []
    probe_faces: list[np.ndarray] = []
    for p in identities:
        imgs = faces[p]
        for img in imgs:
            train_faces.append(img)
            train_labels.append(label_map[p])
        probe_faces.append(imgs[0])  # light_front.jpg is always first

    num_comp = max(1, min(n - 2, 49))
    recognizer = cv.face.FisherFaceRecognizer_create(num_components=num_comp, threshold=1e9)
    recognizer.train(train_faces, np.array(train_labels, dtype=np.int32))

    return _predict_collect_pairs(recognizer, probe_faces, identities, label_map), {
        "num_components": num_comp,
    }


def _predict_collect_pairs(recognizer, probe_faces, identities, label_map) -> list[dict]:
    """Ordered N x (N-1) native OpenCV predict_collect() distances.

    Fisherfaces trains >=2 samples/label (LDA needs within-class scatter), so
    StandardCollector returns one result PER TRAINING SAMPLE, not per label -
    take the min per label (nearest exemplar), same reduction
    ``src/hybrid/independence_test.py`` applies to its LBPH predict_collect loop.
    """
    label_to_identity = {v: k for k, v in label_map.items()}
    records: list[dict] = []
    for i, probe in enumerate(probe_faces):
        query_identity = identities[i]
        collector = cv.face.StandardCollector_create()
        recognizer.predict_collect(probe, collector)
        best_per_label: dict[int, float] = {}
        for label, dist in collector.getResults(True):
            label = int(label)
            d = float(dist)
            if label not in best_per_label or d < best_per_label[label]:
                best_per_label[label] = d
        for label, dist in best_per_label.items():
            candidate_identity = label_to_identity[label]
            if candidate_identity == query_identity:
                continue
            records.append({
                "query_identity": query_identity,
                "candidate_identity": candidate_identity,
                "raw_distance": dist,
            })
    return records


def save_run(key: str, records: list[dict], extra: dict) -> None:
    out_dir = PROJECT_ROOT / "outputs" / "independence" / f"{key}_lasalle_native"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "comparisons.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query_identity", "candidate_identity", "raw_distance"])
        writer.writeheader()
        for r in records:
            writer.writerow({
                "query_identity": r["query_identity"],
                "candidate_identity": r["candidate_identity"],
                "raw_distance": f"{r['raw_distance']:.6f}",
            })
    print(f"[SAVE] CSV: {csv_path} ({len(records)} rows)")

    report = error_pair_report(records, target_far_ppm=10000.0)
    values = np.array([r["raw_distance"] for r in records], dtype=np.float64)
    summary = {
        "dataset": {"path": str(DATASET_DIR), "identities": len(set(r["query_identity"] for r in records))},
        "method": "native cv2.face predict_collect() (real OpenCV recognizer, not a reimplemented distance)",
        "extra": extra,
        "distance_statistics": {
            "min_distance": float(values.min()),
            "max_distance": float(values.max()),
            "mean_distance": float(values.mean()),
            "median_distance": float(np.median(values)),
            "std_dev": float(values.std()),
        },
        "error_pair_thresholds": report,
    }
    json_path = out_dir / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[SAVE] JSON: {json_path}")
    spec = report["spec"]
    print(f"[{key}] rank-8 raw threshold = {spec['raw_threshold']:.4f} "
          f"({spec['query_identity']} vs {spec['candidate_identity']}, "
          f"{spec['realized_far_ppm']:.1f} ppm)")


def main() -> int:
    eigen_records, eigen_extra = build_eigenfaces_records()
    save_run("eigenfaces", eigen_records, eigen_extra)

    fisher_records, fisher_extra = build_fisherfaces_records()
    save_run("fisherfaces", fisher_records, fisher_extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
