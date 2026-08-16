"""Manuscript figure: frozen LFW operating points on the LSDB impostor sweep.

Redraws the Fig. 3 evidence (histograms + KDE of the fresh LSDB clean-impostor
score distributions with the frozen LFW operating points overlaid) as one
readable two-panel vector asset. Inputs are the canonical recorded artifacts
only; every input is verified against ``docs/results/RESULTS_MANIFEST.json``
(status and SHA-256) before drawing. The figure visualizes the frozen LFW
boundaries; it does not recalibrate anything.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.visualization.manuscript_svg import (  # noqa: E402
    configure_matplotlib,
    export_matplotlib_svg,
)

configure_matplotlib()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

RESULTS_ROOT = ROOT / "docs" / "results"
MANIFEST_PATH = RESULTS_ROOT / "RESULTS_MANIFEST.json"

COMPARISONS_REL = (
    "independence_test/reruns/finalized_2026-08-10/hybrid_lasalle_processed/comparisons.csv"
)
SUMMARY_REL = (
    "independence_test/reruns/finalized_2026-08-10/hybrid_lasalle_processed/summary.json"
)
LBPH_LFW_REL = "independence_test/independence/lbph_lfw1/native_predict_scale_yunet.json"
SFACE_LFW_REL = "independence_test/independence/sface_lfw1/standalone_l2_yunet.json"

DEFAULT_OUTPUT = ROOT / "docs" / "manuscript" / "figures" / "fig3_frozen_threshold_overlay.svg"

# Aesthetics
HIST_FACE = "#b8d5f2"       # Soft clear blue fill
HIST_EDGE = "#2b5c8f"       # Crisp dark blue edge
KDE_COLOR = "#0e3a6c"       # Deep navy KDE line
KDE_LINEWIDTH = 1.15        # Light weight for KDE curve
ACCEPT_COLOR = "#1b5e20"    # Dark forest green for accept line
REJECT_COLOR = "#b71c1c"    # Dark crimson red for reject line
GRID_COLOR = "#ebebeb"      # Subtle gridline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(relative: str) -> tuple[Path, dict]:
    """Resolve one result artifact, requiring a matching canonical_snapshot entry."""
    path = RESULTS_ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entry = next(
        (a for a in manifest["artifacts"] if a.get("path") == relative), None
    )
    if entry is None:
        raise RuntimeError(f"{relative} is not in {MANIFEST_PATH.name}")
    if entry.get("status") != "canonical_snapshot":
        raise RuntimeError(f"{relative}: manifest status {entry.get('status')!r}")
    digest = sha256_file(path)
    if entry.get("sha256") not in (None, digest):
        raise RuntimeError(f"{relative}: SHA-256 mismatch against manifest")
    return path, {"path": relative, "sha256": digest}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def score_column(path: Path, key: str) -> np.ndarray:
    with path.open(encoding="utf-8", newline="") as handle:
        values = [float(row[key]) for row in csv.DictReader(handle)]
    array = np.asarray(values, dtype=float)
    if array.size == 0 or not np.isfinite(array).all():
        raise ValueError(f"{key} sample is empty or non-finite")
    return array


def _despine(axis) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def draw_lbph_panel(axis, scores: np.ndarray, tau_accept: float, tau_reject: float) -> None:
    from scipy.stats import gaussian_kde

    axis.hist(
        scores,
        bins=25,
        density=True,
        color=HIST_FACE,
        edgecolor=HIST_EDGE,
        linewidth=0.6,
        alpha=0.85,
    )
    # Taper grid smoothly down to the baseline on both left and right tails
    kde_func = gaussian_kde(scores)
    grid = np.linspace(63.0, 102.0, 500)
    density_vals = kde_func(grid)
    axis.plot(
        grid,
        density_vals,
        color=KDE_COLOR,
        linewidth=KDE_LINEWIDTH,
    )

    # Vertical threshold lines
    axis.axvline(tau_accept, color=ACCEPT_COLOR, linewidth=1.4, linestyle="--")
    axis.axvline(tau_reject, color=REJECT_COLOR, linewidth=1.5, linestyle=":")

    # Clean, horizontal callout annotations
    axis.text(
        tau_accept + 1.2,
        0.102,
        f"$\\tau_{{accept}} = {tau_accept:.2f}$\n(Stage 1 accept)",
        fontsize=7.5,
        color=ACCEPT_COLOR,
        fontweight="bold",
        va="top",
        ha="left",
        bbox=dict(
            boxstyle="round,pad=0.25",
            facecolor="#ffffff",
            edgecolor="#c8e6c9",
            linewidth=0.8,
            alpha=0.95,
        ),
    )
    axis.text(
        tau_reject - 1.2,
        0.102,
        f"$\\tau_{{reject}} = {tau_reject:.2f}$\n(Permissive reject)",
        fontsize=7.5,
        color=REJECT_COLOR,
        fontweight="bold",
        va="top",
        ha="right",
        bbox=dict(
            boxstyle="round,pad=0.25",
            facecolor="#ffffff",
            edgecolor="#ffcdd2",
            linewidth=0.8,
            alpha=0.95,
        ),
    )

    axis.set_xlim(62, 146)
    axis.set_ylim(0, 0.115)
    axis.set_xlabel("LBPH Chi-square distance (predict_collect)", fontsize=8.4, labelpad=4)
    axis.set_ylabel("Density", fontsize=8.4, labelpad=4)
    axis.tick_params(labelsize=7.8)
    axis.grid(True, linestyle="--", linewidth=0.5, color=GRID_COLOR, alpha=0.8)
    _despine(axis)


def draw_sface_panel(axis, scores: np.ndarray, deployed: float) -> None:
    from scipy.stats import gaussian_kde

    axis.hist(
        scores,
        bins=25,
        density=True,
        color=HIST_FACE,
        edgecolor=HIST_EDGE,
        linewidth=0.6,
        alpha=0.85,
    )
    # Taper grid smoothly down to baseline
    kde_func = gaussian_kde(scores)
    grid = np.linspace(0.98, 1.56, 500)
    density_vals = kde_func(grid)
    axis.plot(
        grid,
        density_vals,
        color=KDE_COLOR,
        linewidth=KDE_LINEWIDTH,
    )

    # Vertical threshold line
    axis.axvline(deployed, color=ACCEPT_COLOR, linewidth=1.4, linestyle="--")

    # Clean horizontal annotation
    axis.text(
        deployed + 0.015,
        5.15,
        f"LFW boundary: {deployed:.4f}\n(Stage 2 accept)",
        fontsize=7.5,
        color=ACCEPT_COLOR,
        fontweight="bold",
        va="top",
        ha="left",
        bbox=dict(
            boxstyle="round,pad=0.25",
            facecolor="#ffffff",
            edgecolor="#c8e6c9",
            linewidth=0.8,
            alpha=0.95,
        ),
    )

    axis.set_xlim(0.98, 1.56)
    axis.set_ylim(0, 5.7)
    axis.set_xlabel("SFace L2 distance (FR_NORM_L2)", fontsize=8.4, labelpad=4)
    axis.set_ylabel("Density", fontsize=8.4, labelpad=4)
    axis.tick_params(labelsize=7.8)
    axis.grid(True, linestyle="--", linewidth=0.5, color=GRID_COLOR, alpha=0.8)
    _despine(axis)


def main() -> int:
    args = parse_args()
    comparisons_path, _ = canonical(COMPARISONS_REL)
    summary_path, _ = canonical(SUMMARY_REL)
    lbph_lfw_path, _ = canonical(LBPH_LFW_REL)
    sface_lfw_path, _ = canonical(SFACE_LFW_REL)

    gate = load_json(summary_path)["thresholds"]
    tau_accept = float(load_json(lbph_lfw_path)["raw_threshold"])
    tau_reject = float(gate["lbph_tau_reject"])
    standalone = float(load_json(sface_lfw_path)["raw_threshold_l2"])
    deployed = float(gate["sface_l2_genuine"])
    if abs(tau_accept - float(gate["lbph_tau_accept"])) > 1e-9:
        raise RuntimeError("LFW tau_accept and run-summary gate tau_accept disagree")

    lbph = score_column(comparisons_path, "mean_lbph_distance")
    sface = score_column(comparisons_path, "mean_sface_l2")

    figure, axes = plt.subplots(
        1, 2, figsize=(7.2, 3.0), dpi=300
    )
    draw_lbph_panel(axes[0], lbph, tau_accept, tau_reject)
    draw_sface_panel(axes[1], sface, deployed)

    # Clean, unified top legend
    legend_elements = [
        Patch(facecolor=HIST_FACE, edgecolor=HIST_EDGE, linewidth=0.6, label="LSDB impostors (n=756)"),
        Line2D([0], [0], color=KDE_COLOR, linewidth=KDE_LINEWIDTH, label="KDE density"),
        Line2D([0], [0], color=ACCEPT_COLOR, linestyle="--", linewidth=1.4, label="Accept boundary (frozen)"),
        Line2D([0], [0], color=REJECT_COLOR, linestyle=":", linewidth=1.5, label="Reject boundary (frozen)"),
    ]
    figure.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=4,
        fontsize=7.3,
        frameon=False,
    )

    figure.tight_layout(rect=[0, 0, 1, 0.94], pad=1.0)

    metadata = {
        "Title": "Frozen LFW operating points on LSDB clean-impostor scores",
        "Description": (
            "Histograms and KDE curves of the LSDB ordered impostor pairs "
            "(n=756) with the frozen LFW operating points overlaid; "
            "cross-database transfer visualization, not recalibration. "
            f"Inputs (canonical_snapshot, sha256-verified): {COMPARISONS_REL}; "
            f"{SUMMARY_REL}; {LBPH_LFW_REL}; {SFACE_LFW_REL}. "
            f"Thresholds: tau_accept={tau_accept:.14g}, tau_reject={tau_reject:g}, "
            f"sface standalone={standalone:.14g}, deployed={deployed:g}."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    export_matplotlib_svg(figure, args.output, metadata=metadata)
    figure.savefig(
        args.output.with_suffix(".png"), dpi=300, bbox_inches="tight"
    )
    figure.savefig(
        args.output.with_suffix(".preview.png"), dpi=220, bbox_inches="tight"
    )
    plt.close(figure)
    print(f"[OK] Wrote SVG: {args.output}")
    print(f"[OK] Wrote PNG: {args.output.with_suffix('.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
