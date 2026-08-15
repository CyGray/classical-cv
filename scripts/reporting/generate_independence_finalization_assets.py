"""Regenerate vector assets for the 2026-08-10 independence finalization.

Inputs are recorded canonical JSON/CSV artifacts.  This script intentionally
does not derive a replacement threshold: it visualizes the frozen LFW
deployment boundaries on the fresh LSDB clean impostor sweep.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde


ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def values(csv_path: Path, key: str) -> np.ndarray:
    with csv_path.open(encoding="utf-8", newline="") as f:
        return np.asarray([float(row[key]) for row in csv.DictReader(f)], dtype=float)


def density_panel(ax, x: np.ndarray, title: str, xlabel: str, markers: list[tuple[float, str, str]]) -> None:
    ax.hist(x, bins=24, density=True, alpha=0.28, color="#2a6fdb", label="LSDB ordered impostor pairs (n=756)")
    grid = np.linspace(x.min(), x.max(), 400)
    ax.plot(grid, gaussian_kde(x)(grid), color="#1b4f9c", linewidth=1.8, label="KDE")
    ymax = ax.get_ylim()[1]
    for i, (threshold, label, color) in enumerate(markers):
        ax.axvline(threshold, color=color, linewidth=1.5, linestyle=(0, (1.5, 2.5)))
        ax.text(threshold, ymax * (0.90 - 0.16 * i), f" {label}\n {threshold:.4g}", rotation=90,
                va="top", ha="left", fontsize=7.5, color=color)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Density")
    ax.grid(alpha=0.20)
    ax.legend(fontsize=7.2, loc="upper right")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tradeoff-output", type=Path, required=True)
    args = parser.parse_args()

    indep = ROOT / "docs/results/independence_test/independence"
    lbph_lfw = load_json(indep / "lbph_lfw1/native_predict_scale_yunet.json")
    sface_lfw = load_json(indep / "sface_lfw1/standalone_l2_yunet.json")
    gate = load_json(args.run_dir / "hybrid_lasalle_processed/summary.json")["thresholds"]
    pairs = args.run_dir / "hybrid_lasalle_processed/comparisons.csv"
    lbph = values(pairs, "mean_lbph_distance")
    sface = values(pairs, "mean_sface_l2")

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), constrained_layout=True)
    density_panel(
        axes[0], lbph, "LBPH: deployed LFW boundary on LSDB", "Native predict_collect() distance",
        [(lbph_lfw["raw_threshold"], "tau_accept (LFW, frozen)", "#111111"),
         (gate["lbph_tau_reject"], "tau_reject (LFW, frozen)", "#b22222")],
    )
    density_panel(
        axes[1], sface, "SFace: deployed LFW boundary on LSDB", "SFace L2 distance",
        [(sface_lfw["raw_threshold_l2"], "standalone LFW boundary", "#111111"),
         (gate["sface_l2_genuine"], "deployed hybrid boundary", "#b22222")],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, format="svg")
    print(f"[OK] {args.output}")

    tradeoff = load_json(indep / "tau_reject_tradeoff/curve.json")
    points = tradeoff["points"]
    x = np.asarray([p["tau_reject"] for p in points])
    fig, ax = plt.subplots(figsize=(6.8, 4.0), constrained_layout=True)
    ax.plot(x, [p["genuine_hard_reject_pct"] for p in points], color="#b22222", marker="o",
            label="Genuine hard reject")
    ax.plot(x, [p["impostor_escalated_pct"] for p in points], color="#1b4f9c", marker="s",
            label="Impostor escalation (1:1 proxy)")
    ax.axvline(gate["lbph_tau_reject"], color="#111111", linewidth=1.5, linestyle=(0, (1.5, 2.5)),
               label=f"Deployed tau_reject = {gate['lbph_tau_reject']:.2f}")
    ax.set_xlabel("Candidate LBPH tau_reject (native predict_collect() distance)")
    ax.set_ylabel("Rate (%)")
    ax.set_title("LFW gate trade-off: no favorable separation knee", fontsize=10, fontweight="bold")
    ax.grid(alpha=0.20)
    ax.legend(fontsize=7.5)
    args.tradeoff_output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.tradeoff_output, format="svg")
    print(f"[OK] {args.tradeoff_output}")


if __name__ == "__main__":
    main()
