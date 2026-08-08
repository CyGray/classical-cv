"""SFace impostor L2 distance FAR sweep, full LFW1, native SFace L2 scale,
combined with genuine TAR from 1:1 pairwise verification (clean + 41 mods).

Generates:
  - reports/independence/sface_lfw1/far_sweep.json
  - reports/benchmark/sface_far_sweep_tar_report.json
  - reports/benchmark/sface_far_sweep_tar_report.md
  - docs/experiments/pairwise-verification/lfw-results/SWEEP/sface-table.png
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "pipeline"))

from run_lfw_independence import select_probes  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.hybrid.recognizer import detect_sample  # noqa: E402
from src.sface.recognizer import SFaceRecognizer, default_sface_model_path  # noqa: E402

from scripts.export_far_sweep_png_table import render_far_sweep_table, format_far, format_op_label  # noqa: E402

DEFAULT_TARGET_FAR_PPM = [float(percent * 10000) for percent in range(0, 101, 5)]
PAIRS_CSV = PROJECT_ROOT / "outputs" / "benchmark" / "accuracy_ratio_verification_full_pairs.csv"
OUT_PNG = PROJECT_ROOT.parent / "docs" / "experiments" / "pairwise-verification" / "lfw-results" / "SWEEP" / "sface-table.png"
OUT_INDEP_JSON = PROJECT_ROOT / "reports" / "independence" / "sface_lfw1" / "far_sweep.json"
OUT_TAR_JSON = PROJECT_ROOT / "reports" / "benchmark" / "sface_far_sweep_tar_report.json"
OUT_TAR_MD = PROJECT_ROOT / "reports" / "benchmark" / "sface_far_sweep_tar_report.md"


def load_sface_genuine_distances():
    clean, mods = [], []
    with open(PAIRS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("sface_genuine_l2", "")
            if not d:
                continue
            d = float(d)
            if row["modification"] == "clean":
                clean.append(d)
            else:
                mods.append(d)
        f.seek(0)
        # Also collect clean / mods impostor distances to calculate EER if needed
        reader = csv.DictReader(f)
        clean_imp, mods_imp = [], []
        for row in reader:
            d_imp = row.get("sface_impostor_l2", "")
            if not d_imp:
                continue
            d_imp = float(d_imp)
            if row["modification"] == "clean":
                clean_imp.append(d_imp)
            else:
                mods_imp.append(d_imp)
    return clean, mods, clean_imp, mods_imp


def compute_eer(gen_dists: list[float], imp_dists: list[float]):
    gen = np.sort(gen_dists)
    imp = np.sort(imp_dists)
    
    # Sweep thresholds over range
    thresholds = np.unique(np.concatenate([gen, imp]))
    if len(thresholds) > 2000:
        thresholds = np.linspace(thresholds[0], thresholds[-1], 2000)
        
    best_eer = 1.0
    best_thresh = thresholds[0]
    
    for t in thresholds:
        frr = np.mean(gen > t)
        far = np.mean(imp <= t)
        diff = abs(frr - far)
        eer = (frr + far) / 2.0
        if diff < abs(best_eer - far): # close crossing
            best_eer = eer
            best_thresh = float(t)
            
    return best_thresh, float(best_eer * 100.0)


def tar_at(distances: list[float], threshold: float) -> float:
    if not distances:
        return float("nan")
    accepted = sum(1 for d in distances if d <= threshold)
    return 100.0 * accepted / len(distances)


def main():
    print("[INFO] Loading SFace model & YuNet detector...", flush=True)
    sface = SFaceRecognizer(default_sface_model_path())
    detector = create_face_detector("yunet")
    dataset_dir = PROJECT_ROOT / "data" / "lfw-dataset"

    probes = select_probes(dataset_dir, max_identities=0, seed=42)
    print(f"[INFO] Processing {len(probes)} LFW1 probes...", flush=True)

    feats = []
    names = []
    skipped = 0
    t0 = time.time()

    for i, (person, path, _extras) in enumerate(probes):
        img = cv.imread(path)
        if img is None:
            skipped += 1
            continue
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=False)
        if sample is None:
            skipped += 1
            continue
        
        if sample.yunet_row is not None:
            feat = sface.feature_from_row(sample.image_bgr, sample.yunet_row)
        else:
            feat = sface.feature_from_crop(sample.face_bgr)
            
        feats.append(feat.flatten())
        names.append(person)

        if (i + 1) % 1000 == 0 or i == len(probes) - 1:
            print(f"  [extract] {i + 1}/{len(probes)} ({time.time() - t0:.1f}s)", flush=True)

    matrix = np.array(feats, dtype=np.float32)
    n = len(names)
    print(f"[INFO] {n} probe embeddings extracted ({skipped} skipped). Computing 16.5M impostor distances...", flush=True)

    # Normalize vectors
    norms = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    sim = (norms @ norms.T).astype(np.float32)
    l2_matrix = np.sqrt(np.clip(2.0 - 2.0 * sim, 0.0, None))

    iu = np.triu_indices(n, k=1)
    raw_dists = l2_matrix[iu]
    sorted_dists = np.sort(raw_dists)
    unique_pairs = int(sorted_dists.size)

    sweep_points = []
    for target_ppm in DEFAULT_TARGET_FAR_PPM:
        k = max(1, min(round(target_ppm / 1.0e6 * unique_pairs), unique_pairs))
        thresh = float(sorted_dists[k - 1])
        realized_ppm = 1.0e6 * k / unique_pairs
        sweep_points.append({
            "target_far_ppm": target_ppm,
            "unique_rank": k,
            "raw_threshold": thresh,
            "realized_far_ppm": realized_ppm,
            "realized_far_percent": realized_ppm / 1.0e4
        })

    indep_payload = {
        "detector": "yunet",
        "engine": "sface",
        "dataset": {
            "path": str(dataset_dir),
            "total_identities": 5749,
            "selected_identities": n,
            "skipped_by_detector": skipped
        },
        "scale": "SFace L2 distance (FR_NORM_L2)",
        "unique_pairs": unique_pairs,
        "sweep": sweep_points
    }
    OUT_INDEP_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_INDEP_JSON.write_text(json.dumps(indep_payload, indent=2), encoding="utf-8")
    print(f"[SAVE] {OUT_INDEP_JSON}")

    # Load genuine / 41-mod distances
    clean_gen, mods_gen, clean_imp, mods_imp = load_sface_genuine_distances()
    
    clean_eer_thresh, clean_eer_pct = compute_eer(clean_gen, clean_imp)
    mods_eer_thresh, mods_eer_pct = compute_eer(mods_gen, mods_imp)

    eer_ref_rows = [
        {"label": "EER (clean baseline, unfrozen)", "threshold": clean_eer_thresh, "eer_percent": clean_eer_pct},
        {"label": "EER (all 41 mods, unfrozen)", "threshold": mods_eer_thresh, "eer_percent": mods_eer_pct},
    ]

    rows = []
    for point in sweep_points:
        thresh = point["raw_threshold"]
        lbl = f"{point['target_far_ppm']:.0f} ppm target (current, deployed)" if abs(point["target_far_ppm"] - 10.0) < 1e-3 else f"{point['target_far_ppm']:.0f} ppm target"
        rows.append({
            "label": lbl,
            "target_far_ppm": point["target_far_ppm"],
            "realized_far_ppm": point["realized_far_ppm"],
            "raw_threshold": thresh,
            "clean_tar_percent": tar_at(clean_gen, thresh),
            "overall_tar_percent": tar_at(mods_gen, thresh),
            "family": "far_target",
        })

    for ref in eer_ref_rows:
        eer_far_ppm = ref["eer_percent"] * 10000.0
        rows.append({
            "label": ref["label"],
            "target_far_ppm": eer_far_ppm,
            "realized_far_ppm": eer_far_ppm,
            "raw_threshold": ref["threshold"],
            "clean_tar_percent": tar_at(clean_gen, ref["threshold"]),
            "overall_tar_percent": tar_at(mods_gen, ref["threshold"]),
            "family": "eer_reference",
        })

    tar_payload = {
        "n_clean_genuine_pairs": len(clean_gen),
        "n_mods_genuine_pairs": len(mods_gen),
        "impostor_pool_unique_pairs": unique_pairs,
        "impostor_pool_source": "reports/independence/sface_lfw1/far_sweep.json (full LFW1 cross-identity, YuNet, SFace L2 scale)",
        "genuine_pool_source": "outputs/benchmark/accuracy_ratio_verification_full_pairs.csv",
        "rows": rows
    }
    OUT_TAR_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_TAR_JSON.write_text(json.dumps(tar_payload, indent=2), encoding="utf-8")
    print(f"[SAVE] {OUT_TAR_JSON}")

    # Generate MD report
    md_lines = [
        "# SFace FAR-target sweep vs TAR - full LFW1",
        "",
        f"Impostor pool: {unique_pairs:,} unique cross-identity pairs (full LFW1, YuNet, SFace L2 scale).",
        f"Genuine pool: {len(clean_gen)} clean-baseline pairs, {len(mods_gen)} pooled 41-modification pairs.",
        "",
        "| Operating point | Realized FAR | Raw L2 threshold | Clean TAR | Overall TAR (41 mods) |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        far_col = format_far(r["realized_far_ppm"]) if r["realized_far_ppm"] is not None else "-"
        md_lines.append(
            f"| {r['label']} | {far_col} | {r['raw_threshold']:.4f} | "
            f"{r['clean_tar_percent']:.2f}% | {r['overall_tar_percent']:.2f}% |"
        )
    OUT_TAR_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"[SAVE] {OUT_TAR_MD}")

    # Render PNG table
    headers = ["Operating Point", "Realized FAR", "Raw Threshold", "Clean TAR (%)", "Overall TAR (%)"]
    col_widths = [4.5, 3.2, 1.8, 1.8, 1.8]
    data = []
    row_ppms = []
    family_boundaries = []
    last_family = None

    for row in rows:
        if row["family"] != last_family and last_family is not None:
            family_boundaries.append(len(data))
        last_family = row["family"]
        data.append([
            format_op_label(row),
            format_far(row["realized_far_ppm"]),
            f"{row['raw_threshold']:.4f}",
            f"{row['clean_tar_percent']:.2f}%",
            f"{row['overall_tar_percent']:.2f}%",
        ])
        row_ppms.append(row.get("realized_far_ppm"))

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    render_far_sweep_table(headers, data, col_widths, str(OUT_PNG), family_boundaries=family_boundaries, row_ppms=row_ppms)
    print(f"[SAVE] {OUT_PNG}")


if __name__ == "__main__":
    main()
