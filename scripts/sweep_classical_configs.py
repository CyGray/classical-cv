"""Config sweep for the classical recognizers on the clean La Salle split.

Answers "can the pipeline be configured better?" with measurements instead of
guesses. For each (family, num_components, equalization) combination it trains
on ``data/split_lasalle/train`` and reports:

* closed-set **rank-1** on the held-out ``data/split_lasalle/test`` (56 probes)
* verification **TAR / FRR @ the La Salle independence FAR (~1.058%)** and the
  **EER**, using LFW impostors (Haar-cropped once, shared across configs)
* the **feature-vector size** the config implies (spec budget < 1 KB)

Writes ``reports/benchmark/classical_config_sweep.{json,md}``.

Caveat printed into the report: the held-out genuine set is only 56 probes
(~1.8% granularity) so small deltas are noise; use this to pick *defaults*,
then confirm with the full clean loop + TAR@FAR + accuracy-ratio runs.

Usage::

    python scripts/sweep_classical_configs.py
    python scripts/sweep_classical_configs.py --families eigenfaces --impostor-max 400
"""

import argparse
import json
import time
from pathlib import Path

import cv2 as cv
import numpy as np

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.tar_at_far import equal_error_rate, operating_point  # noqa: E402
from src.classical_faces.datasets import list_image_files  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import (  # noqa: E402
    IMG_SIZE,
    detect_largest_face_box,
    normalize_face,
)

EQUALIZATIONS = ["equalize", "clahe", "tan-triggs"]
EIGEN_COMPONENTS = [0, 20, 40, 60, 80, 100, 150, 200]
FISHER_COMPONENTS = [0, 10, 20]
OPERATING_FAR_PERCENT = 1.058  # La Salle DB1 independence operating point (8th error pair)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep classical recognizer configurations.")
    parser.add_argument("--families", default="lbph,eigenfaces,fisherfaces")
    parser.add_argument("--train-dir", default="data/split_lasalle/train")
    parser.add_argument("--test-dir", default="data/split_lasalle/test")
    parser.add_argument("--impostor-dir", default="data/split_lfw/test")
    parser.add_argument("--impostor-max", type=int, default=0, help="Cap impostor probes (0 = all).")
    parser.add_argument("--cascade-path", default="haar/haarcascade_frontalface_default.xml")
    parser.add_argument("--output-json", default="reports/benchmark/classical_config_sweep.json")
    parser.add_argument("--output-md", default="reports/benchmark/classical_config_sweep.md")
    return parser.parse_args()


def _abs(path_value: str) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else PROJECT_ROOT / p


def load_person_grays(base_dir: Path) -> list[tuple[str, np.ndarray]]:
    """(person, grayscale image) for every image under person sub-folders."""
    out: list[tuple[str, np.ndarray]] = []
    for person_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        for name in list_image_files(str(person_dir)):
            img = cv.imread(str(person_dir / name))
            if img is None:
                continue
            out.append((person_dir.name, cv.cvtColor(img, cv.COLOR_BGR2GRAY)))
    return out


def load_impostor_rois(base_dir: Path, cascade: cv.CascadeClassifier, cap: int) -> list[np.ndarray]:
    """Haar-detect LFW faces ONCE; equalization is applied per config afterwards."""
    rois: list[np.ndarray] = []
    for person_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        for name in list_image_files(str(person_dir)):
            if cap > 0 and len(rois) >= cap:
                return rois
            img = cv.imread(str(person_dir / name))
            if img is None:
                continue
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            box = detect_largest_face_box(
                image_gray=gray, face_cascade=cascade,
                min_face_size=40, scale_factor=1.1, min_neighbors=5,
            )
            if box is None:
                continue
            x, y, w, h = box
            rois.append(gray[y: y + h, x: x + w])
    return rois


def make_recognizer(family: str, num_components: int):
    if family == "lbph":
        return cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    if family == "eigenfaces":
        return cv.face.EigenFaceRecognizer_create(num_components=num_components)
    return cv.face.FisherFaceRecognizer_create(num_components=num_components)


def evaluate_config(
    family: str,
    num_components: int,
    equalization: str,
    train_set: list[tuple[str, np.ndarray]],
    test_set: list[tuple[str, np.ndarray]],
    impostor_rois: list[np.ndarray],
) -> dict:
    spec = SPECS[family]
    label_map: dict[str, int] = {}
    faces: list[np.ndarray] = []
    labels: list[int] = []
    for person, gray in train_set:
        label_map.setdefault(person, len(label_map))
        faces.append(normalize_face(gray, IMG_SIZE, equalization))
        labels.append(label_map[person])
    id_to_name = {v: k for k, v in label_map.items()}

    recognizer = make_recognizer(family, num_components)
    t0 = time.time()
    recognizer.train(faces, np.array(labels, dtype=np.int32))
    train_seconds = time.time() - t0

    genuine: list[tuple[float, bool]] = []
    rank1_correct = 0
    for person, gray in test_set:
        pred_id, dist = recognizer.predict(normalize_face(gray, IMG_SIZE, equalization))
        ok = id_to_name.get(pred_id) == person
        rank1_correct += int(ok)
        genuine.append((float(dist), ok))

    impostor_sorted = sorted(
        float(recognizer.predict(normalize_face(roi, IMG_SIZE, equalization))[1])
        for roi in impostor_rois
    )

    op = operating_point(genuine, impostor_sorted, OPERATING_FAR_PERCENT)
    eer = equal_error_rate(genuine, impostor_sorted)
    return {
        "family": family,
        "num_components": num_components,
        "equalization": equalization,
        "rank1_percent": 100.0 * rank1_correct / len(test_set) if test_set else 0.0,
        "tar_percent": op["tar_percent"],
        "frr_percent": op["frr_percent"],
        "actual_far_percent": op["actual_far_percent"],
        "threshold_predict_scale": op["threshold_predict_scale"],
        "eer_percent": eer.get("eer_percent"),
        "feature_vector_bytes": spec.feature_bytes(recognizer),
        "n_genuine": len(genuine),
        "n_impostor": len(impostor_sorted),
        "train_seconds": train_seconds,
    }


def to_markdown(rows: list[dict], args: argparse.Namespace) -> str:
    lines = [
        "# Classical Config Sweep (clean split)",
        "",
        f"Train: `{args.train_dir}` | Test: `{args.test_dir}` (56 held-out genuine) | "
        f"Impostors: `{args.impostor_dir}` (Haar-cropped).",
        "",
        f"TAR/FRR at the La Salle independence operating FAR (~{OPERATING_FAR_PERCENT}%). "
        "`comps=0` means the library default (Eigen: all samples, Fisher: classes-1).",
        "",
        "**Caveat:** 56 genuine probes -> ~1.8% rank-1/TAR granularity. Treat small deltas as noise.",
        "",
        "| Family | Comps | Equalization | Rank-1 % | TAR % | FRR % | EER % | Feature B | <1 KB? |",
        "|---|---:|---|---:|---:|---:|---:|---:|:--:|",
    ]
    for r in rows:
        eer = f"{r['eer_percent']:.2f}" if r.get("eer_percent") is not None else "n/a"
        lines.append(
            f"| {r['family']} | {r['num_components']} | {r['equalization']} | "
            f"{r['rank1_percent']:.2f} | {r['tar_percent']:.2f} | {r['frr_percent']:.2f} | "
            f"{eer} | {r['feature_vector_bytes']} | "
            f"{'YES' if 0 < r['feature_vector_bytes'] < 1024 else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]

    cascade = cv.CascadeClassifier(str(_abs(args.cascade_path)))
    if cascade.empty():
        raise FileNotFoundError(f"Could not load cascade: {args.cascade_path}")

    print("[INFO] Loading datasets ...")
    train_set = load_person_grays(_abs(args.train_dir))
    test_set = load_person_grays(_abs(args.test_dir))
    print(f"[INFO] train={len(train_set)} test={len(test_set)}")
    print("[INFO] Haar-cropping impostors (once) ...")
    impostor_rois = load_impostor_rois(_abs(args.impostor_dir), cascade, args.impostor_max)
    print(f"[INFO] impostors={len(impostor_rois)}")

    configs: list[tuple[str, int, str]] = []
    for eq in EQUALIZATIONS:
        if "lbph" in families:
            configs.append(("lbph", 0, eq))
        if "eigenfaces" in families:
            configs.extend(("eigenfaces", c, eq) for c in EIGEN_COMPONENTS)
        if "fisherfaces" in families:
            configs.extend(("fisherfaces", c, eq) for c in FISHER_COMPONENTS)

    rows: list[dict] = []
    for i, (family, comps, eq) in enumerate(configs, 1):
        print(f"[{i:>2}/{len(configs)}] {family} comps={comps} eq={eq} ...", end=" ", flush=True)
        row = evaluate_config(family, comps, eq, train_set, test_set, impostor_rois)
        rows.append(row)
        print(
            f"rank1={row['rank1_percent']:6.2f}% TAR={row['tar_percent']:6.2f}% "
            f"EER={row['eer_percent']:5.2f}% feat={row['feature_vector_bytes']}B"
        )

    rows.sort(key=lambda r: (r["family"], -r["tar_percent"], -r["rank1_percent"]))

    out_json = _abs(args.output_json)
    out_md = _abs(args.output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump({"operating_far_percent": OPERATING_FAR_PERCENT, "rows": rows}, f, indent=2)
    with out_md.open("w", encoding="utf-8") as f:
        f.write(to_markdown(rows, args))
    print(f"\n[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")


if __name__ == "__main__":
    main()
