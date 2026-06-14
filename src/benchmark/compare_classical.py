"""Spec-oriented comparison table for the classical recognizers.

Reads the unified evaluation reports in ``reports/evaluation`` (LBPH / Eigenfaces
/ Fisherfaces), joins them with live FPS (``reports/benchmark/live_fps/
aggregate_summary.json``) and the on-disk footprint, and writes a single
comparison the recognizer-selection deliverable (6/30) can read directly:
``reports/benchmark/classical_comparison.{json,md}``.

Columns map to the project spec (docs/READ THIS/BRIEFING.md S6):
    Model | Variant | Dataset | Rank-1 (held-out) | Best-sweep acc |
    Hit@thr | Model MB | Feature B | <1 KB? | Live FPS | >=30 fps? | Verdict

Notes the table records, so nobody mistakes it for the full spec sign-off:
* TAR is reported as closed-set rank-1 on the held-out La Salle test split.
* FAR / FRR need impostors and the rank-based threshold from the independence
  test (the separate 7/15 deliverable); they are marked pending here.
* The live FPS bottleneck is the shared Haar detector, not the recognizer.
"""

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CLASSICAL_FAMILIES = {"lbph", "eigenfaces", "fisherfaces"}
FEATURE_SPEC_BYTES = 1024
FPS_SPEC = 30.0
TAR_SPEC_LOW = 90.0


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str(PROJECT_ROOT.joinpath(candidate))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the classical recognizer spec comparison table.")
    parser.add_argument("--reports-dir", default=root_path("reports", "evaluation"))
    parser.add_argument(
        "--fps-summary",
        default=root_path("reports", "benchmark", "live_fps", "aggregate_summary.json"),
    )
    parser.add_argument("--output-json", default=root_path("reports", "benchmark", "classical_comparison.json"))
    parser.add_argument("--output-md", default=root_path("reports", "benchmark", "classical_comparison.md"))
    parser.add_argument(
        "--tar-at-far-json",
        default=root_path("reports", "benchmark", "tar_at_far.json"),
        help="Optional TAR@FAR report (src/benchmark/tar_at_far.py) to fill the verification columns.",
    )
    parser.add_argument(
        "--accuracy-ratio-json",
        default=root_path("reports", "benchmark", "accuracy_ratio.json"),
        help="Optional Accuracy-Ratio report (src/benchmark/accuracy_ratio.py) for the "
             "modification-robustness table.",
    )
    parser.add_argument(
        "--dataset-contains",
        default="",
        help="Only include reports whose dataset label contains this substring (e.g. 'split').",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _num(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def rank1_percent(report: dict) -> float:
    rank1 = report.get("rank1")
    if isinstance(rank1, dict) and isinstance(rank1.get("accuracy_percent"), (int, float)):
        return float(rank1["accuracy_percent"])
    overall = report.get("overall", {})
    if isinstance(overall, dict):
        return _num(overall.get("closed_set_rank1_percent"))
    return 0.0


def best_sweep_percent(report: dict) -> float:
    best = report.get("best_sweep")
    if isinstance(best, dict):
        return _num(best.get("overall_hit_rate_percent"))
    return 0.0


def hit_at_threshold_percent(report: dict) -> float:
    overall = report.get("overall", {})
    if isinstance(overall, dict):
        return _num(overall.get("hit_rate_percent"))
    return 0.0


def feature_bytes(report: dict) -> int:
    foot = report.get("footprint", {})
    if isinstance(foot, dict):
        return int(_num(foot.get("feature_vector_bytes")))
    return 0


def model_bytes(report: dict) -> int:
    foot = report.get("footprint", {})
    if isinstance(foot, dict):
        return int(_num(foot.get("model_file_bytes")))
    return 0


def load_fps_map(fps_summary_path: str) -> dict[str, float]:
    payload = read_json(Path(fps_summary_path))
    out: dict[str, float] = {}
    if not payload:
        return out
    for row in payload.get("algorithms", []):
        if isinstance(row, dict):
            algo = str(row.get("algorithm", "")).lower()
            if algo:
                out[algo] = _num(row.get("average_fps"))
    return out


def _op_dict(op: dict) -> dict:
    return {
        "target_far_percent": _num(op.get("target_far_percent")),
        "tar_percent": _num(op.get("tar_percent")),
        "frr_percent": _num(op.get("frr_percent")),
        "actual_far_percent": _num(op.get("actual_far_percent")),
        "threshold": _num(op.get("threshold_predict_scale")),
        "resolvable": bool(op.get("resolvable", True)),
    }


def load_tar_at_far(path: str) -> dict[str, dict]:
    """family -> verification operating points (independence FAR + spec 100 ppm) + EER."""
    payload = read_json(Path(path))
    out: dict[str, dict] = {}
    if not payload:
        return out
    for row in payload.get("rows", []):
        if not isinstance(row, dict):
            continue
        family = str(row.get("family", "")).lower()
        ops = row.get("operating_points", [])
        if not (family and isinstance(ops, list) and ops):
            continue
        # operating point closest to the La Salle independence FAR (1.058%)
        independence_op = min(ops, key=lambda o: abs(_num(o.get("target_far_percent")) - 1.058))
        spec_op = min(ops, key=lambda o: abs(_num(o.get("target_far_percent")) - 0.01))
        eer = row.get("eer") or {}
        entry = _op_dict(independence_op)
        entry.update({
            "eer_percent": _num(eer.get("eer_percent")) if eer else None,
            "n_impostor": int(_num(row.get("n_impostor"))),
        })
        if abs(_num(spec_op.get("target_far_percent")) - 0.01) < 1e-6:
            entry["spec_far_op"] = _op_dict(spec_op)
        out[family] = entry
    return out


def load_accuracy_ratio(path: str) -> dict[str, dict]:
    """family -> overall AR + clean acceptance + the three weakest modifications."""
    payload = read_json(Path(path))
    out: dict[str, dict] = {}
    if not payload:
        return out
    for row in payload.get("rows", []):
        if not isinstance(row, dict):
            continue
        family = str(row.get("family", "")).lower()
        if not family:
            continue
        mods = [m for m in row.get("modifications", []) if isinstance(m, dict)]
        worst = sorted(mods, key=lambda m: _num(m.get("ar_percent")))[:3]
        out[family] = {
            "overall_ar_percent": _num(row.get("overall_ar_percent")),
            "clean_acceptance_percent": _num(row.get("clean_acceptance_percent")),
            "modified_probes": int(_num(row.get("modified_probes"))),
            "worst_modifications": [
                {"modification": str(m.get("modification", "")),
                 "ar_percent": _num(m.get("ar_percent"))}
                for m in worst
            ],
        }
    return out


def build_verdict(rank1: float, feat_bytes: int, fps: float | None) -> str:
    parts: list[str] = []
    parts.append(f"TAR(rank-1) {'PASS' if rank1 >= TAR_SPEC_LOW else 'below 90%'}")
    parts.append(f"feature {'PASS <1KB' if 0 < feat_bytes < FEATURE_SPEC_BYTES else 'FAIL >=1KB'}")
    if fps is None:
        parts.append("fps n/a")
    else:
        parts.append(f"{'>=30fps PASS' if fps >= FPS_SPEC else '<30fps'}")
    return "; ".join(parts)


def collect_rows(reports_dir: str, fps_map: dict[str, float], dataset_contains: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for file_path in sorted(Path(reports_dir).glob("*.json")):
        payload = read_json(file_path)
        if not payload:
            continue
        family = str(payload.get("model_family", "")).lower()
        if family not in CLASSICAL_FAMILIES:
            continue
        # Schema guard: the unified pipeline always emits a ``rank1`` block.
        # Pre-refactor reports lack it; skip them so the table stays honest.
        if not isinstance(payload.get("rank1"), dict):
            continue
        dataset_profile = payload.get("dataset_profile", {})
        dataset_label = str(dataset_profile.get("label", "unknown")) if isinstance(dataset_profile, dict) else "unknown"
        if dataset_contains and dataset_contains.lower() not in dataset_label.lower():
            continue
        entity_key = str(payload.get("entity_key", "")) or f"{family}::{file_path.stem}"
        model_variant = str(payload.get("model_variant", "default"))
        run_tag = str(payload.get("run_tag", ""))
        display_variant = run_tag or model_variant.split("__")[0]
        candidate = {
            "entity_key": entity_key,
            "model_family": family,
            "model_variant": model_variant,
            "display_variant": display_variant,
            "run_tag": run_tag,
            "dataset_label": dataset_label,
            "rank1_percent": rank1_percent(payload),
            "best_sweep_percent": best_sweep_percent(payload),
            "hit_at_threshold_percent": hit_at_threshold_percent(payload),
            "unknown_threshold": _num(payload.get("unknown_threshold")),
            "evaluated_images": int(_num(payload.get("overall", {}).get("evaluated_images")
                                          if isinstance(payload.get("overall"), dict) else 0)),
            "feature_vector_bytes": feature_bytes(payload),
            "model_file_bytes": model_bytes(payload),
            "live_fps": fps_map.get(family),
            "report_path": str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "mtime": file_path.stat().st_mtime,
        }
        existing = grouped.get(entity_key)
        if existing is None or candidate["mtime"] > existing["mtime"]:
            grouped[entity_key] = candidate

    rows = list(grouped.values())
    for row in rows:
        row["feature_under_1kb"] = 0 < row["feature_vector_bytes"] < FEATURE_SPEC_BYTES
        row["fps_meets_spec"] = (row["live_fps"] is not None and row["live_fps"] >= FPS_SPEC)
        row["verdict"] = build_verdict(row["rank1_percent"], row["feature_vector_bytes"], row["live_fps"])
    rows.sort(key=lambda r: (r["rank1_percent"], r["best_sweep_percent"]), reverse=True)
    return rows


def _fps_cell(fps: float | None) -> str:
    return f"{fps:.1f}" if isinstance(fps, (int, float)) else "n/a"


def _md_cell(text: str) -> str:
    # Pipes inside a value would break the Markdown table; the dataset label uses
    # " | " as its own separator, so render it with a slash instead.
    return str(text).replace("|", "/").strip()


def to_markdown(
    rows: list[dict],
    tar_far: dict[str, dict] | None = None,
    accuracy_ratio: dict[str, dict] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("# Classical Recognizer Comparison (spec view)")
    lines.append("")
    lines.append("Recognition is closed-set **rank-1** on the held-out La Salle test split "
                 "(every test identity is enrolled, so there are no impostors). Higher is better.")
    lines.append("")
    lines.append(
        "| Model | Variant | Dataset | Rank-1 % | Best-sweep % | Hit@thr % | "
        "Model MB | Feature B | <1 KB? | Live FPS | >=30 fps? | Verdict |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|:--:|---:|:--:|---|")
    for r in rows:
        lines.append(
            f"| {r['model_family']} | {_md_cell(r['display_variant'])} | {_md_cell(r['dataset_label'])} | "
            f"{r['rank1_percent']:.2f} | {r['best_sweep_percent']:.2f} | {r['hit_at_threshold_percent']:.2f} | "
            f"{r['model_file_bytes'] / 1e6:.1f} | {r['feature_vector_bytes']} | "
            f"{'YES' if r['feature_under_1kb'] else 'no'} | {_fps_cell(r['live_fps'])} | "
            f"{'YES' if r['fps_meets_spec'] else 'no'} | {r['verdict']} |"
        )
    lines.append("")

    if tar_far:
        lines.append("## Verification operating point (FAR-controlled, baseline models)")
        lines.append("")
        lines.append("Measured on each recognizer's native `predict()` scale: held-out La Salle genuine "
                     "vs LFW impostors, threshold set at the La Salle independence FAR (~1%, 8th error "
                     "pair). This is the real TAR@FAR the closed-set rank-1 column cannot show.")
        lines.append("")
        lines.append("| Model | Threshold | FAR | TAR | FRR | EER | Spec (TAR 90-95%, FRR 1-5%) |")
        lines.append("|---|---:|---:|---:|---:|---:|:--|")
        for fam in ("lbph", "eigenfaces", "fisherfaces"):
            v = tar_far.get(fam)
            if not v:
                continue
            tar = v["tar_percent"]
            frr = v["frr_percent"]
            # FRR below the 1-5% band is strictly better than the band, not a failure.
            meets = "PASS" if (tar >= 90.0 and frr <= 5.0) else "FAIL"
            eer = f"{v['eer_percent']:.2f}%" if v.get("eer_percent") is not None else "n/a"
            lines.append(
                f"| {fam} | {v['threshold']:.2f} | {v['actual_far_percent']:.2f}% | "
                f"{tar:.2f}% | {frr:.2f}% | {eer} | {meets} |"
            )
        lines.append("")

        spec_rows = [(fam, tar_far[fam]["spec_far_op"]) for fam in ("lbph", "eigenfaces", "fisherfaces")
                     if fam in tar_far and tar_far[fam].get("spec_far_op")]
        if spec_rows:
            lines.append("### At the spec FAR budget (0.01% = 100 ppm)")
            lines.append("")
            lines.append("| Model | Threshold | Actual FAR | TAR | FRR | Resolvable? | Spec verdict |")
            lines.append("|---|---:|---:|---:|---:|:--:|:--|")
            for fam, op in spec_rows:
                meets = "PASS" if (op["tar_percent"] >= 90.0 and op["frr_percent"] <= 5.0) else "FAIL"
                lines.append(
                    f"| {fam} | {op['threshold']:.2f} | {op['actual_far_percent']:.4f}% | "
                    f"{op['tar_percent']:.2f}% | {op['frr_percent']:.2f}% | "
                    f"{'yes' if op['resolvable'] else 'no*'} | {meets} |"
                )
            lines.append("")
            lines.append("`no*` = the impostor sample cannot resolve 100 ppm; the strictest "
                         "threshold below the smallest impostor distance is used.")
            lines.append("")

    if accuracy_ratio:
        lines.append("## Modification robustness (Accuracy Ratio, 41-mod suite)")
        lines.append("")
        lines.append("AR = K/M per (modification, level) at the deployable threshold, mean per "
                     "modification, then mean across the 12 modification types "
                     "(`src/benchmark/accuracy_ratio.py`, spec S9 scheme).")
        lines.append("")
        lines.append("| Model | Clean accept | Overall AR | Probes | Weakest modifications |")
        lines.append("|---|---:|---:|---:|---|")
        for fam in ("lbph", "eigenfaces", "fisherfaces"):
            v = accuracy_ratio.get(fam)
            if not v:
                continue
            worst = "; ".join(
                f"{w['modification']} {w['ar_percent']:.1f}%" for w in v["worst_modifications"])
            lines.append(
                f"| {fam} | {v['clean_acceptance_percent']:.2f}% | "
                f"**{v['overall_ar_percent']:.2f}%** | {v['modified_probes']} | {worst} |"
            )
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- **Rank-1 %** is closed-set rank-1 accuracy on the held-out test split (spec target "
                 "90-95%); Hit@thr is the rate at each model's default unknown-threshold, which is "
                 "CALIBRATED to the spec FAR budget (100 ppm vs full LFW; see tar_at_far.md).")
    lines.append("- **FAR / TAR / FRR / EER** (verification table above) come from "
                 "`src/benchmark/tar_at_far.py` using LFW impostors at the independence operating point. "
                 "Run it after the clean loop to populate them.")
    lines.append("- **Live FPS** comes from `reports/benchmark/live_fps/aggregate_summary.json`; `n/a` means "
                 "no live `detect.py` run has been recorded yet. The FPS bottleneck is the shared Haar "
                 "detector, not the recognizer.")
    lines.append("- **Feature B** is the per-face feature-vector size (spec target < 1 KB): LBPH = "
                 "grid x grid x 2^neighbours histogram bins; Eigen/Fisher = retained components x 4 B.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    args.reports_dir = resolve_path(args.reports_dir)
    args.fps_summary = resolve_path(args.fps_summary)
    args.output_json = resolve_path(args.output_json)
    args.output_md = resolve_path(args.output_md)

    fps_map = load_fps_map(args.fps_summary)
    tar_far = load_tar_at_far(resolve_path(args.tar_at_far_json))
    accuracy_ratio = load_accuracy_ratio(resolve_path(args.accuracy_ratio_json))
    rows = collect_rows(args.reports_dir, fps_map, args.dataset_contains)
    if not rows:
        raise RuntimeError(f"No classical evaluation reports found in: {args.reports_dir}")

    summary = {
        "reports_dir": args.reports_dir,
        "fps_summary": args.fps_summary,
        "spec": {
            "tar_percent_low": TAR_SPEC_LOW,
            "feature_bytes_max": FEATURE_SPEC_BYTES,
            "fps_min": FPS_SPEC,
        },
        "rows": rows,
        "verification_operating_point": tar_far,
        "accuracy_ratio": accuracy_ratio,
    }

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(to_markdown(rows, tar_far, accuracy_ratio))

    print("[OK] Classical comparison written")
    print(f"  - JSON: {args.output_json}")
    print(f"  - Markdown: {args.output_md}")
    print()
    for r in rows:
        fps = _fps_cell(r["live_fps"])
        print(f"  {r['model_family']:<12} {r['display_variant'][:24]:<24} "
              f"rank1={r['rank1_percent']:6.2f}% feat={r['feature_vector_bytes']:>6}B "
              f"<1KB={'Y' if r['feature_under_1kb'] else 'N'} fps={fps}")


if __name__ == "__main__":
    main()
