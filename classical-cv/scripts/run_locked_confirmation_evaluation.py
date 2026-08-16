"""Locked Confirmation Evaluation: Combined Optimized Cascade vs Baselines on 1,804 Conditions.

Evaluates:
  Mode 1: Previous Baseline Sequential Cascade (r1_n8_g8x8 + Sequential)
  Mode 2: Architecture-Only Early Bypass (r1_n8_g8x8 + Early Bypass)
  Mode 3: Descriptor-Only Challenger Sequential (r3_n8_g6x6 + Sequential)
  Mode 4: Combined Optimized Cascade (r3_n8_g6x6 + Early Bypass) [PRIMARY]
  Mode 5: True Direct SFace [Standalone DL Reference]
  Mode 6: Standalone Challenger LBPH (r3_n8_g6x6)

Dataset: 22 locked confirmation identities x 2 source test images x 41 DL41 transforms = 1,804 conditions.
Timing: Intel Core i5-12450H CPU, 1 full warm-up pass + 5 randomized/interleaved repetitions per probe.
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
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
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
        return {"commit": commit, "dirty": len(status) > 0, "status_summary": status[:500]}
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


def train_lbph_model(train_dir: Path, labels_path: Path, config, output_path: Path) -> None:
    with open(labels_path, "r", encoding="utf-8") as f:
        labels_map = json.load(f)
    faces = []
    labels = []
    for person_name, label_id in sorted(labels_map.items()):
        pdir = train_dir / person_name
        for img_path in sorted(pdir.glob("*.jpg")):
            img = cv.imread(str(img_path), cv.IMREAD_GRAYSCALE)
            if img is not None:
                norm = normalize_face(img, img_size=IMG_SIZE, equalization="tan-triggs")
                faces.append(norm)
                labels.append(int(label_id))

    rec = create_lbph_recognizer(config)
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


def bootstrap_ci_mean(data: np.ndarray, n_boot: int = 2000, ci: float = 95.0, seed: int = 42) -> tuple[float, float]:
    rng = np.random.RandomState(seed)
    boot_means = np.empty(n_boot)
    n = len(data)
    for i in range(n_boot):
        sample = rng.choice(data, size=n, replace=True)
        boot_means[i] = np.mean(sample)
    low_pct = (100.0 - ci) / 2.0
    high_pct = 100.0 - low_pct
    return float(np.percentile(boot_means, low_pct)), float(np.percentile(boot_means, high_pct))


def main() -> None:
    seed = 20260816
    output_dir = PROJECT_ROOT / "outputs" / "provenance_reruns" / "challenger_early_bypass_confirmation_2026-08-16"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print(" LOCKED CONFIRMATION EVALUATION: COMBINED OPTIMIZED CASCADE (22 IDENTITIES)    ")
    print("================================================================================")

    # 1. Resolve & Freeze Configuration
    thresh_path = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"
    thresh_data = load_thresholds(thresh_path)
    gate_thresh_baseline = GateThresholds.from_dict(thresh_data["gate"])
    qual_thresh = QualityThresholds.from_dict(thresh_data["quality"])

    # Challenger configuration (frozen from LFW dev calibration)
    gate_thresh_challenger = GateThresholds(
        tau_accept=52.372394898355424,
        tau_reject=140.13,  # Permissive reject policy (preserves genuine SFace escalation)
        margin_min=0.05,    # Scale-free relative margin
    )

    resolved_config = {
        "status": "locked_confirmation_candidate",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_descriptor": {
            "id": DEPLOYED_LBPH_CONFIG.id,
            "radius": DEPLOYED_LBPH_CONFIG.radius,
            "neighbors": DEPLOYED_LBPH_CONFIG.neighbors,
            "grid_x": DEPLOYED_LBPH_CONFIG.grid_x,
            "grid_y": DEPLOYED_LBPH_CONFIG.grid_y,
            "descriptor_bytes": DEPLOYED_LBPH_CONFIG.descriptor_bytes,
            "tau_accept": gate_thresh_baseline.tau_accept,
            "tau_reject": gate_thresh_baseline.tau_reject,
            "margin_min": gate_thresh_baseline.margin_min,
        },
        "challenger_descriptor": {
            "id": SELECTED_LBPH_CONFIG.id,
            "radius": SELECTED_LBPH_CONFIG.radius,
            "neighbors": SELECTED_LBPH_CONFIG.neighbors,
            "grid_x": SELECTED_LBPH_CONFIG.grid_x,
            "grid_y": SELECTED_LBPH_CONFIG.grid_y,
            "descriptor_bytes": SELECTED_LBPH_CONFIG.descriptor_bytes,
            "tau_accept": gate_thresh_challenger.tau_accept,
            "tau_reject": gate_thresh_challenger.tau_reject,
            "margin_min": gate_thresh_challenger.margin_min,
            "tau_accept_provenance": "LFW development split (2,875 identities, 4,131,375 pairs, 10 ppm target FAR, realized FAR 9.924 ppm)",
            "tau_reject_provenance": "Permissive reject policy (inherited 140.13 > genuine range; ensures SFace escalation on difficult genuine probes)",
            "margin_min_provenance": "Scale-free relative top1-top2 distance gap 0.05",
        },
        "quality_thresholds": qual_thresh.to_dict(),
        "sface": {
            "l2_genuine": thresh_data["sface"]["l2_genuine"],
            "cosine_genuine": thresh_data["sface"]["cosine_genuine"],
        },
        "model_hashes": {
            "thresholds_json": sha256_file(thresh_path),
            "lbph_baseline_model": sha256_file(PROJECT_ROOT / "models" / "lbph" / "lasalle_clean.yml"),
            "lbph_labels": sha256_file(PROJECT_ROOT / "models" / "lbph" / "labels_lasalle_clean.json"),
            "sface_model": sha256_file(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx"),
            "sface_gallery": sha256_file(PROJECT_ROOT / "models" / "sface" / "gallery.npy"),
            "sface_labels": sha256_file(PROJECT_ROOT / "models" / "sface" / "labels.json"),
            "yunet_detector": sha256_file(PROJECT_ROOT / "models" / "yunet" / "face_detection_yunet_2023mar.onnx"),
        },
        "git": get_git_info(),
        "preprocessing_contract": "100x100 grayscale Tan-Triggs (gamma=0.2, sigma0=1.0, sigma1=2.0, alpha=0.1, tau=10.0)",
        "modifications_contract": "DL41 41-transformation set, corrected BGR-first generation",
    }
    (output_dir / "resolved_configuration.json").write_text(
        json.dumps(resolved_config, indent=2), encoding="utf-8"
    )

    # 2. Setup Train / Test Split
    train_dir = PROJECT_ROOT.parent / "data" / "lsdb" / "split" / "train"
    if not train_dir.exists():
        train_dir = PROJECT_ROOT / "data" / "lsdb" / "split" / "train"
    test_root = PROJECT_ROOT.parent / "data" / "lsdb" / "split" / "test"
    if not test_root.exists():
        test_root = PROJECT_ROOT / "data" / "lsdb" / "split" / "test"

    labels_path = PROJECT_ROOT / "models" / "lbph" / "labels_lasalle_clean.json"
    temp_challenger_model = output_dir / "challenger_r3_n8_g6x6.yml"
    print("[INFO] Training challenger r3_n8_g6x6 LBPH model on La Salle train split...")
    train_lbph_model(train_dir, labels_path, SELECTED_LBPH_CONFIG, temp_challenger_model)

    # 3. Build Locked Confirmation Manifest (22 Identities x 2 Source Images x 41 Transforms = 1,804 Conditions)
    smoke_identities = {
        "John_Andrei_Gayona",
        "Joseph_Andrew_Ong",
        "Julian_Diego_Mapa",
        "Kenlie_John_Maghari",
        "Kyle_Yuan_Uy",
        "Yuan_Paulo_Sebastian_Belen",
    }

    all_identities = sorted(p.name for p in test_root.iterdir() if p.is_dir())
    confirmation_identities = [ident for ident in all_identities if ident not in smoke_identities]
    assert len(confirmation_identities) == 22, f"Expected 22 confirmation identities, got {len(confirmation_identities)}"

    mods_list, mod_count = get_modification_set("dl41")
    assert mod_count == 41

    locked_manifest: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []

    # Manifest generation
    for ident in confirmation_identities:
        imgs = sorted(p.name for p in (test_root / ident).iterdir() if p.is_file())
        assert len(imgs) == 2, f"Identity {ident} has {len(imgs)} images, expected 2"
        for fname in imgs:
            img_path = test_root / ident / fname
            img_bgr = cv.imread(str(img_path))
            if img_bgr is None:
                raise RuntimeError(f"Could not read {img_path}")

            # Manifest entry for source image
            locked_manifest.append(
                {
                    "identity": ident,
                    "filename": fname,
                    "abs_path": str(img_path),
                    "sha256": sha256_file(img_path),
                }
            )

            # Generate 41 DL41 transformed conditions
            for mod_name, fn, levels in mods_list:
                level = levels[0]
                rng_mod = stable_rng(seed, ident, fname, mod_name, level)
                mod_img_bgr = fn(img_bgr, level, rng_mod)
                probes.append(
                    {
                        "identity": ident,
                        "filename": fname,
                        "mod_name": mod_name,
                        "level": level,
                        "category": DL41_CATEGORY_MAP.get(mod_name, "unknown"),
                        "tier": DL41_TIER_MAP.get(mod_name, "unknown"),
                        "image_bgr": mod_img_bgr,
                    }
                )

    assert len(probes) == 1804, f"Expected 1,804 conditions, got {len(probes)}"
    (output_dir / "locked_manifest.json").write_text(
        json.dumps(
            {
                "seed": seed,
                "confirmation_identities_count": len(confirmation_identities),
                "confirmation_identities": confirmation_identities,
                "source_images_count": len(locked_manifest),
                "total_probe_conditions": len(probes),
                "source_manifest": locked_manifest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[INFO] Successfully locked manifest with {len(probes)} unique conditions across 22 identities.")

    # 4. Load Models & Adapters
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

    # 5. Face Detection Pass
    print("[INFO] Running face detection pass on all 1,804 probes...")
    for p in probes:
        img_bgr = p["image_bgr"]
        img_gray = cv.cvtColor(img_bgr, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img_bgr, image_gray=img_gray, assume_cropped=True)
        p["detector_success"] = sample is not None
        p["sample"] = sample

    detector_failures = sum(1 for p in probes if not p["detector_success"])
    valid_probes = [p for p in probes if p["detector_success"] and p["sample"] is not None]
    print(f"[INFO] Face detection completed. Detector failures: {detector_failures} / {len(probes)} ({100.0*detector_failures/len(probes):.2f}%)")

    # 6. Evaluate all 6 Systems on the 1,804 conditions
    records: list[dict[str, Any]] = []

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
            "tier": tier,
            "category": cat,
            "detector_success": det_ok,
        }

        if not det_ok or sample is None:
            for sys_key in ["baseline_seq", "arch_early_bypass", "config_seq", "combined_unified", "direct_sface", "challenger_lbph"]:
                row[f"{sys_key}_pred"] = "Unknown"
                row[f"{sys_key}_correct"] = False
                row[f"{sys_key}_accepted"] = False
                row[f"{sys_key}_lbph_calls"] = 0
                row[f"{sys_key}_sface_calls"] = 0
                row[f"{sys_key}_dual"] = False
            row["combined_routing_path"] = "detector_failure"
            row["challenger_lbph_distance"] = None
            row["challenger_lbph_margin"] = None
            records.append(row)
            continue

        # Mode 1: Baseline Sequential Cascade (r1_n8_g8x8 + Seq)
        lbph_base.reset_count()
        sface.reset_count()
        m1 = run_sequential_cascade(sample, lbph_base, sface, gate_thresh_baseline, qual_thresh)
        row["baseline_seq_pred"] = m1["pred_name"]
        row["baseline_seq_correct"] = m1["pred_name"] == person
        row["baseline_seq_accepted"] = m1["accepted"]
        row["baseline_seq_lbph_calls"] = lbph_base.call_count
        row["baseline_seq_sface_calls"] = sface.call_count
        row["baseline_seq_dual"] = lbph_base.call_count > 0 and sface.call_count > 0

        # Mode 2: Architecture-Only Early Bypass (r1_n8_g8x8 + Early Bypass)
        lbph_base.reset_count()
        sface.reset_count()
        m2 = run_early_bypass_cascade(sample, lbph_base, sface, gate_thresh_baseline, qual_thresh)
        row["arch_early_bypass_pred"] = m2["pred_name"]
        row["arch_early_bypass_correct"] = m2["pred_name"] == person
        row["arch_early_bypass_accepted"] = m2["accepted"]
        row["arch_early_bypass_lbph_calls"] = lbph_base.call_count
        row["arch_early_bypass_sface_calls"] = sface.call_count
        row["arch_early_bypass_dual"] = lbph_base.call_count > 0 and sface.call_count > 0

        # Mode 3: Descriptor-Only Challenger Sequential (r3_n8_g6x6 + Seq)
        lbph_chal.reset_count()
        sface.reset_count()
        m3 = run_sequential_cascade(sample, lbph_chal, sface, gate_thresh_challenger, qual_thresh)
        row["config_seq_pred"] = m3["pred_name"]
        row["config_seq_correct"] = m3["pred_name"] == person
        row["config_seq_accepted"] = m3["accepted"]
        row["config_seq_lbph_calls"] = lbph_chal.call_count
        row["config_seq_sface_calls"] = sface.call_count
        row["config_seq_dual"] = lbph_chal.call_count > 0 and sface.call_count > 0

        # Mode 4: Combined Optimized Cascade (r3_n8_g6x6 + Early Bypass) [PRIMARY]
        lbph_chal.reset_count()
        sface.reset_count()
        m4 = run_early_bypass_cascade(sample, lbph_chal, sface, gate_thresh_challenger, qual_thresh)
        row["combined_unified_pred"] = m4["pred_name"]
        row["combined_unified_correct"] = m4["pred_name"] == person
        row["combined_unified_accepted"] = m4["accepted"]
        row["combined_unified_lbph_calls"] = lbph_chal.call_count
        row["combined_unified_sface_calls"] = sface.call_count
        row["combined_unified_dual"] = lbph_chal.call_count > 0 and sface.call_count > 0
        row["combined_routing_path"] = m4["routing_path"]

        # Mode 5: True Direct SFace
        sface.reset_count()
        lbph_base.reset_count()
        lbph_chal.reset_count()
        sf_match = sface.score(sample)
        row["direct_sface_pred"] = sf_match.name
        row["direct_sface_correct"] = sf_match.name == person
        row["direct_sface_accepted"] = sf_match.accepted
        row["direct_sface_sface_calls"] = sface.call_count
        row["direct_sface_lbph_calls"] = 0
        row["direct_sface_dual"] = False
        assert lbph_base.call_count == 0 and lbph_chal.call_count == 0

        # Mode 6: Standalone Challenger LBPH
        lbph_chal.reset_count()
        lb_match = lbph_chal.score(sample)
        row["challenger_lbph_pred"] = lb_match.name
        row["challenger_lbph_correct"] = (lb_match.name == person) and (lb_match.distance <= gate_thresh_challenger.tau_accept)
        row["challenger_lbph_accepted"] = (lb_match.distance <= gate_thresh_challenger.tau_accept)
        row["challenger_lbph_distance"] = round(lb_match.distance, 4)
        row["challenger_lbph_margin"] = round(lb_match.margin, 4)
        row["challenger_lbph_lbph_calls"] = lbph_chal.call_count
        row["challenger_lbph_sface_calls"] = 0
        row["challenger_lbph_dual"] = False

        # Assertion: Early-bypass decision matches sequential decision exactly
        assert m1["pred_name"] == m2["pred_name"], f"Decision mismatch between Mode 1 and Mode 2 at row {idx}"
        assert m3["pred_name"] == m4["pred_name"], f"Decision mismatch between Mode 3 and Mode 4 at row {idx}"

        records.append(row)

    print("[SUCCESS] All 1,804 conditions scored and functional invariants verified!")

    # Write per-condition CSV with explicit sorted fieldnames union
    all_keys = list(dict.fromkeys(k for r in records for k in r.keys()))
    csv_path = output_dir / "per_condition_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(records)

    # 7. Rigorous Isolated Timing Benchmark (1 Warmup + 5 Interleaved Repetitions per probe)
    print("\n[INFO] Starting randomized interleaved timing benchmark across 1,804 probes (5 reps)...")
    modes_to_time = [
        "baseline_seq",
        "arch_early_bypass",
        "config_seq",
        "combined_unified",
        "direct_sface",
        "challenger_lbph",
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
        elif m_name == "challenger_lbph":
            lbph_chal.score(s)

    # Warmup
    for p in valid_probes:
        s = p["sample"]
        for m_name in modes_to_time:
            execute_timed_mode(m_name, s)

    # Timed Repetitions
    repeats = 5
    per_probe_timings: dict[str, list[list[float]]] = {m: [[] for _ in range(len(valid_probes))] for m in modes_to_time}

    for r in range(repeats):
        for p_idx, p in enumerate(valid_probes):
            s = p["sample"]
            shuffled_modes = list(modes_to_time)
            random.shuffle(shuffled_modes)
            for m_name in shuffled_modes:
                t0 = time.perf_counter()
                execute_timed_mode(m_name, s)
                t1 = time.perf_counter()
                per_probe_timings[m_name][p_idx].append((t1 - t0) * 1000.0)

    # Compute mean latency per probe, then compute population distribution statistics
    mode_probe_means: dict[str, np.ndarray] = {}
    timing_summary: dict[str, Any] = {}

    for m_name in modes_to_time:
        probe_means = np.array([np.mean(reps) for reps in per_probe_timings[m_name]])
        mode_probe_means[m_name] = probe_means
        ci_low, ci_high = bootstrap_ci_mean(probe_means, n_boot=2000, ci=95.0, seed=seed)
        timing_summary[m_name] = {
            "mean_ms": float(np.mean(probe_means)),
            "ci_95_mean_ms": [ci_low, ci_high],
            "p50_ms": float(np.median(probe_means)),
            "p95_ms": float(np.percentile(probe_means, 95)),
            "p99_ms": float(np.percentile(probe_means, 99)),
            "std_ms": float(np.std(probe_means)),
        }

    # Paired differences (Combined vs SFace, Combined vs Baseline)
    diff_combined_vs_sface = mode_probe_means["combined_unified"] - mode_probe_means["direct_sface"]
    diff_combined_vs_baseline = mode_probe_means["combined_unified"] - mode_probe_means["baseline_seq"]

    paired_timing = {
        "combined_vs_direct_sface": {
            "mean_diff_ms": float(np.mean(diff_combined_vs_sface)),
            "ci_95_mean_diff_ms": list(bootstrap_ci_mean(diff_combined_vs_sface, n_boot=2000, ci=95.0, seed=seed)),
            "p50_diff_ms": float(np.median(diff_combined_vs_sface)),
            "faster_percentage_of_probes": float(100.0 * np.count_nonzero(diff_combined_vs_sface < 0) / len(diff_combined_vs_sface)),
            "mean_reduction_pct": float(100.0 * (np.mean(mode_probe_means["direct_sface"]) - np.mean(mode_probe_means["combined_unified"])) / np.mean(mode_probe_means["direct_sface"])),
        },
        "combined_vs_baseline_seq": {
            "mean_diff_ms": float(np.mean(diff_combined_vs_baseline)),
            "ci_95_mean_diff_ms": list(bootstrap_ci_mean(diff_combined_vs_baseline, n_boot=2000, ci=95.0, seed=seed)),
            "p50_diff_ms": float(np.median(diff_combined_vs_baseline)),
            "faster_percentage_of_probes": float(100.0 * np.count_nonzero(diff_combined_vs_baseline < 0) / len(diff_combined_vs_baseline)),
            "mean_reduction_pct": float(100.0 * (np.mean(mode_probe_means["baseline_seq"]) - np.mean(mode_probe_means["combined_unified"])) / np.mean(mode_probe_means["baseline_seq"])),
        },
    }

    # 8. Recognition Performance & Contingency Tables
    total_conditions = len(probes)
    
    # 2x2: Combined vs Direct SFace
    table_combined_vs_sface = {
        "both_correct": sum(1 for r in records if r["combined_unified_correct"] and r["direct_sface_correct"]),
        "combined_only_correct": sum(1 for r in records if r["combined_unified_correct"] and not r["direct_sface_correct"]),
        "sface_only_correct": sum(1 for r in records if not r["combined_unified_correct"] and r["direct_sface_correct"]),
        "both_fail": sum(1 for r in records if not r["combined_unified_correct"] and not r["direct_sface_correct"]),
    }

    # 2x2: Challenger LBPH vs Direct SFace (Complementarity Ceiling)
    table_lbph_vs_sface = {
        "both_correct": sum(1 for r in records if r["challenger_lbph_correct"] and r["direct_sface_correct"]),
        "lbph_only_correct": sum(1 for r in records if r["challenger_lbph_correct"] and not r["direct_sface_correct"]),
        "sface_only_correct": sum(1 for r in records if not r["challenger_lbph_correct"] and r["direct_sface_correct"]),
        "both_fail": sum(1 for r in records if not r["challenger_lbph_correct"] and not r["direct_sface_correct"]),
    }

    # Identify any discordant cases
    discordant_cases = []
    for r in records:
        if r["combined_unified_correct"] != r["direct_sface_correct"]:
            discordant_cases.append({
                "condition_idx": r["condition_idx"],
                "identity": r["identity"],
                "source_image": r["source_image"],
                "transformation": r["transformation"],
                "combined_pred": r["combined_unified_pred"],
                "sface_pred": r["direct_sface_pred"],
                "combined_correct": r["combined_unified_correct"],
                "sface_correct": r["direct_sface_correct"],
                "routing_path": r["combined_routing_path"],
            })

    # 9. Severity / Workload Breakdown
    severity_groups = {
        "light": [r for r in records if r["tier"] == "light"],
        "medium": [r for r in records if r["tier"] == "medium"],
        "heavy": [r for r in records if r["tier"] == "heavy"],
    }

    severity_breakdown = {}
    for tier_name, tier_records in severity_groups.items():
        t_total = len(tier_records)
        t_indices = [r["condition_idx"] - 1 for r in tier_records if r["detector_success"]]
        
        # Latency subset for detected probes in this tier
        t_combined_lat = mode_probe_means["combined_unified"][[i for i, p in enumerate(valid_probes) if p["tier"] == tier_name]]
        t_sface_lat = mode_probe_means["direct_sface"][[i for i, p in enumerate(valid_probes) if p["tier"] == tier_name]]
        t_lbph_lat = mode_probe_means["challenger_lbph"][[i for i, p in enumerate(valid_probes) if p["tier"] == tier_name]]

        severity_breakdown[tier_name] = {
            "total_conditions": t_total,
            "combined_cascade": {
                "correct_count": sum(1 for r in tier_records if r["combined_unified_correct"]),
                "correct_pct": 100.0 * sum(1 for r in tier_records if r["combined_unified_correct"]) / t_total,
                "sface_invocation_rate_pct": 100.0 * sum(r["combined_unified_sface_calls"] for r in tier_records) / t_total,
                "lbph_terminal_rate_pct": 100.0 * sum(1 for r in tier_records if r["combined_routing_path"] == "quality_clear_lbph_terminal") / t_total,
                "mean_latency_ms": float(np.mean(t_combined_lat)) if len(t_combined_lat) > 0 else 0.0,
                "p95_latency_ms": float(np.percentile(t_combined_lat, 95)) if len(t_combined_lat) > 0 else 0.0,
            },
            "direct_sface": {
                "correct_count": sum(1 for r in tier_records if r["direct_sface_correct"]),
                "correct_pct": 100.0 * sum(1 for r in tier_records if r["direct_sface_correct"]) / t_total,
                "mean_latency_ms": float(np.mean(t_sface_lat)) if len(t_sface_lat) > 0 else 0.0,
                "p95_latency_ms": float(np.percentile(t_sface_lat, 95)) if len(t_sface_lat) > 0 else 0.0,
            },
            "challenger_lbph": {
                "correct_count": sum(1 for r in tier_records if r["challenger_lbph_correct"]),
                "correct_pct": 100.0 * sum(1 for r in tier_records if r["challenger_lbph_correct"]) / t_total,
                "mean_latency_ms": float(np.mean(t_lbph_lat)) if len(t_lbph_lat) > 0 else 0.0,
                "p95_latency_ms": float(np.percentile(t_lbph_lat, 95)) if len(t_lbph_lat) > 0 else 0.0,
            },
        }

    # Evaluate Clean Source Images Separately (44 clean images)
    clean_records = []
    for ident in confirmation_identities:
        for fname in ["dark_name.jpg", "light_name.jpg"]:
            img_path = test_root / ident / fname
            img_bgr = cv.imread(str(img_path))
            img_gray = cv.cvtColor(img_bgr, cv.COLOR_BGR2GRAY)
            sample = detect_sample(detector, image_bgr=img_bgr, image_gray=img_gray, assume_cropped=True)
            if sample is not None:
                m_comb = run_early_bypass_cascade(sample, lbph_chal, sface, gate_thresh_challenger, qual_thresh)
                m_sf = sface.score(sample)
                m_lb = lbph_chal.score(sample)
                clean_records.append({
                    "identity": ident,
                    "filename": fname,
                    "combined_correct": m_comb["pred_name"] == ident,
                    "sface_correct": m_sf.name == ident and m_sf.accepted,
                    "lbph_correct": m_lb.name == ident and m_lb.distance <= gate_thresh_challenger.tau_accept,
                    "combined_routing_path": m_comb["routing_path"],
                })

    clean_summary = {
        "total_clean_images": len(clean_records),
        "combined_correct_pct": 100.0 * sum(1 for r in clean_records if r["combined_correct"]) / len(clean_records),
        "sface_correct_pct": 100.0 * sum(1 for r in clean_records if r["sface_correct"]) / len(clean_records),
        "lbph_correct_pct": 100.0 * sum(1 for r in clean_records if r["lbph_correct"]) / len(clean_records),
        "lbph_terminal_count": sum(1 for r in clean_records if r["combined_routing_path"] == "quality_clear_lbph_terminal"),
        "lbph_terminal_pct": 100.0 * sum(1 for r in clean_records if r["combined_routing_path"] == "quality_clear_lbph_terminal") / len(clean_records),
    }

    # 10. Descriptor Resource Audit
    baseline_model_path = PROJECT_ROOT / "models" / "lbph" / "lasalle_clean.yml"
    chal_model_path = temp_challenger_model
    
    resource_audit = {
        "baseline_r1_n8_g8x8": {
            "descriptor_bytes_per_template": DEPLOYED_LBPH_CONFIG.descriptor_bytes,
            "templates_per_identity_in_gallery": 10,
            "total_enrolled_templates": 280,
            "total_feature_bytes_in_gallery": 280 * DEPLOYED_LBPH_CONFIG.descriptor_bytes,
            "total_feature_kib_in_gallery": (280 * DEPLOYED_LBPH_CONFIG.descriptor_bytes) / 1024.0,
            "serialized_model_file_bytes": baseline_model_path.stat().st_size,
            "serialized_model_file_mib": baseline_model_path.stat().st_size / (1024.0 * 1024.0),
            "extrapolated_ram_10k_single_template_mib": (10000 * DEPLOYED_LBPH_CONFIG.descriptor_bytes) / (1024.0 * 1024.0),
            "extrapolated_ram_10k_10_templates_mib": (10000 * 10 * DEPLOYED_LBPH_CONFIG.descriptor_bytes) / (1024.0 * 1024.0),
        },
        "challenger_r3_n8_g6x6": {
            "descriptor_bytes_per_template": SELECTED_LBPH_CONFIG.descriptor_bytes,
            "templates_per_identity_in_gallery": 10,
            "total_enrolled_templates": 280,
            "total_feature_bytes_in_gallery": 280 * SELECTED_LBPH_CONFIG.descriptor_bytes,
            "total_feature_kib_in_gallery": (280 * SELECTED_LBPH_CONFIG.descriptor_bytes) / 1024.0,
            "serialized_model_file_bytes": chal_model_path.stat().st_size,
            "serialized_model_file_mib": chal_model_path.stat().st_size / (1024.0 * 1024.0),
            "extrapolated_ram_10k_single_template_mib": (10000 * SELECTED_LBPH_CONFIG.descriptor_bytes) / (1024.0 * 1024.0),
            "extrapolated_ram_10k_10_templates_mib": (10000 * 10 * SELECTED_LBPH_CONFIG.descriptor_bytes) / (1024.0 * 1024.0),
        },
        "delta_reduction_pct": 100.0 * (DEPLOYED_LBPH_CONFIG.descriptor_bytes - SELECTED_LBPH_CONFIG.descriptor_bytes) / DEPLOYED_LBPH_CONFIG.descriptor_bytes,
    }

    # 11. Full Summary Compilation
    full_ablation_summary = {
        "status": "locked_confirmation_completed",
        "total_confirmation_conditions": total_conditions,
        "detector_failures": detector_failures,
        "valid_conditions": len(valid_probes),
        "systems": {
            "baseline_seq": {
                "correct_count": sum(1 for r in records if r["baseline_seq_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["baseline_seq_correct"]) / total_conditions,
                "lbph_invocations": sum(r["baseline_seq_lbph_calls"] for r in records),
                "sface_invocations": sum(r["baseline_seq_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["baseline_seq_dual"]),
                "timing": timing_summary["baseline_seq"],
            },
            "arch_early_bypass": {
                "correct_count": sum(1 for r in records if r["arch_early_bypass_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["arch_early_bypass_correct"]) / total_conditions,
                "lbph_invocations": sum(r["arch_early_bypass_lbph_calls"] for r in records),
                "sface_invocations": sum(r["arch_early_bypass_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["arch_early_bypass_dual"]),
                "timing": timing_summary["arch_early_bypass"],
            },
            "config_seq": {
                "correct_count": sum(1 for r in records if r["config_seq_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["config_seq_correct"]) / total_conditions,
                "lbph_invocations": sum(r["config_seq_lbph_calls"] for r in records),
                "sface_invocations": sum(r["config_seq_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["config_seq_dual"]),
                "timing": timing_summary["config_seq"],
            },
            "combined_unified": {
                "correct_count": sum(1 for r in records if r["combined_unified_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["combined_unified_correct"]) / total_conditions,
                "lbph_invocations": sum(r["combined_unified_lbph_calls"] for r in records),
                "sface_invocations": sum(r["combined_unified_sface_calls"] for r in records),
                "dual_inferences": sum(1 for r in records if r["combined_unified_dual"]),
                "routing_paths": {
                    "quality_triggered_sface": sum(1 for r in records if r["combined_routing_path"] == "quality_triggered_sface"),
                    "quality_clear_lbph_terminal": sum(1 for r in records if r["combined_routing_path"] == "quality_clear_lbph_terminal"),
                    "quality_clear_dual_sface": sum(1 for r in records if r["combined_routing_path"] == "quality_clear_dual_sface"),
                    "detector_failure": detector_failures,
                },
                "timing": timing_summary["combined_unified"],
            },
            "direct_sface": {
                "correct_count": sum(1 for r in records if r["direct_sface_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["direct_sface_correct"]) / total_conditions,
                "lbph_invocations": 0,
                "sface_invocations": sum(1 for r in records if r["detector_success"]),
                "dual_inferences": 0,
                "timing": timing_summary["direct_sface"],
            },
            "challenger_lbph": {
                "correct_count": sum(1 for r in records if r["challenger_lbph_correct"]),
                "correct_pct": 100.0 * sum(1 for r in records if r["challenger_lbph_correct"]) / total_conditions,
                "lbph_invocations": sum(1 for r in records if r["detector_success"]),
                "sface_invocations": 0,
                "dual_inferences": 0,
                "timing": timing_summary["challenger_lbph"],
            },
        },
        "paired_timing": paired_timing,
        "contingency_tables": {
            "combined_vs_direct_sface": table_combined_vs_sface,
            "challenger_lbph_vs_direct_sface": table_lbph_vs_sface,
        },
        "discordant_cases": discordant_cases,
        "clean_summary": clean_summary,
        "severity_breakdown": severity_breakdown,
        "resource_audit": resource_audit,
    }

    (output_dir / "summary.json").write_text(json.dumps(full_ablation_summary, indent=2), encoding="utf-8")
    (output_dir / "complementarity_2x2.json").write_text(json.dumps(table_lbph_vs_sface, indent=2), encoding="utf-8")
    (output_dir / "severity_workload_breakdown.json").write_text(json.dumps(severity_breakdown, indent=2), encoding="utf-8")
    (output_dir / "resource_audit.json").write_text(json.dumps(resource_audit, indent=2), encoding="utf-8")

    print("\n[COMPLETE] Wrote all confirmation artifacts to:")
    print(f"  Directory: {output_dir}")
    print(f"  Summary: {output_dir / 'summary.json'}")
    print(f"  Per-condition CSV: {csv_path}")

    print("\n================================================================================")
    print(" LOCKED CONFIRMATION EVALUATION SUMMARY")
    print("================================================================================")
    print(f"Total Conditions: {total_conditions} | Detector Failures: {detector_failures}")
    print(f"Combined Cascade Correct: {full_ablation_summary['systems']['combined_unified']['correct_count']} / {total_conditions} ({full_ablation_summary['systems']['combined_unified']['correct_pct']:.2f}%)")
    print(f"Direct SFace Correct:     {full_ablation_summary['systems']['direct_sface']['correct_count']} / {total_conditions} ({full_ablation_summary['systems']['direct_sface']['correct_pct']:.2f}%)")
    print(f"Challenger LBPH Correct:  {full_ablation_summary['systems']['challenger_lbph']['correct_count']} / {total_conditions} ({full_ablation_summary['systems']['challenger_lbph']['correct_pct']:.2f}%)")
    print(f"Discordant Cases:         {len(discordant_cases)}")
    print(f"Combined Mean Latency:    {timing_summary['combined_unified']['mean_ms']:.3f} ms (p50: {timing_summary['combined_unified']['p50_ms']:.3f} ms, p95: {timing_summary['combined_unified']['p95_ms']:.3f} ms)")
    print(f"Direct SFace Mean Lat:    {timing_summary['direct_sface']['mean_ms']:.3f} ms (p50: {timing_summary['direct_sface']['p50_ms']:.3f} ms, p95: {timing_summary['direct_sface']['p95_ms']:.3f} ms)")
    print(f"Mean Latency Delta:       {paired_timing['combined_vs_direct_sface']['mean_diff_ms']:.3f} ms ({paired_timing['combined_vs_direct_sface']['mean_reduction_pct']:.2f}% faster than SFace)")
    print(f"Dual Inferences Cut:      {full_ablation_summary['systems']['baseline_seq']['dual_inferences']} -> {full_ablation_summary['systems']['combined_unified']['dual_inferences']} (-{100.0*(full_ablation_summary['systems']['baseline_seq']['dual_inferences']-full_ablation_summary['systems']['combined_unified']['dual_inferences'])/full_ablation_summary['systems']['baseline_seq']['dual_inferences']:.1f}%)")
    print("================================================================================")


if __name__ == "__main__":
    main()
