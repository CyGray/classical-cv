"""Render final LSDB complementarity battery from one traced rerun package."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "classical-cv" / "outputs" / "provenance_reruns" / "complementarity_finalized_2026-08-10"
OUT = ROOT / "docs" / "results" / "complementarity_test" / "reruns" / "lsdb_dl41_2026-08-10"


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(OUT / name, format="svg", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def recovery(battery: dict) -> None:
    rows = [r for r in battery["per_modification"] if r["recovery_rate_ci95"]]
    rows.sort(key=lambda r: r["recovery_rate_ci95"]["percent"])
    y = np.arange(len(rows))
    vals = [r["recovery_rate_ci95"]["percent"] for r in rows]
    lo = [max(0.0, v - r["recovery_rate_ci95"]["ci95_low_percent"]) for v, r in zip(vals, rows)]
    hi = [max(0.0, r["recovery_rate_ci95"]["ci95_high_percent"] - v) for v, r in zip(vals, rows)]
    fig, ax = plt.subplots(figsize=(10.0, 8.3))
    ax.barh(y, vals, color="#3b7ddd", height=0.64)
    ax.errorbar(vals, y, xerr=[lo, hi], fmt="none", ecolor="#1d3557", capsize=2, lw=0.8)
    ax.set_yticks(y, [r["modification"] for r in rows], fontsize=8)
    ax.set_xlim(0, 104)
    ax.set_xlabel("SFace recovery among LBPH errors (%)")
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)
    save(fig, "recovery_rate.svg")


def mcnemar(overall: dict) -> None:
    t = overall["table"]
    mc = overall["mcnemar"]
    fig, ax = plt.subplots(figsize=(10.0, 2.2))
    ax.axis("off")
    cells = [["", "SFace right", "SFace wrong"],
             ["LBPH right", str(t["both_right"]), str(t["cv_only_right"])],
             ["LBPH wrong", str(t["dl_only_right"]), str(t["both_wrong"])]]
    table = ax.table(cellText=cells, cellLoc="center", loc="upper left", bbox=[0, 0.30, 1, 0.70])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, col), cell in table.get_celld().items():
        cell.set_linewidth(0.6)
        cell.set_edgecolor("#404040")
        if row == 0 or col == 0:
            cell.set_facecolor("#e9eef5")
            cell.set_text_props(weight="bold")
    ax.text(0, 0.08,
            f"Exact two-sided McNemar: b={mc['b']}, c={mc['c']}, p<1e-300. "
            f"Recovery={overall['recovery_rate_ci95']['percent']:.1f}% (n={overall['recovery_rate_ci95']['trials']}); "
            f"both fail={overall['both_fail_ci95']['percent']:.1f}% (n={overall['probes']}).",
            fontsize=10, transform=ax.transAxes)
    save(fig, "mcnemar_table.svg")


def auc(labels: list[int], scores: list[float]) -> tuple[np.ndarray, np.ndarray, float]:
    order = np.argsort(-np.asarray(scores))
    y = np.asarray(labels)[order]
    pos, neg = int(y.sum()), int(len(y) - y.sum())
    tpr = np.r_[0, np.cumsum(y) / pos, 1]
    fpr = np.r_[0, np.cumsum(1 - y) / neg, 1]
    return fpr, tpr, float(np.trapezoid(tpr, fpr))


def gate(battery: dict) -> None:
    rows = list(csv.DictReader((RAW / "gate_operating_curve_probes.csv").open(encoding="utf-8")))
    scored = [r for r in rows if r["mod"] != "clean" and r["d1"] and r["margin"]]
    labels = [0 if r["lbph_rank1_correct"].lower() == "true" else 1 for r in scored]
    fpr_d, tpr_d, area_d = auc(labels, [float(r["d1"]) for r in scored])
    fpr_m, tpr_m, area_m = auc(labels, [-float(r["margin"]) for r in scored])
    g = battery["gate"]["modified_only"]["escalate_vs_lbph_wrong"]
    fig, ax = plt.subplots(figsize=(6.5, 5.0))
    ax.plot(fpr_d, tpr_d, lw=2, color="#3b7ddd", label=f"LBPH distance (AUC {area_d:.3f})")
    ax.plot(fpr_m, tpr_m, lw=2, color="#d97706", label=f"Negative margin (AUC {area_m:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="#777", lw=1)
    ax.scatter([g["fpr_on_right"]], [g["tpr_recall_of_wrong"]], marker="*", s=180,
               color="#111", zorder=5, label="Deployed gate")
    ax.set(xlim=(0, 1), ylim=(0, 1.02), xlabel="False-positive rate on LBPH Rank-1-correct probes",
           ylabel="Recall of LBPH Rank-1-wrong probes")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    save(fig, "gate_competence.svg")


def speed(curve: dict) -> None:
    points = curve["settings"]
    by_margin: dict[float, list[dict]] = {}
    for p in points:
        by_margin.setdefault(float(p["margin_min"]), []).append(p)
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    cmap = plt.get_cmap("viridis")
    for i, (margin, vals) in enumerate(sorted(by_margin.items())):
        vals.sort(key=lambda p: p["mean_latency_ms"])
        ax.plot([p["mean_latency_ms"] for p in vals], [p["overall_ar_percent"] for p in vals],
                "o-", ms=3.8, lw=1.2, color=cmap(i / max(1, len(by_margin) - 1)), label=f"margin={margin:g}")
    for name, point, color in (("LBPH-only", curve["anchors"]["cv_only"], "#3b7ddd"),
                               ("SFace-only", curve["anchors"]["dl_only"], "#d62728"),
                               ("Deployed cascade", curve["deployed"], "#111")):
        ax.scatter(point["mean_latency_ms"], point["overall_ar_percent"], s=80, marker="*" if name.startswith("Deployed") else "s", color=color, zorder=6)
        ax.annotate(name, (point["mean_latency_ms"], point["overall_ar_percent"]), xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.set(xlabel="Mean latency per modified probe (ms)", ylabel="Overall thresholded identification rate (%)")
    ax.grid(alpha=0.25)
    ax.legend(title="Gate margin", fontsize=8, title_fontsize=8, frameon=False, loc="lower right")
    save(fig, "speed_accuracy_curve.svg")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = json.loads((RAW / "accuracy_ratio_hybrid.json").read_text(encoding="utf-8"))
    curve = json.loads((RAW / "gate_operating_curve.json").read_text(encoding="utf-8"))
    battery = summary["complementarity_battery"]
    recovery(battery)
    mcnemar(battery["overall_modified"])
    gate(battery)
    speed(curve)


if __name__ == "__main__":
    main()
