"""Combine the LBPH impostor FAR sweep with genuine-side TAR from the full
1:1 pairwise-verification run, to show what TAR costs at each FAR checkpoint
instead of only the single 10ppm deployment gate.

Inputs (both already computed, this script does no new distance computation):
  - reports/independence/lbph_lfw1/far_sweep.json
    (far_sweep_impostor_thresholds.py - impostor-only, full LFW1, 16.5M pairs)
  - outputs/benchmark/accuracy_ratio_verification_full_pairs.csv
    (accuracy_ratio_verification.py - genuine LBPH distances, clean + 41 mods,
    same detector/crop/equalization/dataset - see robustness-protocol-map
    skill Sec 4b for the cross-artifact scale match already verified)

Output: reports/benchmark/far_sweep_tar_report.json + .md
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SWEEP_JSON = PROJECT_ROOT / "reports" / "independence" / "lbph_lfw1" / "far_sweep.json"
PAIRS_CSV = PROJECT_ROOT / "outputs" / "benchmark" / "accuracy_ratio_verification_full_pairs.csv"
THRESHOLDS_JSON = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"

OUT_JSON = PROJECT_ROOT / "reports" / "benchmark" / "far_sweep_tar_report.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark" / "far_sweep_tar_report.md"

# Known from reports/benchmark/accuracy_ratio_verification_full.md - EER is a
# separate, unfrozen, run-specific operating point, not a FAR-target checkpoint.
# Kept as reference rows only (see robustness-protocol-map skill Sec 2).
EER_REFERENCE_ROWS = [
    {"label": "EER (clean baseline, unfrozen)", "threshold": 85.709, "eer_percent": 39.29},
    {"label": "EER (all 41 mods, unfrozen)", "threshold": 88.162, "eer_percent": 42.33},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join a native-LBPH impostor FAR sweep with 1:1 genuine TAR records."
    )
    parser.add_argument("--sweep-json", default=str(SWEEP_JSON))
    parser.add_argument("--pairs-csv", default=str(PAIRS_CSV))
    parser.add_argument("--output-json", default=str(OUT_JSON))
    parser.add_argument("--output-md", default=str(OUT_MD))
    return parser.parse_args()


def format_far(ppm: float) -> str:
    if ppm >= 10000:
        return f"{ppm / 10000:.1f}%"
    if ppm >= 1000:
        return f"{ppm / 10000:.2f}%"
    return f"{ppm:.2f} ppm"


def load_genuine_distances(pairs_path: Path):
    clean, mods = [], []
    clean_trials = mods_trials = 0
    with pairs_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            is_clean = row["modification"] == "clean"
            if is_clean:
                clean_trials += 1
            else:
                mods_trials += 1
            d = row.get("lbph_genuine_dist", "")
            if not d:
                continue
            d = float(d)
            if is_clean:
                clean.append(d)
            else:
                mods.append(d)
    return clean, mods, clean_trials, mods_trials


def tar_at(distances: list[float], threshold: float, trials: int | None = None) -> float:
    denominator = len(distances) if trials is None else trials
    if not denominator:
        return float("nan")
    accepted = sum(1 for d in distances if d <= threshold)
    return 100.0 * accepted / denominator


def main() -> None:
    args = parse_args()
    sweep_path = Path(args.sweep_json)
    pairs_path = Path(args.pairs_csv)
    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
    clean_dists, mods_dists, clean_trials, mods_trials = load_genuine_distances(pairs_path)

    rows = []
    for point in sweep["sweep"]:
        threshold = point["raw_threshold"]
        lbl = f"{point['target_far_ppm']:.0f} ppm target (current, deployed)" if abs(point["target_far_ppm"] - 10.0) < 1e-3 else f"{point['target_far_ppm']:.0f} ppm target"
        rows.append(
            {
                "label": lbl,
                "target_far_ppm": point["target_far_ppm"],
                "realized_far_ppm": point["realized_far_ppm"],
                "raw_threshold": threshold,
                "clean_tar_percent": tar_at(clean_dists, threshold),
                "overall_tar_percent": tar_at(mods_dists, threshold),
                "clean_strict_tar_percent": tar_at(clean_dists, threshold, clean_trials),
                "overall_strict_tar_percent": tar_at(mods_dists, threshold, mods_trials),
                "family": "far_target",
            }
        )

    for ref in EER_REFERENCE_ROWS:
        eer_far_ppm = ref["eer_percent"] * 10000.0
        rows.append(
            {
                "label": ref["label"],
                "target_far_ppm": eer_far_ppm,
                "realized_far_ppm": eer_far_ppm,
                "raw_threshold": ref["threshold"],
                "clean_tar_percent": tar_at(clean_dists, ref["threshold"]),
                "overall_tar_percent": tar_at(mods_dists, ref["threshold"]),
                "clean_strict_tar_percent": tar_at(clean_dists, ref["threshold"], clean_trials),
                "overall_strict_tar_percent": tar_at(mods_dists, ref["threshold"], mods_trials),
                "family": "eer_reference",
            }
        )

    payload = {
        "n_clean_genuine_pairs": len(clean_dists),
        "n_mods_genuine_pairs": len(mods_dists),
        "n_clean_genuine_trials_strict": clean_trials,
        "n_mods_genuine_trials_strict": mods_trials,
        "impostor_pool_unique_pairs": sweep["unique_pairs"],
        "impostor_pool_source": str(sweep_path),
        "genuine_pool_source": str(pairs_path),
        "rows": rows,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# LBPH FAR-target sweep vs TAR - full LFW1",
        "",
        f"Impostor pool: {sweep['unique_pairs']:,} unique cross-identity pairs "
        "(full LFW1, YuNet, native predict_collect scale) - "
        f"`{sweep_path}`.",
        f"Genuine pool: {len(clean_dists)}/{clean_trials} clean-baseline pairs scored; "
        f"{len(mods_dists)}/{mods_trials} pooled 41-modification pairs scored - "
        f"`{pairs_path}`.",
        "",
        "Each FAR-target row picks a threshold from the impostor-only pool, "
        "then reports what fraction of the (separately-collected) genuine "
        "scorable pairs would clear that same threshold. The strict TAR column "
        "uses every probe as its denominator, including no-face failures. The EER rows are NOT FAR "
        "targets - they are this run's own break-even point, shown for "
        "reference only (not frozen, not comparable across runs - see "
        "robustness-protocol-map skill Sec 2).",
        "",
        "| Operating point | Realized FAR | Raw threshold | Clean TAR | 41-mod TAR (scorable) | 41-mod TAR (strict) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        far_col = format_far(r["realized_far_ppm"]) if r["realized_far_ppm"] is not None else "-"
        lines.append(
            f"| {r['label']} | {far_col} | {r['raw_threshold']:.4f} | "
            f"{r['clean_tar_percent']:.2f}% | {r['overall_tar_percent']:.2f}% | "
            f"{r['overall_strict_tar_percent']:.2f}% |"
        )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[SAVE] {out_json}")
    print(f"[SAVE] {out_md}")


if __name__ == "__main__":
    main()
