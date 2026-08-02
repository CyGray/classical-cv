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


def format_far(ppm: float) -> str:
    if ppm >= 10000:
        return f"{ppm / 10000:.1f}%"
    if ppm >= 1000:
        return f"{ppm / 10000:.2f}%"
    return f"{ppm:.2f} ppm"


def load_genuine_distances():
    clean, mods = [], []
    with open(PAIRS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("lbph_genuine_dist", "")
            if not d:
                continue
            d = float(d)
            if row["modification"] == "clean":
                clean.append(d)
            else:
                mods.append(d)
    return clean, mods


def tar_at(distances: list[float], threshold: float) -> float:
    if not distances:
        return float("nan")
    accepted = sum(1 for d in distances if d <= threshold)
    return 100.0 * accepted / len(distances)


def main() -> None:
    sweep = json.loads(SWEEP_JSON.read_text(encoding="utf-8"))
    clean_dists, mods_dists = load_genuine_distances()
    thresholds_cfg = json.loads(THRESHOLDS_JSON.read_text(encoding="utf-8"))
    deployed_tau = thresholds_cfg["gate"]["tau_accept"]

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
                "family": "eer_reference",
            }
        )

    payload = {
        "n_clean_genuine_pairs": len(clean_dists),
        "n_mods_genuine_pairs": len(mods_dists),
        "impostor_pool_unique_pairs": sweep["unique_pairs"],
        "impostor_pool_source": "reports/independence/lbph_lfw1/far_sweep.json (full LFW1 cross-identity, YuNet, native predict_collect scale)",
        "genuine_pool_source": "outputs/benchmark/accuracy_ratio_verification_full_pairs.csv (same detector/crop/equalization/dataset, verified same scale)",
        "rows": rows,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# LBPH FAR-target sweep vs TAR - full LFW1",
        "",
        f"Impostor pool: {sweep['unique_pairs']:,} unique cross-identity pairs "
        "(full LFW1, YuNet, native predict_collect scale) - "
        "reports/independence/lbph_lfw1/far_sweep.json.",
        f"Genuine pool: {len(clean_dists)} clean-baseline pairs, "
        f"{len(mods_dists)} pooled 41-modification pairs - "
        "outputs/benchmark/accuracy_ratio_verification_full_pairs.csv.",
        "",
        "Each FAR-target row picks a threshold from the impostor-only pool, "
        "then reports what fraction of the (separately-collected) genuine "
        "pairs would clear that same threshold. The EER rows are NOT FAR "
        "targets - they are this run's own break-even point, shown for "
        "reference only (not frozen, not comparable across runs - see "
        "robustness-protocol-map skill Sec 2).",
        "",
        "| Operating point | Realized FAR | Raw threshold | Clean TAR | Overall TAR (41 mods) |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        far_col = format_far(r["realized_far_ppm"]) if r["realized_far_ppm"] is not None else "-"
        lines.append(
            f"| {r['label']} | {far_col} | {r['raw_threshold']:.4f} | "
            f"{r['clean_tar_percent']:.2f}% | {r['overall_tar_percent']:.2f}% |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[SAVE] {OUT_JSON}")
    print(f"[SAVE] {OUT_MD}")


if __name__ == "__main__":
    main()
