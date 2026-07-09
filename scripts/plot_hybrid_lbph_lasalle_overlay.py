"""Overlay the raw LBPH distance KDE curves across the La Salle runs of the hybrid
(LBPH + SFace cascade) independence test: lsdb1, lsdb2_light, lsdb2_medium.

Companion to ``plot_independence_overlay.py`` (same ``compute_kde_curve`` primitive,
same Agg/matplotlib conventions) but built specifically for
``src/hybrid/independence_test.py``'s per-dataset outputs: each dataset's own
``comparisons.csv`` -> ``mean_lbph_distance`` column, which for a 1-iteration run
(all three below) equals the raw per-pair LBPH chi-square distance - the hybrid
track never normalizes this value (its ``lbph_rank_thresholds`` only ever populates
``raw_threshold``; ``normalized_threshold`` is always 0.0).

Y-axis is COUNT, not density: each KDE curve is scaled by ``n * bin_width`` (the
same trick ``src/independence_plots.save_distance_histogram`` uses to overlay a KDE
on a count histogram), using one shared bin width across all three series so the
counts stay directly comparable. X-axis is zoomed to the pooled [min, max] of the
three datasets' raw distances, +/- ``--buffer``.

Usage:
    python scripts/plot_hybrid_lbph_lasalle_overlay.py
    python scripts/plot_hybrid_lbph_lasalle_overlay.py --buffer 5 --bins 30
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from src.independence_plots import compute_kde_curve  # noqa: E402

COLOR_CYCLE = ["#1f77b4", "#d62728", "#2ca02c"]

# label -> comparisons.csv (mean_lbph_distance column; 1 iteration => raw distance)
DATASETS: dict[str, str] = {
    "LSDB1": "outputs/hybrid/independence_test_lsdb1/comparisons.csv",
    "LSDB2 (light)": "outputs/hybrid/independence_test/comparisons.csv",
    "LSDB2 (medium)": "outputs/hybrid/independence_test_lsdb2_medium/comparisons.csv",
}


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def load_raw_lbph_distances(path: Path) -> np.ndarray:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        values = np.array(
            [float(row["mean_lbph_distance"]) for row in reader], dtype=np.float64
        )
    return values[np.isfinite(values)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--buffer", type=float, default=2.0,
        help="Padding added outside [min, max] of the pooled raw distances (default: 2.0).",
    )
    parser.add_argument(
        "--bins", type=int, default=40,
        help="Bin count used only to derive the shared bin-width for count scaling (default: 40).",
    )
    parser.add_argument("--curve-points", type=int, default=500)
    parser.add_argument(
        "--output", type=Path,
        default=PROJECT_ROOT / "reports" / "independence" / "overlay" / "hybrid_lbph_lasalle_overlay.png",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    series: dict[str, np.ndarray] = {}
    for label, rel_path in DATASETS.items():
        path = PROJECT_ROOT / rel_path
        if not path.exists():
            raise SystemExit(f"[ERROR] {label}: missing {path}")
        series[label] = load_raw_lbph_distances(path)

    all_values = np.concatenate(list(series.values()))
    data_min, data_max = float(np.min(all_values)), float(np.max(all_values))
    xlim = (data_min - args.buffer, data_max + args.buffer)
    bin_width = (xlim[1] - xlim[0]) / args.bins

    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for (label, values), color in zip(series.items(), COLOR_CYCLE):
        x, y, _bandwidth = compute_kde_curve(values, points=args.curve_points)
        y_count = y * values.size * bin_width
        ax.plot(
            x, y_count, color=color, linewidth=2.2,
            label=f"{label} (n={values.size}, raw min={values.min():.1f} max={values.max():.1f})",
        )

    ax.set_title("Hybrid Independence Test — LBPH Raw-Distance KDE Overlay (La Salle datasets)")
    ax.set_xlabel("LBPH distance (raw, chi-square)")
    ax.set_ylabel(f"Count ({args.bins}-bin-equivalent KDE)")
    ax.set_xlim(*xlim)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9, framealpha=0.9)

    footnote = (
        f"x-range = pooled [min, max] ± {args.buffer:g} buffer "
        f"({xlim[0]:.2f}–{xlim[1]:.2f} raw distance); y = Gaussian KDE (Silverman bandwidth) "
        f"scaled to an equivalent {args.bins}-bin count (shared bin width={bin_width:.3f}). "
        "No cross-dataset normalization; each engine call is 1 iteration, so mean_lbph_distance == raw distance."
    )
    fig.text(0.01, 0.01, footnote, fontsize=7.5, color="#555555")
    fig.tight_layout(rect=(0, 0.05, 1, 1))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=200)
    plt.close(fig)

    print(f"[SAVE] {args.output}")
    for label, values in series.items():
        print(
            f"  {label}: n={values.size} min={values.min():.3f} "
            f"max={values.max():.3f} mean={values.mean():.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
