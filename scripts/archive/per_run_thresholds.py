"""Backfill per-run k-th-error-pair thresholds from already-committed raw runs.

``src/independence_common.py:aggregate_pairwise_results`` averages each pair's
distance across the seeded repeats *before* ranking, so the published
threshold (e.g. lbph_lasalle's 85.88 normalized) is a single point estimate
with no run-to-run uncertainty band, even though the 10 individual runs are
sitting on disk in ``_raw_runs/run_*/comparisons.csv``.

This script reads those committed per-run CSVs directly - no re-running the
N x (N-1) sweep - and reports the k-th-smallest distance within each run
separately, plus the mean/std/min/max across runs.

Caveat: the committed raw-run CSVs only carry ``distance_normalized`` (each
run's own distances normalized against that run's own max), not
``raw_distance`` - so this backfill can only recover the *normalized*-scale
per-run threshold, not the raw-scale one. New runs going forward carry both
(see ``per_run_error_pair_thresholds`` in src/independence_common.py, wired
into the live summary writers), so this raw-scale gap is a backfill-only
limitation, not a permanent one.

Usage:
    python scripts/archive/per_run_thresholds.py reports/independence/lbph_lasalle --k 8
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_run_normalized_distances(csv_path: Path) -> list[float]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f"[ERROR] {csv_path} has no header row.")
        key = next(
            (c for c in reader.fieldnames if c.lower() in {"distance_normalized", "normalized_distance"}),
            None,
        )
        if key is None:
            raise SystemExit(f"[ERROR] No normalized-distance column found in {csv_path}.")
        return [float(row[key]) for row in reader if (row.get(key) or "").strip()]


def per_run_kth_threshold(distances: list[float], k: int) -> float | None:
    if not distances:
        return None
    k = max(1, min(k, len(distances)))
    return sorted(distances)[k - 1]


def backfill(run_dir: Path, k: int) -> dict:
    raw_runs_dir = run_dir / "_raw_runs"
    if not raw_runs_dir.is_dir():
        raise SystemExit(f"[ERROR] No _raw_runs/ directory under {run_dir}.")

    run_csvs = sorted(raw_runs_dir.glob("run_*/comparisons.csv"))
    if not run_csvs:
        raise SystemExit(f"[ERROR] No run_*/comparisons.csv files under {raw_runs_dir}.")

    per_run_normalized: list[float] = []
    for csv_path in run_csvs:
        distances = _load_run_normalized_distances(csv_path)
        threshold = per_run_kth_threshold(distances, k)
        if threshold is not None:
            per_run_normalized.append(threshold)
            print(f"[RUN] {csv_path.parent.name}: {k}th-smallest normalized distance = {threshold:.4f}")

    if not per_run_normalized:
        raise SystemExit("[ERROR] No usable per-run thresholds computed.")

    result = {
        "k": k,
        "num_runs": len(per_run_normalized),
        "per_run_normalized_threshold": per_run_normalized,
        "normalized_threshold_stats": {
            "mean": statistics.mean(per_run_normalized),
            "std": statistics.pstdev(per_run_normalized),
            "min": min(per_run_normalized),
            "max": max(per_run_normalized),
        },
        "note": "raw-scale per-run threshold unavailable - committed _raw_runs CSVs only "
        "carry distance_normalized; new runs record both scales via "
        "per_run_error_pair_thresholds in src/independence_common.py",
    }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path, help="e.g. reports/independence/lbph_lasalle")
    parser.add_argument("--k", type=int, default=None, help="Error-pair rank (default: read from sibling summary.json).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else (PROJECT_ROOT / args.run_dir)

    k = args.k
    if k is None:
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            raise SystemExit("[ERROR] --k not given and no sibling summary.json to read it from.")
        spec = json.loads(summary_path.read_text(encoding="utf-8-sig")).get("error_pair_thresholds", {}).get("spec")
        if not spec or "error_pair_rank" not in spec:
            raise SystemExit("[ERROR] summary.json has no error_pair_thresholds.spec.error_pair_rank.")
        k = int(spec["error_pair_rank"])
        print(f"[INFO] Using k={k} from {summary_path.name}")

    result = backfill(run_dir, k)
    stats = result["normalized_threshold_stats"]
    print(
        f"\n[RESULT] {k}th-pair threshold across {result['num_runs']} seeded runs "
        f"(normalized): mean {stats['mean']:.2f} +/- {stats['std']:.2f} "
        f"(range {stats['min']:.2f}-{stats['max']:.2f})"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
