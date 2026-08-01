#!/usr/bin/env python3
"""Render docs/reports/SPEC_COMPARISON.md's ## 2. Spec scorecard as two
presentation-slide PNGs (one metric group per slide), with the winning model
per row highlighted.

Split in half by theme so each half fits one presentation page:
  - Part 1: Accuracy & Robustness (TAR, FAR, FRR, Rank-1, EER, AR)
  - Part 2: Footprint & Deployment (feature size, model size, speed, latency,
    thresholds)

"Best" highlighting is a per-row comparison across the 3 models (which one
wins THIS metric), independent of the existing PASS/FAIL-vs-spec-target
annotation already in the source table - both are kept, on separate visual
channels: PASS/FAIL as colored text, "best of the 3" as a green cell wash +
checkmark (dataviz skill status-good, reserved color, never themed).
Rows with no meaningful winner (calibrated-equal, tied PASS, not
instrumented, or a bare calibration constant with no "better/worse"
direction) are left neutral.

Usage:
    python scripts/archive/build_spec_scorecard_pngs.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "reports" / "CV_COMPARISON"

# dataviz skill: chart chrome/ink + status-good (fixed, never themed)
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
SURFACE = "#fcfcfb"
GRIDLINE = "#e1e0d9"
STATUS_GOOD = "#0ca30c"
STATUS_GOOD_WASH = "#e3f7e3"
STATUS_CRITICAL = "#d03b3b"
HEADER_TINTS = {
    "LBPH": "#eaf2fc",       # blue slot 1, light tint
    "Eigenfaces": "#e6f5e6",  # green slot 2, light tint
    "Fisherfaces": "#fdf3e0",  # yellow slot 4, light tint
}
HEADER_INK = {
    "LBPH": "#184f95",
    "Eigenfaces": "#006300",
    "Fisherfaces": "#8a6400",
}

MODELS = ["LBPH (Tan-Triggs)", "Eigenfaces", "Fisherfaces"]
MODEL_KEYS = ["LBPH", "Eigenfaces", "Fisherfaces"]

# Each row: (metric, target, [val_lbph, val_eigen, val_fisher], winner_idx_or_None)
PART1_ROWS = [
    ("TAR @ FAR ≤ 100 ppm", "90–95 %",
     ["98.21 % — PASS", "23.21 % — FAIL", "10.71 % — FAIL"], 0),
    ("FAR achieved", "< 0.01 %",
     ["0.0076 % — PASS", "0.0076 % (TAR collapses)", "0.0076 % (TAR collapses)"], 0),
    ("FRR @ that FAR", "1–5 %",
     ["1.79 % — PASS", "76.79 % — FAIL", "89.29 % — FAIL"], 0),
    ("Rank-1 (closed-set, held-out)", "(90–95 % read)",
     ["100 %", "75.0 %", "66.1 %"], 0),
    ("EER (context, no target)", "—",
     ["0.07 %", "31.8 %", "35.7 %"], 0),
    ("Accuracy Ratio (41-mod suite)", "(robustness view)",
     ["85.4 %", "47.7 %", "30.5 %"], 0),
]

PART2_ROWS = [
    ("Feature vector", "< 1 KB",
     ["64 KB — FAIL", "1,120 B — FAIL", "108 B — PASS"], 2),
    ("Model / template store", "(Pi context)",
     ["33.3 MB", "82.6 MB", "8.2 MB"], 2),
    ("Speed (desktop live loop)", "≥ 30 fps",
     ["19.9 — FAIL", "29.0 — borderline", "27.8 — borderline"], 1),
    ("Speed (Stage-1: 1 face/s)", "≥ 1 fps",
     ["PASS", "PASS", "PASS"], "all"),
    ("Latency", "< 100 ms",
     ["not instrumented", "not instrumented", "not instrumented"], None),
    ("Deployable threshold (predict scale)", "—",
     ["73.0", "4,308", "738"], None),
    ("Independence threshold (LSDB1, 8th pair, native predict-scale)", "—",
     ["70.6089", "3,698.57", "1,956.00"], None),
]


def clean_val(v: str) -> str:
    """Strip em dashes and the literal word PASS - a winner checkmark/wash
    already signals pass; FAIL/borderline stay as plain text (no icon)."""
    v = v.replace(" — PASS", "")
    v = v.replace("—", " ")
    v = v.replace("PASS", "")
    return " ".join(v.split())


def render_slide(rows: list[tuple], out_path: Path) -> None:
    n_rows = len(rows)
    fig_w, fig_h = 13.333, 7.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    col_x = [0.0, 0.34, 0.46, 0.64, 0.82, 1.0]  # metric | target | 3 models
    header_h = 1.0 / (len(rows) + 1)
    header_top = 1.0
    top = header_top - header_h  # table body starts right below the header row
    row_h = top / n_rows  # body fills exactly down to y=0, no bottom padding

    # header row
    header_labels = ["Spec metric", "Target"] + MODELS
    for c in range(5):
        x0, x1 = col_x[c], col_x[c + 1]
        bg = HEADER_TINTS.get(MODEL_KEYS[c - 2], "#f1f0ec") if c >= 2 else "#f1f0ec"
        ink = HEADER_INK.get(MODEL_KEYS[c - 2], INK_PRIMARY) if c >= 2 else INK_PRIMARY
        ax.add_patch(plt.Rectangle((x0, top), x1 - x0, header_h, facecolor=bg,
                                    edgecolor=GRIDLINE, linewidth=1.0, transform=ax.transAxes))
        ax.text((x0 + x1) / 2 if c >= 1 else x0 + 0.01, top + header_h / 2, header_labels[c],
                ha="center" if c >= 1 else "left", va="center", fontsize=12.5,
                fontweight="bold", color=ink, transform=ax.transAxes)

    # body rows
    for r, (metric, target, values, winner) in enumerate(rows):
        y0 = top - (r + 1) * row_h
        band = "#ffffff" if r % 2 == 0 else "#f7f7f5"
        for c in range(5):
            x0, x1 = col_x[c], col_x[c + 1]
            is_winner_cell = winner == "all" or (c - 2) == winner
            cell_bg = STATUS_GOOD_WASH if is_winner_cell else band
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, row_h, facecolor=cell_bg,
                                        edgecolor=GRIDLINE, linewidth=0.8, transform=ax.transAxes))

        metric_wrapped = textwrap.fill(metric, 40)
        metric_fs = 11.3 if "\n" not in metric_wrapped else 10.0
        ax.text(col_x[0] + 0.012, y0 + row_h / 2, metric_wrapped, ha="left", va="center",
                fontsize=metric_fs, color=INK_PRIMARY, transform=ax.transAxes)
        ax.text((col_x[1] + col_x[2]) / 2, y0 + row_h / 2, textwrap.fill(target, 16),
                ha="center", va="center",
                fontsize=10.5, color=INK_MUTED, style="italic", transform=ax.transAxes)

        for c in range(3):
            x0, x1 = col_x[2 + c], col_x[3 + c]
            val = values[c]
            is_winner = winner == "all" or winner == c
            text = clean_val(val)
            txt_color = STATUS_GOOD if is_winner else (
                STATUS_CRITICAL if "FAIL" in val else INK_PRIMARY
            )
            label = ("✓  " if is_winner else "") + text
            val_fs = 11.3 if len(label) <= 18 else (9.6 if len(label) <= 28 else 8.6)
            ax.text((x0 + x1) / 2, y0 + row_h / 2, label, ha="center", va="center",
                     fontsize=val_fs, fontweight=("bold" if is_winner else "normal"),
                     color=txt_color, transform=ax.transAxes)

    fig.savefig(out_path, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[SAVE] PNG: {out_path}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    render_slide(PART1_ROWS, OUTPUT_DIR / "spec_scorecard_part1_accuracy.png")
    render_slide(PART2_ROWS, OUTPUT_DIR / "spec_scorecard_part2_footprint.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
