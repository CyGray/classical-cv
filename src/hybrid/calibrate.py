"""Derive the deployed hybrid thresholds and write ``thresholds.json``.

Every value is either **measured now** or **carried with explicit provenance** -
no invented numbers (PLAN risk "don't invent fused numbers"):

* **SFace operating cosines** - measured here from the real LFW impostor cosine
  distribution (``SFaceFarModel.cosine_at_far`` at 100 ppm and 1% FAR).
* **LBPH gate edges** (``tau_accept`` / ``tau_reject``) - carried from
  ``reports/benchmark/tar_at_far.md`` (LBPH vs 13,149 LFW impostors: 73.04 @
  100 ppm, 76.85 @ ~1%), stamped with that provenance.
* **LBPH margin_min** - measured from the clean-train top-1/top-2 distance gaps
  (set below the genuine distribution so clean faces don't trip ``low_margin``).
* **Quality-probe thresholds** - measured from the clean-crop probe distributions
  (the operating edge; the full LBPH<->SFace per-modification crossover on the
  DB2 41-mod suite is the on-device refinement, Phase 6.4).

Run after enrolling the gallery. Writes ``src/hybrid/thresholds.json``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.detection import create_face_detector
from src.hybrid.quality import compute_quality, QualityThresholds
from src.hybrid.recognizer import (
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_SFACE_IMPOSTORS,
    DEFAULT_THRESHOLDS_PATH,
    LBPHAdapter,
    detect_sample,
)
from src.sface.recognizer import COSINE_GENUINE_THRESHOLD, SFaceFarModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

# Carried LBPH gate edges (measured, reports/benchmark/tar_at_far.md).
LBPH_TAU_ACCEPT = 73.04   # 100 ppm FAR vs 13,149 LFW impostors (TAR 98.21%)
LBPH_TAU_REJECT = 76.85   # ~1% FAR band edge (TAR 100.00%)
TAR_AT_FAR_PROVENANCE = "reports/benchmark/tar_at_far.md (LBPH vs 13,149 LFW impostors)"

# Relative top1<->top2 gap below which LBPH is treated as a near-tie and escalated.
# A POLICY default, deliberately not dataset-fitted: train distances are inflated
# by memorisation so a train-fitted margin over-escalates the held-out set, while
# fitting on the test set would leak. 0.05 = "runner-up within 5% of the best".
MARGIN_MIN_POLICY = 0.05


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(value: str) -> str:
    p = Path(value)
    return str(p) if p.is_absolute() else str(PROJECT_ROOT / p)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Calibrate hybrid thresholds.")
    p.add_argument("--clean-dir", default=root_path("data", "split_lasalle", "train"))
    p.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    p.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    p.add_argument("--impostors-npy", default=DEFAULT_SFACE_IMPOSTORS)
    p.add_argument("--output", default=DEFAULT_THRESHOLDS_PATH)
    p.add_argument("--far-accept", type=float, default=1e-4, help="Strict FAR budget (100 ppm).")
    p.add_argument("--far-reject", type=float, default=1e-2, help="Band-edge FAR (1 percent).")
    return p.parse_args()


def _percentile(values: list[float], q: float, default: float) -> float:
    return float(np.percentile(values, q)) if values else default


def calibrate_quality(clean_dir: Path) -> tuple[QualityThresholds, dict]:
    """Measure the probe distributions on clean crops and set the operating edges.

    Clean faces should pass every probe, so each threshold is placed just beyond
    the clean distribution: blur at a low VoL percentile, luma bounds around the
    clean luma spread, noise/pose at high percentiles, px_min from the box sizes.
    """
    detector = create_face_detector("yunet")
    blur, luma, noise, pose, px = [], [], [], [], []
    n = 0
    for person_dir in sorted(p for p in clean_dir.iterdir() if p.is_dir()):
        for img_path in sorted(f for f in person_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS):
            image_bgr = cv.imread(str(img_path))
            if image_bgr is None:
                continue
            gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
            sample = detect_sample(detector, image_bgr=image_bgr, image_gray=gray, assume_cropped=True)
            if sample is None:
                continue
            q = compute_quality(
                gray_roi=sample.quality_gray,
                landmarks=sample.landmarks,
                face_px=sample.face_px,
                thresholds=QualityThresholds(),
            )
            blur.append(q.blur_var)
            luma.append(q.luma_mean)
            noise.append(q.noise_sigma)
            pose.append(q.pose_angle)
            px.append(sample.face_px)
            n += 1

    # Clean faces sit ABOVE tau_blur, INSIDE [luma_lo, luma_hi], BELOW tau_noise/
    # tau_pose. Place each edge just outside the clean spread.
    thresholds = QualityThresholds(
        tau_blur=round(_percentile(blur, 5, 60.0), 2),
        luma_lo=round(max(0.0, _percentile(luma, 2, 50.0)), 2),
        luma_hi=round(min(255.0, _percentile(luma, 98, 205.0)), 2),
        tau_noise=round(_percentile(noise, 95, 12.0), 3),
        tau_pose=round(_percentile(pose, 95, 18.0), 2),
        px_min=int(max(1, np.floor(_percentile(px, 5, 80) * 0.9))) if px else 80,
    )
    stats = {
        "clean_samples": n,
        "blur_var": _spread(blur),
        "luma_mean": _spread(luma),
        "noise_sigma": _spread(noise),
        "pose_angle": _spread(pose),
        "face_px": _spread(px),
    }
    return thresholds, stats


def _spread(values: list[float]) -> dict:
    if not values:
        return {}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "min": round(float(arr.min()), 3),
        "p5": round(float(np.percentile(arr, 5)), 3),
        "median": round(float(np.median(arr)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "max": round(float(arr.max()), 3),
    }


def calibrate_lbph_margin(clean_dir: Path, lbph: LBPHAdapter) -> tuple[float, dict]:
    """Measure clean top-1/top-2 LBPH distance gaps; set margin_min below them."""
    detector = create_face_detector("yunet")
    margins = []
    for person_dir in sorted(p for p in clean_dir.iterdir() if p.is_dir()):
        for img_path in sorted(f for f in person_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS):
            image_bgr = cv.imread(str(img_path))
            if image_bgr is None:
                continue
            gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
            sample = detect_sample(detector, image_bgr=image_bgr, image_gray=gray, assume_cropped=True)
            if sample is None:
                continue
            margins.append(lbph.score(sample).margin)
    # Clean genuine faces have a wide margin; flag "low margin" below the 10th
    # percentile of the clean distribution.
    margin_min = round(_percentile(margins, 10, 8.0), 2) if margins else 8.0
    return margin_min, _spread(margins)


def main() -> int:
    args = parse_args()
    clean_dir = Path(resolve_path(args.clean_dir))
    if not clean_dir.exists():
        raise FileNotFoundError(f"Clean calibration dir not found: {clean_dir}")

    start = time.time()
    print(f"[CAL] Clean crops: {clean_dir}")

    # 1) SFace operating cosines from the real LFW impostor distribution.
    far_model = SFaceFarModel.from_features_npy(resolve_path(args.impostors_npy))
    cos_accept = round(far_model.cosine_at_far(args.far_accept), 4)
    cos_reject = round(far_model.cosine_at_far(args.far_reject), 4)
    print(f"[CAL] SFace cosine @ {args.far_accept:.0e} FAR = {cos_accept} | "
          f"@ {args.far_reject:.0e} FAR = {cos_reject} (genuine rule {COSINE_GENUINE_THRESHOLD})")

    # 2) LBPH margin: policy default (see MARGIN_MIN_POLICY). The clean relative
    # gap spread is still measured and recorded for transparency.
    lbph = LBPHAdapter(model_path=resolve_path(args.lbph_model), labels_path=resolve_path(args.lbph_labels))
    _, margin_stats = calibrate_lbph_margin(clean_dir, lbph)
    margin_min = MARGIN_MIN_POLICY
    print(f"[CAL] LBPH margin_min = {margin_min} (policy; clean relative-gap spread {margin_stats})")

    # 3) Quality-probe thresholds from the clean-crop probe distributions.
    quality, quality_stats = calibrate_quality(clean_dir)
    print(f"[CAL] Quality thresholds: {quality.to_dict()}")

    config = {
        "_note": "Deployed hybrid config derived by src/hybrid/calibrate.py. Values are "
        "measured-now or carried-with-provenance; see 'provenance'.",
        "gate": {
            "tau_accept": LBPH_TAU_ACCEPT,
            "tau_reject": LBPH_TAU_REJECT,
            "margin_min": margin_min,
        },
        "quality": quality.to_dict(),
        "lbph_far_anchors": [[0.0, 0.0], [LBPH_TAU_ACCEPT, 1e-4], [LBPH_TAU_REJECT, 1e-2], [200.0, 1.0]],
        "sface": {
            "cosine_genuine": COSINE_GENUINE_THRESHOLD,
            "l2_genuine": 1.128,
            "cosine_operating": cos_accept,
            "cosine_operating_1pct": cos_reject,
        },
        "provenance": {
            "gate.tau_accept": f"carried: {TAR_AT_FAR_PROVENANCE}, 100 ppm FAR",
            "gate.tau_reject": f"carried: {TAR_AT_FAR_PROVENANCE}, ~1% FAR",
            "gate.margin_min": "policy: relative top1-top2 gap 0.05 (not dataset-fitted; "
            "train margins are inflated by memorisation, test-fitting would leak)",
            "quality.*": f"measured: clean-crop probe distribution edges ({clean_dir.name}); "
            "DB2 41-mod LBPH<->SFace crossover refinement deferred to Phase 6.4",
            "sface.cosine_operating": f"measured: SFaceFarModel.cosine_at_far({args.far_accept:.0e}) "
            f"over {Path(args.impostors_npy).name}",
        },
        "calibration_stats": {
            "lbph_margin": margin_stats,
            "quality": quality_stats,
        },
    }

    out = Path(resolve_path(args.output))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"\n[CAL] Wrote {out} in {time.time() - start:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
