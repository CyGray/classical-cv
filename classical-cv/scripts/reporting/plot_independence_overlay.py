"""Overlay several datasets' impostor-distance curves for ONE engine (LBPH or
SFace) onto a single figure, one color per dataset.

This is the multi-dataset companion to ``plot_independence_comparisons.py``
(which renders a single run's histogram+curve). Point it at N per-dataset
inputs for the same engine and it draws N colored curves on shared axes so
the datasets can be compared directly - it does NOT merge LBPH and SFace
onto the same axes (their distance metrics are on incompatible scales; run
this once per engine instead, see --preset below).

Two render modes (--mode):

* ``density`` - a distance-density curve, the "hist + curve" shape used
  everywhere else in this repo. Exact (solid) when a raw comparisons CSV is
  on disk: a real Gaussian KDE over the per-pair distances. Approximate
  (dashed) when only a summary.json survives: reconstructed via monotone
  (PCHIP) interpolation of whatever CDF points the report kept - LBPH's
  ``distance_statistics.percentiles`` (full 0-100 range) if present,
  otherwise the rank-based FAR curve.
* ``far`` - false-accept rate (%, log scale) vs. threshold, i.e. the
  multi-dataset version of this repo's existing ``far_curve.png``. Plots the
  real reported numbers directly with no differentiation, so it's the right
  choice when a dataset only has a *rank*-based curve to offer: those curves
  sample threshold space geometrically (ranks 1,2,4,8,...), which a log-y FAR
  axis represents naturally but a linear density axis cannot (differentiating
  it produces a spike that overstates precision the sparse tail doesn't have).

SFace distances are plotted as ``1 - cosine`` ("cosine distance"), matching
the convention already used by ``src/hybrid/independence_test.py`` for its
own per-dataset plots.

Usage:
    # Ready-made mapping for this repo's current lsdb1/lsdb2/lfw1/lfw2 reports:
    python scripts/reporting/plot_independence_overlay.py --preset lbph-datasets
    python scripts/reporting/plot_independence_overlay.py --preset sface-datasets

    # Or build your own set of series:
    python scripts/reporting/plot_independence_overlay.py --engine lbph --mode density \\
        --series "LSDB1=reports/independence/lbph_latest/lsdb1_comparisons.csv" \\
        --series "LFW1=reports/independence/lbph_latest/lfw1_summary.json" \\
        --output reports/independence/overlay/lbph_custom.png
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
from scipy.interpolate import PchipInterpolator  # noqa: E402

from src.independence_plots import compute_kde_curve  # noqa: E402

COLOR_CYCLE = [
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd",
    "#ff7f0e", "#17becf", "#e377c2", "#7f7f7f",
]

ENGINE_DISTANCE_CANDIDATES = {
    "lbph": ["distance_normalized", "normalized_distance", "mean_lbph_distance",
             "raw_distance", "distance"],
    "sface": ["mean_sface_cosine", "sface_cosine", "cosine",
              "distance_normalized", "normalized_distance", "raw_distance", "distance"],
}

# Ready-made mapping for the datasets already sitting in this repo (see the
# module docstring). "sface-datasets" pulls from the hybrid independence
# reports since standalone SFace-only reports don't exist per-dataset yet, and
# defaults to FAR mode since 3 of its 4 datasets only have the rank curve.
PRESETS: dict[str, dict] = {
    "lbph-datasets": {
        "engine": "lbph",
        "mode": "density",
        "series": {
            "LSDB1": "outputs/independence/lbph/old/lbph_latest/lsdb1_comparisons.csv",
            "LSDB2 (light)": "outputs/independence/lbph/old/lbph_latest/lsdb2_light_comparisons.csv",
            "LFW1": "outputs/independence/lbph/old/lbph_latest/lfw1_summary.json",
            "LFW2 (light)": "outputs/independence/lbph/old/lbph_latest/summary.json",
        },
        "output": "reports/independence/overlay/lbph_cross_dataset_curve.png",
    },
    "sface-datasets": {
        "engine": "sface",
        "mode": "far",
        "series": {
            "LSDB1": "outputs/independence/hybrid/lsdb1/summary.json",
            "LSDB2 (light)": "outputs/independence/hybrid/lsdb2_light/summary.json",
            "LSDB2 (medium)": "outputs/independence/hybrid/lsdb2_medium/summary.json",
            "LFW1": "outputs/independence/hybrid/lfw1/summary.json",
            "LFW2 (light)": "outputs/independence/hybrid/lfw2_light/summary.json",
            "LFW2 (medium)": "outputs/independence/hybrid/lfw2_medium/summary.json",
        },
        "output": "reports/independence/overlay/sface_cross_dataset_curve.png",
    },
}


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _pick_key(available: list[str], forced: str | None, engine: str) -> str:
    if forced:
        for c in available:
            if c.lower() == forced.lower():
                return c
        raise SystemExit(f"[ERROR] --column '{forced}' not found. Available: {available}")
    lower_map = {c.lower(): c for c in available}
    for cand in ENGINE_DISTANCE_CANDIDATES[engine]:
        if cand in lower_map:
            return lower_map[cand]
    for c in available:
        cl = c.lower()
        if "dist" in cl and "path" not in cl and "identity" not in cl:
            return c
    raise SystemExit(
        f"[ERROR] Could not auto-detect a '{engine}' distance column. Available: {available}. "
        "Pass --column explicitly."
    )


def _load_raw_csv(path: Path, forced_column: str | None, engine: str) -> tuple[np.ndarray, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f"[ERROR] {path} has no header row.")
        key = _pick_key(list(reader.fieldnames), forced_column, engine)
        values: list[float] = []
        for row in reader:
            raw = (row.get(key) or "").strip()
            if raw:
                try:
                    values.append(float(raw))
                except ValueError:
                    pass
        return np.asarray(values, dtype=np.float64), key


def _load_values(path: Path, engine: str, column: str | None) -> tuple[np.ndarray, str]:
    """Raw per-pair distances from a CSV, with the SFace cosine->cosine-distance flip."""
    values, col = _load_raw_csv(path, column, engine)
    note_col = col
    if engine == "sface" and "cosine" in col.lower() and "dist" not in col.lower():
        values = 1.0 - values
        note_col = f"1-{col}"
    return values, note_col


# --------------------------------------------------------------------------- #
# density mode: exact KDE, or PCHIP-reconstructed density from CDF points
# --------------------------------------------------------------------------- #
def _dedup_increasing(xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """PCHIP needs strictly increasing x; keep the first point of any tie."""
    keep_x, keep_y = [xs[0]], [ys[0]]
    for x, y in zip(xs[1:], ys[1:]):
        if x > keep_x[-1]:
            keep_x.append(x)
            keep_y.append(y)
    return np.asarray(keep_x), np.asarray(keep_y)


def _density_from_cdf_points(xs: np.ndarray, cdf: np.ndarray, points: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Monotone cubic (PCHIP) fit through empirical CDF points, then differentiate.

    Only sensible for evenly-ish sampled CDF points (e.g. percentiles). Rank
    curves sample threshold space geometrically instead - use --mode far for
    those (see module docstring for why differentiating them is misleading).
    """
    order = np.argsort(xs)
    xs, cdf = _dedup_increasing(xs[order], cdf[order])
    if len(xs) < 3:
        return np.array([]), np.array([])
    max_secant = float(np.max(np.diff(cdf) / np.diff(xs)))
    interp = PchipInterpolator(xs, cdf, extrapolate=False)
    deriv = interp.derivative()
    x_grid = np.linspace(xs[0], xs[-1], points)
    y = np.asarray(deriv(x_grid), dtype=np.float64)
    y = np.clip(np.nan_to_num(y, nan=0.0), 0.0, max_secant)
    return x_grid, y


def _percentile_cdf_points(stats: dict) -> tuple[np.ndarray, np.ndarray]:
    pct = stats["percentiles"]
    xs = [float(stats["min_distance"])]
    cdf = [0.0]
    for k in sorted(pct, key=lambda s: float(s)):
        xs.append(float(pct[k]))
        cdf.append(float(k) / 100.0)
    xs.append(float(stats["max_distance"]))
    cdf.append(1.0)
    return np.asarray(xs), np.asarray(cdf)


def _load_series_density(path: Path, engine: str, column: str | None) -> dict:
    if path.suffix.lower() == ".csv":
        values, note_col = _load_values(path, engine, column)
        x, y, _bw = compute_kde_curve(values, points=500)
        return {"x": x, "y": y, "linestyle": "-", "marker": None,
                "note": f"exact KDE, n={values.size:,} ({note_col})"}

    payload = json.loads(path.read_text(encoding="utf-8-sig"))

    if engine == "lbph":
        stats = payload.get("distance_statistics")
        if stats and stats.get("percentiles"):
            xs, cdf = _percentile_cdf_points(stats)
            x, y = _density_from_cdf_points(xs, cdf)
            n = stats.get("count")
            note = "approx. from percentiles" + (f", n={n:,}" if n else "")
            return {"x": x, "y": y, "linestyle": "--", "marker": None, "note": note}

    raise SystemExit(
        f"[ERROR] {path}: no distance_statistics.percentiles for engine={engine!r} - "
        "this report only has a rank/FAR curve, which doesn't reconstruct into a "
        "trustworthy density (see module docstring). Use --mode far instead."
    )


# --------------------------------------------------------------------------- #
# far mode: false-accept rate (%, log scale) vs threshold - no differentiation
# --------------------------------------------------------------------------- #
def _far_points_from_values(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    xs = np.sort(values)
    n = xs.size
    far_percent = 100.0 * (np.arange(1, n + 1) / n)
    return xs, far_percent


def _far_points_from_curve(curve: list[dict], x_field: str) -> tuple[np.ndarray, np.ndarray]:
    xs = np.array([float(e[x_field]) for e in curve], dtype=np.float64)
    far = np.array([max(float(e["realized_far_percent"]), 1e-6) for e in curve], dtype=np.float64)
    order = np.argsort(xs)
    return xs[order], far[order]


def _load_series_far(path: Path, engine: str, column: str | None) -> dict:
    if path.suffix.lower() == ".csv":
        values, note_col = _load_values(path, engine, column)
        x, y = _far_points_from_values(values)
        return {"x": x, "y": y, "linestyle": "-", "marker": None,
                "note": f"empirical FAR curve, n={values.size:,} ({note_col})"}

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    block = payload.get(f"{engine}_rank_thresholds") or payload.get("error_pair_thresholds")
    if not block or not block.get("curve"):
        raise SystemExit(f"[ERROR] {path}: no usable '{engine}' rank/FAR curve found.")
    x_field = "normalized_threshold" if engine == "lbph" else "raw_threshold"
    x, y = _far_points_from_curve(block["curve"], x_field)
    n = block.get("comparisons")
    note = "reported FAR-rank curve" + (f", n={n:,}" if n else "") + f" ({len(x)} points)"
    return {"x": x, "y": y, "linestyle": "-", "marker": "o", "note": note}


def load_series(path: Path, engine: str, column: str | None, mode: str) -> dict:
    loader = _load_series_density if mode == "density" else _load_series_far
    return loader(path, engine, column)


def plot_overlay(
    series: dict[str, dict], *, title: str, xlabel: str, ylabel: str,
    yscale: str, footnote: str, output_path: Path,
) -> None:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for (label, data), color in zip(series.items(), COLOR_CYCLE):
        if data["x"].size == 0:
            print(f"[WARN] {label}: nothing plottable, skipping.")
            continue
        ax.plot(
            data["x"], data["y"], color=color, linewidth=2.2,
            linestyle=data["linestyle"], marker=data["marker"],
            markersize=5, markevery=1,
            label=f"{label} — {data['note']}",
        )
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if yscale == "log":
        ax.set_yscale("log")
        ax.grid(True, which="both", alpha=0.3)
    else:
        ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8.5, framealpha=0.9)
    fig.text(0.01, 0.01, footnote, fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    print(f"[SAVE] {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overlay one engine's distance curve across multiple datasets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--preset", choices=sorted(PRESETS), default=None,
                        help="Use a ready-made label->path mapping (see module docstring).")
    parser.add_argument("--engine", choices=["lbph", "sface"], default=None,
                        help="Required unless --preset is given.")
    parser.add_argument("--mode", choices=["density", "far"], default=None,
                        help="Required unless --preset is given.")
    parser.add_argument("--series", action="append", default=[], metavar="LABEL=PATH",
                        help="Repeatable. Adds to / overrides the preset's series by label.")
    parser.add_argument("--column", default=None, help="Force the CSV distance column name.")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--title", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    engine = args.engine
    mode = args.mode
    series_paths: dict[str, str] = {}
    output_path = args.output

    if args.preset:
        preset = PRESETS[args.preset]
        engine = engine or preset["engine"]
        mode = mode or preset["mode"]
        series_paths.update(preset["series"])
        if output_path is None:
            output_path = PROJECT_ROOT / preset["output"]

    for item in args.series:
        if "=" not in item:
            raise SystemExit(f"[ERROR] --series must be LABEL=PATH, got: {item}")
        label, raw_path = item.split("=", 1)
        series_paths[label] = raw_path

    if engine is None:
        raise SystemExit("[ERROR] --engine is required unless --preset is given.")
    if mode is None:
        raise SystemExit("[ERROR] --mode is required unless --preset is given.")
    if not series_paths:
        raise SystemExit("[ERROR] No series given (use --preset or --series).")
    if output_path is None:
        raise SystemExit("[ERROR] --output is required when not using --preset.")

    engine_label = "LBPH" if engine == "lbph" else "SFace"
    xlabel = (
        "Normalized inter-identity distance (0-100)" if engine == "lbph"
        else "Cosine distance (1 - cosine similarity)"
    )
    if mode == "density":
        ylabel = "Estimated density"
        yscale = "linear"
        footnote = (
            "Solid = exact KDE from raw pairs.  Dashed = approximate, reconstructed from "
            "published percentiles (no raw sample on disk)."
        )
        title = args.title or f"{engine_label} Independence Test: Cross-Dataset Distance Curve"
    else:
        ylabel = "False-accept rate (%, log scale)"
        yscale = "log"
        footnote = (
            "Plain line = empirical FAR curve from raw pairs.  Marked line = the report's own "
            "rank-based FAR curve (fewer, geometrically-spaced points; no raw sample on disk)."
        )
        title = args.title or f"{engine_label} Independence Test: Cross-Dataset FAR Curve"

    series: dict[str, dict] = {}
    for label, raw_path in series_paths.items():
        path = Path(raw_path)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        if not path.is_file() and "outputs" in str(path):
            alt_path = Path(str(path).replace("outputs", "reports"))
            if alt_path.is_file():
                path = alt_path
        if not path.is_file() and "lbph_latest" in str(path):
            alt_path = Path(str(path).replace("independence/lbph_latest", "independence/lbph/old/lbph_latest").replace("independence\\lbph_latest", "independence\\lbph\\old\\lbph_latest"))
            if alt_path.is_file():
                path = alt_path
        if not path.is_file():
            raise SystemExit(f"[ERROR] Not a file: {path}")
        print(f"[LOAD] {label} <- {path}")
        data = load_series(path, engine, args.column, mode)
        print(f"       {data['note']}")
        series[label] = data

    plot_overlay(series, title=title, xlabel=xlabel, ylabel=ylabel,
                 yscale=yscale, footnote=footnote, output_path=output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
