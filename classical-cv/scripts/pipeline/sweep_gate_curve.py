"""Gate operating-curve sweep: the speed-accuracy trade-off as a CURVE, not 3 dots.

Paper section 4.4 currently shows three operating points (LBPH-only, SFace-only,
cascade at the deployed gate). A reviewer's first question is "did you pick the
setting that looks good?". This script answers it by sweeping the gate's
aggressiveness - the relative-margin floor ``margin_min`` and a symmetric shift
of the (tau_accept, tau_reject) band - and scoring the SAME 41-modification
probe suite (identical seeds to ``accuracy_ratio_hybrid.py``) at every setting.

Efficiency: each probe is scored ONCE by each engine (LBPH distance/margin +
quality probes, SFace name), with per-engine wall latency recorded. A gate
setting only changes the ROUTING, so every sweep point is pure arithmetic over
the cached records: cascade latency = lbph_ms + (sface_ms if escalated).
25 settings cost the same as one 2-engine pass. The quality probes are part of
the calibrated gate contract and are NOT swept.

Semantics mirror ``HybridRecognizer`` exactly:
* escalate            -> SFace decides (name already thresholded by the genuine rule)
* no-escalate, accept -> LBPH's name stands (d1 <= tau_accept)
* no-escalate, reject -> Unknown
Anchors reported from the same records: cv_only (accept = d1 <= frozen
tau_reject, the deployed cv_only rule) and dl_only (SFace on every probe).

Writes ``reports/benchmark/gate_operating_curve.{json,md,png}``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2 as cv
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.benchmark.modifications import MODIFICATIONS, VARIANT_COUNT, stable_rng
from src.benchmark.accuracy_ratio_hybrid import load_originals, tile_sample
from src.classical_faces.detection import create_face_detector
from src.hybrid.gate import GateThresholds, decide_escalation
from src.hybrid.quality import QualityThresholds, compute_quality
from src.hybrid.recognizer import (
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_SFACE_GALLERY,
    DEFAULT_SFACE_IMPOSTORS,
    DEFAULT_THRESHOLDS_PATH,
    LBPHAdapter,
    SFaceAdapter,
    detect_sample,
    load_thresholds,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MARGINS = "0.0,0.025,0.05,0.1,0.2"
DEFAULT_SHIFTS = "-8,-4,0,4,8"


def _abs(path_value: str) -> str:
    p = Path(path_value)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep the cascade gate thresholds and plot the speed-accuracy curve."
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
                        help="Enroll-parity: one seeded image per identity (needed for the "
                             "LFW2 one-per-person models). Off = every image under originals-dir.")
    parser.add_argument("--max-originals", type=int, default=0,
                        help="Cap originals after the seeded selection (0 = all). Shrinks the "
                             "single scoring pass; the threshold sweep over it stays free.")
    parser.add_argument("--margins", default=DEFAULT_MARGINS,
                        help="Comma list of margin_min values to sweep (gate axis).")
    parser.add_argument("--tau-shifts", default=DEFAULT_SHIFTS,
                        help="Comma list of shifts applied to BOTH tau_accept and tau_reject (gate axis).")
    parser.add_argument("--lbph-taus", default=None,
                        help="Comma list of LBPH tau_reject values (cv_only axis). "
                             "Default: 13 auto points from genuine-match d1 quantiles.")
    parser.add_argument("--sface-cutoffs", default=None,
                        help="Comma list of SFace genuine cosine cutoffs (dl axis). "
                             "Default: 13 auto points from genuine-match cosine quantiles.")
    parser.add_argument("--output-json", default="outputs/benchmark/gate_operating_curve.json")
    parser.add_argument("--output-md", default="reports/benchmark/gate_operating_curve.md")
    parser.add_argument("--output-png", default="reports/benchmark/gate_operating_curve.png")
    parser.add_argument("--output-records-csv",
                        default="outputs/benchmark/gate_operating_curve_probes.csv",
                        help="Raw per-probe records (the reusable asset: re-cut any threshold/"
                             "presentation later with no re-scoring). '' to skip.")
    parser.add_argument("--output-settings-csv",
                        default="outputs/benchmark/gate_operating_curve_settings.csv",
                        help="One row per swept threshold setting, all three axes stacked. '' to skip.")
    return parser.parse_args()


def collect_probe_records(args) -> list[dict]:
    """Score every clean + modified probe once with both engines."""
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
    if not originals:
        raise RuntimeError(f"No original images under {args.originals_dir}")
    if args.max_originals and args.max_originals < len(originals):
        originals = originals[: args.max_originals]
    print(f"[INFO] originals={len(originals)}; probes = clean + "
          f"{len(originals)} x {VARIANT_COUNT} modified")

    records: list[dict] = []

    def score(gray: np.ndarray, person: str, mod: str, level) -> None:
        bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
        sample = detect_sample(detector, image_bgr=bgr, image_gray=gray, assume_cropped=True)
        if sample is None:
            sample = tile_sample(bgr, gray)  # fallback policy, as in the AR benchmark
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

    for person, fname, gray in originals:
        score(gray, person, "clean", None)
    for mod_name, fn, levels in MODIFICATIONS:
        for level in levels:
            for person, fname, gray in originals:
                rng = stable_rng(args.seed, person, fname, mod_name, level)
                score(fn(gray, level, rng), person, mod_name, level)
        print(f"  scored {mod_name}")
    return records


def evaluate_setting(records: list[dict], thresholds: GateThresholds) -> dict:
    """Route every cached record through one gate setting (pure arithmetic)."""
    per_mod_level: dict[str, dict] = {}
    clean_matched = clean_total = 0
    lat_sum = 0.0
    esc = 0
    n_mod = 0
    for r in records:
        gate = decide_escalation(
            lbph_distance=r["d1"], lbph_margin=r["margin"],
            quality=r["quality"], thresholds=thresholds,
        )
        if gate.escalate:
            matched = r["sface_name"] == r["person"]
            lat = r["lbph_ms"] + r["sface_ms"]
        else:
            matched = gate.lbph_accept and r["lbph_name"] == r["person"]
            lat = r["lbph_ms"]
        if r["mod"] == "clean":
            clean_matched += matched
            clean_total += 1
            continue
        n_mod += 1
        lat_sum += lat
        esc += gate.escalate
        slot = per_mod_level.setdefault(r["mod"], {})
        lv = slot.setdefault(r["level"], [0, 0])
        lv[0] += matched
        lv[1] += 1
    mod_ars = []
    for mod, levels in per_mod_level.items():
        level_ars = [100.0 * m / t for m, t in levels.values()]
        mod_ars.append(sum(level_ars) / len(level_ars))
    return {
        "tau_accept": thresholds.tau_accept,
        "tau_reject": thresholds.tau_reject,
        "margin_min": thresholds.margin_min,
        "overall_ar_percent": sum(mod_ars) / len(mod_ars),
        "clean_acceptance_percent": 100.0 * clean_matched / max(1, clean_total),
        "mean_latency_ms": lat_sum / max(1, n_mod),
        "escalation_percent": 100.0 * esc / max(1, n_mod),
    }


def evaluate_anchors(records: list[dict], frozen: GateThresholds) -> dict:
    """LBPH-only and SFace-only corners from the same records."""
    def agg(matched_fn, lat_key: str) -> dict:
        per_mod_level: dict[str, dict] = {}
        lat_sum = 0.0
        n_mod = 0
        for r in records:
            if r["mod"] == "clean":
                continue
            n_mod += 1
            lat_sum += r[lat_key]
            slot = per_mod_level.setdefault(r["mod"], {})
            lv = slot.setdefault(r["level"], [0, 0])
            lv[0] += matched_fn(r)
            lv[1] += 1
        mod_ars = [sum(100.0 * m / t for m, t in lv.values()) / len(lv)
                   for lv in per_mod_level.values()]
        return {"overall_ar_percent": sum(mod_ars) / len(mod_ars),
                "mean_latency_ms": lat_sum / max(1, n_mod)}

    cv_only = agg(lambda r: r["lbph_name"] == r["person"] and r["d1"] <= frozen.tau_reject,
                  "lbph_ms")
    dl_only = agg(lambda r: r["sface_name"] == r["person"], "sface_ms")
    return {"cv_only": cv_only, "dl_only": dl_only}


# --------------------------------------------------------------------------- #
# Single-engine threshold axes (LBPH tau_reject, SFace cosine cutoff) - swept
# as pure arithmetic over the SAME cached records as the gate axis. Quality
# probes are the calibrated gate contract and are not part of these two axes.
# --------------------------------------------------------------------------- #
def _suite_ar(records: list[dict], matched_fn) -> tuple[float, float]:
    """Mean per-modification AR (%) over the 41-mod suite + clean acceptance (%)
    for an arbitrary accept predicate. Averaging mirrors accuracy_ratio_hybrid."""
    per_mod_level: dict[str, dict] = {}
    clean_matched = clean_total = 0
    for r in records:
        m = bool(matched_fn(r))
        if r["mod"] == "clean":
            clean_matched += m
            clean_total += 1
            continue
        lv = per_mod_level.setdefault(r["mod"], {}).setdefault(r["level"], [0, 0])
        lv[0] += m
        lv[1] += 1
    mod_ars = [sum(100.0 * mm / tt for mm, tt in lv.values()) / len(lv)
               for lv in per_mod_level.values()]
    return (
        (sum(mod_ars) / len(mod_ars)) if mod_ars else 0.0,
        100.0 * clean_matched / max(1, clean_total),
    )


def _mean_modified_latency(records: list[dict], lat_key: str) -> float:
    vals = [r[lat_key] for r in records if r["mod"] != "clean"]
    return sum(vals) / max(1, len(vals))


def _auto_grid(values: list[float], lo_q: float, hi_q: float, n: int) -> list[float]:
    if not values:
        return []
    qs = np.quantile(np.asarray(values, dtype=float), np.linspace(lo_q, hi_q, n))
    return sorted({round(float(v), 4) for v in qs})


def sweep_lbph_axis(records: list[dict], taus: list[float]) -> list[dict]:
    """cv_only accept = nearest LBPH id correct AND d1 <= tau_reject. Latency = lbph_ms."""
    lat = _mean_modified_latency(records, "lbph_ms")
    out = []
    for tau in taus:
        ar, clean = _suite_ar(
            records, lambda r, t=tau: r["lbph_name"] == r["person"] and r["d1"] <= t)
        out.append({"axis": "lbph", "tau_reject": float(tau),
                    "overall_ar_percent": ar, "clean_acceptance_percent": clean,
                    "mean_latency_ms": lat, "escalation_percent": 0.0})
    return out


def sweep_sface_axis(records: list[dict], cutoffs: list[float]) -> list[dict]:
    """dl accept = nearest SFace id correct AND cosine >= cutoff. Latency = sface_ms."""
    lat = _mean_modified_latency(records, "sface_ms")
    out = []
    for c in cutoffs:
        ar, clean = _suite_ar(
            records, lambda r, cc=c: r["sface_name"] == r["person"] and r["sface_cosine"] >= cc)
        out.append({"axis": "sface", "sface_cutoff": float(c),
                    "overall_ar_percent": ar, "clean_acceptance_percent": clean,
                    "mean_latency_ms": lat, "escalation_percent": 0.0})
    return out


def write_records_csv(records: list[dict], path: Path) -> None:
    """The reusable asset: one raw row per probe. Every threshold/presentation
    downstream re-cuts from here with no re-scoring (FAR/ROC excepted - needs impostors)."""
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["person", "mod", "level", "lbph_name", "d1", "margin", "lbph_rank1_correct",
              "sface_name", "sface_cosine", "sface_rank1_correct",
              "blur_var", "luma_mean", "noise_sigma", "pose_angle", "face_px",
              "flag_blur", "flag_low_light", "flag_noise", "flag_off_pose", "flag_small_face",
              "lbph_ms", "sface_ms"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            q = r["quality"]
            flags = q.flags
            w.writerow({
                "person": r["person"], "mod": r["mod"], "level": r["level"],
                "lbph_name": r["lbph_name"], "d1": r["d1"], "margin": r["margin"],
                "lbph_rank1_correct": r["lbph_name"] == r["person"],
                "sface_name": r["sface_name"], "sface_cosine": r["sface_cosine"],
                "sface_rank1_correct": r["sface_name"] == r["person"],
                "blur_var": q.blur_var, "luma_mean": q.luma_mean,
                "noise_sigma": q.noise_sigma, "pose_angle": q.pose_angle, "face_px": q.face_px,
                "flag_blur": flags.get("blur"), "flag_low_light": flags.get("low_light"),
                "flag_noise": flags.get("noise"), "flag_off_pose": flags.get("off_pose"),
                "flag_small_face": flags.get("small_face"),
                "lbph_ms": r["lbph_ms"], "sface_ms": r["sface_ms"],
            })


def write_settings_csv(rows: list[dict], path: Path) -> None:
    """One row per swept setting; all three axes stacked, tagged by `axis`."""
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["axis", "tau_accept", "tau_reject", "margin_min", "sface_cutoff",
              "overall_ar_percent", "clean_acceptance_percent",
              "mean_latency_ms", "escalation_percent"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def write_plot(points: list[dict], anchors: dict, deployed: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 5.0), dpi=150)
    margins = sorted({p["margin_min"] for p in points})
    cmap = plt.get_cmap("viridis")
    for i, m in enumerate(margins):
        pts = sorted((p for p in points if p["margin_min"] == m),
                     key=lambda p: p["mean_latency_ms"])
        ax.plot([p["mean_latency_ms"] for p in pts],
                [p["overall_ar_percent"] for p in pts],
                "o-", ms=4, lw=1.2, color=cmap(i / max(1, len(margins) - 1)),
                label=f"margin_min={m}")
    for name, a in anchors.items():
        ax.scatter([a["mean_latency_ms"]], [a["overall_ar_percent"]],
                   marker="s", s=70, zorder=5,
                   color="#d62728" if name == "dl_only" else "#2ca02c")
        ax.annotate(name.replace("_", "-"), (a["mean_latency_ms"], a["overall_ar_percent"]),
                    textcoords="offset points", xytext=(6, -12), fontsize=9)
    ax.scatter([deployed["mean_latency_ms"]], [deployed["overall_ar_percent"]],
               marker="*", s=260, color="#ff7f0e", edgecolor="black", zorder=6,
               label="deployed gate")
    ax.set_xlabel("Mean latency per modified probe (ms)")
    ax.set_ylabel("Overall AR over the 41-modification suite (%)")
    ax.set_title("Cascade speed-accuracy operating curve (gate threshold sweep)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def to_markdown(payload: dict) -> str:
    dep = payload["deployed"]
    lines = [
        "# Gate operating curve - cascade speed-accuracy sweep",
        "",
        f"Probes: `{payload['originals_dir']}` clean + 41-mod suite (seed={payload['seed']}, "
        f"same probes as `accuracy_ratio_hybrid.py`). Latency = lbph_ms + sface_ms when "
        "escalated, else lbph_ms; per-engine costs measured once per probe, routing swept "
        "as arithmetic. Quality probes fixed (calibrated, not swept).",
        "",
        f"Deployed gate: tau_a={dep['tau_accept']}, tau_r={dep['tau_reject']}, "
        f"margin_min={dep['margin_min']} -> **AR {dep['overall_ar_percent']:.2f}%** at "
        f"**{dep['mean_latency_ms']:.2f} ms** ({dep['escalation_percent']:.0f}% escalation, "
        f"clean acceptance {dep['clean_acceptance_percent']:.1f}%).",
        "",
        "Anchors (same records): "
        f"cv_only AR {payload['anchors']['cv_only']['overall_ar_percent']:.2f}% @ "
        f"{payload['anchors']['cv_only']['mean_latency_ms']:.2f} ms | "
        f"dl_only AR {payload['anchors']['dl_only']['overall_ar_percent']:.2f}% @ "
        f"{payload['anchors']['dl_only']['mean_latency_ms']:.2f} ms.",
        "",
        "| tau_a | tau_r | margin_min | AR % | clean % | latency ms | escalation % |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in payload["settings"]:
        star = " *" if p is dep or (
            p["tau_accept"] == dep["tau_accept"] and p["margin_min"] == dep["margin_min"]) else ""
        lines.append(
            f"| {p['tau_accept']:.2f} | {p['tau_reject']:.2f} | {p['margin_min']} "
            f"| {p['overall_ar_percent']:.2f}{star} | {p['clean_acceptance_percent']:.1f} "
            f"| {p['mean_latency_ms']:.2f} | {p['escalation_percent']:.0f} |")
    lines += ["", f"Curve figure: `{payload['plot']}`", ""]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    cfg = load_thresholds(_abs(args.thresholds_json))
    frozen = GateThresholds.from_dict(cfg.get("gate"))
    margins = [float(v) for v in args.margins.split(",") if v.strip()]
    shifts = [float(v) for v in args.tau_shifts.split(",") if v.strip()]

    records = collect_probe_records(args)

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

    # Single-engine axes over the same records (free): LBPH tau_reject + SFace cosine.
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
    raise SystemExit(main())
