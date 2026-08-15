"""Score LSDB classical candidates with calibration-only operating points."""
from __future__ import annotations

import argparse, json, math
from pathlib import Path
import cv2 as cv

from src.classical_faces.pipeline import SPECS, load_recognizer
from src.classical_faces.preprocess import IMG_SIZE, normalize_face
from src.independence_common import lbph_config_metadata, resolve_lbph_config

FAMILIES = ("lbph", "eigenfaces", "fisherfaces")
FEATURE_BYTES = {"eigenfaces": 896, "fisherfaces": 108}

def images(root: Path):
    return [(p.parent.name, p) for p in sorted(root.glob("*/*")) if p.is_file()]

def scores(recognizer, gray, equalization):
    face = normalize_face(gray, IMG_SIZE, equalization)
    collector = cv.face.StandardCollector_create()
    recognizer.predict_collect(face, collector)
    per_label = {}
    for label, distance in collector.getResults(True):
        per_label[int(label)] = min(per_label.get(int(label), float("inf")), float(distance))
    return per_label


def validate_lbph_model(model_path: Path, recognizer, descriptor_metadata: dict) -> None:
    """Ensure OpenCV read restored the descriptor expected by this result."""
    fs = cv.FileStorage(str(model_path), cv.FILE_STORAGE_READ)
    root = fs.getNode("opencv_lbphfaces")
    actual = {
        "radius": int(root.getNode("radius").real()),
        "neighbors": int(root.getNode("neighbors").real()),
        "grid_x": int(root.getNode("grid_x").real()),
        "grid_y": int(root.getNode("grid_y").real()),
    }
    fs.release()
    expected = {key: descriptor_metadata[key] for key in ("radius", "neighbors", "grid_x", "grid_y")}
    if actual != expected:
        raise RuntimeError(
            f"LBPH model {model_path} has descriptor {actual}, expected {expected} "
            f"for config {descriptor_metadata['id']}"
        )
    restored = {
        "radius": int(recognizer.getRadius()),
        "neighbors": int(recognizer.getNeighbors()),
        "grid_x": int(recognizer.getGridX()),
        "grid_y": int(recognizer.getGridY()),
    }
    if restored != expected:
        raise RuntimeError(
            f"OpenCV recognizer parameters after read disagree with YAML: {restored} != {expected}"
        )


def lbph_feature_bytes(recognizer) -> int:
    return (
        int(recognizer.getGridX())
        * int(recognizer.getGridY())
        * (2 ** int(recognizer.getNeighbors()))
        * 4
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-root", type=Path, required=True)
    ap.add_argument("--test-root", type=Path, required=True)
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--far-percent", type=float, default=1.058)
    ap.add_argument(
        "--lbph-config", default="deployed",
        help="LBPH descriptor alias/ID (deployed, selected, or rN_nN_gNxN).",
    )
    args = ap.parse_args()
    descriptor_config = resolve_lbph_config(args.lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)
    calibration, test = images(args.split_root / "calibration"), images(args.test_root)
    if not calibration or not test: raise SystemExit("Missing calibration or untouched test images")
    report = {"protocol": {"fit": "split_root/fit", "calibration": str(args.split_root / "calibration"), "test": str(args.test_root), "target_far_percent": args.far_percent, "threshold_source": "LSDB calibration cross-identity scores only"}, "lbph_config": descriptor_metadata, "families": {}}
    for family in FAMILIES:
        labels = json.loads((args.model_dir / f"labels_{family}_fit.json").read_text())
        id_to_name = {int(v): k for k, v in labels.items()}
        model_path = args.model_dir / f"{family}_fit.yml"
        recognizer = load_recognizer(SPECS[family], str(model_path))
        if family == "lbph":
            validate_lbph_model(model_path, recognizer, descriptor_metadata)
        genuine, impostor = [], []
        for name, path in calibration:
            values = scores(recognizer, cv.imread(str(path), cv.IMREAD_GRAYSCALE), SPECS[family].default_equalization)
            genuine.append(values[labels[name]])
            impostor.extend(v for key, v in values.items() if id_to_name[key] != name)
        impostor.sort()
        k = max(1, math.floor(args.far_percent / 100 * len(impostor)))
        threshold = impostor[k - 1]
        accepted = correct_rank1 = 0
        for name, path in test:
            values = scores(recognizer, cv.imread(str(path), cv.IMREAD_GRAYSCALE), SPECS[family].default_equalization)
            best, distance = min(values.items(), key=lambda x: x[1])
            correct = id_to_name[best] == name
            correct_rank1 += correct
            accepted += correct and distance <= threshold
        feature_bytes = lbph_feature_bytes(recognizer) if family == "lbph" else FEATURE_BYTES[family]
        row = {"threshold": threshold, "calibration_pairs": len(impostor), "calibration_error_rank": k, "calibration_far_percent": 100*k/len(impostor), "calibration_tar_percent": 100*sum(d <= threshold for d in genuine)/len(genuine), "test_n": len(test), "test_rank1_percent": 100*correct_rank1/len(test), "test_tar_percent": 100*accepted/len(test), "feature_vector_bytes": feature_bytes}
        if family == "lbph":
            row["lbph_config"] = descriptor_metadata
        report["families"][family] = row
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__": main()
