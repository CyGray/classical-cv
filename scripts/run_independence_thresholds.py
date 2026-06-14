"""Determine each classical recognizer's match threshold via the independence test.

Runs the N x (N-1) cross-identity independence test for LBPH / Eigenfaces /
Fisherfaces on La Salle DB1 and consolidates the **rank-based k-th-error-pair
threshold** (the project-spec method: 8th error pair ~ 10,000 ppm for La Salle's
756 comparisons) into one report:
``reports/benchmark/independence_thresholds.{json,md}``.

This is the threshold-determination half of the 7/15 deliverable. It does NOT by
itself produce end-to-end TAR@FAR: each threshold lives on that model's own
feature-distance scale (LBPH chi-square histogram distance; Eigen/Fisher
euclidean on subspace projections), so turning it into a recognition operating
point needs an impostor-inclusive recognition run on the same scale (noted below).

Usage::

    python scripts/run_independence_thresholds.py
    python scripts/run_independence_thresholds.py --skip-run        # consolidate only
    python scripts/run_independence_thresholds.py --error-pair-rank 8
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ["lbph", "eigenfaces", "fisherfaces"]
DISTANCE_METRIC = {
    "lbph": "chi-square (LBPH histograms)",
    "eigenfaces": "euclidean (PCA projections)",
    "fisherfaces": "euclidean (LDA projections)",
}


def python_exe() -> str:
    return os.environ.get("FACE_G3_PYTHON") or sys.executable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Determine classical match thresholds (independence test).")
    parser.add_argument("--families", default=",".join(FAMILIES))
    parser.add_argument("--dataset-dir", default="data/split_lasalle/train",
                        help="Folder of identity sub-folders (one image per identity is sampled).")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--target-far-ppm", type=float, default=10000.0)
    parser.add_argument("--error-pair-rank", type=int, default=None)
    parser.add_argument("--skip-run", action="store_true", help="Reuse existing summaries; don't re-run tests.")
    parser.add_argument("--output-json", default="reports/benchmark/independence_thresholds.json")
    parser.add_argument("--output-md", default="reports/benchmark/independence_thresholds.md")
    return parser.parse_args()


def run_test(py: str, family: str, args: argparse.Namespace, out_dir: str) -> None:
    cmd = [
        py, "-m", f"src.{family}.independence_test",
        "--dataset-dir", args.dataset_dir,
        "--no-align-eyes",
        "--iterations", str(args.iterations),
        "--target-far-ppm", str(args.target_far_ppm),
        "--output-dir", out_dir,
    ]
    if args.error_pair_rank is not None:
        cmd += ["--error-pair-rank", str(args.error_pair_rank)]
    print(f"\n[RUN] {family} independence test -> {out_dir}")
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))


def load_spec(out_dir: str) -> dict | None:
    path = PROJECT_ROOT / out_dir / "summary.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        summary = json.load(f)
    report = summary.get("error_pair_thresholds")
    return report.get("spec") if isinstance(report, dict) else None


def to_markdown(rows: list[dict], dataset_dir: str) -> str:
    lines = ["# Classical Match Thresholds - Independence Test (rank-based)", ""]
    lines.append(f"Dataset: `{dataset_dir}` | Method: feature distance of the **k-th nearest "
                 "impostor pair** at the target false-alarm rate (spec rule).")
    lines.append("")
    lines.append("| Model | Feature distance | Comparisons | Spec rank (k) | Realized FAR | "
                 "Threshold (raw) | Threshold (norm 0-100) | Boundary impostor pair |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        s = r["spec"]
        if not s:
            lines.append(f"| {r['family']} | {DISTANCE_METRIC[r['family']]} | - | - | - | - | - | (no result) |")
            continue
        pair = f"{s.get('query_identity','')} vs {s.get('candidate_identity','')}"
        lines.append(
            f"| {r['family']} | {DISTANCE_METRIC[r['family']]} | {s['comparisons']} | "
            f"{s['error_pair_rank']} | {s['realized_far_ppm']:.0f} ppm "
            f"({s['realized_far_percent']:.3f}%) | {s['raw_threshold']:.4f} | "
            f"{s['normalized_threshold']:.4f} | {pair} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- **Threshold = k-th error pair.** Sort the N x (N-1) cross-identity (impostor) "
        "distances ascending; the k-th smallest sets the match threshold whose false-alarm "
        "rate is `k / N`. Per spec, La Salle DB1 uses the **8th error pair (~10,000 ppm)**; "
        "LFW DB1 uses the **331st (~10 ppm)**.",
        "- **Scales are per-model, not comparable across rows.** LBPH uses chi-square histogram "
        "distance; Eigen/Fisher use euclidean distance on their subspace projections.",
        "- **La Salle DB1 (756 comparisons) cannot resolve finer than ~1,300 ppm** (k=1). The "
        "spec's 100 ppm / 10 ppm operating points require LFW DB1 (33M comparisons).",
        "- **Not yet TAR@FAR.** Each threshold is on the independence test's feature-distance "
        "scale, which differs from the recognizer's `predict()` scale. End-to-end TAR/FRR at "
        "this FAR needs an impostor-inclusive recognition run (e.g. La Salle genuine + LFW "
        "impostors through the open-set evaluator) measured on the recognizer's own scale.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    py = python_exe()
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]

    rows = []
    for family in families:
        out_dir = f"reports/independence/{family}_lasalle"
        if not args.skip_run:
            run_test(py, family, args, out_dir)
        rows.append({"family": family, "spec": load_spec(out_dir)})

    out_json = PROJECT_ROOT / args.output_json
    out_md = PROJECT_ROOT / args.output_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump({"dataset_dir": args.dataset_dir, "rows": rows}, f, indent=2)
    with out_md.open("w", encoding="utf-8") as f:
        f.write(to_markdown(rows, args.dataset_dir))

    print("\n[OK] Independence thresholds consolidated")
    print(f"  - JSON: {out_json}")
    print(f"  - Markdown: {out_md}")
    for r in rows:
        s = r["spec"]
        if s:
            print(f"  {r['family']:<12} k={s['error_pair_rank']} FAR={s['realized_far_ppm']:.0f}ppm "
                  f"raw_threshold={s['raw_threshold']:.4f}")


if __name__ == "__main__":
    main()
