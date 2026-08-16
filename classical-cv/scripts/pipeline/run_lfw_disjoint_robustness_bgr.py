#!/usr/bin/env python3
"""Run the corrected BGR-first 41-modification robustness evaluation on the
held-out 2,874 LFW evaluation identities (strictly disjoint from the 2,875
development identities).

Features:
- BGR-first transformation generation (operates on 3-channel color image).
- Strict separation: 2,875 dev identities (calibration) vs 2,874 eval identities (evaluation).
- Evaluates:
  1. Standalone Challenger LBPH (r3_n8_g6x6)
  2. Standalone Direct SFace
  3. Combined Optimized Cascade (Quality-First Routing + r3_n8_g6x6)
  4. Baseline Sequential Cascade (r1_n8_g8x8 + Sequential)
- Multi-worker parallel execution across segments.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import dataclasses
import datetime
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.modifications import DL41_DETECTOR_CANONICAL, DL41_MODIFICATIONS, stable_rng
from src.classical_faces.detection import create_face_detector
from src.classical_faces.preprocess import normalize_face
from src.hybrid.quality import QualityThresholds, compute_quality
from src.hybrid.recognizer import (
    FaceSample,
    GateThresholds,
    LBPHAdapter,
    LBPHMatch,
    QualityThresholds,
    SFaceAdapter,
    detect_sample,
    load_thresholds,
)
from src.independence_common import (
    create_lbph_recognizer_for_config,
    resolve_lbph_config,
)


def stable_order(names: Sequence[str], seed: int = 42, stratum: str = "lfw") -> list[str]:
    def key(name: str) -> bytes:
        return hashlib.sha256(f"{seed}:{stratum}:{name}".encode("utf-8")).digest()
    return sorted(names, key=key)


def get_lfw_identity_splits(lfw_root: Path, seed: int = 42) -> tuple[list[str], list[str]]:
    all_idents = sorted([p.name for p in lfw_root.iterdir() if p.is_dir()])
    ordered = stable_order(all_idents, seed, "lfw")
    midpoint = (len(ordered) + 1) // 2
    dev_idents = ordered[:midpoint]
    eval_idents = ordered[midpoint:]
    return dev_idents, eval_idents


def enroll_eval_gallery(
    lfw_root: Path,
    eval_idents: list[str],
    seed: int = 42,
) -> tuple[dict[str, str], dict[str, np.ndarray], np.ndarray, list[str]]:
    """Enroll 1 reference image per eval identity for LBPH and SFace."""
    import random
    rng = random.Random(seed)
    detector = create_face_detector("yunet")
    sface_raw = cv.FaceRecognizerSF.create(str(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx"), "")

    gallery_paths: dict[str, str] = {}
    gallery_lbph_faces: dict[str, np.ndarray] = {}
    gallery_sface_feats: list[np.ndarray] = []
    enrolled_names: list[str] = []

    print(f"[INFO] Enrolling gallery across {len(eval_idents)} evaluation identities...")
    for idx, person in enumerate(eval_idents):
        pdir = lfw_root / person
        img_files = sorted([f for f in pdir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        if not img_files:
            continue
        chosen_file = rng.choice(img_files)
        img_bgr = cv.imread(str(chosen_file))
        if img_bgr is None:
            continue
        img_gray = cv.cvtColor(img_bgr, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img_bgr, image_gray=img_gray, assume_cropped=False)
        if sample is None or sample.yunet_row is None:
            # Fallback crop center
            h, w = img_bgr.shape[:2]
            face_bgr = img_bgr
            face_gray = img_gray
            aligned = cv.resize(img_bgr, (112, 112))
        else:
            aligned = sface_raw.alignCrop(img_bgr, sample.yunet_row)
            face_gray = sample.face_gray

        norm_face = normalize_face(face_gray, img_size=(100, 100), equalization="tan-triggs")
        feat = sface_raw.feature(aligned).flatten()
        feat_u = feat / max(float(np.linalg.norm(feat)), 1e-6)

        gallery_paths[person] = str(chosen_file)
        gallery_lbph_faces[person] = norm_face
        gallery_sface_feats.append(feat_u)
        enrolled_names.append(person)

    sface_mat = np.vstack(gallery_sface_feats).astype(np.float32)
    print(f"[INFO] Successfully enrolled {len(enrolled_names)} identities in evaluation gallery.")
    return gallery_paths, gallery_lbph_faces, sface_mat, enrolled_names


def train_eval_lbph(
    gallery_lbph_faces: dict[str, np.ndarray],
    enrolled_names: list[str],
    config_tuple: tuple[int, int, int],
) -> Any:
    radius, neighbors, grid = config_tuple
    recognizer = cv.face.LBPHFaceRecognizer_create(
        radius=radius,
        neighbors=neighbors,
        grid_x=grid,
        grid_y=grid,
        threshold=10000.0,
    )
    faces = []
    labels = []
    for label, person in enumerate(enrolled_names):
        faces.append(gallery_lbph_faces[person])
        labels.append(label)
    recognizer.train(faces, np.array(labels, dtype=np.int32))
    return recognizer


def evaluate_identity_probes(
    person: str,
    orig_path: str,
    person_idx: int,
    enrolled_names: list[str],
    sface_gallery_mat: np.ndarray,
    lbph_chal_model: Any,
    lbph_base_model: Any,
    gate_chal: GateThresholds,
    gate_base: GateThresholds,
    qual_thresh: QualityThresholds,
    sface_l2_thresh: float,
    sface_cos_thresh: float,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Evaluates 1 clean + 41 transformed probes for one identity."""
    detector = create_face_detector("yunet")
    sface_raw = cv.FaceRecognizerSF.create(str(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx"), "")
    img_bgr = cv.imread(orig_path)
    if img_bgr is None:
        return []

    fname = Path(orig_path).name
    rows: list[dict[str, Any]] = []

    # Build probe set: clean + 41 modifications
    probes_to_eval: list[tuple[str, Any, np.ndarray]] = [("clean", "clean", img_bgr)]
    for mod_name, fn, levels in DL41_MODIFICATIONS:
        for level in levels:
            rng = stable_rng(seed, person, fname, mod_name, level)
            mod_bgr = fn(img_bgr, level, rng)
            probes_to_eval.append((mod_name, level, mod_bgr))

    for mod_name, level, probe_bgr in probes_to_eval:
        probe_gray = cv.cvtColor(probe_bgr, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=probe_bgr, image_gray=probe_gray, assume_cropped=False)
        det_ok = sample is not None

        row: dict[str, Any] = {
            "identity": person,
            "filename": fname,
            "modification": mod_name,
            "level": level,
            "detector_success": det_ok,
            "is_canonical_rot": mod_name in DL41_DETECTOR_CANONICAL,
        }

        if not det_ok or sample is None:
            for sys_key in ["challenger_lbph", "direct_sface", "combined_cascade", "baseline_seq"]:
                row[f"{sys_key}_correct"] = False
                row[f"{sys_key}_pred"] = "Unknown"
                row[f"{sys_key}_accepted"] = False
            row["combined_routing_path"] = "detector_failure"
            row["combined_sface_used"] = False
            row["combined_dual_inference"] = False
            rows.append(row)
            continue

        # SFace direct scoring (Unit-normalized cosine and L2)
        if sample.yunet_row is not None:
            aligned = sface_raw.alignCrop(probe_bgr, sample.yunet_row)
        else:
            aligned = cv.resize(probe_bgr, (112, 112))
        q_feat = sface_raw.feature(aligned).flatten()
        q_ufeat = q_feat / max(float(np.linalg.norm(q_feat)), 1e-6)

        # Vectorized SFace scoring against unit-normalized gallery
        cosines = np.dot(sface_gallery_mat, q_ufeat)
        l2_dists = np.sqrt(np.clip(2.0 - 2.0 * cosines, 0.0, 4.0))
        sf_best_idx = int(np.argmax(cosines))
        sf_best_cos = float(cosines[sf_best_idx])
        sf_best_l2 = float(l2_dists[sf_best_idx])
        sf_pred_name = enrolled_names[sf_best_idx]
        sf_accepted = (sf_best_l2 <= sface_l2_thresh) and (sf_best_cos >= sface_cos_thresh)
        sf_correct = (sf_pred_name == person) and sf_accepted

        row["direct_sface_pred"] = sf_pred_name
        row["direct_sface_correct"] = sf_correct
        row["direct_sface_accepted"] = sf_accepted
        row["direct_sface_l2"] = round(sf_best_l2, 4)
        row["direct_sface_cosine"] = round(sf_best_cos, 4)

        # Challenger LBPH scoring
        norm_face = normalize_face(sample.face_gray, img_size=(100, 100), equalization="tan-triggs")
        lb_label, lb_dist = lbph_chal_model.predict(norm_face)
        lb_pred_name = enrolled_names[lb_label]
        lb_accepted = lb_dist <= gate_chal.tau_accept
        lb_correct = (lb_pred_name == person) and lb_accepted

        row["challenger_lbph_pred"] = lb_pred_name
        row["challenger_lbph_correct"] = lb_correct
        row["challenger_lbph_accepted"] = lb_accepted
        row["challenger_lbph_dist"] = round(lb_dist, 4)

        # Baseline LBPH scoring
        base_label, base_dist = lbph_base_model.predict(norm_face)
        base_pred_name = enrolled_names[base_label]
        base_accepted = base_dist <= gate_base.tau_accept

        # Combined Optimized Cascade (Quality-First Early Bypass + r3_n8_g6x6)
        # Quality check first:
        q_report = compute_quality(
            gray_roi=sample.quality_gray,
            landmarks=sample.landmarks,
            face_px=sample.face_px,
            thresholds=qual_thresh,
        )
        q_flag = q_report.any_flag

        if q_flag:
            # Quality flag triggers direct SFace fallback
            row["combined_routing_path"] = "quality_triggered_sface"
            row["combined_cascade_pred"] = sf_pred_name
            row["combined_cascade_correct"] = sf_correct
            row["combined_cascade_accepted"] = sf_accepted
            row["combined_sface_used"] = True
            row["combined_dual_inference"] = False
        else:
            # Quality clear: evaluate challenger LBPH
            if lb_accepted:
                row["combined_routing_path"] = "quality_clear_lbph_terminal"
                row["combined_cascade_pred"] = lb_pred_name
                row["combined_cascade_correct"] = lb_correct
                row["combined_cascade_accepted"] = True
                row["combined_sface_used"] = False
                row["combined_dual_inference"] = False
            else:
                # Escalates to SFace
                row["combined_routing_path"] = "quality_clear_dual_sface"
                row["combined_cascade_pred"] = sf_pred_name
                row["combined_cascade_correct"] = sf_correct
                row["combined_cascade_accepted"] = sf_accepted
                row["combined_sface_used"] = True
                row["combined_dual_inference"] = True

        # Baseline Sequential Cascade (r1_n8_g8x8 + Sequential)
        if base_accepted and not q_flag:
            row["baseline_seq_pred"] = base_pred_name
            row["baseline_seq_correct"] = (base_pred_name == person) and base_accepted
            row["baseline_seq_accepted"] = True
            row["baseline_seq_dual"] = False
        else:
            row["baseline_seq_pred"] = sf_pred_name
            row["baseline_seq_correct"] = sf_correct
            row["baseline_seq_accepted"] = sf_accepted
            row["baseline_seq_dual"] = True

        rows.append(row)

    return rows


def worker_job(
    ident_subset: list[str],
    gallery_paths: dict[str, str],
    enrolled_names: list[str],
    sface_gallery_mat: np.ndarray,
    lbph_chal_path: str,
    lbph_base_path: str,
    gate_chal: GateThresholds,
    gate_base: GateThresholds,
    qual_thresh: QualityThresholds,
    sface_l2_thresh: float,
    sface_cos_thresh: float,
    seed: int = 42,
) -> list[dict[str, Any]]:
    # Load LBPH models once per worker process
    lbph_chal_model = cv.face.LBPHFaceRecognizer_create()
    lbph_chal_model.read(lbph_chal_path)
    lbph_base_model = cv.face.LBPHFaceRecognizer_create()
    lbph_base_model.read(lbph_base_path)

    results: list[dict[str, Any]] = []
    for person in ident_subset:
        person_idx = enrolled_names.index(person)
        orig_path = gallery_paths[person]
        rows = evaluate_identity_probes(
            person=person,
            orig_path=orig_path,
            person_idx=person_idx,
            enrolled_names=enrolled_names,
            sface_gallery_mat=sface_gallery_mat,
            lbph_chal_model=lbph_chal_model,
            lbph_base_model=lbph_base_model,
            gate_chal=gate_chal,
            gate_base=gate_base,
            qual_thresh=qual_thresh,
            sface_l2_thresh=sface_l2_thresh,
            sface_cos_thresh=sface_cos_thresh,
            seed=seed,
        )
        results.extend(rows)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BGR-first LFW robustness evaluation on disjoint eval identities.")
    parser.add_argument("--lfw-root", default="data/lfw-dataset", help="Path to LFW dataset.")
    parser.add_argument("--num-workers", type=int, default=8, help="Number of parallel worker processes.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--output-dir", default="docs/results/robustness_test/lfw_disjoint_bgr41_robustness", help="Output directory.")
    args = parser.parse_args()

    lfw_root = PROJECT_ROOT / args.lfw_root
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir = PROJECT_ROOT / "models" / "lfw_disjoint"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(" CORRECTED BGR-FIRST LFW ROBUSTNESS EVALUATION (2,874 DISJOINT IDENTITIES)")
    print("=" * 80)

    # 1. Identity Splits
    dev_idents, eval_idents = get_lfw_identity_splits(lfw_root, args.seed)
    print(f"[INFO] Total identities: {len(dev_idents) + len(eval_idents)}")
    print(f"[INFO] Development identities (calibration cohort): {len(dev_idents)}")
    print(f"[INFO] Evaluation identities (robustness cohort):   {len(eval_idents)}")

    # 2. Gallery Enrollment on Evaluation Cohort
    gallery_paths, gallery_lbph_faces, sface_mat, enrolled_names = enroll_eval_gallery(lfw_root, eval_idents, args.seed)

    # 3. Train LBPH Models on Evaluation Cohort and Save to disk
    chal_model_path = str(models_dir / "lbph_r3_n8_g6x6_eval2874.yml")
    base_model_path = str(models_dir / "lbph_r1_n8_g8x8_eval2874.yml")

    print("[INFO] Training Challenger r3_n8_g6x6 LBPH model on 2,874 evaluation identities...")
    lbph_chal = train_eval_lbph(gallery_lbph_faces, enrolled_names, (3, 8, 6))
    lbph_chal.write(chal_model_path)
    del lbph_chal

    print("[INFO] Training Baseline r1_n8_g8x8 LBPH model on 2,874 evaluation identities...")
    lbph_base = train_eval_lbph(gallery_lbph_faces, enrolled_names, (1, 8, 8))
    lbph_base.write(base_model_path)
    del lbph_base

    # 4. Threshold Calibration (Frozen from Development Partition)
    gate_chal = GateThresholds(tau_accept=52.372394898355424, tau_reject=140.13, margin_min=0.05)
    gate_base = GateThresholds(tau_accept=67.0132357790767, tau_reject=140.13, margin_min=0.05)
    qual_thresh = QualityThresholds(
        tau_blur=587.83,
        luma_lo=52.88,
        luma_hi=137.71,
        tau_noise=8.206,
        tau_pose=63.74,
        px_min=61,
    )
    sface_l2_thresh = 1.0313
    sface_cos_thresh = 0.363

    # 5. Parallel Multi-Worker Evaluation across 2,874 Identities
    num_workers = min(args.num_workers, os.cpu_count() or 4)
    chunks = np.array_split(eval_idents, num_workers)
    print(f"\n[INFO] Launching parallel evaluation across {num_workers} workers ({len(eval_idents)} total identities)...")

    start_time = time.perf_counter()
    all_results: list[dict[str, Any]] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(
                worker_job,
                list(chunk),
                gallery_paths,
                enrolled_names,
                sface_mat,
                chal_model_path,
                base_model_path,
                gate_chal,
                gate_base,
                qual_thresh,
                sface_l2_thresh,
                sface_cos_thresh,
                args.seed,
            )
            for chunk in chunks
        ]
        for future in concurrent.futures.as_completed(futures):
            chunk_res = future.result()
            all_results.extend(chunk_res)
            print(f"  [PROGRESS] Completed chunk with {len(chunk_res)} condition records (total so far: {len(all_results)})")

    elapsed = time.perf_counter() - start_time
    print(f"\n[SUCCESS] Completed {len(all_results)} conditions in {elapsed:.2f} seconds ({elapsed/60.0:.2f} minutes)!")

    # 6. Process and Aggregate Results
    # Separate clean vs 41 modified transformations
    clean_records = [r for r in all_results if r["modification"] == "clean"]
    mod_records = [r for r in all_results if r["modification"] != "clean"]

    total_clean = len(clean_records)
    total_mod = len(mod_records)
    assert total_clean == 2874
    assert total_mod == 2874 * 41

    det_failures_mod = sum(1 for r in mod_records if not r["detector_success"])

    # Aggregate per modification
    mod_names = [m[0] for m in DL41_MODIFICATIONS]
    per_mod_stats: dict[str, dict[str, float]] = {}

    for m_name in mod_names:
        sub = [r for r in mod_records if r["modification"] == m_name]
        n_sub = len(sub)
        per_mod_stats[m_name] = {
            "total_probes": n_sub,
            "detector_failures": sum(1 for r in sub if not r["detector_success"]),
            "detector_failure_pct": 100.0 * sum(1 for r in sub if not r["detector_success"]) / n_sub,
            "direct_sface_retention_pct": 100.0 * sum(1 for r in sub if r["direct_sface_correct"]) / n_sub,
            "challenger_lbph_retention_pct": 100.0 * sum(1 for r in sub if r["challenger_lbph_correct"]) / n_sub,
            "combined_cascade_retention_pct": 100.0 * sum(1 for r in sub if r["combined_cascade_correct"]) / n_sub,
            "baseline_seq_retention_pct": 100.0 * sum(1 for r in sub if r["baseline_seq_correct"]) / n_sub,
            "combined_sface_invocation_pct": 100.0 * sum(1 for r in sub if r["combined_sface_used"]) / n_sub,
            "combined_dual_inference_pct": 100.0 * sum(1 for r in sub if r["combined_dual_inference"]) / n_sub,
        }

    # Macro averages across all 41 modifications
    macro_all41 = {
        "direct_sface_mean_pct": float(np.mean([stats["direct_sface_retention_pct"] for stats in per_mod_stats.values()])),
        "challenger_lbph_mean_pct": float(np.mean([stats["challenger_lbph_retention_pct"] for stats in per_mod_stats.values()])),
        "combined_cascade_mean_pct": float(np.mean([stats["combined_cascade_retention_pct"] for stats in per_mod_stats.values()])),
        "baseline_seq_mean_pct": float(np.mean([stats["baseline_seq_retention_pct"] for stats in per_mod_stats.values()])),
        "combined_sface_invocation_mean_pct": float(np.mean([stats["combined_sface_invocation_pct"] for stats in per_mod_stats.values()])),
        "combined_dual_inference_mean_pct": float(np.mean([stats["combined_dual_inference_pct"] for stats in per_mod_stats.values()])),
    }

    # Macro averages excluding 4 detector canonical (37 modifications)
    macro_ex_canon = {
        "direct_sface_mean_pct": float(np.mean([stats["direct_sface_retention_pct"] for m, stats in per_mod_stats.items() if m not in DL41_DETECTOR_CANONICAL])),
        "challenger_lbph_mean_pct": float(np.mean([stats["challenger_lbph_retention_pct"] for m, stats in per_mod_stats.items() if m not in DL41_DETECTOR_CANONICAL])),
        "combined_cascade_mean_pct": float(np.mean([stats["combined_cascade_retention_pct"] for m, stats in per_mod_stats.items() if m not in DL41_DETECTOR_CANONICAL])),
        "baseline_seq_mean_pct": float(np.mean([stats["baseline_seq_retention_pct"] for m, stats in per_mod_stats.items() if m not in DL41_DETECTOR_CANONICAL])),
    }

    # Clean metrics
    clean_summary = {
        "total_clean_probes": total_clean,
        "direct_sface_retention_pct": 100.0 * sum(1 for r in clean_records if r["direct_sface_correct"]) / total_clean,
        "challenger_lbph_retention_pct": 100.0 * sum(1 for r in clean_records if r["challenger_lbph_correct"]) / total_clean,
        "combined_cascade_retention_pct": 100.0 * sum(1 for r in clean_records if r["combined_cascade_correct"]) / total_clean,
        "combined_sface_invocation_pct": 100.0 * sum(1 for r in clean_records if r["combined_sface_used"]) / total_clean,
        "combined_dual_inference_pct": 100.0 * sum(1 for r in clean_records if r["combined_dual_inference"]) / total_clean,
    }

    summary_payload = {
        "protocol": "controlled_self_match_robustness_bgr_first",
        "dataset": "LFW (lfw-dataset)",
        "development_identities": len(dev_idents),
        "evaluation_identities": len(eval_idents),
        "total_modified_conditions": total_mod,
        "total_clean_conditions": total_clean,
        "detector_failures_modified": det_failures_mod,
        "detector_failure_rate_pct": 100.0 * det_failures_mod / total_mod,
        "clean_summary": clean_summary,
        "macro_averages_all41": macro_all41,
        "macro_averages_exclude_canonical": macro_ex_canon,
        "per_modification_stats": per_mod_stats,
        "thresholds_used": {
            "challenger_lbph_tau_accept": gate_chal.tau_accept,
            "baseline_lbph_tau_accept": gate_base.tau_accept,
            "tau_reject": gate_chal.tau_reject,
            "margin_min": gate_chal.margin_min,
            "sface_l2": sface_l2_thresh,
            "sface_cosine": sface_cos_thresh,
        },
    }

    # Save summary.json
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)

    # Save per_modification_results.csv
    csv_path = output_dir / "per_modification_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "modification",
            "total_probes",
            "detector_failures",
            "detector_failure_pct",
            "challenger_lbph_retention_pct",
            "direct_sface_retention_pct",
            "combined_cascade_retention_pct",
            "baseline_seq_retention_pct",
            "combined_sface_invocation_pct",
            "combined_dual_inference_pct",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m_name, stats in per_mod_stats.items():
            row_dict = {"modification": m_name, **stats}
            writer.writerow(row_dict)

    # Print summary table
    print("\n" + "=" * 80)
    print(" LFW ROBUSTNESS EVALUATION SUMMARY (117,834 CONDITIONS)")
    print("=" * 80)
    print(f"Clean Retention:      Challenger LBPH: {clean_summary['challenger_lbph_retention_pct']:.2f}% | SFace: {clean_summary['direct_sface_retention_pct']:.2f}% | Combined: {clean_summary['combined_cascade_retention_pct']:.2f}%")
    print(f"All-41 Macro Mean:    Challenger LBPH: {macro_all41['challenger_lbph_mean_pct']:.2f}% | SFace: {macro_all41['direct_sface_mean_pct']:.2f}% | Combined: {macro_all41['combined_cascade_mean_pct']:.2f}% (Baseline Seq: {macro_all41['baseline_seq_mean_pct']:.2f}%)")
    print(f"Ex-Canon Macro Mean:  Challenger LBPH: {macro_ex_canon['challenger_lbph_mean_pct']:.2f}% | SFace: {macro_ex_canon['direct_sface_mean_pct']:.2f}% | Combined: {macro_ex_canon['combined_cascade_mean_pct']:.2f}% (Baseline Seq: {macro_ex_canon['baseline_seq_mean_pct']:.2f}%)")
    print(f"Detector Failures:    {det_failures_mod} / {total_mod} ({100.0*det_failures_mod/total_mod:.2f}%)")
    print(f"Combined SFace Use:   {macro_all41['combined_sface_invocation_mean_pct']:.2f}%")
    print(f"Combined Dual Infer:  {macro_all41['combined_dual_inference_mean_pct']:.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
