#!/usr/bin/env python3
"""Generate native predict scale independence test reports and plots.

Creates /reports/independence/ containing:
1. standalone_lbph_independence.png  (Chi-Square distance, threshold 70.6089 / 67.0084)
2. standalone_sface_independence.png (L2 distance, threshold 1.018)
3. hybrid_lbph_independence.png      (Chi-Square distance, tau_accept 67.0084 & tau_reject 76.85)
4. hybrid_sface_independence.png    (L2 distance, threshold 1.018)
5. independence_overview_grid.png   (2x2 combined panel)
6. independence_metrics.json         (Raw distance statistics and threshold analysis)
7. independence_report.md           (Structured markdown report)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2 as cv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "classical-cv"))

from src.lbph.preprocess import IMG_SIZE, normalize_face

# Output directory: root /reports/independence/
OUTPUT_DIR = PROJECT_ROOT / "reports" / "independence"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def compute_gaussian_kde(values: np.ndarray, points: int = 500) -> tuple[np.ndarray, np.ndarray, float]:
    """Compute Gaussian KDE using Silverman's rule."""
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return np.array([]), np.array([]), 0.0

    if arr.size > 50000:
        rng = np.random.default_rng(42)
        kde_sample = rng.choice(arr, size=50000, replace=False)
    else:
        kde_sample = arr

    data_min = float(np.min(arr))
    data_max = float(np.max(arr))
    data_std = float(np.std(kde_sample, ddof=1)) if kde_sample.size > 1 else 1.0

    bandwidth = 1.06 * data_std * (kde_sample.size ** (-1 / 5)) if data_std > 0 else 1.0
    if bandwidth <= 0:
        bandwidth = max((data_max - data_min) / 50.0, 1.0)

    padding = bandwidth * 3.0
    x = np.linspace(data_min - padding, data_max + padding, points)
    
    y = np.zeros_like(x)
    block = 4096
    for b0 in range(0, kde_sample.size, block):
        chunk = kde_sample[b0 : b0 + block]
        z = (x[:, None] - chunk[None, :]) / bandwidth
        y += np.exp(-0.5 * z * z).sum(axis=1) / np.sqrt(2 * np.pi)
    y /= kde_sample.size * bandwidth
    return x, y, float(bandwidth)


def load_lbph_distances() -> tuple[np.ndarray, dict]:
    """Compute raw LBPH predict_collect Chi-Square distances on La Salle DB1."""
    dataset_dir = PROJECT_ROOT / "classical-cv" / "data" / "lasalle_db1_processed"
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    identities = sorted([d for d in os.listdir(dataset_dir) if (dataset_dir / d).is_dir()])
    faces = []
    for p in identities:
        img_path = dataset_dir / p / "light_front.jpg"
        img = cv.imread(str(img_path), cv.IMREAD_GRAYSCALE)
        if img is None:
            continue
        norm = normalize_face(img, img_size=IMG_SIZE, equalization="tan-triggs")
        faces.append(norm)

    recognizer = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(faces, np.arange(len(faces), dtype=np.int32))

    distances = []
    for i, face in enumerate(faces):
        collector = cv.face.StandardCollector_create()
        recognizer.predict_collect(face, collector)
        for label, d in collector.getResults(True):
            if int(label) != i:
                distances.append(float(d))

    arr = np.array(distances, dtype=np.float64)
    stats = {
        "count": len(arr),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr)),
        "p1": float(np.percentile(arr, 1)),
        "p5": float(np.percentile(arr, 5)),
        "p10": float(np.percentile(arr, 10)),
    }
    return arr, stats


def load_sface_distances() -> tuple[np.ndarray, dict]:
    """Compute raw SFace L2 distances on LFW feature database."""
    feature_path = PROJECT_ROOT / "deep-learning" / "features" / "lfw-sface.npy"
    if not feature_path.exists():
        feature_path = PROJECT_ROOT / "classical-cv" / "models" / "sface" / "impostors-lfw.npy"

    data = np.load(feature_path, allow_pickle=True)
    if isinstance(data, np.ndarray) and data.dtype == object:
        obj = data.item()
        embs = []
        for k, v in obj.items():
            if isinstance(v, dict) and "embeddings" in v:
                embs.append(v["embeddings"][0])
            elif isinstance(v, np.ndarray):
                embs.append(v)
        feats = np.array(embs, dtype=np.float32)
    else:
        feats = np.asarray(data, dtype=np.float32)

    # Normalize embeddings to unit norm
    norm = feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9)
    sim = (norm @ norm.T).astype(np.float32)
    # L2 distance = sqrt(max(0, 2 - 2 * cosine))
    l2_mat = np.sqrt(np.clip(2.0 - 2.0 * sim, 0.0, None))
    mask = ~np.eye(len(feats), dtype=bool)
    arr = l2_mat[mask].astype(np.float64)

    stats = {
        "count": len(arr),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr)),
        "p001": float(np.percentile(arr, 0.01)),
        "p01": float(np.percentile(arr, 0.1)),
        "p1": float(np.percentile(arr, 1)),
        "p5": float(np.percentile(arr, 5)),
    }
    return arr, stats


def plot_independence_figure(
    distances: np.ndarray,
    thresholds: list[dict],
    title: str,
    xlabel: str,
    output_path: Path,
    bins: int = 40,
    ambiguous_range: tuple[float, float] | None = None,
) -> None:
    """Plot Histogram + KDE Curve + Horizontal & Vertical Threshold Lines."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=200)

    # Histogram
    counts, edges, patches = ax.hist(
        distances, bins=bins, color="#34495e", alpha=0.6, edgecolor="#1a252f", linewidth=1.0, label="Impostor Pair Hist"
    )
    bin_width = edges[1] - edges[0]

    # KDE curve
    x_kde, y_kde, bw = compute_gaussian_kde(distances, points=500)
    # Scale KDE to count axis
    y_kde_scaled = y_kde * len(distances) * bin_width
    ax.plot(x_kde, y_kde_scaled, color="#2980b9", linewidth=2.5, label=f"KDE Density (bw={bw:.3f})")

    # Ambiguous band shading if applicable
    if ambiguous_range is not None:
        t_lo, t_hi = ambiguous_range
        ax.axvspan(t_lo, t_hi, color="#f39c12", alpha=0.2, label=f"Ambiguous Band [{t_lo:.2f}, {t_hi:.2f}]")

    # Process thresholds (horizontal + vertical lines)
    colors = ["#c0392b", "#d35400", "#8e44ad", "#27ae60"]
    for idx, thr in enumerate(thresholds):
        val = thr["value"]
        label_text = thr["label"]
        color = thr.get("color", colors[idx % len(colors)])

        # Interpolate KDE count height at threshold value
        y_val_scaled = float(np.interp(val, x_kde, y_kde_scaled))

        # Vertical line for threshold
        ax.axvline(val, color=color, linestyle="--", linewidth=2, label=f"{label_text} (x = {val:.4g})")

        # Horizontal line for threshold cut-off level
        ax.axhline(
            y_val_scaled,
            color=color,
            linestyle=":",
            linewidth=1.8,
            alpha=0.85,
            label=f"Horizontal Threshold Level (y = {y_val_scaled:.1f})",
        )

        # Annotation text
        ymax = ax.get_ylim()[1]
        ax.text(
            val,
            ymax * (0.92 - idx * 0.08),
            f"  {label_text}\n  x={val:.4g}, y={y_val_scaled:.1f}",
            color=color,
            fontsize=9.5,
            fontweight="bold",
            va="top",
            ha="left",
        )

    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=11, labelpad=8)
    ax.set_ylabel("Count (Impostor Comparisons)", fontsize=11, labelpad=8)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    print(f"[SAVE] Plot: {output_path}")


def main() -> int:
    print("[INFO] Starting native predict scale independence report generation...")

    # Load distances
    lbph_dist, lbph_stats = load_lbph_distances()
    sface_dist, sface_stats = load_sface_distances()

    print(f"[INFO] LBPH comparisons loaded: {len(lbph_dist):,} pairs")
    print(f"[INFO] SFace comparisons loaded: {len(sface_dist):,} pairs")

    # Defined Thresholds
    lbph_standalone_thr = 70.6089  # Rank-8 / canonical threshold
    sface_standalone_thr = 1.018   # L2 genuine threshold (frozen)

    tau_accept = 67.0084           # Deployed frozen LBPH tau_accept
    tau_reject = 76.85             # Deployed frozen LBPH tau_reject

    sface_hybrid_thr = 1.018       # Deployed SFace L2 genuine threshold

    # 1) Standalone LBPH Plot
    plot_independence_figure(
        distances=lbph_dist,
        thresholds=[{"value": lbph_standalone_thr, "label": "Standalone Threshold", "color": "#c0392b"}],
        title="Standalone LBPH Independence Test (Native Chi-Square Distance)",
        xlabel="Chi-Square Distance (Native Predict Scale)",
        output_path=OUTPUT_DIR / "standalone_lbph_independence.png",
    )

    # 2) Standalone SFace Plot
    plot_independence_figure(
        distances=sface_dist,
        thresholds=[{"value": sface_standalone_thr, "label": "L2 Genuine Threshold", "color": "#27ae60"}],
        title="Standalone SFace Independence Test (Native L2 Distance)",
        xlabel="L2 Distance (Native Predict Scale, FR_NORM_L2)",
        output_path=OUTPUT_DIR / "standalone_sface_independence.png",
    )

    # 3) Hybrid LBPH Plot (tau accept + tau reject)
    plot_independence_figure(
        distances=lbph_dist,
        thresholds=[
            {"value": tau_accept, "label": "tau_accept", "color": "#27ae60"},
            {"value": tau_reject, "label": "tau_reject", "color": "#c0392b"},
        ],
        title="Hybrid LBPH Independence Test (tau_accept & tau_reject)",
        xlabel="Chi-Square Distance (Native Predict Scale)",
        output_path=OUTPUT_DIR / "hybrid_lbph_independence.png",
        ambiguous_range=(tau_accept, tau_reject),
    )

    # 4) Hybrid SFace Plot
    plot_independence_figure(
        distances=sface_dist,
        thresholds=[{"value": sface_hybrid_thr, "label": "SFace Operating Threshold", "color": "#8e44ad"}],
        title="Hybrid SFace Independence Test (Native L2 Distance)",
        xlabel="L2 Distance (Native Predict Scale, FR_NORM_L2)",
        output_path=OUTPUT_DIR / "hybrid_sface_independence.png",
    )

    # 5) Multi-panel Grid (2x2) Overview
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), dpi=250)

    configs = [
        (
            axes[0, 0],
            lbph_dist,
            [{"value": lbph_standalone_thr, "label": "Standalone Thr (70.61)", "color": "#c0392b"}],
            "Standalone LBPH (Chi-Square Scale)",
            "Chi-Square Distance",
            None,
        ),
        (
            axes[0, 1],
            sface_dist,
            [{"value": sface_standalone_thr, "label": "L2 Genuine Thr (1.018)", "color": "#27ae60"}],
            "Standalone SFace (L2 Scale)",
            "L2 Distance",
            None,
        ),
        (
            axes[1, 0],
            lbph_dist,
            [
                {"value": tau_accept, "label": "tau_accept (67.01)", "color": "#27ae60"},
                {"value": tau_reject, "label": "tau_reject (76.85)", "color": "#c0392b"},
            ],
            "Hybrid LBPH (tau_accept & tau_reject)",
            "Chi-Square Distance",
            (tau_accept, tau_reject),
        ),
        (
            axes[1, 1],
            sface_dist,
            [{"value": sface_hybrid_thr, "label": "Hybrid SFace Thr (1.018)", "color": "#8e44ad"}],
            "Hybrid SFace (L2 Scale)",
            "L2 Distance",
            None,
        ),
    ]

    for ax, dists, thrs, title, xl, amb_band in configs:
        counts, edges, _ = ax.hist(dists, bins=40, color="#34495e", alpha=0.6, edgecolor="#1a252f")
        bin_w = edges[1] - edges[0]
        xk, yk, bw = compute_gaussian_kde(dists, points=400)
        yk_scaled = yk * len(dists) * bin_w
        ax.plot(xk, yk_scaled, color="#2980b9", lw=2, label="KDE")

        if amb_band is not None:
            ax.axvspan(amb_band[0], amb_band[1], color="#f39c12", alpha=0.2, label="Ambiguous Band")

        for idx, thr in enumerate(thrs):
            val = thr["value"]
            c = thr["color"]
            y_val = float(np.interp(val, xk, yk_scaled))
            ax.axvline(val, color=c, ls="--", lw=1.8, label=thr["label"])
            ax.axhline(y_val, color=c, ls=":", lw=1.5, alpha=0.85)

        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlabel(xl, fontsize=9.5)
        ax.set_ylabel("Count", fontsize=9.5)
        ax.grid(True, ls="--", alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)

    fig.suptitle("Independence Test Distributions & Thresholds (Native Predict Scale)", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    grid_path = OUTPUT_DIR / "independence_overview_grid.png"
    fig.savefig(grid_path, dpi=250)
    plt.close(fig)
    print(f"[SAVE] Combined Grid: {grid_path}")

    # 6) Metrics JSON
    metrics = {
        "lbph_chi_square": {
            "scale": "Chi-Square Distance (cv2.face.LBPHFaceRecognizer.predict_collect)",
            "statistics": lbph_stats,
            "thresholds": {
                "standalone": lbph_standalone_thr,
                "tau_accept": tau_accept,
                "tau_reject": tau_reject,
            },
            "false_accept_rates": {
                "standalone_percent": float(np.mean(lbph_dist <= lbph_standalone_thr) * 100),
                "tau_accept_percent": float(np.mean(lbph_dist <= tau_accept) * 100),
                "tau_reject_percent": float(np.mean(lbph_dist <= tau_reject) * 100),
            },
        },
        "sface_l2": {
            "scale": "L2 Distance (FR_NORM_L2, Euclidean)",
            "statistics": sface_stats,
            "thresholds": {
                "standalone_l2_genuine": sface_standalone_thr,
                "hybrid_operating_l2": sface_hybrid_thr,
            },
            "false_accept_rates": {
                "standalone_percent": float(np.mean(sface_dist <= sface_standalone_thr) * 100),
                "hybrid_percent": float(np.mean(sface_dist <= sface_hybrid_thr) * 100),
            },
        },
    }

    json_path = OUTPUT_DIR / "independence_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[SAVE] Metrics JSON: {json_path}")

    # 7) Markdown Summary Report
    md_content = f"""# Independence Test Report (Native Predict Scale)

This directory contains the canonical independence test distributions, histograms, KDE curves, and horizontal/vertical threshold lines for **Standalone LBPH**, **Standalone SFace**, **Hybrid LBPH**, and **Hybrid SFace** evaluated in their native predict distance metrics.

---

## Executive Summary & Threshold Comparison

| Engine / Mode | Native Metric Scale | Threshold | FAR (%) | Primary Artifact |
| :--- | :--- | :--- | :--- | :--- |
| **Standalone LBPH** | Chi-Square Distance | `{lbph_standalone_thr:.4f}` | `{metrics['lbph_chi_square']['false_accept_rates']['standalone_percent']:.4f}%` | [standalone_lbph_independence.png](file:///{OUTPUT_DIR.as_posix()}/standalone_lbph_independence.png) |
| **Standalone SFace** | L2 Distance (`FR_NORM_L2`) | `{sface_standalone_thr:.4f}` | `{metrics['sface_l2']['false_accept_rates']['standalone_percent']:.4f}%` | [standalone_sface_independence.png](file:///{OUTPUT_DIR.as_posix()}/standalone_sface_independence.png) |
| **Hybrid LBPH ($\\\\tau_{{accept}}$)** | Chi-Square Distance | `{tau_accept:.4f}` | `{metrics['lbph_chi_square']['false_accept_rates']['tau_accept_percent']:.4f}%` | [hybrid_lbph_independence.png](file:///{OUTPUT_DIR.as_posix()}/hybrid_lbph_independence.png) |
| **Hybrid LBPH ($\\\\tau_{{reject}}$)** | Chi-Square Distance | `{tau_reject:.4f}` | `{metrics['lbph_chi_square']['false_accept_rates']['tau_reject_percent']:.4f}%` | [hybrid_lbph_independence.png](file:///{OUTPUT_DIR.as_posix()}/hybrid_lbph_independence.png) |
| **Hybrid SFace** | L2 Distance (`FR_NORM_L2`) | `{sface_hybrid_thr:.4f}` | `{metrics['sface_l2']['false_accept_rates']['hybrid_percent']:.4f}%` | [hybrid_sface_independence.png](file:///{OUTPUT_DIR.as_posix()}/hybrid_sface_independence.png) |

---

## Key Visualizations

### 1. Overview Grid (2x2 Panel)
![Independence Overview Grid](file:///{OUTPUT_DIR.as_posix()}/independence_overview_grid.png)

### 2. Standalone LBPH Independence
![Standalone LBPH](file:///{OUTPUT_DIR.as_posix()}/standalone_lbph_independence.png)

### 3. Standalone SFace Independence
![Standalone SFace](file:///{OUTPUT_DIR.as_posix()}/standalone_sface_independence.png)

### 4. Hybrid LBPH Independence (tau_accept & tau_reject)
![Hybrid LBPH](file:///{OUTPUT_DIR.as_posix()}/hybrid_lbph_independence.png)

### 5. Hybrid SFace Independence
![Hybrid SFace](file:///{OUTPUT_DIR.as_posix()}/hybrid_sface_independence.png)

---

## Detailed Distance Statistics

### LBPH Chi-Square Distance Statistics
* **Count**: `{lbph_stats['count']:,}` cross-identity pairs
* **Min**: `{lbph_stats['min']:.4f}`
* **Max**: `{lbph_stats['max']:.4f}`
* **Mean**: `{lbph_stats['mean']:.4f}`
* **Median**: `{lbph_stats['median']:.4f}`
* **Std Dev**: `{lbph_stats['std']:.4f}`

### SFace L2 Distance Statistics
* **Count**: `{sface_stats['count']:,}` cross-identity pairs
* **Min**: `{sface_stats['min']:.4f}`
* **Max**: `{sface_stats['max']:.4f}`
* **Mean**: `{sface_stats['mean']:.4f}`
* **Median**: `{sface_stats['median']:.4f}`
* **Std Dev**: `{sface_stats['std']:.4f}`

---
*Report automatically generated by `scripts/reporting/generate_independence_reports.py`.*
"""

    md_path = OUTPUT_DIR / "independence_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[SAVE] Report Markdown: {md_path}")

    print("[SUCCESS] Independence reports generated cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
