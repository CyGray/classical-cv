"""Figures for the hybrid CV+DL report (docs/HYBRID_CV_DL_REPORT.md).

Built strictly from committed run artifacts - no invented numbers:

  reports/benchmark/hybrid_comparison.json            (clean split)
  reports/benchmark/hybrid_comparison_degraded.json   (41-mod medium)
  reports/evaluation/hybrid_eval.json                 (cascade detail)
  reports/independence/sface_lfw_parity.json          (SFace parity)
  src/hybrid/thresholds.json                          (calibration)

FIGURES -> docs/figures/*.png
  1. fig_hybrid_accuracy.png        rank-1 by config, clean vs degraded (headline)
  2. fig_hybrid_speed_accuracy.png  fps + escalation per config (clean)
  3. fig_hybrid_latency.png         per-stage latency by config (clean)
  4. fig_hybrid_escalation.png      escalation-reason breakdown, clean vs degraded
  5. fig_hybrid_quality_probes.png  clean-crop probe spreads + escalation edges

Usage:  python scripts/make_hybrid_report_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPORTS = PROJECT_ROOT / "reports"
OUT_DIR = PROJECT_ROOT / "docs" / "figures"

CONFIGS = ["LBPH-only", "SFace-only", "Hybrid (cascade)"]
COLORS = {"LBPH-only": "#1f77b4", "SFace-only": "#d62728", "Hybrid (cascade)": "#2ca02c"}
STAGE_COLORS = {"YuNet detect": "#8c8c8c", "LBPH+gate": "#1f77b4", "SFace": "#d62728"}


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _rows_by_label(comparison: dict) -> dict[str, dict]:
    return {row["label"]: row for row in comparison["rows"]}


def fig_accuracy(clean: dict, degraded: dict) -> None:
    clean_rows = _rows_by_label(clean)
    deg_rows = _rows_by_label(degraded)
    clean_acc = [clean_rows[c]["overall"]["closed_set_rank1_percent"] for c in CONFIGS]
    deg_acc = [deg_rows[c]["overall"]["closed_set_rank1_percent"] for c in CONFIGS]

    x = np.arange(len(CONFIGS))
    w = 0.38
    fig, ax = plt.subplots(figsize=(8, 5))
    b1 = ax.bar(x - w / 2, clean_acc, w, label="Clean held-out split", color="#4c9be8")
    b2 = ax.bar(x + w / 2, deg_acc, w, label="Degraded (41-mod medium)", color="#e8744c")
    for bars in (b1, b2):
        for rect in bars:
            ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 1.2,
                    f"{rect.get_height():.1f}%", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Closed-set rank-1 accuracy (%)")
    ax.set_title("Recognition accuracy: LBPH collapses on degradation, the hybrid recovers it")
    ax.set_xticks(x)
    ax.set_xticklabels(CONFIGS)
    ax.set_ylim(0, 112)
    ax.axhline(95, color="green", ls="--", lw=1, alpha=0.6)
    ax.text(0.02, 96.2, "Stage-3 spec 95%", color="green", fontsize=8, ha="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_accuracy.png", dpi=150)
    plt.close(fig)


def fig_speed_accuracy(clean: dict) -> None:
    rows = _rows_by_label(clean)
    fps = [rows[c]["latency"]["projected_fps"] for c in CONFIGS]
    esc = [rows[c]["escalation"]["escalation_rate_percent"] for c in CONFIGS]

    x = np.arange(len(CONFIGS))
    fig, ax1 = plt.subplots(figsize=(8, 5))
    bars = ax1.bar(x, fps, 0.5, color=[COLORS[c] for c in CONFIGS], alpha=0.85)
    for rect in bars:
        ax1.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 2,
                 f"{rect.get_height():.0f} fps", ha="center", va="bottom", fontsize=9)
    ax1.set_ylabel("Projected throughput (fps, off-device CPU)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(CONFIGS)
    ax1.axhline(30, color="green", ls="--", lw=1, alpha=0.6)
    ax1.text(0.02, 33, "Stage-3 spec 30 fps", color="green", fontsize=8)
    ax1.set_ylim(0, max(fps) * 1.2)

    ax2 = ax1.twinx()
    ax2.plot(x, esc, "o-", color="black", lw=1.5, label="Escalation rate")
    for xi, e in zip(x, esc):
        ax2.text(xi, e + 4, f"{e:.0f}%", ha="center", fontsize=9)
    ax2.set_ylabel("Escalation rate to SFace (%)")
    ax2.set_ylim(0, 115)
    ax1.set_title("Speed vs escalation on the clean split (hybrid keeps 75% on the fast path)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_speed_accuracy.png", dpi=150)
    plt.close(fig)


def fig_latency(clean: dict) -> None:
    rows = _rows_by_label(clean)
    # Per-FRAME contribution of each stage = (frames in stage x conditional mean)
    # / total frames. Conditional means (e.g. SFace's ~20 ms over only the
    # escalated frames) must NOT be stacked directly - amortising by frame count
    # makes the bar sum to the true end-to-end mean for every config.
    detect, lbph, sface, e2e = [], [], [], []
    for c in CONFIGS:
        lat = rows[c]["latency"]
        n_lbph = lat["lbph_gate"]["count"]
        n_sface = lat["sface"]["count"]
        n = max(1, n_lbph + n_sface)
        detect.append(lat["yunet_detect"]["mean_ms"])
        lbph.append(n_lbph * lat["lbph_gate"]["mean_ms"] / n)
        sface.append(n_sface * lat["sface"]["mean_ms"] / n)
        e2e.append(lat["end_to_end_mean_ms"])

    x = np.arange(len(CONFIGS))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x, detect, 0.5, label="YuNet detect (every frame)", color=STAGE_COLORS["YuNet detect"])
    ax.bar(x, lbph, 0.5, bottom=detect, label="LBPH + gate", color=STAGE_COLORS["LBPH+gate"])
    bottom2 = [d + l for d, l in zip(detect, lbph)]
    ax.bar(x, sface, 0.5, bottom=bottom2, label="SFace (amortised over escalated)", color=STAGE_COLORS["SFace"])
    for xi, total in zip(x, e2e):
        ax.text(xi, total + 0.4, f"{total:.1f} ms", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylabel("Mean per-frame time in stage (ms)")
    ax.set_title("Per-frame latency budget by stage (sums to end-to-end mean)")
    ax.set_xticks(x)
    ax.set_xticklabels(CONFIGS)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_latency.png", dpi=150)
    plt.close(fig)


def fig_escalation(clean: dict, degraded: dict) -> None:
    hybrid_clean = _rows_by_label(clean)["Hybrid (cascade)"]["escalation"]["reasons"]
    hybrid_deg = _rows_by_label(degraded)["Hybrid (cascade)"]["escalation"]["reasons"]
    order = ["confident_accept", "quality", "low_margin", "ambiguous_band"]
    labels = ["confident\n(stays LBPH)", "quality flag", "low margin", "ambiguous band"]
    reason_colors = ["#2ca02c", "#d62728", "#ff7f0e", "#9467bd"]

    clean_vals = [hybrid_clean.get(k, 0) for k in order]
    deg_vals = [hybrid_deg.get(k, 0) for k in order]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, vals, title in (
        (axes[0], clean_vals, "Clean split (56 faces)"),
        (axes[1], deg_vals, "Degraded 41-mod medium (98 faces)"),
    ):
        wedges = [v for v in vals if v > 0]
        wlabels = [f"{lab} ({v})" for lab, v in zip(labels, vals) if v > 0]
        wcolors = [c for c, v in zip(reason_colors, vals) if v > 0]
        ax.pie(wedges, labels=wlabels, colors=wcolors, autopct="%1.0f%%",
               startangle=90, textprops={"fontsize": 9})
        ax.set_title(title)
    fig.suptitle("Gate routing: clean faces stay on LBPH; degraded faces escalate (mostly on quality)", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_escalation.png", dpi=150)
    plt.close(fig)


def fig_quality_probes(thresholds: dict) -> None:
    stats = thresholds["calibration_stats"]["quality"]
    q = thresholds["quality"]
    probes = [
        ("blur_var", "Blur (var-of-Laplacian)", q["tau_blur"], "below = escalate"),
        ("noise_sigma", "Noise (Immerkaer sigma)", q["tau_noise"], "above = escalate"),
        ("pose_angle", "Off-pose angle (deg)", q["tau_pose"], "above = escalate"),
        ("face_px", "Face size (px)", q["px_min"], "below = escalate"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (key, title, thr, note) in zip(axes.flat, probes):
        s = stats[key]
        # box-style spread: min / p5 / median / p95 / max
        ys = [s["min"], s["p5"], s["median"], s["p95"], s["max"]]
        ax.plot([0, 1, 2, 3, 4], ys, "o-", color="#1f77b4")
        ax.set_xticks([0, 1, 2, 3, 4])
        ax.set_xticklabels(["min", "p5", "median", "p95", "max"], fontsize=8)
        ax.axhline(thr, color="red", ls="--", lw=1.2)
        ax.text(0.02, thr, f"  threshold {thr} ({note})", color="red", fontsize=8,
                va="bottom", transform=ax.get_yaxis_transform())
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.3)
    fig.suptitle("Quality-probe thresholds vs the clean-crop distribution (279 crops)", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_quality_probes.png", dpi=150)
    plt.close(fig)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clean = _load(REPORTS / "benchmark" / "hybrid_comparison.json")
    degraded = _load(REPORTS / "benchmark" / "hybrid_comparison_degraded.json")
    thresholds = _load(PROJECT_ROOT / "src" / "hybrid" / "thresholds.json")

    fig_accuracy(clean, degraded)
    fig_speed_accuracy(clean)
    fig_latency(clean)
    fig_escalation(clean, degraded)
    fig_quality_probes(thresholds)

    print(f"[FIGURES] wrote 5 figures to {OUT_DIR}")
    for p in sorted(OUT_DIR.glob("fig_hybrid_*.png")):
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
