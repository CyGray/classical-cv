"""Full Evaluation: Quality-First Early-Bypass Routing on the Full 2,296 La Salle DB1-DL41 Suite.

Evaluates all 56 held-out test images x 41 DL41 transformations = 2,296 conditions.
Modes compared:
  A. Always LBPH
  B. True Direct SFace
  C. Current Sequential LS-Face
  D. Quality-Only Exclusive Router
  E. Quality-First Early-Bypass Cascade

Timing Methodology:
  - 1 Warmup pass
  - 5 Timed repetitions with per-probe mode-order interleaving/randomization to eliminate thermal & order bias.
  - Paired condition records and strict detector failure policy.
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
import time
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.modifications import (
    DL41_CATEGORY_MAP,
    DL41_TIER_MAP,
    get_modification_set,
    stable_rng,
)
from src.classical_faces.detection import create_face_detector
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
from src.sface.recognizer import SFaceMatch


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_git_info() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=PROJECT_ROOT, text=True
        ).strip()
        is_dirty = len(status) > 0
        return {"commit": commit, "dirty": is_dirty, "status_summary": status[:500]}
    except Exception as e:
        return {"commit": "unknown", "dirty": True, "error": str(e)}


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


def run_mode_a_always_lbph(
    sample: FaceSample,
    lbph: InstrumentedLBPH,
    gate_thresh: GateThresholds,
) -> dict[str, Any]:
    match = lbph.score(sample)
    accepted = match.distance <= gate_thresh.tau_accept
    pred_name = match.name if accepted else "Unknown"
    return {
        "pred_name": pred_name,
        "accepted": accepted,
        "lbph_name": match.name,
        "lbph_distance": match.distance,
        "lbph_margin": match.margin,
        "sface_name": None,
        "sface_cosine": None,
        "sface_l2": None,
        "reason": "always_lbph",
        "escalated": False,
    }


def run_mode_b_direct_sface(
    sample: FaceSample,
    sface: InstrumentedSFace,
) -> dict[str, Any]:
    match = sface.score(sample)
    accepted = match.accepted
    pred_name = match.name
    return {
        "pred_name": pred_name,
        "accepted": accepted,
        "lbph_name": None,
        "lbph_distance": None,
        "lbph_margin": None,
        "sface_name": match.name,
        "sface_cosine": match.cosine,
        "sface_l2": match.l2,
        "reason": "direct_sface",
        "escalated": True,
    }


def run_mode_c_sequential_cascade(
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
            "quality": quality,
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
            "quality": quality,
        }


def run_mode_d_quality_only_router(
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
            "reason": "quality_router_sface:" + ",".join(quality.active_flags),
            "escalated": True,
            "quality": quality,
        }
    else:
        lbph_match = lbph.score(sample)
        accepted = lbph_match.distance <= gate_thresh.tau_accept
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
            "reason": "quality_router_lbph_accept" if accepted else "quality_router_lbph_reject",
            "escalated": False,
            "quality": quality,
        }


def run_mode_e_early_bypass_cascade(
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
            "quality": quality,
        }

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
            "quality": quality,
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
            "quality": quality,
        }


def main() -> None:
    output_dir = PROJECT_ROOT / "outputs" / "quality_first_eval_2296_2026-08-16"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load thresholds & models
    thresh_path = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"
    thresh_data = load_thresholds(thresh_path)
    gate_thresh = GateThresholds.from_dict(thresh_data["gate"])
    qual_thresh = QualityThresholds.from_dict(thresh_data["quality"])
    sface_l2_thresh = thresh_data["sface"]["l2_genuine"]
    sface_cos_thresh = thresh_data["sface"]["cosine_genuine"]

    resolved_config = {
        "gate_tau_accept": gate_thresh.tau_accept,
        "gate_tau_reject": gate_thresh.tau_reject,
        "gate_margin_min": gate_thresh.margin_min,
        "quality_tau_blur": qual_thresh.tau_blur,
        "quality_luma_lo": qual_thresh.luma_lo,
        "quality_luma_hi": qual_thresh.luma_hi,
        "quality_tau_noise": qual_thresh.tau_noise,
        "quality_tau_pose": qual_thresh.tau_pose,
        "quality_px_min": qual_thresh.px_min,
        "sface_l2_genuine": sface_l2_thresh,
        "sface_cosine_genuine": sface_cos_thresh,
        "model_hashes": {
            "thresholds_json": sha256_file(thresh_path),
            "lbph_model": sha256_file(PROJECT_ROOT / "models" / "lbph" / "lasalle_clean.yml"),
            "lbph_labels": sha256_file(PROJECT_ROOT / "models" / "lbph" / "labels_lasalle_clean.json"),
            "sface_model": sha256_file(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx"),
            "sface_gallery": sha256_file(PROJECT_ROOT / "models" / "sface" / "gallery.npy"),
            "sface_labels": sha256_file(PROJECT_ROOT / "models" / "sface" / "labels.json"),
            "yunet_detector": sha256_file(PROJECT_ROOT / "models" / "yunet" / "face_detection_yunet_2023mar.onnx"),
        },
        "git": get_git_info(),
        "scope": "Full La Salle DB1-DL41 held-out test evaluation (56 source test images x 41 DL41 transforms = 2,296 conditions)",
        "status": "full_evaluation_run",
    }
    (output_dir / "resolved_configuration.json").write_text(
        json.dumps(resolved_config, indent=2), encoding="utf-8"
    )

    # 2. Collect all 56 source test images
    test_root = PROJECT_ROOT.parent / "data" / "lsdb" / "split" / "test"
    if not test_root.exists():
        test_root = PROJECT_ROOT / "data" / "lsdb" / "split" / "test"
    if not test_root.exists():
        raise FileNotFoundError(f"Test split root not found at {test_root}")

    all_identities = sorted(p.name for p in test_root.iterdir() if p.is_dir())
    source_images: list[dict[str, str]] = []
    for ident in all_identities:
        imgs = sorted(p.name for p in (test_root / ident).iterdir() if p.is_file())
        for img_name in imgs:
            source_images.append({
                "identity": ident,
                "filename": img_name,
                "abs_path": str(test_root / ident / img_name),
            })

    print(f"[INFO] Loaded {len(source_images)} source test images across {len(all_identities)} identities.")
    assert len(source_images) == 56, f"Expected 56 source test images, found {len(source_images)}"

    (output_dir / "source_manifest.json").write_text(
        json.dumps(
            {
                "identities_count": len(all_identities),
                "source_images_count": len(source_images),
                "source_images": source_images,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # 3. Load Models
    detector = create_face_detector("yunet")
    raw_lbph = LBPHAdapter(
        model_path=str(PROJECT_ROOT / "models" / "lbph" / "lasalle_clean.yml"),
        labels_path=str(PROJECT_ROOT / "models" / "lbph" / "labels_lasalle_clean.json"),
        far_anchors=thresh_data.get("lbph_far_anchors"),
    )
    raw_sface = SFaceAdapter(
        model_path=str(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx"),
        gallery_path=str(PROJECT_ROOT / "models" / "sface" / "gallery.npy"),
    )
    lbph = InstrumentedLBPH(raw_lbph)
    sface = InstrumentedSFace(raw_sface)

    # 4. Generate all 2,296 transformed conditions
    mods_list, mod_count = get_modification_set("dl41")
    assert mod_count == 41

    probes: list[dict[str, Any]] = []
    for entry in source_images:
        person = entry["identity"]
        fname = entry["filename"]
        img_bgr = cv.imread(entry["abs_path"])
        if img_bgr is None:
            raise RuntimeError(f"Could not read {entry['abs_path']}")

        for mod_name, fn, levels in mods_list:
            level = levels[0]
            rng_mod = stable_rng(42, person, fname, mod_name, level)
            mod_bgr = fn(img_bgr, level, rng_mod)
            probes.append({
                "identity": person,
                "filename": fname,
                "mod_name": mod_name,
                "level": level,
                "category": DL41_CATEGORY_MAP.get(mod_name, "unknown"),
                "tier": DL41_TIER_MAP.get(mod_name, "unknown"),
                "image_bgr": mod_bgr,
            })

    print(f"[INFO] Generated {len(probes)} transformed conditions ({len(source_images)} x {mod_count}).")
    assert len(probes) == 2296, f"Expected 2296 probes, got {len(probes)}"

    # 5. Face detection on all probes
    print("[INFO] Running YuNet face detection on all 2,296 probes...")
    for p in probes:
        img_bgr = p["image_bgr"]
        img_gray = cv.cvtColor(img_bgr, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img_bgr, image_gray=img_gray, assume_cropped=True)
        p["detector_success"] = sample is not None
        p["sample"] = sample

    detector_failures = sum(1 for p in probes if not p["detector_success"])
    print(f"[INFO] Face detection complete. Detector failures: {detector_failures} / 2296 ({detector_failures/2296*100:.2f}%)")

    # 6. Evaluation of all 5 architectures & invariant assertions
    condition_records: list[dict[str, Any]] = []
    contingency = {
        "quality_clear_lbph_correct": 0,
        "quality_clear_lbph_failure": 0,
        "quality_flagged_lbph_correct": 0,
        "quality_flagged_lbph_failure": 0,
    }

    print("[INFO] Scoring all 2,296 conditions and verifying invariant assertions...")
    for idx, p in enumerate(probes):
        person = p["identity"]
        fname = p["filename"]
        mod_name = p["mod_name"]
        cat = p["category"]
        tier = p["tier"]
        sample = p["sample"]
        det_ok = p["detector_success"]

        row: dict[str, Any] = {
            "condition_idx": idx + 1,
            "identity": person,
            "source_image": fname,
            "transformation": mod_name,
            "transformation_tier": tier,
            "transformation_category": cat,
            "detector_success": det_ok,
        }

        if not det_ok or sample is None:
            for flag in ["blur", "low_light", "noise", "off_pose", "small_face"]:
                row[f"quality_flag_{flag}"] = False
            row["quality_any_flag"] = False
            row["quality_blur_var"] = None
            row["quality_luma_mean"] = None
            row["quality_noise_sigma"] = None
            row["quality_pose_angle"] = None
            row["quality_face_px"] = None

            for mode_key in ["always_lbph", "direct_sface", "seq_cascade", "quality_only", "early_bypass"]:
                row[f"{mode_key}_pred"] = "Unknown"
                row[f"{mode_key}_correct"] = False
                row[f"{mode_key}_accepted"] = False
                row[f"{mode_key}_lbph_invoked"] = False
                row[f"{mode_key}_sface_invoked"] = False

            row["lbph_name"] = None
            row["lbph_distance"] = None
            row["lbph_margin"] = None
            row["sface_name"] = None
            row["sface_cosine"] = None
            row["sface_l2"] = None
            row["seq_cascade_reason"] = "detector_failure"
            row["early_bypass_reason"] = "detector_failure"
            row["early_bypass_routing_path"] = "detector_failure"
            condition_records.append(row)
            continue

        q_rep = compute_quality(
            gray_roi=sample.quality_gray,
            landmarks=sample.landmarks,
            face_px=sample.face_px,
            thresholds=qual_thresh,
        )
        for flag_name, flag_val in q_rep.flags.items():
            row[f"quality_flag_{flag_name}"] = flag_val
        row["quality_any_flag"] = q_rep.any_flag
        row["quality_blur_var"] = round(q_rep.blur_var, 3)
        row["quality_luma_mean"] = round(q_rep.luma_mean, 2)
        row["quality_noise_sigma"] = round(q_rep.noise_sigma, 3)
        row["quality_pose_angle"] = round(q_rep.pose_angle, 2)
        row["quality_face_px"] = q_rep.face_px

        lbph.reset_count()
        raw_lbph_match = lbph.score(sample)
        lbph_standalone_correct = (
            raw_lbph_match.name == person and raw_lbph_match.distance <= gate_thresh.tau_accept
        )
        row["lbph_name"] = raw_lbph_match.name
        row["lbph_distance"] = round(raw_lbph_match.distance, 4)
        row["lbph_margin"] = round(raw_lbph_match.margin, 4)

        if q_rep.any_flag:
            if lbph_standalone_correct:
                contingency["quality_flagged_lbph_correct"] += 1
            else:
                contingency["quality_flagged_lbph_failure"] += 1
        else:
            if lbph_standalone_correct:
                contingency["quality_clear_lbph_correct"] += 1
            else:
                contingency["quality_clear_lbph_failure"] += 1

        sface.reset_count()
        raw_sface_match = sface.score(sample)
        row["sface_name"] = raw_sface_match.name
        row["sface_cosine"] = round(raw_sface_match.cosine, 4)
        row["sface_l2"] = round(raw_sface_match.l2, 4)

        # Mode A: Always LBPH
        lbph.reset_count()
        sface.reset_count()
        res_a = run_mode_a_always_lbph(sample, lbph, gate_thresh)
        row["always_lbph_pred"] = res_a["pred_name"]
        row["always_lbph_accepted"] = res_a["accepted"]
        row["always_lbph_correct"] = res_a["pred_name"] == person
        row["always_lbph_lbph_invoked"] = lbph.call_count > 0
        row["always_lbph_sface_invoked"] = sface.call_count > 0

        # Mode B: Direct SFace
        lbph.reset_count()
        sface.reset_count()
        res_b = run_mode_b_direct_sface(sample, sface)
        row["direct_sface_pred"] = res_b["pred_name"]
        row["direct_sface_accepted"] = res_b["accepted"]
        row["direct_sface_correct"] = res_b["pred_name"] == person
        row["direct_sface_lbph_invoked"] = lbph.call_count > 0
        row["direct_sface_sface_invoked"] = sface.call_count > 0
        assert lbph.call_count == 0, "Direct SFace performed LBPH call!"

        # Mode C: Current Sequential Cascade
        lbph.reset_count()
        sface.reset_count()
        res_c = run_mode_c_sequential_cascade(sample, lbph, sface, gate_thresh, qual_thresh)
        row["seq_cascade_pred"] = res_c["pred_name"]
        row["seq_cascade_accepted"] = res_c["accepted"]
        row["seq_cascade_correct"] = res_c["pred_name"] == person
        row["seq_cascade_reason"] = res_c["reason"]
        row["seq_cascade_escalated"] = res_c["escalated"]
        row["seq_cascade_lbph_invoked"] = lbph.call_count > 0
        row["seq_cascade_sface_invoked"] = sface.call_count > 0

        # Mode D: Quality-Only Router
        lbph.reset_count()
        sface.reset_count()
        res_d = run_mode_d_quality_only_router(sample, lbph, sface, gate_thresh, qual_thresh)
        row["quality_only_pred"] = res_d["pred_name"]
        row["quality_only_accepted"] = res_d["accepted"]
        row["quality_only_correct"] = res_d["pred_name"] == person
        row["quality_only_reason"] = res_d["reason"]
        row["quality_only_lbph_invoked"] = lbph.call_count > 0
        row["quality_only_sface_invoked"] = sface.call_count > 0

        # Mode E: Quality-First Early Bypass
        lbph.reset_count()
        sface.reset_count()
        res_e = run_mode_e_early_bypass_cascade(sample, lbph, sface, gate_thresh, qual_thresh)
        row["early_bypass_pred"] = res_e["pred_name"]
        row["early_bypass_accepted"] = res_e["accepted"]
        row["early_bypass_correct"] = res_e["pred_name"] == person
        row["early_bypass_reason"] = res_e["reason"]
        row["early_bypass_escalated"] = res_e["escalated"]
        row["early_bypass_routing_path"] = res_e["routing_path"]
        row["early_bypass_lbph_invoked"] = lbph.call_count > 0
        row["early_bypass_sface_invoked"] = sface.call_count > 0

        # Invariant Assertions
        assert res_c["pred_name"] == res_e["pred_name"], f"Decision mismatch at row {idx+1}"
        assert res_c["accepted"] == res_e["accepted"], f"Accept mismatch at row {idx+1}"
        assert (res_c["pred_name"] == person) == (res_e["pred_name"] == person), f"Correctness mismatch at row {idx+1}"
        assert (sface.call_count > 0) == (row["seq_cascade_sface_invoked"]), f"SFace invocation mismatch at row {idx+1}"
        if q_rep.any_flag:
            assert not row["early_bypass_lbph_invoked"], f"LBPH invoked on quality trigger at row {idx+1}"
        if row["early_bypass_lbph_invoked"] and row["early_bypass_sface_invoked"]:
            assert not q_rep.any_flag, f"Quality flag present in dual inference at row {idx+1}"

        condition_records.append(row)

    print("[SUCCESS] All automated invariant assertions passed on all 2,296 conditions!")

    # 7. Interleaved Timing Benchmark
    print("\n[INFO] Starting Interleaved Timing Benchmark on all 2,296 conditions (1 warmup + 5 timed reps)...")
    timing_repeats = 5

    def run_direct_sface(s: FaceSample) -> float:
        t0 = time.perf_counter()
        _ = sface.score(s)
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_always_lbph(s: FaceSample) -> float:
        t0 = time.perf_counter()
        lm = lbph.score(s)
        _ = lm.distance <= gate_thresh.tau_accept
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_seq_cascade(s: FaceSample) -> float:
        t0 = time.perf_counter()
        lm = lbph.score(s)
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        gate = decide_escalation(lbph_distance=lm.distance, lbph_margin=lm.margin, quality=q, thresholds=gate_thresh)
        if gate.escalate:
            _ = sface.score(s)
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_quality_only(s: FaceSample) -> float:
        t0 = time.perf_counter()
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        if q.any_flag:
            _ = sface.score(s)
        else:
            lm = lbph.score(s)
            _ = lm.distance <= gate_thresh.tau_accept
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def run_early_bypass(s: FaceSample) -> float:
        t0 = time.perf_counter()
        q = compute_quality(gray_roi=s.quality_gray, landmarks=s.landmarks, face_px=s.face_px, thresholds=qual_thresh)
        if q.any_flag:
            _ = sface.score(s)
        else:
            lm = lbph.score(s)
            is_amb = gate_thresh.tau_accept < lm.distance < gate_thresh.tau_reject
            is_low_m = lm.margin < gate_thresh.margin_min
            if is_amb or is_low_m:
                _ = sface.score(s)
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    detected_probes = [p for p in probes if p["detector_success"]]

    # Warmup
    for p in detected_probes:
        s = p["sample"]
        run_always_lbph(s)
        run_direct_sface(s)
        run_seq_cascade(s)
        run_quality_only(s)
        run_early_bypass(s)

    lat_accumulator: dict[str, list[list[float]]] = {
        m: [[] for _ in probes]
        for m in ["always_lbph", "direct_sface", "seq_cascade", "quality_only", "early_bypass"]
    }

    rng_timing = random.Random(42)
    modes_to_test = ["always_lbph", "direct_sface", "seq_cascade", "quality_only", "early_bypass"]

    for rep in range(timing_repeats):
        indices = list(range(len(probes)))
        rng_timing.shuffle(indices)

        for i in indices:
            p = probes[i]
            if not p["detector_success"] or p["sample"] is None:
                for m in modes_to_test:
                    lat_accumulator[m][i].append(0.0)
                continue

            s = p["sample"]
            mode_order = list(modes_to_test)
            rng_timing.shuffle(mode_order)

            for m in mode_order:
                if m == "always_lbph":
                    lat_accumulator[m][i].append(run_always_lbph(s))
                elif m == "direct_sface":
                    lat_accumulator[m][i].append(run_direct_sface(s))
                elif m == "seq_cascade":
                    lat_accumulator[m][i].append(run_seq_cascade(s))
                elif m == "quality_only":
                    lat_accumulator[m][i].append(run_quality_only(s))
                elif m == "early_bypass":
                    lat_accumulator[m][i].append(run_early_bypass(s))

    # Mean latencies per condition
    for m in modes_to_test:
        for i in range(len(probes)):
            mean_val = float(np.mean(lat_accumulator[m][i]))
            condition_records[i][f"latency_{m}_ms"] = round(mean_val, 3)

    # 8. Compute Summary Metrics
    total_conditions = len(probes)

    def compute_mode_metrics(mode_key: str) -> dict[str, Any]:
        correct_count = sum(1 for r in condition_records if r[f"{mode_key}_correct"])
        accepted_wrong = sum(
            1
            for r in condition_records
            if r[f"{mode_key}_accepted"] and not r[f"{mode_key}_correct"] and r[f"{mode_key}_pred"] != "Unknown"
        )
        rejected = sum(1 for r in condition_records if r[f"{mode_key}_pred"] == "Unknown")
        lbph_calls = sum(1 for r in condition_records if r[f"{mode_key}_lbph_invoked"])
        sface_calls = sum(1 for r in condition_records if r[f"{mode_key}_sface_invoked"])
        dual_calls = sum(
            1
            for r in condition_records
            if r[f"{mode_key}_lbph_invoked"] and r[f"{mode_key}_sface_invoked"]
        )

        lats = [r[f"latency_{mode_key}_ms"] for r in condition_records if r["detector_success"]]
        mean_lat = float(np.mean(lats)) if lats else 0.0
        p50_lat = float(np.median(lats)) if lats else 0.0
        p95_lat = float(np.percentile(lats, 95)) if lats else 0.0

        return {
            "correct_acceptance_count": correct_count,
            "correct_acceptance_rate_pct": round(correct_count / total_conditions * 100.0, 2),
            "accepted_wrong_identity_count": accepted_wrong,
            "rejected_count": rejected,
            "lbph_invocations": lbph_calls,
            "lbph_invocation_rate_pct": round(lbph_calls / total_conditions * 100.0, 2),
            "sface_invocations": sface_calls,
            "sface_invocation_rate_pct": round(sface_calls / total_conditions * 100.0, 2),
            "dual_inferences": dual_calls,
            "dual_inference_rate_pct": round(dual_calls / total_conditions * 100.0, 2),
            "latency_mean_ms": round(mean_lat, 3),
            "latency_p50_ms": round(p50_lat, 3),
            "latency_p95_ms": round(p95_lat, 3),
        }

    summary_metrics: dict[str, Any] = {
        "status": "full_evaluation_run",
        "total_transformed_conditions": total_conditions,
        "detector_failures": detector_failures,
        "detector_failure_rate_pct": round(detector_failures / total_conditions * 100.0, 2),
        "modes": {
            "always_lbph": compute_mode_metrics("always_lbph"),
            "direct_sface": compute_mode_metrics("direct_sface"),
            "seq_cascade": compute_mode_metrics("seq_cascade"),
            "quality_only": compute_mode_metrics("quality_only"),
            "early_bypass": compute_mode_metrics("early_bypass"),
        },
    }

    final_mismatches = sum(
        1 for r in condition_records if r["seq_cascade_pred"] != r["early_bypass_pred"]
    )
    routing_mismatches = sum(
        1
        for r in condition_records
        if r["seq_cascade_sface_invoked"] != r["early_bypass_sface_invoked"]
    )
    lbph_calls_seq = summary_metrics["modes"]["seq_cascade"]["lbph_invocations"]
    lbph_calls_eb = summary_metrics["modes"]["early_bypass"]["lbph_invocations"]
    lbph_calls_avoided = lbph_calls_seq - lbph_calls_eb
    pct_lbph_avoided = round(lbph_calls_avoided / total_conditions * 100.0, 2)

    seq_mean_lat = summary_metrics["modes"]["seq_cascade"]["latency_mean_ms"]
    eb_mean_lat = summary_metrics["modes"]["early_bypass"]["latency_mean_ms"]
    latency_saving_ms = round(seq_mean_lat - eb_mean_lat, 3)
    latency_saving_pct = round((latency_saving_ms / seq_mean_lat) * 100.0, 2)

    routing_breakdown = {
        "quality_triggered_sface": sum(
            1 for r in condition_records if r.get("early_bypass_routing_path") == "quality_triggered_sface"
        ),
        "quality_clear_lbph_terminal": sum(
            1 for r in condition_records if r.get("early_bypass_routing_path") == "quality_clear_lbph_terminal"
        ),
        "quality_clear_dual_sface": sum(
            1 for r in condition_records if r.get("early_bypass_routing_path") == "quality_clear_dual_sface"
        ),
        "detector_failure": sum(
            1 for r in condition_records if r.get("early_bypass_routing_path") == "detector_failure"
        ),
    }

    summary_metrics["early_bypass_equivalence"] = {
        "final_decision_mismatches": final_mismatches,
        "sface_routing_mismatches": routing_mismatches,
        "lbph_calls_seq_cascade": lbph_calls_seq,
        "lbph_calls_early_bypass": lbph_calls_eb,
        "lbph_calls_avoided": lbph_calls_avoided,
        "lbph_calls_avoided_pct_of_all_inputs": pct_lbph_avoided,
        "latency_reduction_ms": latency_saving_ms,
        "latency_reduction_pct": latency_saving_pct,
        "routing_breakdown": routing_breakdown,
    }

    qc_lc = contingency["quality_clear_lbph_correct"]
    qc_lf = contingency["quality_clear_lbph_failure"]
    qf_lc = contingency["quality_flagged_lbph_correct"]
    qf_lf = contingency["quality_flagged_lbph_failure"]

    lbph_failures_total = qf_lf + qc_lf
    lbph_correct_total = qf_lc + qc_lc

    recall_lbph_failures = (
        round(qf_lf / lbph_failures_total * 100.0, 2) if lbph_failures_total else 0.0
    )
    unnecessary_flags_on_correct = (
        round(qf_lc / lbph_correct_total * 100.0, 2) if lbph_correct_total else 0.0
    )

    summary_metrics["quality_diagnostic"] = {
        "contingency_table": {
            "quality_clear_lbph_correct": qc_lc,
            "quality_clear_lbph_failure": qc_lf,
            "quality_flagged_lbph_correct": qf_lc,
            "quality_flagged_lbph_failure": qf_lf,
        },
        "total_lbph_failures": lbph_failures_total,
        "total_lbph_correct": lbph_correct_total,
        "recall_of_lbph_failures_by_quality_flags_pct": recall_lbph_failures,
        "unnecessary_quality_flags_on_lbph_correct_pct": unnecessary_flags_on_correct,
    }

    # Branch Latency Breakdown
    b1_lats = [r["latency_early_bypass_ms"] for r in condition_records if r.get("early_bypass_routing_path") == "quality_triggered_sface"]
    b2_lats = [r["latency_early_bypass_ms"] for r in condition_records if r.get("early_bypass_routing_path") == "quality_clear_lbph_terminal"]
    b3_lats = [r["latency_early_bypass_ms"] for r in condition_records if r.get("early_bypass_routing_path") == "quality_clear_dual_sface"]

    summary_metrics["branch_latency_breakdown"] = {
        "branch_1_quality_triggered_sface": {
            "count": len(b1_lats),
            "mean_ms": round(float(np.mean(b1_lats)), 3) if b1_lats else 0.0,
            "p50_ms": round(float(np.median(b1_lats)), 3) if b1_lats else 0.0,
            "p95_ms": round(float(np.percentile(b1_lats, 95)), 3) if b1_lats else 0.0,
        },
        "branch_2_quality_clear_lbph_terminal": {
            "count": len(b2_lats),
            "mean_ms": round(float(np.mean(b2_lats)), 3) if b2_lats else 0.0,
            "p50_ms": round(float(np.median(b2_lats)), 3) if b2_lats else 0.0,
            "p95_ms": round(float(np.percentile(b2_lats, 95)), 3) if b2_lats else 0.0,
        },
        "branch_3_quality_clear_dual_sface": {
            "count": len(b3_lats),
            "mean_ms": round(float(np.mean(b3_lats)), 3) if b3_lats else 0.0,
            "p50_ms": round(float(np.median(b3_lats)), 3) if b3_lats else 0.0,
            "p95_ms": round(float(np.percentile(b3_lats, 95)), 3) if b3_lats else 0.0,
        },
    }

    (output_dir / "summary.json").write_text(json.dumps(summary_metrics, indent=2), encoding="utf-8")

    # 9. Write Per-Condition CSV
    csv_fields = [
        "condition_idx",
        "identity",
        "source_image",
        "transformation",
        "transformation_tier",
        "transformation_category",
        "detector_success",
        "quality_flag_blur",
        "quality_flag_low_light",
        "quality_flag_noise",
        "quality_flag_off_pose",
        "quality_flag_small_face",
        "quality_any_flag",
        "quality_blur_var",
        "quality_luma_mean",
        "quality_noise_sigma",
        "quality_pose_angle",
        "quality_face_px",
        "lbph_name",
        "lbph_distance",
        "lbph_margin",
        "sface_name",
        "sface_cosine",
        "sface_l2",
        "always_lbph_pred",
        "always_lbph_correct",
        "direct_sface_pred",
        "direct_sface_correct",
        "seq_cascade_pred",
        "seq_cascade_correct",
        "seq_cascade_reason",
        "seq_cascade_sface_invoked",
        "quality_only_pred",
        "quality_only_correct",
        "quality_only_reason",
        "early_bypass_pred",
        "early_bypass_correct",
        "early_bypass_reason",
        "early_bypass_routing_path",
        "early_bypass_lbph_invoked",
        "early_bypass_sface_invoked",
        "latency_always_lbph_ms",
        "latency_direct_sface_ms",
        "latency_seq_cascade_ms",
        "latency_quality_only_ms",
        "latency_early_bypass_ms",
    ]
    with (output_dir / "per_condition_results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in condition_records:
            row_dict = {k: r.get(k) for k in csv_fields}
            writer.writerow(row_dict)

    # 10. Write Markdown Report
    report_md = f"""# Full Evaluation Report: Quality-First Early-Bypass Routing (La Salle DB1-DL41)

> **Scope: Full 2,296 Transformed Conditions (56 held-out test images x 41 DL41 transforms)**  
> **Timing Protocol**: 1 warmup pass + 5 timed repetitions with per-probe randomized execution order.

## 1. Executive Summary & Equivalence Confirmation

- **Total Transformed Conditions**: `{total_conditions}`
- **YuNet Face Detector Failures**: `{detector_failures}` ({summary_metrics['detector_failure_rate_pct']}%)
- **Invariant Assertions**:
  - Final decision mismatches between Sequential Cascade & Early-Bypass: **0 / 2,296** (100.00% exact match)
  - SFace routing mismatches between Sequential Cascade & Early-Bypass: **0 / 2,296** (100.00% exact match)
  - LBPH calls eliminated by early bypass: **{lbph_calls_avoided} / 2,296** ({pct_lbph_avoided}%)

## 2. Accuracy Comparison

| Mode | Correct Acceptance (TPIR) | Correct Rate (%) | SFace Invocations | LBPH Invocations | Dual Inferences |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Always LBPH** | {summary_metrics['modes']['always_lbph']['correct_acceptance_count']} / {total_conditions} | {summary_metrics['modes']['always_lbph']['correct_acceptance_rate_pct']}% | 0 (0.0%) | {summary_metrics['modes']['always_lbph']['lbph_invocations']} ({summary_metrics['modes']['always_lbph']['lbph_invocation_rate_pct']}%) | 0 (0.0%) |
| **Direct SFace** | {summary_metrics['modes']['direct_sface']['correct_acceptance_count']} / {total_conditions} | {summary_metrics['modes']['direct_sface']['correct_acceptance_rate_pct']}% | {summary_metrics['modes']['direct_sface']['sface_invocations']} ({summary_metrics['modes']['direct_sface']['sface_invocation_rate_pct']}%) | 0 (0.0%) | 0 (0.0%) |
| **Current Cascade (Seq)** | {summary_metrics['modes']['seq_cascade']['correct_acceptance_count']} / {total_conditions} | {summary_metrics['modes']['seq_cascade']['correct_acceptance_rate_pct']}% | {summary_metrics['modes']['seq_cascade']['sface_invocations']} ({summary_metrics['modes']['seq_cascade']['sface_invocation_rate_pct']}%) | {summary_metrics['modes']['seq_cascade']['lbph_invocations']} ({summary_metrics['modes']['seq_cascade']['lbph_invocation_rate_pct']}%) | {summary_metrics['modes']['seq_cascade']['dual_inferences']} ({summary_metrics['modes']['seq_cascade']['dual_inference_rate_pct']}%) |
| **Quality-Only Router** | {summary_metrics['modes']['quality_only']['correct_acceptance_count']} / {total_conditions} | {summary_metrics['modes']['quality_only']['correct_acceptance_rate_pct']}% | {summary_metrics['modes']['quality_only']['sface_invocations']} ({summary_metrics['modes']['quality_only']['sface_invocation_rate_pct']}%) | {summary_metrics['modes']['quality_only']['lbph_invocations']} ({summary_metrics['modes']['quality_only']['lbph_invocation_rate_pct']}%) | 0 (0.0%) |
| **Quality-First Early Bypass** | {summary_metrics['modes']['early_bypass']['correct_acceptance_count']} / {total_conditions} | {summary_metrics['modes']['early_bypass']['correct_acceptance_rate_pct']}% | {summary_metrics['modes']['early_bypass']['sface_invocations']} ({summary_metrics['modes']['early_bypass']['sface_invocation_rate_pct']}%) | {summary_metrics['modes']['early_bypass']['lbph_invocations']} ({summary_metrics['modes']['early_bypass']['lbph_invocation_rate_pct']}%) | {summary_metrics['modes']['early_bypass']['dual_inferences']} ({summary_metrics['modes']['early_bypass']['dual_inference_rate_pct']}%) |

## 3. Recognition-Stage Latency (Excluding Face Detection)

| Mode | Mean Latency (ms) | Median / p50 (ms) | p95 (ms) |
| :--- | :--- | :--- | :--- |
| **Always LBPH** | {summary_metrics['modes']['always_lbph']['latency_mean_ms']:.3f} ms | {summary_metrics['modes']['always_lbph']['latency_p50_ms']:.3f} ms | {summary_metrics['modes']['always_lbph']['latency_p95_ms']:.3f} ms |
| **Direct SFace** | {summary_metrics['modes']['direct_sface']['latency_mean_ms']:.3f} ms | {summary_metrics['modes']['direct_sface']['latency_p50_ms']:.3f} ms | {summary_metrics['modes']['direct_sface']['latency_p95_ms']:.3f} ms |
| **Current Cascade (Seq)** | {summary_metrics['modes']['seq_cascade']['latency_mean_ms']:.3f} ms | {summary_metrics['modes']['seq_cascade']['latency_p50_ms']:.3f} ms | {summary_metrics['modes']['seq_cascade']['latency_p95_ms']:.3f} ms |
| **Quality-Only Router** | {summary_metrics['modes']['quality_only']['latency_mean_ms']:.3f} ms | {summary_metrics['modes']['quality_only']['latency_p50_ms']:.3f} ms | {summary_metrics['modes']['quality_only']['latency_p95_ms']:.3f} ms |
| **Quality-First Early Bypass** | {summary_metrics['modes']['early_bypass']['latency_mean_ms']:.3f} ms | {summary_metrics['modes']['early_bypass']['latency_p50_ms']:.3f} ms | {summary_metrics['modes']['early_bypass']['latency_p95_ms']:.3f} ms |

### Latency Savings:
- **Mean Latency Reduction**: `{latency_saving_ms:.3f} ms` ({latency_saving_pct}% faster)
- **LBPH Invocations Avoided**: `{lbph_calls_avoided} / 2,296` ({pct_lbph_avoided}%)

### Branch Latency Breakdown (Early Bypass):
- **Branch 1: Quality-Triggered -> SFace**: `{summary_metrics['branch_latency_breakdown']['branch_1_quality_triggered_sface']['count']}` conditions ({summary_metrics['branch_latency_breakdown']['branch_1_quality_triggered_sface']['mean_ms']} ms mean, {summary_metrics['branch_latency_breakdown']['branch_1_quality_triggered_sface']['p50_ms']} ms p50)
- **Branch 2: Quality-Clear -> LBPH Terminal**: `{summary_metrics['branch_latency_breakdown']['branch_2_quality_clear_lbph_terminal']['count']}` conditions ({summary_metrics['branch_latency_breakdown']['branch_2_quality_clear_lbph_terminal']['mean_ms']} ms mean, {summary_metrics['branch_latency_breakdown']['branch_2_quality_clear_lbph_terminal']['p50_ms']} ms p50)
- **Branch 3: Quality-Clear -> Dual (LBPH + SFace)**: `{summary_metrics['branch_latency_breakdown']['branch_3_quality_clear_dual_sface']['count']}` conditions ({summary_metrics['branch_latency_breakdown']['branch_3_quality_clear_dual_sface']['mean_ms']} ms mean, {summary_metrics['branch_latency_breakdown']['branch_3_quality_clear_dual_sface']['p50_ms']} ms p50)

## 4. Quality Diagnostic Contingency Table

```text
                     LBPH Correct    LBPH Failure    Total
Quality Clear        {qc_lc:<15} {qc_lf:<15} {qc_lc + qc_lf}
Quality Flagged      {qf_lc:<15} {qf_lf:<15} {qf_lc + qf_lf}
Total                {lbph_correct_total:<15} {lbph_failures_total:<15} {total_conditions - detector_failures}
```

- **Recall of LBPH Failures by Quality Flags**: `{recall_lbph_failures}%` ({qf_lf} / {lbph_failures_total})
- **False Alarm (Unnecessary Quality Flag on LBPH Correct)**: `{unnecessary_flags_on_correct}%` ({qf_lc} / {lbph_correct_total})
"""
    (output_dir / "REPORT.md").write_text(report_md, encoding="utf-8")
    print(f"\n[COMPLETE] Full 2,296 evaluation complete. Outputs saved to {output_dir}")


if __name__ == "__main__":
    main()
