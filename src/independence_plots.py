"""Shared plotting for the independence tests (histogram + FAR curve).

These helpers were previously copy-pasted into every ``*_light_front.py`` file.
They now live here so the classical mains, the light-front variants, and the
hybrid test all render the SAME two paper figures:

* ``distance_histogram.png`` - the impostor-distance distribution with the spec
  k-th-error-pair threshold marked (a KDE overlay smooths the shape). Shows how
  well a model separates impostors.
* ``far_curve.png`` - false-accept rate (ppm, log scale) vs. match threshold,
  built straight from an ``error_pair_report`` result, with the spec operating
  point highlighted. This is the visual of the rank-based threshold method.

matplotlib is imported lazily (Agg backend) so importing this module stays cheap
for callers that only need :func:`compute_kde_curve`.
"""

from __future__ import annotations

import os
from typing import Sequence

import numpy as np


# --------------------------------------------------------------------------- #
# matplotlib (lazy, headless)
# --------------------------------------------------------------------------- #
def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _ensure_parent(output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)


# --------------------------------------------------------------------------- #
# NumPy-only Gaussian KDE (no scipy dependency at plot time)
# --------------------------------------------------------------------------- #
def compute_kde_curve(
    values: Sequence[float],
    points: int = 500,
    bandwidth: float | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Smooth density curve for *values* via a Gaussian KDE (Silverman default).

    Returns ``(x, y, used_bandwidth)``. Empty input yields empty arrays.
    """
    arr = np.asarray(values, dtype=np.float64)

    if arr.size == 0:
        return np.array([]), np.array([]), 0.0

    if arr.size == 1:
        x = np.linspace(arr[0] - 1.0, arr[0] + 1.0, points)
        y = np.zeros_like(x)
        y[np.argmin(np.abs(x - arr[0]))] = 1.0
        return x, y, 1.0

    data_min = float(np.min(arr))
    data_max = float(np.max(arr))
    data_std = float(np.std(arr, ddof=1))

    if bandwidth is None:
        # Silverman's rule of thumb.
        bandwidth = 1.06 * data_std * (arr.size ** (-1 / 5))
    if bandwidth <= 0:
        bandwidth = max((data_max - data_min) / 50.0, 1.0)

    padding = bandwidth * 3.0
    x = np.linspace(data_min - padding, data_max + padding, points)
    # Chunk the kernel evaluation so a large sample doesn't allocate an
    # (points x n) matrix all at once.
    y = np.zeros_like(x)
    block = 4096
    for b0 in range(0, arr.size, block):
        chunk = arr[b0: b0 + block]
        z = (x[:, None] - chunk[None, :]) / bandwidth
        y += np.exp(-0.5 * z * z).sum(axis=1) / np.sqrt(2 * np.pi)
    y /= arr.size * bandwidth
    return x, y, float(bandwidth)


# --------------------------------------------------------------------------- #
# Figure 1: distance histogram (+ KDE overlay + threshold line)
# --------------------------------------------------------------------------- #
def save_distance_histogram(
    distances: Sequence[float],
    output_path: str,
    *,
    threshold: float | None = None,
    bins: int = 40,
    title: str = "Independence Test: Inter-Identity Distance Histogram",
    xlabel: str = "Normalized Distance (0-100)",
    kde_overlay: bool = True,
    curve_points: int = 500,
    curve_bandwidth: float | None = None,
    xlim: tuple[float, float] | None = None,
    far_percent: float | None = None,
    dpi: int = 200,
) -> float:
    """Histogram of impostor distances; area left of *threshold* = false accepts.

    Returns the KDE bandwidth used (0.0 if no overlay was drawn).
    """
    plt = _pyplot()
    _ensure_parent(output_path)

    values = np.asarray(distances, dtype=np.float64)
    values = values[np.isfinite(values)]

    fig, ax = plt.subplots(figsize=(10, 6))
    if values.size:
        ax.hist(values, bins=bins, edgecolor="black", alpha=0.75, color="#4c72b0")

    used_bandwidth = 0.0
    if kde_overlay and values.size > 1:
        x, y, used_bandwidth = compute_kde_curve(
            values, points=curve_points, bandwidth=curve_bandwidth
        )
        if x.size:
            # Scale the density to the histogram's count axis for a readable overlay.
            counts, edges = np.histogram(values, bins=bins)
            bin_w = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0
            ax.plot(x, y * values.size * bin_w, color="#dd8452", lw=2, label="KDE")

    if threshold is not None:
        ax.axvline(threshold, color="#c44e52", ls="--", lw=2)
        ymax = ax.get_ylim()[1]
        label = f"Threshold = {threshold:.4g}"
        if far_percent is not None:
            label += f"\nFAR = {far_percent:.3f}%"
        ax.text(threshold, ymax * 0.95, label, rotation=90,
                va="top", ha="right", fontsize=9, color="#c44e52")

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    if xlim is not None:
        ax.set_xlim(*xlim)
    ax.grid(True, alpha=0.3)
    if kde_overlay and values.size > 1:
        ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return used_bandwidth

# --------------------------------------------------------------------------- #
# Figure 1b: distance curve plot (pure KDE, no histogram)
# --------------------------------------------------------------------------- #
def save_distance_curve_plot(
    distances: Sequence[float],
    output_path: str,
    *,
    threshold: float | None = None,
    title: str = "Independence Test: Inter-Identity Distance Curve",
    xlabel: str = "Normalized Distance",
    curve_points: int = 500,
    curve_bandwidth: float | None = None,
    xlim: tuple[float, float] | None = None,
    dpi: int = 200,
) -> float:
    """Save a curve-style distance distribution plot (KDE density only)."""
    plt = _pyplot()
    _ensure_parent(output_path)

    values = np.asarray(distances, dtype=np.float64)
    values = values[np.isfinite(values)]

    fig, ax = plt.subplots(figsize=(10, 6))
    
    used_bandwidth = 0.0
    if values.size > 1:
        x, y, used_bandwidth = compute_kde_curve(
            values, points=curve_points, bandwidth=curve_bandwidth
        )
        if x.size > 0 and y.size > 0:
            ax.plot(x, y, linewidth=2, color="#4c72b0")

            if threshold is not None:
                ax.axvline(threshold, color="#c44e52", ls="--", lw=2)
                ymax = ax.get_ylim()[1]
                label = f"Threshold = {threshold:.4g}"
                ax.text(threshold, ymax * 0.95, label, rotation=90,
                        va="top", ha="right", fontsize=9, color="#c44e52")

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Estimated Frequency Density")
    
    if xlim is not None:
        ax.set_xlim(*xlim)
    elif values.size > 0:
        ax.set_xlim(max(0, np.min(values) - 5), 100)
    else:
        ax.set_xlim(0, 100)
        
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return used_bandwidth


# --------------------------------------------------------------------------- #
# Figure 2: FAR-vs-threshold curve (from an error_pair_report)
# --------------------------------------------------------------------------- #
def save_far_curve(
    report: dict,
    output_path: str,
    *,
    model_label: str = "",
    engine_label: str = "",
    threshold_field: str = "raw_threshold",
    xlabel: str = "Match threshold (raw feature distance)",
    dpi: int = 200,
) -> bool:
    """Plot false-accept rate (ppm, log-y) vs. match threshold.

    *report* is an ``error_pair_report`` / ``error_pair_report_from_topk`` result
    with ``"spec"`` and ``"curve"`` entries. *threshold_field* selects the x scale
    (``"raw_threshold"`` or ``"normalized_threshold"``). Returns True if written.
    """
    curve = report.get("curve") or []
    if not curve:
        return False

    plt = _pyplot()
    _ensure_parent(output_path)

    thr = [float(e[threshold_field]) for e in curve]
    far = [max(float(e["realized_far_ppm"]), 1e-9) for e in curve]
    order = np.argsort(thr)
    thr = list(np.asarray(thr)[order])
    far = list(np.asarray(far)[order])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.semilogy(thr, far, "o-", color="#4c72b0", lw=2, ms=4, label="FAR curve")

    spec = report.get("spec")
    if spec:
        sx = float(spec[threshold_field])
        sy = max(float(spec["realized_far_ppm"]), 1e-9)
        ax.scatter([sx], [sy], color="#c44e52", zorder=5, s=70,
                   label=f"spec k={spec['error_pair_rank']}")
        ax.annotate(
            f"  spec: FAR={spec['realized_far_ppm']:.1f} ppm\n"
            f"  thr={spec[threshold_field]:.4g}",
            (sx, sy), fontsize=9, color="#c44e52", va="center",
        )

    title = "Independence Test: FAR vs Threshold (rank-based)"
    if model_label or engine_label:
        tag = " / ".join(t for t in (model_label, engine_label) if t)
        title = f"{tag} - FAR vs Threshold (rank-based k-th error pair)"
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("False-accept rate (ppm, log scale)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return True
