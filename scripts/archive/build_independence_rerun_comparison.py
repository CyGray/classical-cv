#!/usr/bin/env python3
"""Build the LBPH / Eigenfaces / Fisherfaces independence-test deliverables for
LSDB1, on each model's NATIVE OpenCV predict_collect() distance scale.

The earlier version of this script forced all 3 models onto one artificial
0-100 scale via `independence_common.py`'s hand-rolled `chi_squared_distance` /
`euclidean_distance` reimplementation. That reimplementation is NOT what the
deployed OpenCV recognizers compute - it gave LBPH a rank-8 threshold of 17.65
raw, which is nowhere near the real predict-scale distance (confirmed by 3
independent native runs: 70.6089, matching the deployed `tau_accept` = 73.04's
scale). Cross-model comparability on a fake shared scale is retired; each model
now gets its own native-scale number and its own chart:

  - LBPH:        `reports/independence/hybrid/lsdb1_fixed/` (real
                  `cv.face.LBPHFaceRecognizer` + `predict_collect()`, from the
                  hybrid independence test)
  - Eigenfaces:   `reports/independence/eigenfaces_lasalle_native/` (real
                  `cv.face.EigenFaceRecognizer` + `predict_collect()`)
  - Fisherfaces:  `reports/independence/fisherfaces_lasalle_native/` (real
                  `cv.face.FisherFaceRecognizer` + `predict_collect()`)

All three: light_front.jpg deterministic probe, rank-8 error pair (756 ordered
La Salle DB1 comparisons, 10,000 ppm target -> 10,582 realized ppm).

Outputs into docs/reports/INDEPENDENCE_RERUN_CV/:
  - independence_rerun_comparison.csv / .md  - one row per model, native units
  - independence_rerun_lbph.png
  - independence_rerun_eigenfaces.png
  - independence_rerun_fisherfaces.png       - one PNG PER MODEL (own scale)

Usage:
    python scripts/archive/build_independence_rerun_comparison.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.independence_plots import compute_kde_curve  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "docs" / "reports" / "INDEPENDENCE_RERUN_CV"
THRESHOLD_COLOR = "#c44e52"

# key, label, run_dir, distance_csv_column, color, distance_metric_label
MODELS = [
    (
        "lbph", "LBPH",
        "outputs/independence/hybrid/lsdb1_fixed",
        "mean_lbph_distance",
        "#2a78d6",
        "LBPH chi-square (native cv2.face predict_collect)",
    ),
    (
        "eigenfaces", "Eigenfaces",
        "outputs/independence/eigenfaces/eigenfaces_lasalle_native",
        "raw_distance",
        "#008300",
        "Eigenfaces Euclidean, PCA space (native cv2.face predict_collect)",
    ),
    (
        "fisherfaces", "Fisherfaces",
        "outputs/independence/fisherfaces/fisherfaces_lasalle_native",
        "raw_distance",
        "#eda100",
        "Fisherfaces Euclidean, LDA space (native cv2.face predict_collect)",
    ),
]


def load_distances(run_dir: Path, column: str) -> np.ndarray:
    values = []
    with (run_dir / "comparisons.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            values.append(float(row[column]))
    return np.asarray(values, dtype=np.float64)


def load_spec(run_dir: Path, key: str) -> dict:
    with (run_dir / "summary.json").open("r", encoding="utf-8") as f:
        summary = json.load(f)
    if key == "lbph":
        return summary["lbph_rank_thresholds"]["spec"]
    return summary["error_pair_thresholds"]["spec"]


def build_rows() -> list[dict]:
    rows = []
    for key, label, rel_dir, column, color, metric_label in MODELS:
        run_dir = PROJECT_ROOT / rel_dir
        candidates = [
            run_dir,
            PROJECT_ROOT / rel_dir.replace("outputs", "reports"),
            PROJECT_ROOT / "outputs" / "independence" / key / f"{key}_lasalle_native",
            PROJECT_ROOT / "reports" / "independence" / key / f"{key}_lasalle_native",
        ]
        for c in candidates:
            if c.exists():
                run_dir = c
                break
        distances = load_distances(run_dir, column)
        spec = load_spec(run_dir, key)
        rows.append({
            "key": key,
            "label": label,
            "color": color,
            "metric_label": metric_label,
            "comparisons": spec["comparisons"],
            "realized_far_ppm": spec["realized_far_ppm"],
            "realized_far_percent": spec["realized_far_percent"],
            "raw_threshold": spec["raw_threshold"],
            "boundary_query": spec["query_identity"],
            "boundary_candidate": spec["candidate_identity"],
            "min_distance": float(distances.min()),
            "max_distance": float(distances.max()),
            "mean_distance": float(distances.mean()),
            "median_distance": float(np.median(distances)),
            "std_dev": float(distances.std()),
            "distances": distances,
        })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    fieldnames = [
        "model", "distance_metric", "comparisons", "realized_far_ppm", "realized_far_percent",
        "raw_threshold", "min_distance", "max_distance",
        "mean_distance", "median_distance", "std_dev",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "model": r["label"],
                "distance_metric": r["metric_label"],
                "comparisons": r["comparisons"],
                "realized_far_ppm": f"{r['realized_far_ppm']:.4f}",
                "realized_far_percent": f"{r['realized_far_percent']:.4f}",
                "raw_threshold": f"{r['raw_threshold']:.6f}",
                "min_distance": f"{r['min_distance']:.4f}",
                "max_distance": f"{r['max_distance']:.4f}",
                "mean_distance": f"{r['mean_distance']:.4f}",
                "median_distance": f"{r['median_distance']:.4f}",
                "std_dev": f"{r['std_dev']:.4f}",
            })
    print(f"[SAVE] CSV: {path}")


def write_md(rows: list[dict], path: Path) -> None:
    lines = [
        "# Independence Test Rerun - LBPH vs Eigenfaces vs Fisherfaces (LSDB1)",
        "",
        "Native-scale rerun: each model's rank-8 threshold is read straight off the",
        "real deployed OpenCV recognizer (`cv.face.LBPHFaceRecognizer` /",
        "`EigenFaceRecognizer` / `FisherFaceRecognizer`) via `predict_collect()` -",
        "not a hand-rolled distance reimplementation. Each model's raw threshold is",
        "therefore on its OWN native scale (chi-square for LBPH, Euclidean-in-PCA for",
        "Eigenfaces, Euclidean-in-LDA for Fisherfaces) and the three are **not**",
        "comparable to each other on one axis - that cross-model 0-100 normalization",
        "has been retired (it previously misreported LBPH's threshold as 17.65,",
        "~4x too small vs the real 70.61 predict-scale value).",
        "",
        "Every identity's probe image is always `light_front.jpg` (deterministic -",
        "same fix as the hybrid LBPH+SFace independence test), guaranteeing the",
        "exact same N x (N-1) = 756 cross-identity comparisons on every run.",
        "",
        f"Dataset: `data/lasalle_db1_processed` - 28 identities, {rows[0]['comparisons']} ordered impostor pairs.",
        "Threshold spec: 8th error pair (target FAR = 10,000 ppm), same operating point for all 3 models.",
        "",
        "## Rank-based threshold (native scale per model)",
        "",
        "| Model | Distance metric | Realized FAR (ppm) | Realized FAR (%) | Raw threshold | Boundary pair |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['metric_label']} | {r['realized_far_ppm']:.1f} | "
            f"{r['realized_far_percent']:.3f}% | {r['raw_threshold']:.4f} | "
            f"{r['boundary_query']} vs {r['boundary_candidate']} |"
        )

    lines += [
        "",
        "## Distance distribution (native scale, NOT cross-model comparable)",
        "",
        "| Model | Min | Max | Mean | Median | Std Dev |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['min_distance']:.4f} | {r['max_distance']:.4f} | "
            f"{r['mean_distance']:.4f} | {r['median_distance']:.4f} | {r['std_dev']:.4f} |"
        )

    lines += [
        "",
        "![LBPH](independence_rerun_lbph.png)",
        "",
        "![Eigenfaces](independence_rerun_eigenfaces.png)",
        "",
        "![Fisherfaces](independence_rerun_fisherfaces.png)",
        "",
        "Raw per-run outputs: `reports/independence/hybrid/lsdb1_fixed/` (LBPH), "
        "`reports/independence/{eigenfaces,fisherfaces}_lasalle_native/`.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[SAVE] Markdown: {path}")


def write_model_png(row: dict, path: Path, *, bins: int = 30) -> None:
    values = row["distances"]
    color = row["color"]
    thr = row["raw_threshold"]

    fig, ax = plt.subplots(figsize=(7, 5.5), dpi=150)

    counts, edges, _ = ax.hist(
        values, bins=bins, color=color, alpha=0.45, edgecolor=color, linewidth=0.8,
    )

    x, y, _ = compute_kde_curve(values, points=500)
    if x.size:
        bin_w = float(edges[1] - edges[0])
        ax.plot(x, y * values.size * bin_w, color=color, linewidth=2)

    ax.axvline(thr, color=THRESHOLD_COLOR, ls="--", lw=2)
    ymax = ax.get_ylim()[1]
    ax.text(
        thr, ymax * 0.97,
        f"Threshold = {thr:.2f}\nFAR = {row['realized_far_percent']:.3f}%",
        rotation=90, va="top", ha="right", fontsize=9, color=THRESHOLD_COLOR,
    )

    ax.set_title(f"{row['label']} - Impostor Distance (LSDB1, deterministic light_front.jpg)",
                 color=color, fontweight="bold")
    ax.set_xlabel(row["metric_label"])
    ax.set_ylabel("Count")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print(f"[SAVE] PNG: {path}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    write_csv(rows, OUTPUT_DIR / "independence_rerun_comparison.csv")
    write_md(rows, OUTPUT_DIR / "independence_rerun_comparison.md")
    for row in rows:
        write_model_png(row, OUTPUT_DIR / f"independence_rerun_{row['key']}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
