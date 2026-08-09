#!/usr/bin/env python3
"""Parallel wrapper for sweep_gate_curve.py

This script duplicates the arguments and functionality of sweep_gate_curve.py,
but splits the scoring workload across multiple processes using concurrent.futures.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Import logic from the original sweep script
from scripts.pipeline.sweep_gate_curve import (
    DEFAULT_THRESHOLDS_PATH, DEFAULT_LBPH_MODEL, DEFAULT_LBPH_LABELS,
    DEFAULT_SFACE_GALLERY, DEFAULT_SFACE_IMPOSTORS, _abs, DEFAULT_MARGINS, DEFAULT_SHIFTS,
    evaluate_setting, evaluate_anchors, _auto_grid, sweep_lbph_axis, sweep_sface_axis,
    write_plot, write_records_csv, write_settings_csv, to_markdown
)

from src.benchmark.accuracy_ratio_hybrid import load_originals
from src.hybrid.gate import GateThresholds
from src.hybrid.recognizer import load_thresholds


def parse_args_multithread() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parallel wrapper for sweep_gate_curve.py"
    )
    parser.add_argument("--originals-dir", default="data/split_lasalle/test")
    parser.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    parser.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    parser.add_argument("--sface-gallery", default=DEFAULT_SFACE_GALLERY)
    parser.add_argument("--sface-impostors", default=DEFAULT_SFACE_IMPOSTORS)
    parser.add_argument("--seed", type=int, default=42,
                        help="Keep at 42 to reproduce the accuracy_ratio probes.")
    parser.add_argument("--select-one-per-person", action="store_true",
                        help="Enroll-parity: one seeded image per identity.")
    parser.add_argument("--max-originals", type=int, default=0,
                        help="Cap originals after the seeded selection (0 = all).")
    parser.add_argument("--margins", default=DEFAULT_MARGINS,
                        help="Comma list of margin_min values to sweep (gate axis).")
    parser.add_argument("--tau-shifts", default=DEFAULT_SHIFTS,
                        help="Comma list of shifts applied to BOTH tau_accept and tau_reject (gate axis).")
    parser.add_argument("--lbph-taus", default=None,
                        help="Comma list of LBPH tau_reject values (cv_only axis).")
    parser.add_argument("--sface-cutoffs", default=None,
                        help="Comma list of SFace genuine cosine cutoffs (dl axis).")
    parser.add_argument("--output-json", default="outputs/benchmark/gate_operating_curve.json")
    parser.add_argument("--output-md", default="reports/benchmark/gate_operating_curve.md")
    parser.add_argument("--output-png", default="reports/benchmark/gate_operating_curve.png")
    parser.add_argument("--output-records-csv",
                        default="outputs/benchmark/gate_operating_curve_probes.csv",
                        help="Raw per-probe records. '' to skip.")
    parser.add_argument("--output-settings-csv",
                        default="outputs/benchmark/gate_operating_curve_settings.csv",
                        help="One row per swept threshold setting. '' to skip.")
    parser.add_argument("--num-workers", type=int, default=4,
                        help="Number of parallel processes to use.")
    return parser.parse_args()


def _worker_task(args, start_idx: int, end_idx: int, worker_id: int) -> list[dict]:
    """Score a chunk of originals with both engines."""
    from scripts.pipeline.sweep_gate_curve import _abs
    from src.benchmark.accuracy_ratio_hybrid import tile_sample
    from src.classical_faces.detection import create_face_detector
    from src.hybrid.quality import QualityThresholds, compute_quality
    from src.hybrid.recognizer import LBPHAdapter, SFaceAdapter, detect_sample, load_thresholds
    from src.benchmark.modifications import MODIFICATIONS, stable_rng
    import cv2 as cv
    import time

    cfg = load_thresholds(_abs(args.thresholds_json))
    quality_thresholds = QualityThresholds.from_dict(cfg.get("quality"))
    lbph = LBPHAdapter(
        model_path=_abs(args.lbph_model),
        labels_path=_abs(args.lbph_labels),
        far_anchors=cfg.get("lbph_far_anchors"),
    )
    impostors = _abs(args.sface_impostors) if args.sface_impostors else None
    if impostors and not Path(impostors).exists():
        impostors = None
    sface = SFaceAdapter(gallery_path=_abs(args.sface_gallery), impostors_path=impostors)
    detector = create_face_detector("yunet")

    originals = load_originals(
        _abs(args.originals_dir),
        select_one_per_person=args.select_one_per_person,
        seed=args.seed,
    )
    if args.max_originals and args.max_originals < len(originals):
        originals = originals[: args.max_originals]
        
    originals_chunk = originals[start_idx:end_idx]
    records: list[dict] = []

    def score(gray, person, mod, level):
        bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
        sample = detect_sample(detector, image_bgr=bgr, image_gray=gray, assume_cropped=True)
        if sample is None:
            sample = tile_sample(bgr, gray)
        t0 = time.perf_counter()
        lm = lbph.score(sample)
        lbph_ms = (time.perf_counter() - t0) * 1000.0
        quality = compute_quality(
            gray_roi=sample.quality_gray,
            landmarks=sample.landmarks,
            face_px=sample.face_px,
            thresholds=quality_thresholds,
        )
        t0 = time.perf_counter()
        sm = sface.score(sample)
        sface_ms = (time.perf_counter() - t0) * 1000.0
        records.append({
            "person": person, "mod": mod, "level": level,
            "lbph_name": lm.name, "d1": float(lm.distance), "margin": float(lm.margin),
            "sface_name": sm.name, "sface_cosine": float(sm.cosine), "quality": quality,
            "lbph_ms": lbph_ms, "sface_ms": sface_ms,
        })

    for person, fname, gray in originals_chunk:
        score(gray, person, "clean", None)
    print(f"[Worker {worker_id}] Scored clean")
    
    for mod_name, fn, levels in MODIFICATIONS:
        for level in levels:
            for person, fname, gray in originals_chunk:
                rng = stable_rng(args.seed, person, fname, mod_name, level)
                score(fn(gray, level, rng), person, mod_name, level)
        print(f"[Worker {worker_id}] Scored modification: {mod_name}")

    return records


def main() -> int:
    args = parse_args_multithread()
    cfg = load_thresholds(_abs(args.thresholds_json))
    frozen = GateThresholds.from_dict(cfg.get("gate"))
    margins = [float(v) for v in args.margins.split(",") if v.strip()]
    shifts = [float(v) for v in args.tau_shifts.split(",") if v.strip()]

    # Load once just to get the total length for splitting
    originals = load_originals(
        _abs(args.originals_dir),
        select_one_per_person=args.select_one_per_person,
        seed=args.seed,
    )
    if args.max_originals and args.max_originals < len(originals):
        originals = originals[: args.max_originals]
        
    total = len(originals)
    if total == 0:
        print(f"[ERROR] No original images found under {args.originals_dir}")
        return 1

    num_workers = args.num_workers
    chunk_size = math.ceil(total / num_workers)
    
    records = []
    
    print(f"[INFO] Using {num_workers} parallel workers to score {total} originals.")
    t0 = time.time()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_worker = {}
        for i in range(num_workers):
            start_idx = i * chunk_size
            end_idx = min(start_idx + chunk_size, total)
            if start_idx >= total:
                break
            worker_id = i + 1
            print(f"[INFO] Launching Worker {worker_id} (indices {start_idx}-{end_idx})")
            future = executor.submit(_worker_task, args, start_idx, end_idx, worker_id)
            future_to_worker[future] = worker_id
        
        for future in concurrent.futures.as_completed(future_to_worker):
            worker_id = future_to_worker[future]
            records.extend(future.result())
            print(f"[INFO] Worker {worker_id} finished")
            
    print(f"[INFO] Parallel scoring completed in {time.time() - t0:.1f} seconds. Gathered {len(records)} records.")

    settings = []
    for m in margins:
        for s in shifts:
            gt = GateThresholds(
                tau_accept=frozen.tau_accept + s,
                tau_reject=frozen.tau_reject + s,
                margin_min=m,
            )
            settings.append(evaluate_setting(records, gt))
    deployed = evaluate_setting(records, frozen)
    anchors = evaluate_anchors(records, frozen)

    taus = ([float(v) for v in args.lbph_taus.split(",") if v.strip()] if args.lbph_taus
            else _auto_grid([r["d1"] for r in records
                             if r["lbph_name"] == r["person"] and r["mod"] != "clean"],
                            0.5, 0.999, 13))
    cutoffs = ([float(v) for v in args.sface_cutoffs.split(",") if v.strip()] if args.sface_cutoffs
               else _auto_grid([r["sface_cosine"] for r in records
                                if r["sface_name"] == r["person"] and r["mod"] != "clean"],
                               0.001, 0.5, 13))
    lbph_points = sweep_lbph_axis(records, taus)
    sface_points = sweep_sface_axis(records, cutoffs)
    all_settings = [{**p, "axis": "gate"} for p in settings] + lbph_points + sface_points

    out_png = Path(_abs(args.output_png))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    write_plot(settings, anchors, deployed, out_png)

    if args.output_records_csv:
        rc = Path(_abs(args.output_records_csv))
        write_records_csv(records, rc)
        print(f"[OK] Wrote {rc} ({len(records)} raw probe records)")
    if args.output_settings_csv:
        sc = Path(_abs(args.output_settings_csv))
        write_settings_csv(all_settings, sc)
        print(f"[OK] Wrote {sc} (gate={len(settings)} + lbph={len(lbph_points)} "
              f"+ sface={len(sface_points)} = {len(all_settings)} settings)")

    payload = {
        "originals_dir": args.originals_dir,
        "seed": args.seed,
        "frozen_gate": frozen.to_dict(),
        "margins": margins,
        "tau_shifts": shifts,
        "deployed": deployed,
        "anchors": anchors,
        "settings": settings,
        "lbph_axis": lbph_points,
        "sface_axis": sface_points,
        "plot": str(out_png.relative_to(PROJECT_ROOT)) if out_png.is_relative_to(PROJECT_ROOT)
                else str(out_png),
    }
    out_json = Path(_abs(args.output_json))
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    Path(_abs(args.output_md)).write_text(to_markdown(payload), encoding="utf-8")

    print(f"\n[DEPLOYED] AR {deployed['overall_ar_percent']:.2f}% @ "
          f"{deployed['mean_latency_ms']:.2f} ms ({deployed['escalation_percent']:.0f}% esc)")
    print(f"[ANCHORS] cv_only {anchors['cv_only']['overall_ar_percent']:.2f}% @ "
          f"{anchors['cv_only']['mean_latency_ms']:.2f} ms | dl_only "
          f"{anchors['dl_only']['overall_ar_percent']:.2f}% @ "
          f"{anchors['dl_only']['mean_latency_ms']:.2f} ms")
    print(f"[OK] Wrote {out_json}")
    print(f"[OK] Wrote {_abs(args.output_md)}")
    print(f"[OK] Wrote {out_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
