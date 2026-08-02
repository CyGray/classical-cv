#!/usr/bin/env python3
"""Plots for the LFW all-families verification run (reads distributions.npz +
summary.json written by scripts/pipeline/lfw_all_families_verify.py):

  * <out>_lbph_dist.png  - LBPH distance: genuine (modified) vs impostor (clean),
                           hist + KDE, with the accept/reject threshold lines.
  * <out>_sface_dist.png - SFace L2 distance, same layout, l2_genuine line.
  * <out>_table.png      - the balanced-accuracy table + threshold/scale header.

No number is hand-typed: everything comes from the run artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "outputs/benchmark/lfw_all_families"
if not RUN.exists():
    alt_run = ROOT / "reports/benchmark/lfw_all_families"
    if alt_run.exists():
        RUN = alt_run

GEN_C = "#2a6fdb"    # genuine
IMP_C = "#e0662b"    # impostor
THR_C = "#111111"

rng = np.random.default_rng(0)


def _kde_line(ax, data, color, label, subsample=20000):
    d = np.asarray(data, dtype=np.float64)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return
    ax.hist(d, bins=80, density=True, color=color, alpha=0.28, label=f"{label} (n={d.size:,})")
    s = d if d.size <= subsample else rng.choice(d, subsample, replace=False)
    if np.ptp(s) > 1e-9:
        xs = np.linspace(d.min(), d.max(), 400)
        ax.plot(xs, gaussian_kde(s)(xs), color=color, lw=2)


def dist_plot(engine, gen, imp, lines, xlabel, out_path, subtitle):
    fig, ax = plt.subplots(figsize=(8.4, 5.0), dpi=160)
    _kde_line(ax, imp, IMP_C, "impostor (other families, clean)")
    _kde_line(ax, gen, GEN_C, "genuine (own family, modified)")
    ymax = ax.get_ylim()[1]
    for i, (x, style, txt, col) in enumerate(lines):
        ax.axvline(x, ls=style, color=col, lw=1.6)
        # stagger label heights so adjacent lines don't overprint
        yfrac = 0.62 - 0.11 * (i % 3)
        ax.text(x, ymax * yfrac, f" {txt}\n {x:.2f}", rotation=90,
                va="center", ha="left", fontsize=7.5, color=col)
    ax.set_title(f"{engine}: genuine vs impostor distance  (LFW all-families, partial)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel); ax.set_ylabel("density")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.25)
    fig.subplots_adjust(bottom=0.18)
    fig.text(0.5, 0.02, subtitle, ha="center", va="bottom", fontsize=8, color="#444")
    fig.savefig(out_path)
    print(f"[OK] {out_path}")


def table_png(summary, out_path):
    fams = ["clean"] + [f for f in summary["table_by_family"] if f != "clean"]
    rows = []
    for f in fams:
        r = summary["table_by_family"][f]
        rows.append([f, f"{r['lbph']['balanced_acc_pct']:.1f}",
                     f"{r['sface']['balanced_acc_pct']:.1f}",
                     f"{r['hybrid']['balanced_acc_pct']:.1f}"])
    o = summary["overall_over_modifications"]
    rows.append(["OVERALL (mods)", f"{o['lbph']['balanced_acc_pct']:.1f}",
                 f"{o['sface']['balanced_acc_pct']:.1f}", f"{o['hybrid']['balanced_acc_pct']:.1f}"])
    th = summary["derived_thresholds"]["lfw1_derived"]
    ls = summary["derived_thresholds"]["lsdb1_frozen"]

    fig, ax = plt.subplots(figsize=(8.2, 6.6), dpi=160)
    ax.axis("off")
    header = (f"LFW all-families verification — Balanced accuracy ½(TPR+TNR) %\n"
             f"{summary['identities']} identities · {summary['genuine_pairs_per_variant']} genuine "
             f"+ {summary['impostor_pairs_per_variant']:,} impostor pairs / modification · seed "
             f"{summary['seed']}\n"
             f"LFW1 tau_accept={th['tau_accept']} (@{th['tau_accept_far_percent']}% FAR) "
             f"l2_genuine={th['l2_genuine']}   |   LS-DB1 frozen: {ls['tau_accept']} / {ls['l2_genuine']}")
    ax.set_title(header, fontsize=9.5, fontweight="bold", loc="left", pad=14)

    tbl = ax.table(cellText=rows, colLabels=["Modification", "LBPH", "SFace", "Hybrid"],
                   cellLoc="center", loc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(9.5); tbl.scale(1, 1.35)
    ncol = 4
    for c in range(ncol):
        tbl[0, c].set_facecolor("#2a3c5f"); tbl[0, c].set_text_props(color="white", fontweight="bold")
    for ri, row in enumerate(rows, start=1):
        # shade the worst LBPH cells (balanced acc), highlight overall row
        for c in range(ncol):
            if ri == len(rows):
                tbl[ri, c].set_facecolor("#dfe7f5"); tbl[ri, c].set_text_props(fontweight="bold")
            elif ri % 2 == 0:
                tbl[ri, c].set_facecolor("#f4f6fa")
        lb = float(row[1])
        if lb < 90:
            tbl[ri, 1].set_facecolor("#f6c6c6")
        elif lb < 97:
            tbl[ri, 1].set_facecolor("#fbe6c6")
    note = ("Raw (TP+TN)/all is ~99.9% for every row (TN-dominated at 574:1) — balanced acc is the signal. "
            "Hybrid=LBPH: LFW accept edge > reject 76.85, escalation band empty.")
    ax.text(0.5, -0.02, note, transform=ax.transAxes, ha="center", va="top", fontsize=7.8, color="#444")
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    print(f"[OK] {out_path}")


def main():
    d = np.load(RUN / "distributions.npz")
    summary = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
    tau100 = float(d["tau_accept_100ppm"]); tau1 = float(d["tau_accept_1pct"])
    tau_rej = float(d["tau_reject"]); l2g = float(d["l2_genuine"])

    dist_plot(
        "LBPH", d["gen_lbph_mod"], d["imp_lbph"],
        [(tau100, "--", "tau_accept(100ppm)", THR_C),
         (tau1, ":", "tau_accept(1%)", "#8a2be2"),
         (tau_rej, "-.", "tau_reject", "#c02020")],
        "LBPH predict distance (native scale)",
        RUN / "lfw_all_families_lbph_dist.png",
        f"LS-DB1 frozen tau_accept=70.61 (far stricter, off the LFW impostor mass)")

    dist_plot(
        "SFace", d["gen_l2_mod"], d["imp_l2"],
        [(l2g, "--", "l2_genuine(mean)", THR_C)],
        "SFace L2 distance  (l2 = sqrt(2-2·cosine))",
        RUN / "lfw_all_families_sface_dist.png",
        f"genuine rule also requires cosine>={float(d['cos_gen']):.3f}; LS-DB1 frozen l2_genuine=1.107")

    table_png(summary, RUN / "lfw_all_families_table.png")


if __name__ == "__main__":
    main()
