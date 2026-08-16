"""Timing Control Pass: Paired, Interleaved Verification on the 246 Smoke Conditions.

Tests:
1. Paired comparison: Direct SFace vs (Quality -> SFace) on the exact same 121 quality-flagged samples.
2. Paired comparison: Sequential Cascade vs Early-Bypass on the exact same 100 dual-inference samples.
3. Fully interleaved/randomized execution order per probe per repetition to eliminate thermal/order/cache biases.
4. Concrete p95 analysis across branch distributions.
"""

from __future__ import annotations

import csv
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.modifications import get_modification_set, stable_rng
from src.classical_faces.detection import create_face_detector
from src.hybrid.gate import GateThresholds, decide_escalation
from src.hybrid.quality import QualityThresholds, compute_quality
from src.hybrid.recognizer import (
    FaceSample,
    LBPHAdapter,
    SFaceAdapter,
    detect_sample,
    load_thresholds,
)


def main() -> None:
    seed = 20260816
    output_dir = PROJECT_ROOT / "outputs" / "smoke_tests" / "timing_control_2026-08-16"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load thresholds & models
    thresh_path = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"
    thresh_data = load_thresholds(thresh_path)
    gate_thresh = GateThresholds.from_dict(thresh_data["gate"])
    qual_thresh = QualityThresholds.from_dict(thresh_data["quality"])

    detector = create_face_detector("yunet")
    lbph = LBPHAdapter(
        model_path=str(PROJECT_ROOT / "models" / "lbph" / "lasalle_clean.yml"),
        labels_path=str(PROJECT_ROOT / "models" / "lbph" / "labels_lasalle_clean.json"),
        far_anchors=thresh_data.get("lbph_far_anchors"),
    )
    sface = SFaceAdapter(
        model_path=str(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx"),
        gallery_path=str(PROJECT_ROOT / "models" / "sface" / "gallery.npy"),
    )

    # 2. Load the 246 smoke subset
    manifest_path = PROJECT_ROOT / "outputs" / "smoke_tests" / "quality_first_smoke_2026-08-16" / "subset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    mods_list, mod_count = get_modification_set("dl41")
    probes = []
    for entry in manifest["selected_source_images"]:
        person = entry["identity"]
        fname = entry["filename"]
        img_bgr = cv.imread(entry["abs_path"])
        for mod_name, fn, levels in mods_list:
            level = levels[0]
            rng_mod = stable_rng(seed, person, fname, mod_name, level)
            mod_bgr = fn(img_bgr, level, rng_mod)
            probes.append({
                "identity": person,
                "filename": fname,
                "mod_name": mod_name,
                "image_bgr": mod_bgr,
            })

    # Run detection
    for p in probes:
        img_bgr = p["image_bgr"]
        img_gray = cv.cvtColor(img_bgr, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img_bgr, image_gray=img_gray, assume_cropped=True)
        p["sample"] = sample
        p["detected"] = sample is not None

    detected_probes = [p for p in probes if p["detected"]]
    print(f"[INFO] Loaded {len(probes)} probes; {len(detected_probes)} detected faces.")

    # 3. Classify ground truth routing branch for each probe
    for p in detected_probes:
        s = p["sample"]
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        lm = lbph.score(s)
        p["quality"] = q
        p["quality_any_flag"] = q.any_flag
        p["lbph_match"] = lm
        is_ambiguous = gate_thresh.tau_accept < lm.distance < gate_thresh.tau_reject
        is_low_margin = lm.margin < gate_thresh.margin_min

        if q.any_flag:
            p["branch"] = "quality_triggered_sface"
        elif is_ambiguous or is_low_margin:
            p["branch"] = "quality_clear_dual_sface"
        else:
            p["branch"] = "quality_clear_lbph_terminal"

    branch1_probes = [p for p in detected_probes if p["branch"] == "quality_triggered_sface"]
    branch2_probes = [p for p in detected_probes if p["branch"] == "quality_clear_lbph_terminal"]
    branch3_probes = [p for p in detected_probes if p["branch"] == "quality_clear_dual_sface"]
    print(f"[INFO] Ground truth branches: Branch 1 (Quality->SFace)={len(branch1_probes)}, "
          f"Branch 2 (LBPH terminal)={len(branch2_probes)}, Branch 3 (Dual)={len(branch3_probes)}")

    # 4. Define isolated execution functions with identical timing boundaries
    def run_direct_sface(s: FaceSample) -> float:
        t0 = time.perf_counter()
        sm = sface.score(s)
        _ = sm.name
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_quality_then_sface(s: FaceSample) -> float:
        t0 = time.perf_counter()
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        sm = sface.score(s)
        _ = sm.name
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_sequential_cascade(s: FaceSample) -> float:
        t0 = time.perf_counter()
        lm = lbph.score(s)
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        gate = decide_escalation(lbph_distance=lm.distance, lbph_margin=lm.margin, quality=q, thresholds=gate_thresh)
        if gate.escalate:
            sm = sface.score(s)
            _ = sm.name
        else:
            _ = lm.name if gate.lbph_accept else "Unknown"
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_early_bypass_cascade(s: FaceSample) -> float:
        t0 = time.perf_counter()
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        if q.any_flag:
            sm = sface.score(s)
            _ = sm.name
        else:
            lm = lbph.score(s)
            is_amb = gate_thresh.tau_accept < lm.distance < gate_thresh.tau_reject
            is_low_m = lm.margin < gate_thresh.margin_min
            if is_amb or is_low_m:
                sm = sface.score(s)
                _ = sm.name
            else:
                _ = lm.name if lm.distance <= gate_thresh.tau_accept else "Unknown"
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_isolated_quality_check(s: FaceSample) -> float:
        t0 = time.perf_counter()
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        _ = q.any_flag
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    # 5. Randomized / Interleaved Benchmark
    print("\n[INFO] Running Warm-up pass...")
    for p in detected_probes:
        s = p["sample"]
        run_direct_sface(s)
        run_quality_then_sface(s)
        run_sequential_cascade(s)
        run_early_bypass_cascade(s)

    NUM_REPETITIONS = 10
    print(f"[INFO] Running {NUM_REPETITIONS} interleaved timing repetitions with per-probe order randomization...")

    # Data structures to accumulate per-probe latencies
    probe_direct_sface: list[list[float]] = [[] for _ in detected_probes]
    probe_qual_sface: list[list[float]] = [[] for _ in detected_probes]
    probe_seq: list[list[float]] = [[] for _ in detected_probes]
    probe_early_bypass: list[list[float]] = [[] for _ in detected_probes]
    probe_quality_alone: list[list[float]] = [[] for _ in detected_probes]

    modes_to_test = ["direct_sface", "qual_sface", "seq", "early_bypass", "quality_alone"]

    rng_timing = random.Random(42)

    for rep in range(NUM_REPETITIONS):
        # Shuffle probe order each repetition
        indices = list(range(len(detected_probes)))
        rng_timing.shuffle(indices)

        for i in indices:
            s = detected_probes[i]["sample"]
            # Shuffle mode execution order for this specific probe
            mode_order = list(modes_to_test)
            rng_timing.shuffle(mode_order)

            for m in mode_order:
                if m == "direct_sface":
                    lat = run_direct_sface(s)
                    probe_direct_sface[i].append(lat)
                elif m == "qual_sface":
                    lat = run_quality_then_sface(s)
                    probe_qual_sface[i].append(lat)
                elif m == "seq":
                    lat = run_sequential_cascade(s)
                    probe_seq[i].append(lat)
                elif m == "early_bypass":
                    lat = run_early_bypass_cascade(s)
                    probe_early_bypass[i].append(lat)
                elif m == "quality_alone":
                    lat = run_isolated_quality_check(s)
                    probe_quality_alone[i].append(lat)

    # Compute mean per probe across repetitions
    mean_direct_sface = [float(np.mean(l)) for l in probe_direct_sface]
    mean_qual_sface = [float(np.mean(l)) for l in probe_qual_sface]
    mean_seq = [float(np.mean(l)) for l in probe_seq]
    mean_early_bypass = [float(np.mean(l)) for l in probe_early_bypass]
    mean_qual_alone = [float(np.mean(l)) for l in probe_quality_alone]

    # Analysis 1: Paired comparison on 121 Quality-Flagged Samples
    # Direct SFace vs Quality -> SFace
    b1_indices = [i for i, p in enumerate(detected_probes) if p["branch"] == "quality_triggered_sface"]
    assert len(b1_indices) == 121

    paired_diff_b1 = [mean_qual_sface[i] - mean_direct_sface[i] for i in b1_indices]
    q_alone_b1 = [mean_qual_alone[i] for i in b1_indices]

    print("\n" + "=" * 60)
    print("ANALYSIS 1: Direct SFace vs Quality->SFace on the 121 Quality-Flagged Samples")
    print("=" * 60)
    print(f"Direct SFace Mean Latency:        {np.mean([mean_direct_sface[i] for i in b1_indices]):.3f} ms (p50: {np.median([mean_direct_sface[i] for i in b1_indices]):.3f} ms)")
    print(f"Quality->SFace Mean Latency:      {np.mean([mean_qual_sface[i] for i in b1_indices]):.3f} ms (p50: {np.median([mean_qual_sface[i] for i in b1_indices]):.3f} ms)")
    print(f"Paired Difference (Qual->SF - SF): Mean = {np.mean(paired_diff_b1):.3f} ms, Median = {np.median(paired_diff_b1):.3f} ms")
    print(f"Standalone Quality Check Latency:  Mean = {np.mean(q_alone_b1):.3f} ms, Median = {np.median(q_alone_b1):.3f} ms")
    print(f"Overhead Ratio (Paired Diff / Q): {np.mean(paired_diff_b1) / np.mean(q_alone_b1):.2f}x")

    # Analysis 2: Paired comparison on the 100 Dual-Inference Samples
    # Sequential vs Early-Bypass
    b3_indices = [i for i, p in enumerate(detected_probes) if p["branch"] == "quality_clear_dual_sface"]
    assert len(b3_indices) == 100

    seq_b3 = [mean_seq[i] for i in b3_indices]
    eb_b3 = [mean_early_bypass[i] for i in b3_indices]
    paired_diff_b3 = [eb_b3[k] - seq_b3[k] for k in range(len(b3_indices))]

    print("\n" + "=" * 60)
    print("ANALYSIS 2: Sequential vs Early-Bypass on the 100 Dual-Inference Samples")
    print("=" * 60)
    print(f"Sequential Cascade on Dual:   Mean = {np.mean(seq_b3):.3f} ms, Median = {np.median(seq_b3):.3f} ms, p95 = {np.percentile(seq_b3, 95):.3f} ms")
    print(f"Early-Bypass on Dual:         Mean = {np.mean(eb_b3):.3f} ms, Median = {np.median(eb_b3):.3f} ms, p95 = {np.percentile(eb_b3, 95):.3f} ms")
    print(f"Paired Difference (EB - Seq): Mean = {np.mean(paired_diff_b3):.3f} ms, Median = {np.median(paired_diff_b3):.3f} ms, Std = {np.std(paired_diff_b3):.3f} ms")

    # Analysis 3: Overall Cascade Latency with Randomized Interleaving
    print("\n" + "=" * 60)
    print("ANALYSIS 3: Overall 246-Condition Latency (Interleaved 10-Repetition Average)")
    print("=" * 60)
    print(f"Direct SFace:    Mean = {np.mean(mean_direct_sface):.3f} ms, p50 = {np.median(mean_direct_sface):.3f} ms, p95 = {np.percentile(mean_direct_sface, 95):.3f} ms")
    print(f"Sequential:      Mean = {np.mean(mean_seq):.3f} ms, p50 = {np.median(mean_seq):.3f} ms, p95 = {np.percentile(mean_seq, 95):.3f} ms")
    print(f"Early-Bypass:    Mean = {np.mean(mean_early_bypass):.3f} ms, p50 = {np.median(mean_early_bypass):.3f} ms, p95 = {np.percentile(mean_early_bypass, 95):.3f} ms")
    diff_overall = np.mean(mean_seq) - np.mean(mean_early_bypass)
    pct_overall = (diff_overall / np.mean(mean_seq)) * 100.0
    print(f"Overall Latency Saving: {diff_overall:.3f} ms ({pct_overall:.2f}%)")

    # Analysis 4: Concrete p95 Diagnosis
    print("\n" + "=" * 60)
    print("ANALYSIS 4: Concrete p95 Breakdown by Branch")
    print("=" * 60)
    eb_b1_lats = [mean_early_bypass[i] for i in b1_indices]
    eb_b2_indices = [i for i, p in enumerate(detected_probes) if p["branch"] == "quality_clear_lbph_terminal"]
    eb_b2_lats = [mean_early_bypass[i] for i in eb_b2_indices]
    eb_b3_lats = [mean_early_bypass[i] for i in b3_indices]

    seq_b1_lats = [mean_seq[i] for i in b1_indices]
    seq_b2_lats = [mean_seq[i] for i in eb_b2_indices]
    seq_b3_lats = [mean_seq[i] for i in b3_indices]

    print(f"Branch 1 (Qual->SF, N=121):  EB Mean={np.mean(eb_b1_lats):.3f}, p95={np.percentile(eb_b1_lats, 95):.3f} | Seq Mean={np.mean(seq_b1_lats):.3f}, p95={np.percentile(seq_b1_lats, 95):.3f}")
    print(f"Branch 2 (LBPH term, N=18):  EB Mean={np.mean(eb_b2_lats):.3f}, p95={np.percentile(eb_b2_lats, 95):.3f} | Seq Mean={np.mean(seq_b2_lats):.3f}, p95={np.percentile(seq_b2_lats, 95):.3f}")
    print(f"Branch 3 (Dual, N=100):      EB Mean={np.mean(eb_b3_lats):.3f}, p95={np.percentile(eb_b3_lats, 95):.3f} | Seq Mean={np.mean(seq_b3_lats):.3f}, p95={np.percentile(seq_b3_lats, 95):.3f}")

    # Output detailed JSON
    results = {
        "num_repetitions": NUM_REPETITIONS,
        "direct_sface": {
            "mean_ms": round(float(np.mean(mean_direct_sface)), 3),
            "p50_ms": round(float(np.median(mean_direct_sface)), 3),
            "p95_ms": round(float(np.percentile(mean_direct_sface, 95)), 3),
        },
        "sequential_cascade": {
            "mean_ms": round(float(np.mean(mean_seq)), 3),
            "p50_ms": round(float(np.median(mean_seq)), 3),
            "p95_ms": round(float(np.percentile(mean_seq, 95)), 3),
        },
        "early_bypass_cascade": {
            "mean_ms": round(float(np.mean(mean_early_bypass)), 3),
            "p50_ms": round(float(np.median(mean_early_bypass)), 3),
            "p95_ms": round(float(np.percentile(mean_early_bypass, 95)), 3),
        },
        "paired_analysis_121_quality_flagged": {
            "direct_sface_mean_ms": round(float(np.mean([mean_direct_sface[i] for i in b1_indices])), 3),
            "quality_sface_mean_ms": round(float(np.mean([mean_qual_sface[i] for i in b1_indices])), 3),
            "paired_difference_mean_ms": round(float(np.mean(paired_diff_b1)), 3),
            "paired_difference_median_ms": round(float(np.median(paired_diff_b1)), 3),
            "quality_alone_mean_ms": round(float(np.mean(q_alone_b1)), 3),
        },
        "paired_analysis_100_dual_inference": {
            "sequential_mean_ms": round(float(np.mean(seq_b3)), 3),
            "early_bypass_mean_ms": round(float(np.mean(eb_b3)), 3),
            "paired_difference_mean_ms": round(float(np.mean(paired_diff_b3)), 3),
            "paired_difference_median_ms": round(float(np.median(paired_diff_b3)), 3),
            "paired_difference_std_ms": round(float(np.std(paired_diff_b3)), 3),
        },
        "overall_reduction": {
            "mean_diff_ms": round(float(diff_overall), 3),
            "percent_reduction": round(float(pct_overall), 2),
        },
    }
    (output_dir / "timing_control_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[COMPLETE] Saved timing control results to {output_dir}")


if __name__ == "__main__":
    main()
