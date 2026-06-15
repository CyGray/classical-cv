"""Honest offline evaluation of the fused hybrid (one system, real numbers).

Reports, for a chosen mode, on the held-out clean split:

* **closed-set rank-1** - the deciding engine's nearest identity (no threshold);
  the honest recognition number when every test identity is enrolled,
* **thresholded hit rate / TAR / FRR** - using the fused, gated decision,
* **FAR** - against an optional impostor set (LFW), accept = any known identity,
* **escalation rate** - fraction of faces that hit SFace (the FPS<->accuracy knob),
* **per-stage latency** - YuNet / LBPH+gate / SFace, so the Pi budget is
  predictable before hardware.

Numbers come only from the run; nothing is hard-coded. Writes a report JSON in
the same schema family the launcher's overview reads (``model_family``,
``overall.hit_rate_percent`` / ``closed_set_rank1_percent``).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.detection import create_face_detector
from src.hybrid.recognizer import (
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_SFACE_GALLERY,
    HYBRID_MODES,
    HybridRecognizer,
    build_hybrid,
    detect_sample,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(value: str) -> str:
    p = Path(value)
    return str(p) if p.is_absolute() else str(PROJECT_ROOT / p)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate the fused hybrid recognizer.")
    p.add_argument("--mode", choices=list(HYBRID_MODES), default="cascade")
    p.add_argument("--test-dir", default=root_path("data", "split_lasalle", "test"))
    p.add_argument(
        "--impostor-dir",
        default="",
        help="Optional out-of-gallery set (e.g. data/lfw-dataset) for FAR.",
    )
    p.add_argument("--max-impostors", type=int, default=600)
    p.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    p.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    p.add_argument("--sface-gallery", default=DEFAULT_SFACE_GALLERY)
    p.add_argument("--report-json", default=root_path("reports", "evaluation", "hybrid_eval.json"))
    p.add_argument("--assume-cropped", action=argparse.BooleanOptionalAction, default=True)
    return p.parse_args()


def _iter_images(root: Path, *, flat: bool = False):
    if flat:
        for img in sorted(root.rglob("*")):
            if img.suffix.lower() in IMAGE_EXTS:
                yield img.parent.name, img
        return
    for person_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for img in sorted(f for f in person_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS):
            yield person_dir.name, img


def evaluate_hybrid(
    hybrid: HybridRecognizer,
    *,
    detector,
    test_dir: Path,
    known_names: set[str],
    assume_cropped: bool,
    impostor_dir: Path | None = None,
    max_impostors: int = 600,
) -> dict:
    detect_ms: list[float] = []
    lbph_ms: list[float] = []
    sface_ms: list[float] = []

    total = evaluated = no_face = 0
    rank1_correct = 0
    thresh_correct = 0          # known accepted as correct identity (TAR numerator)
    known_total = 0
    escalated = 0
    engine_usage = {"lbph": 0, "sface": 0}
    reason_counts: dict[str, int] = {}
    misses: list[dict] = []

    for truth, img_path in _iter_images(test_dir):
        total += 1
        known_total += 1
        image_bgr = cv.imread(str(img_path))
        if image_bgr is None:
            continue
        gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)

        t0 = time.perf_counter()
        sample = detect_sample(detector, image_bgr=image_bgr, image_gray=gray, assume_cropped=assume_cropped)
        detect_ms.append((time.perf_counter() - t0) * 1000.0)
        if sample is None:
            no_face += 1
            continue

        evaluated += 1
        t1 = time.perf_counter()
        decision = hybrid.predict(sample)
        elapsed_ms = (time.perf_counter() - t1) * 1000.0
        if decision.escalated and decision.engine == "sface":
            sface_ms.append(elapsed_ms)
        else:
            lbph_ms.append(elapsed_ms)

        engine_usage[decision.engine] = engine_usage.get(decision.engine, 0) + 1
        if decision.escalated:
            escalated += 1
        reason_key = decision.reason.split(":")[0]
        reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1

        if decision.name_raw == truth:
            rank1_correct += 1
        if decision.name == truth:
            thresh_correct += 1
        elif len(misses) < 20:
            misses.append({
                "truth": truth, "predicted": decision.name, "engine": decision.engine,
                "escalated": decision.escalated, "reason": decision.reason,
                "lbph_distance": round(decision.lbph_distance, 2),
                "sface_cosine": decision.sface_cosine,
            })

    # FAR against the impostor set (accept = any known identity returned).
    far_accepts = far_total = 0
    if impostor_dir is not None and impostor_dir.exists():
        for truth, img_path in _iter_images(impostor_dir, flat=True):
            if truth in known_names:
                continue
            if far_total >= max_impostors:
                break
            image_bgr = cv.imread(str(img_path))
            if image_bgr is None:
                continue
            gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
            sample = detect_sample(detector, image_bgr=image_bgr, image_gray=gray, assume_cropped=False)
            if sample is None:
                continue
            far_total += 1
            decision = hybrid.predict(sample)
            if decision.name != "Unknown":
                far_accepts += 1

    rank1 = 100.0 * rank1_correct / evaluated if evaluated else 0.0
    hit_rate = 100.0 * thresh_correct / evaluated if evaluated else 0.0
    tar = 100.0 * thresh_correct / known_total if known_total else 0.0
    frr = 100.0 - tar if known_total else 0.0
    far = (100.0 * far_accepts / far_total) if far_total else None
    escalation_rate = 100.0 * escalated / evaluated if evaluated else 0.0

    def _stats(ms: list[float]) -> dict:
        if not ms:
            return {"count": 0, "mean_ms": 0.0, "p95_ms": 0.0}
        arr = np.asarray(ms)
        return {
            "count": int(arr.size),
            "mean_ms": round(float(arr.mean()), 3),
            "p95_ms": round(float(np.percentile(arr, 95)), 3),
        }

    detect_mean = float(np.mean(detect_ms)) if detect_ms else 0.0
    recog_mean = float(np.mean(lbph_ms + sface_ms)) if (lbph_ms or sface_ms) else 0.0
    end_to_end_ms = detect_mean + recog_mean

    return {
        "mode": hybrid.mode,
        "overall": {
            "total_images": total,
            "evaluated_images": evaluated,
            "no_face": no_face,
            "correct": thresh_correct,
            "hit_rate_percent": round(hit_rate, 2),
            "closed_set_rank1_percent": round(rank1, 2),
        },
        "fused_metrics": {
            "tar_percent": round(tar, 2),
            "frr_percent": round(frr, 2),
            "far_percent": (round(far, 4) if far is not None else None),
            "far_impostors_evaluated": far_total,
        },
        "escalation": {
            "escalation_rate_percent": round(escalation_rate, 2),
            "escalated_frames": escalated,
            "engine_usage": engine_usage,
            "reasons": reason_counts,
        },
        "latency": {
            "yunet_detect": _stats(detect_ms),
            "lbph_gate": _stats(lbph_ms),
            "sface": _stats(sface_ms),
            "end_to_end_mean_ms": round(end_to_end_ms, 3),
            "projected_fps": round((1000.0 / end_to_end_ms), 2) if end_to_end_ms > 0 else None,
        },
        "sample_misclassifications": misses,
    }


def main() -> int:
    args = parse_args()
    test_dir = Path(resolve_path(args.test_dir))
    if not test_dir.exists():
        raise FileNotFoundError(f"Test dir not found: {test_dir}")

    hybrid = build_hybrid(
        mode=args.mode,
        lbph_model=resolve_path(args.lbph_model),
        lbph_labels=resolve_path(args.lbph_labels),
        sface_gallery=resolve_path(args.sface_gallery),
        require_sface=(args.mode != "cv_only"),
    )
    detector = create_face_detector("yunet")
    known_names = set(hybrid.labels)
    impostor_dir = Path(resolve_path(args.impostor_dir)) if args.impostor_dir else None

    print(f"[EVAL] mode={hybrid.mode} | test={test_dir} | identities={len(known_names)}")
    start = time.time()
    result = evaluate_hybrid(
        hybrid,
        detector=detector,
        test_dir=test_dir,
        known_names=known_names,
        assume_cropped=args.assume_cropped,
        impostor_dir=impostor_dir,
        max_impostors=args.max_impostors,
    )
    elapsed = time.time() - start

    report = {
        "model_family": "hybrid",
        "model_variant": args.mode,
        "run_tag": args.mode,
        "entity_key": f"hybrid_{args.mode}",
        "dataset_profile": {"label": f"split=test | dir={test_dir.name} | mode={args.mode}"},
        "elapsed_seconds": round(elapsed, 2),
        "thresholds_path": "src/hybrid/thresholds.json",
        **result,
    }

    out = Path(resolve_path(args.report_json))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    o = result["overall"]
    fm = result["fused_metrics"]
    esc = result["escalation"]
    lat = result["latency"]
    print(f"\n[RESULT] hybrid ({args.mode}) on {test_dir.name}")
    print(f"[OVERALL] rank1(closed-set)={o['closed_set_rank1_percent']:.2f}% "
          f"hit_rate@gate={o['hit_rate_percent']:.2f}% evaluated={o['evaluated_images']} no_face={o['no_face']}")
    far_disp = f"{fm['far_percent']:.4f}%" if fm["far_percent"] is not None else "N/A (no impostor set)"
    print(f"[FUSED] TAR={fm['tar_percent']:.2f}% FRR={fm['frr_percent']:.2f}% FAR={far_disp}")
    print(f"[ESCALATION] rate={esc['escalation_rate_percent']:.2f}% engine_usage={esc['engine_usage']} reasons={esc['reasons']}")
    print(f"[LATENCY] detect={lat['yunet_detect']['mean_ms']:.2f}ms lbph_gate={lat['lbph_gate']['mean_ms']:.2f}ms "
          f"sface={lat['sface']['mean_ms']:.2f}ms end2end={lat['end_to_end_mean_ms']:.2f}ms "
          f"(~{lat['projected_fps']} fps)")
    print(f"[INFO] Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
