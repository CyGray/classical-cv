"""Score LSDB classical candidates with calibration-only operating points."""
from __future__ import annotations

import argparse, json, math
from pathlib import Path
import cv2 as cv

from src.classical_faces.pipeline import SPECS, load_recognizer
from src.classical_faces.preprocess import IMG_SIZE, normalize_face

FAMILIES = ("lbph", "eigenfaces", "fisherfaces")
FEATURE_BYTES = {"lbph": 65536, "eigenfaces": 896, "fisherfaces": 108}

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-root", type=Path, required=True)
    ap.add_argument("--test-root", type=Path, required=True)
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--far-percent", type=float, default=1.058)
    args = ap.parse_args()
    calibration, test = images(args.split_root / "calibration"), images(args.test_root)
    if not calibration or not test: raise SystemExit("Missing calibration or untouched test images")
    report = {"protocol": {"fit": "split_root/fit", "calibration": str(args.split_root / "calibration"), "test": str(args.test_root), "target_far_percent": args.far_percent, "threshold_source": "LSDB calibration cross-identity scores only"}, "families": {}}
    for family in FAMILIES:
        labels = json.loads((args.model_dir / f"labels_{family}_fit.json").read_text())
        id_to_name = {int(v): k for k, v in labels.items()}
        recognizer = load_recognizer(SPECS[family], str(args.model_dir / f"{family}_fit.yml"))
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
        report["families"][family] = {"threshold": threshold, "calibration_pairs": len(impostor), "calibration_error_rank": k, "calibration_far_percent": 100*k/len(impostor), "calibration_tar_percent": 100*sum(d <= threshold for d in genuine)/len(genuine), "test_n": len(test), "test_rank1_percent": 100*correct_rank1/len(test), "test_tar_percent": 100*accepted/len(test), "feature_vector_bytes": FEATURE_BYTES[family]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__": main()
