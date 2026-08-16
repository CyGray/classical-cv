"""Smoke Test: Joint Combination of Quality-First Early-Bypass Routing + r3_n8_g6x6 LBPH.

Evaluates:
  1. Baseline Cascade: r1_n8_g8x8 + Sequential Routing
  2. Architecture-Only: r1_n8_g8x8 + Quality-First Early Bypass
  3. Descriptor-Only: r3_n8_g6x6 + Sequential Routing
  4. Combined Unified Cascade: r3_n8_g6x6 + Quality-First Early Bypass
  5. Standalone SFace
  6. Standalone LBPH Baseline vs Challenger

Dataset: 6 source test images x 41 DL41 transforms = 246 conditions (seed 20260816).
Timing: 1 warmup pass + 5 randomized interleaved repetitions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.modifications import (
    DL41_CATEGORY_MAP,
    DL41_TIER_MAP,
    get_modification_set,
    stable_rng,
)
from src.classical_faces.detection import create_face_detector
from src.classical_faces.lbph_config import (
    DEPLOYED_LBPH_CONFIG,
    SELECTED_LBPH_CONFIG,
    create_lbph_recognizer,
)
from src.hybrid.gate import GateThresholds, decide_escalation
from src.hybrid.quality import QualityReport, QualityThresholds, compute_quality
from src.hybrid.recognizer import (
    FaceSample,
    LBPHAdapter,
    LBPHMatch,
    SFaceAdapter,
    detect_sample,
    load_thresholds,
)
from src.lbph.preprocess import IMG_SIZE, normalize_face
from src.sface.recognizer import SFaceMatch


class InstrumentedLBPH:
    def __init__(self, adapter: LBPHAdapter) -> None:
        self.adapter = adapter
        self.call_count = 0

    def score(self, sample: FaceSample) -> LBPHMatch:
        self.call_count += 1
        return self.adapter.score(sample)

    def reset_count(self) -> None:
        self.call_count = 0


class InstrumentedSFace:
    def __init__(self, adapter: SFaceAdapter) -> None:
        self.adapter = adapter
        self.call_count = 0

    def score(self, sample: FaceSample) -> SFaceMatch:
        self.call_count += 1
        return self.adapter.score(sample)

    def reset_count(self) -> None:
        self.call_count = 0


def train_challenger_lbph(train_dir: Path, labels_path: Path, output_path: Path) -> None:
    with open(labels_path, "r", encoding="utf-8") as f:
        labels_map = json.load(f)
    faces = []
    labels = []
    for person_name, label_id in labels_map.items():
        pdir = train_dir / person_name
        for img_path in sorted(pdir.glob("*.jpg")):
            img = cv.imread(str(img_path), cv.IMREAD_GRAYSCALE)
            if img is not None:
                norm = normalize_face(img, img_size=IMG_SIZE, equalization="tan-triggs")
                faces.append(norm)
                labels.append(int(label_id))

    rec = create_lbph_recognizer(SELECTED_LBPH_CONFIG)
    rec.train(faces, np.array(labels, dtype=np.int32))
    rec.write(str(output_path))


def run_sequential_cascade(
    sample: FaceSample,
    lbph: InstrumentedLBPH,
    sface: InstrumentedSFace,
    gate_thresh: GateThresholds,
    qual_thresh: QualityThresholds,
) -> dict[str, Any]:
    lbph_match = lbph.score(sample)
    quality = compute_quality(
        gray_roi=sample.quality_gray,
        landmarks=sample.landmarks,
        face_px=sample.face_px,
        thresholds=qual_thresh,
    )
    gate = decide_escalation(
        lbph_distance=lbph_match.distance,
        lbph_margin=lbph_match.margin,
        quality=quality,
        thresholds=gate_thresh,
    )
    if gate.escalate:
        sface_match = sface.score(sample)
        return {
            "pred_name": sface_match.name,
            "accepted": sface_match.accepted,
            "lbph_name": lbph_match.name,
            "lbph_distance": lbph_match.distance,
            "lbph_margin": lbph_match.margin,
            "sface_name": sface_match.name,
            "sface_cosine": sface_match.cosine,
            "sface_l2": sface_match.l2,
            "reason": gate.reason,
            "escalated": True,
            "routing_path": "dual_sface",
        }
    else:
        accepted = gate.lbph_accept
        pred_name = lbph_match.name if accepted else "Unknown"
        return {
            "pred_name": pred_name,
            "accepted": accepted,
            "lbph_name": lbph_match.name,
            "lbph_distance": lbph_match.distance,
            "lbph_margin": lbph_match.margin,
            "sface_name": None,
            "sface_cosine": None,
            "sface_l2": None,
            "reason": gate.reason,
            "escalated": False,
            "routing_path": "lbph_terminal",
        }


def run_early_bypass_cascade(
    sample: FaceSample,
    lbph: InstrumentedLBPH,
    sface: InstrumentedSFace,
    gate_thresh: GateThresholds,
    qual_thresh: QualityThresholds,
) -> dict[str, Any]:
    quality = compute_quality(
        gray_roi=sample.quality_gray,
        landmarks=sample.landmarks,
        face_px=sample.face_px,
        thresholds=qual_thresh,
    )
    if quality.any_flag:
        # Bypasses LBPH directly
        sface_match = sface.score(sample)
        return {
            "pred_name": sface_match.name,
            "accepted": sface_match.accepted,
            "lbph_name": None,
            "lbph_distance": None,
            "lbph_margin": None,
            "sface_name": sface_match.name,
            "sface_cosine": sface_match.cosine,
            "sface_l2": sface_match.l2,
            "reason": "quality:" + ",".join(quality.active_flags),
            "escalated": True,
            "routing_path": "quality_triggered_sface",
        }

    # Quality clear -> evaluate LBPH
    lbph_match = lbph.score(sample)
    is_ambiguous = gate_thresh.tau_accept < lbph_match.distance < gate_thresh.tau_reject
    is_low_margin = lbph_match.margin < gate_thresh.margin_min

    if is_ambiguous or is_low_margin:
        sface_match = sface.score(sample)
        reason = "ambiguous_band" if is_ambiguous else "low_margin"
        return {
            "pred_name": sface_match.name,
            "accepted": sface_match.accepted,
            "lbph_name": lbph_match.name,
            "lbph_distance": lbph_match.distance,
            "lbph_margin": lbph_match.margin,
            "sface_name": sface_match.name,
            "sface_cosine": sface_match.cosine,
            "sface_l2": sface_match.l2,
            "reason": reason,
            "escalated": True,
            "routing_path": "quality_clear_dual_sface",
        }
    else:
        accepted = lbph_match.distance <= gate_thresh.tau_accept
        pred_name = lbph_match.name if accepted else "Unknown"
        reason = "confident_accept" if accepted else "confident_reject"
        return {
            "pred_name": pred_name,
            "accepted": accepted,
            "lbph_name": lbph_match.name,
            "lbph_distance": lbph_match.distance,
            "lbph_margin": lbph_match.margin,
            "sface_name": None,
            "sface_cosine": None,
            "sface_l2": None,
            "reason": reason,
            "escalated": False,
            "routing_path": "quality_clear_lbph_terminal",
        }


def main() -> None:
    seed = 20260816
    output_dir = PROJECT_ROOT / "outputs" / "smoke_tests" / "combined_major_smoke_2026-08-16"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load thresholds
    thresh_path = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"
    thresh_data = load_thresholds(thresh_path)
    gate_thresh_baseline = GateThresholds.from_dict(thresh_data["gate"])
    qual_thresh = QualityThresholds.from_dict(thresh_data["quality"])

    # Challenger threshold: 52.3724 from calibrated LFW derivation
    gate_thresh_challenger = GateThresholds(
        tau_accept=52.372394898355424,
        tau_reject=gate_thresh_baseline.tau_reject,
        margin_min=gate_thresh_baseline.margin_min,
    )

    # 2. Prepare train / test directories
    train_dir = PROJECT_ROOT.parent / "data" / "lsdb" / "split" / "train"
    if not train_dir.exists():
        train_dir = PROJECT_ROOT / "data" / "lsdb" / "split" / "train"
    test_root = PROJECT_ROOT.parent / "data" / "lsdb" / "split" / "test"
    if not test_root.exists():
        test_root = PROJECT_ROOT / "data" / "lsdb" / "split" / "test"

    labels_path = PROJECT_ROOT / "models" / "lbph" / "labels_lasalle_clean.json"
    temp_challenger_model = output_dir / "challenger_r3_n8_g6x6.yml"
    print("[INFO] Training challenger r3_n8_g6x6 LBPH model on La Salle train split...")
    train_challenger_lbph(train_dir, labels_path, temp_challenger_model)

    # 3. Load Model Adapters
    detector = create_face_detector("yunet")
    raw_lbph_baseline = LBPHAdapter(
        model_path=str(PROJECT_ROOT / "models" / "lbph" / "lasalle_clean.yml"),
        labels_path=str(labels_path),
        lbph_config=DEPLOYED_LBPH_CONFIG,
    )
    raw_lbph_challenger = LBPHAdapter(
        model_path=str(temp_challenger_model),
        labels_path=str(labels_path),
        lbph_config=SELECTED_LBPH_CONFIG,
    )
    raw_sface = SFaceAdapter(
        model_path=str(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx"),
        gallery_path=str(PROJECT_ROOT / "models" / "sface" / "gallery.npy"),
    )

    lbph_base = InstrumentedLBPH(raw_lbph_baseline)
    lbph_chal = InstrumentedLBPH(raw_lbph_challenger)
    sface = InstrumentedSFace(raw_sface)

    # 4. Generate identical 246 probe conditions
    all_identities = sorted(p.name for p in test_root.iterdir() if p.is_dir())
    rng = random.Random(seed)
    selected_identities = sorted(rng.sample(all_identities, 6))

    subset_manifest: list[dict[str, str]] = []
    for ident in selected_identities:
        images_in_ident = sorted(p.name for p in (test_root / ident).iterdir() if p.is_file())
        chosen_img = rng.choice(images_in_ident)
        subset_manifest.append(
            {
                "identity": ident,
                "filename": chosen_img,
                "abs_path": str(test_root / ident / chosen_img),
            }
        )

    mods_list, mod_count = get_modification_set("dl41")
    assert mod_count == 41

    probes: list[dict[str, Any]] = []
    for entry in subset_manifest:
        person = entry["identity"]
        fname = entry["filename"]
        img_bgr = cv.imread(entry["abs_path"])
        if img_bgr is None:
            raise RuntimeError(f"Could not read {entry['abs_path']}")

        for mod_name, fn, levels in mods_list:
            level = levels[0]
            rng_mod = stable_rng(seed, person, fname, mod_name, level)
            mod_img_bgr = fn(img_bgr, level, rng_mod)
            probes.append(
                {
                    "identity": person,
                    "filename": fname,
                    "mod_name": mod_name,
                    "level": level,
                    "category": DL41_CATEGORY_MAP.get(mod_name, "unknown"),
                    "tier": DL41_TIER_MAP.get(mod_name, "unknown"),
                    "image_bgr": mod_img_bgr,
                }
            )

    print(f"[INFO] Generated {len(probes)} transformed probe conditions across 6 identities.")

    # 5. Detect samples
    for p in probes:
        img_bgr = p["image_bgr"]
        img_gray = cv.cvtColor(img_bgr, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img_bgr, image_gray=img_gray, assume_cropped=True)
        p["detector_success"] = sample is not None
        p["sample"] = sample

    detector_failures = sum(1 for p in probes if not p["detector_success"])
    print(f"[INFO] Face Detection complete. Failures: {detector_failures} / {len(probes)}")

    # 6. Evaluate all modes across 246 conditions
    records = []
    for idx, p in enumerate(probes):
        person = p["identity"]
        mod_name = p["mod_name"]
        sample = p["sample"]
        det_ok = p["detector_success"]

        row: dict[str, Any] = {
            "idx": idx + 1,
            "identity": person,
            "mod_name": mod_name,
            "detector_success": det_ok,
        }

        if not det_ok or sample is None:
            for mode_key in ["baseline_seq", "arch_early_bypass", "config_seq", "combined_unified", "direct_sface", "lbph_base", "lbph_chal"]:
                row[f"{mode_key}_pred"] = "Unknown"
                row[f"{mode_key}_correct"] = False
                row[f"{mode_key}_accepted"] = False
                row[f"{mode_key}_lbph_calls"] = 0
                row[f"{mode_key}_sface_calls"] = 0
            records.append(row)
            continue

        # Mode 1: Baseline Sequential Cascade (r1_n8_g8x8 + Seq)
        lbph_base.reset_count()
        sface.reset_count()
        r1 = run_sequential_cascade(sample, lbph_base, sface, gate_thresh_baseline, qual_thresh)
        row["baseline_seq_pred"] = r1["pred_name"]
        row["baseline_seq_correct"] = r1["pred_name"] == person
        row["baseline_seq_accepted"] = r1["accepted"]
        row["baseline_seq_lbph_calls"] = lbph_base.call_count
        row["baseline_seq_sface_calls"] = sface.call_count

        # Mode 2: Architecture-Only (r1_n8_g8x8 + Early Bypass)
        lbph_base.reset_count()
        sface.reset_count()
        r2 = run_early_bypass_cascade(sample, lbph_base, sface, gate_thresh_baseline, qual_thresh)
        row["arch_early_bypass_pred"] = r2["pred_name"]
        row["arch_early_bypass_correct"] = r2["pred_name"] == person
        row["arch_early_bypass_accepted"] = r2["accepted"]
        row["arch_early_bypass_lbph_calls"] = lbph_base.call_count
        row["arch_early_bypass_sface_calls"] = sface.call_count

        # Mode 3: Descriptor-Only (r3_n8_g6x6 + Seq)
        lbph_chal.reset_count()
        sface.reset_count()
        r3 = run_sequential_cascade(sample, lbph_chal, sface, gate_thresh_challenger, qual_thresh)
        row["config_seq_pred"] = r3["pred_name"]
        row["config_seq_correct"] = r3["pred_name"] == person
        row["config_seq_accepted"] = r3["accepted"]
        row["config_seq_lbph_calls"] = lbph_chal.call_count
        row["config_seq_sface_calls"] = sface.call_count

        # Mode 4: Combined Unified Cascade (r3_n8_g6x6 + Early Bypass)
        lbph_chal.reset_count()
        sface.reset_count()
        r4 = run_early_bypass_cascade(sample, lbph_chal, sface, gate_thresh_challenger, qual_thresh)
        row["combined_unified_pred"] = r4["pred_name"]
        row["combined_unified_correct"] = r4["pred_name"] == person
        row["combined_unified_accepted"] = r4["accepted"]
        row["combined_unified_lbph_calls"] = lbph_chal.call_count
        row["combined_unified_sface_calls"] = sface.call_count

        # Mode 5: Direct SFace
        sface.reset_count()
        sf_m = sface.score(sample)
        row["direct_sface_pred"] = sf_m.name
        row["direct_sface_correct"] = sf_m.name == person
        row["direct_sface_accepted"] = sf_m.accepted

        # Mode 6: Standalone LBPH Base vs Chal
        lbph_base.reset_count()
        m_base = lbph_base.score(sample)
        row["lbph_base_pred"] = m_base.name
        row["lbph_base_correct"] = (m_base.name == person) and (m_base.distance <= gate_thresh_baseline.tau_accept)

        lbph_chal.reset_count()
        m_chal = lbph_chal.score(sample)
        row["lbph_chal_pred"] = m_chal.name
        row["lbph_chal_correct"] = (m_chal.name == person) and (m_chal.distance <= gate_thresh_challenger.tau_accept)

        # Invariant Assertions
        assert r1["pred_name"] == r2["pred_name"], f"Decision mismatch between Mode 1 and 2 at probe {idx}"
        assert r3["pred_name"] == r4["pred_name"], f"Decision mismatch between Mode 3 and 4 at probe {idx}"

        records.append(row)

    print("[SUCCESS] All functional decisions and parity checks verified!")

    # 7. Randomized Interleaved Latency Benchmarking (1 Warmup + 5 Repeats)
    print("\n[INFO] Starting randomized interleaved timing benchmark (5 repetitions)...")
    valid_samples = [p["sample"] for p in probes if p["detector_success"] and p["sample"] is not None]

    modes_to_time = [
        "baseline_seq",
        "arch_early_bypass",
        "config_seq",
        "combined_unified",
        "direct_sface",
        "lbph_base_only",
        "lbph_chal_only",
    ]

    def execute_timed_mode(m_name: str, s: FaceSample) -> None:
        if m_name == "baseline_seq":
            run_sequential_cascade(s, lbph_base, sface, gate_thresh_baseline, qual_thresh)
        elif m_name == "arch_early_bypass":
            run_early_bypass_cascade(s, lbph_base, sface, gate_thresh_baseline, qual_thresh)
        elif m_name == "config_seq":
            run_sequential_cascade(s, lbph_chal, sface, gate_thresh_challenger, qual_thresh)
        elif m_name == "combined_unified":
            run_early_bypass_cascade(s, lbph_chal, sface, gate_thresh_challenger, qual_thresh)
        elif m_name == "direct_sface":
            sface.score(s)
        elif m_name == "lbph_base_only":
            lbph_base.score(s)
        elif m_name == "lbph_chal_only":
            lbph_chal.score(s)

    # Warmup
    for s in valid_samples:
        for m_name in modes_to_time:
            execute_timed_mode(m_name, s)

    mode_timings: dict[str, list[float]] = {m: [] for m in modes_to_time}
    repeats = 5
    for r in range(repeats):
        for s in valid_samples:
            # Randomize mode order per sample to neutralize cache bias
            shuffled_modes = list(modes_to_time)
            random.shuffle(shuffled_modes)
            for m_name in shuffled_modes:
                t0 = time.perf_counter()
                execute_timed_mode(m_name, s)
                t1 = time.perf_counter()
                mode_timings[m_name].append((t1 - t0) * 1000.0)

    timing_summary = {}
    for m_name, times in mode_timings.items():
        arr = np.array(times)
        timing_summary[m_name] = {
            "mean_ms": float(np.mean(arr)),
            "p50_ms": float(np.median(arr)),
            "p95_ms": float(np.percentile(arr, 95)),
            "std_ms": float(np.std(arr)),
        }

    # 8. Summary Aggregation
    total_conds = len(probes)
    valid_conds = len(valid_samples)
    
    summary = {
        "status": "smoke_test_completed_cleanly",
        "total_probes": total_conds,
        "detector_failures": detector_failures,
        "valid_probes": valid_conds,
        "modes": {
            "baseline_seq": {
                "correct_count": sum(1 for r in records if r["baseline_seq_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["baseline_seq_correct"]) / total_conds,
                "lbph_invocations": sum(r["baseline_seq_lbph_calls"] for r in records),
                "sface_invocations": sum(r["baseline_seq_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["baseline_seq_lbph_calls"] > 0 and r["baseline_seq_sface_calls"] > 0),
                "timing": timing_summary["baseline_seq"],
            },
            "arch_early_bypass": {
                "correct_count": sum(1 for r in records if r["arch_early_bypass_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["arch_early_bypass_correct"]) / total_conds,
                "lbph_invocations": sum(r["arch_early_bypass_lbph_calls"] for r in records),
                "sface_invocations": sum(r["arch_early_bypass_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["arch_early_bypass_lbph_calls"] > 0 and r["arch_early_bypass_sface_calls"] > 0),
                "timing": timing_summary["arch_early_bypass"],
            },
            "config_seq": {
                "correct_count": sum(1 for r in records if r["config_seq_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["config_seq_correct"]) / total_conds,
                "lbph_invocations": sum(r["config_seq_lbph_calls"] for r in records),
                "sface_invocations": sum(r["config_seq_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["config_seq_lbph_calls"] > 0 and r["config_seq_sface_calls"] > 0),
                "timing": timing_summary["config_seq"],
            },
            "combined_unified": {
                "correct_count": sum(1 for r in records if r["combined_unified_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["combined_unified_correct"]) / total_conds,
                "lbph_invocations": sum(r["combined_unified_lbph_calls"] for r in records),
                "sface_invocations": sum(r["combined_unified_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["combined_unified_lbph_calls"] > 0 and r["combined_unified_sface_calls"] > 0),
                "timing": timing_summary["combined_unified"],
            },
            "direct_sface": {
                "correct_count": sum(1 for r in records if r["direct_sface_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["direct_sface_correct"]) / total_conds,
                "timing": timing_summary["direct_sface"],
            },
            "lbph_base_standalone": {
                "correct_count": sum(1 for r in records if r["lbph_base_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["lbph_base_correct"]) / total_conds,
                "timing": timing_summary["lbph_base_only"],
            },
            "lbph_chal_standalone": {
                "correct_count": sum(1 for r in records if r["lbph_chal_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["lbph_chal_correct"]) / total_conds,
                "timing": timing_summary["lbph_chal_only"],
            },
        },
        "deltas_and_synergy": {
            "lbph_calls_avoided": sum(r["baseline_seq_lbph_calls"] for r in records) - sum(r["combined_unified_lbph_calls"] for r in records),
            "lbph_calls_avoided_pct": 100.0 * (sum(r["baseline_seq_lbph_calls"] for r in records) - sum(r["combined_unified_lbph_calls"] for r in records)) / sum(r["baseline_seq_lbph_calls"] for r in records),
            "dual_inferences_cut": sum(1 for r in records if r["baseline_seq_lbph_calls"] > 0 and r["baseline_seq_sface_calls"] > 0) - sum(1 for r in records if r["combined_unified_lbph_calls"] > 0 and r["combined_unified_sface_calls"] > 0),
            "dual_inferences_cut_pct": 100.0 * (sum(1 for r in records if r["baseline_seq_lbph_calls"] > 0 and r["baseline_seq_sface_calls"] > 0) - sum(1 for r in records if r["combined_unified_lbph_calls"] > 0 and r["combined_unified_sface_calls"] > 0)) / sum(1 for r in records if r["baseline_seq_lbph_calls"] > 0 and r["baseline_seq_sface_calls"] > 0),
            "latency_saving_ms": timing_summary["baseline_seq"]["mean_ms"] - timing_summary["combined_unified"]["mean_ms"],
            "latency_saving_pct": 100.0 * (timing_summary["baseline_seq"]["mean_ms"] - timing_summary["combined_unified"]["mean_ms"]) / timing_summary["baseline_seq"]["mean_ms"],
            "template_bytes_reduction_pct": 100.0 * (DEPLOYED_LBPH_CONFIG.descriptor_bytes - SELECTED_LBPH_CONFIG.descriptor_bytes) / DEPLOYED_LBPH_CONFIG.descriptor_bytes,
        },
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[COMPLETE] Wrote full summary to {output_dir / 'summary.json'}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
