#!/usr/bin/env python3
"""Merge per-segment hybrid independence-test outputs for ONE variant.

Each work unit is (variant, segment): a directory produced by
``python -m src.hybrid.independence_test --segment-count N --segment-index i``
(optionally ``--modification <name>:<level>``), containing ``summary.json``
(with a ``segment`` block: ``{count, index, seg_start, seg_end, n_total,
query_rows, comparisons}``) and ``comparisons.csv`` (or ``.gz``).

This script verifies a full segment set for one variant, then merges it into
a single ``summary.json`` + ``comparisons.csv.gz`` shaped exactly like an
unsegmented run of ``src.hybrid.independence_test``, so downstream tooling
(``scripts/archive/build_systematic_matrix.py``, the paper pipeline) consumes it
unchanged.

Merge semantics mirror ``src/hybrid/independence_test.py::main`` exactly:

* Per iteration, false-accept COUNTS (lbph/sface/both/cascade) and gate
  escalation counts are summed across segments (segments partition query
  rows, so no pair is double-counted); FAR percents, Wilson CIs, Yule Q /
  Fisher exact / diversity are recomputed from those summed counts, never
  from averaged percentages.
* Across iterations, the merge reproduces the unsegmented test's own
  aggregation: ``mean_fp_percent`` / ``mean_escalation_percent`` are the mean
  of the (now full-N) per-iteration percentages, and ``pooled`` sums FP
  counts over all iterations for the pooled 2x2 diversity table - identical
  in shape to ``independence_test.py``'s own ``pooled`` block.
* ``lbph_rank_thresholds`` / ``sface_rank_thresholds`` (the k-th-error-pair
  spec report) are recomputed from the concatenated ``comparisons.csv``
  rows' ``mean_lbph_distance`` / ``mean_sface_cosine`` columns (each already
  the per-pair mean over iterations, computed independently per segment on
  its disjoint query-row slice) using the same top-k selection and
  ``error_pair_report`` helper the unsegmented test uses.

Row-count invariant (verified against the actual code, not assumed): each
segment's ``comparisons.csv`` holds ONE row per (query, candidate) ordered
pair with FP counts already summed over iterations in that row (columns
``*_fp_runs``, ``runs``) - see ``save_aggregated_csv`` in
``src/hybrid/independence_test.py``. The row count is therefore
``query_rows * (n_total - 1)`` regardless of ``--iterations``; it is NOT
multiplied by iterations (iterations are folded into the row via
``*_fp_runs``/``runs``, not stacked as extra rows).
"""

from __future__ import annotations

import argparse
import csv
import glob
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.stats_utils import wilson_interval_percent, error_diversity  # noqa: E402
from src.independence_common import error_pair_report  # noqa: E402

FP_KEYS = ("lbph", "sface", "both", "cascade")


class MergeError(RuntimeError):
    """Raised when segment inputs fail a merge precondition (hard fail)."""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--segment-dirs", nargs="+", required=True,
                   help="Per-segment output dirs for ONE variant (explicit paths or globs).")
    p.add_argument("--output-dir", required=True, help="Merged output directory.")
    p.add_argument("--expect-count", type=int, default=0,
                   help="If > 0, hard-fail unless the segment count equals this.")
    p.add_argument("--concat-csv", action=argparse.BooleanOptionalAction, default=True,
                   help="Write merged comparisons.csv.gz, header once, segments in index order "
                        "(default: on).")
    p.add_argument("--target-far-ppm", type=float, default=10000.0,
                   help="Target FAR for the recomputed rank-based spec report (default matches "
                        "independence_test.py's own default).")
    p.add_argument("--error-pair-rank", type=int, default=None,
                   help="Explicit k-th error pair (overrides --target-far-ppm).")
    return p.parse_args()


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _expand_dirs(patterns: list[str]) -> list[Path]:
    dirs: list[Path] = []
    for pat in patterns:
        matches = sorted(glob.glob(pat))
        if matches:
            dirs.extend(Path(m) for m in matches)
        else:
            dirs.append(Path(pat))
    # de-dup, keep deterministic order
    seen = set()
    out = []
    for d in dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _csv_path_for(d: Path) -> Path:
    gz_path = d / "comparisons.csv.gz"
    plain_path = d / "comparisons.csv"
    if gz_path.exists():
        return gz_path
    if plain_path.exists():
        return plain_path
    raise MergeError(f"{d}: missing comparisons.csv (or comparisons.csv.gz)")


def _open_csv_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _csv_row_count(path: Path) -> int:
    n = 0
    with _open_csv_text(path) as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for _ in reader:
            n += 1
    return n


def _load_segment(d: Path) -> tuple[Path, dict, Path]:
    summary_path = d / "summary.json"
    if not summary_path.exists():
        raise MergeError(f"{d}: missing summary.json")
    with summary_path.open("r", encoding="utf-8") as f:
        summary = json.load(f)
    csv_path = _csv_path_for(d)
    return d, summary, csv_path


# --------------------------------------------------------------------------- #
# Verification (hard fail, name the offender)
# --------------------------------------------------------------------------- #
def verify_segments(
    loaded: list[tuple[Path, dict, Path]], expect_count: int,
) -> tuple[int, int, dict, dict | None, dict[int, tuple[Path, dict]]]:
    if not loaded:
        raise MergeError("no segment dirs found for the given --segment-dirs")

    for d, summary, _ in loaded:
        if "segment" not in summary or summary["segment"] is None:
            raise MergeError(f"{d}: summary.json has no 'segment' block - not a segmented run")

    counts = {summary["segment"]["count"] for _, summary, _ in loaded}
    if len(counts) != 1:
        offenders = ", ".join(f"{d} (count={s['segment']['count']})" for d, s, _ in loaded)
        raise MergeError(f"segment 'count' disagrees across inputs: {offenders}")
    count = counts.pop()
    if expect_count and count != expect_count:
        raise MergeError(f"segment count {count} != --expect-count {expect_count}")

    indices = [summary["segment"]["index"] for _, summary, _ in loaded]
    if len(indices) != len(set(indices)):
        dupes = sorted({i for i in indices if indices.count(i) > 1})
        offenders = [str(d) for d, s, _ in loaded if s["segment"]["index"] in dupes]
        raise MergeError(f"duplicate segment index {dupes} across: {offenders}")

    expected_idx = set(range(1, count + 1))
    got_idx = set(indices)
    if got_idx != expected_idx:
        missing = sorted(expected_idx - got_idx)
        extra = sorted(got_idx - expected_idx)
        parts = []
        if missing:
            parts.append(f"missing segment index(es) {missing}")
        if extra:
            parts.append(f"unexpected segment index(es) {extra}")
        raise MergeError(f"segment set is not exactly 1..{count}: " + "; ".join(parts))

    by_index: dict[int, tuple[Path, dict]] = {
        summary["segment"]["index"]: (d, summary) for d, summary, _ in loaded
    }
    csv_by_index: dict[int, Path] = {
        summary["segment"]["index"]: c for d, summary, c in loaded
    }

    base_dir, base_summary = by_index[1]
    n_total = base_summary["segment"]["n_total"]
    iterations = base_summary["iterations"]
    thresholds = base_summary["thresholds"]
    base_mod = base_summary.get("modification")

    for idx in sorted(by_index):
        d, s = by_index[idx]
        seg = s["segment"]
        if seg["n_total"] != n_total:
            raise MergeError(f"{d}: segment.n_total {seg['n_total']} != {n_total} (segment 1, {base_dir})")
        if s["dataset"]["identities"] != n_total:
            raise MergeError(
                f"{d}: dataset.identities {s['dataset']['identities']} != n_total {n_total}"
            )
        if s["iterations"] != iterations:
            raise MergeError(
                f"{d}: iterations {s['iterations']} != {iterations} (segment 1, {base_dir})"
            )
        if s["thresholds"] != thresholds:
            raise MergeError(
                f"{d}: thresholds {s['thresholds']} != {thresholds} (segment 1, {base_dir})"
            )
        mod = s.get("modification")
        if mod != base_mod:
            raise MergeError(
                f"{d}: modification block {mod!r} != {base_mod!r} (segment 1, {base_dir})"
            )
        if len(s["per_iteration"]) != iterations:
            raise MergeError(
                f"{d}: has {len(s['per_iteration'])} per_iteration entries, expected {iterations}"
            )
        for it_i, it_entry in enumerate(s["per_iteration"]):
            base_it = base_summary["per_iteration"][it_i]
            if it_entry.get("random_seed") != base_it.get("random_seed"):
                raise MergeError(
                    f"{d}: iteration {it_i + 1} random_seed {it_entry.get('random_seed')} "
                    f"!= {base_it.get('random_seed')} (segment 1, {base_dir})"
                )

    # Bounds tile [0, n_total) exactly - no gaps, no overlaps.
    bounds = sorted(
        (by_index[idx][1]["segment"]["seg_start"], by_index[idx][1]["segment"]["seg_end"], idx)
        for idx in by_index
    )
    cursor = 0
    for start, end, idx in bounds:
        if start != cursor:
            raise MergeError(
                f"segment {idx} starts at seg_start={start}, expected {cursor} "
                f"(gap or overlap in query-row tiling)"
            )
        if end <= start:
            raise MergeError(f"segment {idx} has empty/invalid bounds [{start}, {end})")
        cursor = end
    if cursor != n_total:
        raise MergeError(
            f"segment bounds cover [0, {cursor}) but n_total is {n_total} - gap at the end"
        )

    # Row-count check: comparisons.csv holds one row per ordered pair, FP
    # counts already summed over iterations per row (see module docstring) -
    # so the invariant is query_rows * (n_total - 1), NOT multiplied by
    # iterations.
    for idx in sorted(by_index):
        d, summary = by_index[idx]
        csv_path = csv_by_index[idx]
        seg = summary["segment"]
        expected_rows = seg["query_rows"] * (n_total - 1)
        actual_rows = _csv_row_count(csv_path)
        if actual_rows != expected_rows:
            raise MergeError(
                f"{d}: {csv_path.name} has {actual_rows} data rows, expected "
                f"query_rows({seg['query_rows']}) * (n_total-1)({n_total - 1}) = {expected_rows}"
            )
        if seg["comparisons"] != expected_rows:
            raise MergeError(
                f"{d}: segment.comparisons {seg['comparisons']} != query_rows*(n_total-1) "
                f"{expected_rows}"
            )

    return n_total, iterations, thresholds, base_mod, by_index


# --------------------------------------------------------------------------- #
# Merge: per-iteration counts -> recomputed stats (mirrors independence_test.py)
# --------------------------------------------------------------------------- #
def merge_per_iteration(by_index: dict[int, tuple[Path, dict]], n_total: int, iterations: int) -> list[dict]:
    merged_iterations = []
    for it_i in range(iterations):
        summed_fa = {k: 0 for k in FP_KEYS}
        summed_escalated = 0
        reasons: dict[str, int] = {}
        comparisons_total = 0
        thresholds = dataset_dir = max_identities = random_seed = thresholds_json = None

        for idx in sorted(by_index):
            _, s = by_index[idx]
            it = s["per_iteration"][it_i]
            for k in FP_KEYS:
                summed_fa[k] += int(it["false_accepts"][k])
            comparisons_total += int(it["comparisons"])
            summed_escalated += int(it["gate"]["escalated_probes"])
            for rk, rv in it["gate"]["reasons"].items():
                reasons[rk] = reasons.get(rk, 0) + int(rv)
            if thresholds is None:
                thresholds = it["thresholds"]
                dataset_dir = it["dataset_dir"]
                max_identities = it["max_identities"]
                random_seed = it["random_seed"]
                thresholds_json = it["thresholds_json"]

        fp_union = summed_fa["lbph"] + summed_fa["sface"] - summed_fa["both"]
        p_lbph = summed_fa["lbph"] / comparisons_total
        p_sface = summed_fa["sface"] / comparisons_total
        expected_both = p_lbph * p_sface * comparisons_total

        merged_iterations.append({
            "identities": n_total,
            "comparisons": comparisons_total,
            "false_accepts": {**summed_fa, "union": fp_union},
            "fp_percent": {k: 100.0 * summed_fa[k] / comparisons_total for k in FP_KEYS},
            "fp_rates_ci95": {
                k: wilson_interval_percent(summed_fa[k], comparisons_total) for k in FP_KEYS
            },
            "error_overlap": {
                "observed_joint_fp": summed_fa["both"],
                "expected_joint_fp_if_independent": expected_both,
                "observed_over_expected": (
                    summed_fa["both"] / expected_both if expected_both > 0 else None
                ),
                "p_sface_fp_given_lbph_fp": (
                    summed_fa["both"] / summed_fa["lbph"] if summed_fa["lbph"] else None
                ),
                "p_lbph_fp_given_sface_fp": (
                    summed_fa["both"] / summed_fa["sface"] if summed_fa["sface"] else None
                ),
            },
            "diversity": error_diversity(
                summed_fa["both"], summed_fa["lbph"] - summed_fa["both"],
                summed_fa["sface"] - summed_fa["both"], comparisons_total - fp_union,
            ),
            "gate": {
                "escalated_probes": summed_escalated,
                "escalation_percent": 100.0 * summed_escalated / n_total,
                "reasons": reasons,
            },
            "thresholds": thresholds,
            "dataset_dir": dataset_dir,
            "max_identities": max_identities,
            "random_seed": random_seed,
            "thresholds_json": thresholds_json,
        })
    return merged_iterations


# --------------------------------------------------------------------------- #
# Rank-based spec report, recomputed from the merged CSV's aggregated columns
# --------------------------------------------------------------------------- #
def compute_rank_reports(
    records: list[dict], target_far_ppm: float, error_pair_rank: int | None,
) -> dict[str, dict]:
    n = len(records)
    lbph_d = np.array([r["mean_lbph_distance"] for r in records], dtype=np.float64)
    sface_d = 1.0 - np.array([r["mean_sface_cosine"] for r in records], dtype=np.float64)
    top_k = min(n, 500_000)

    def top_pairs(dists: np.ndarray) -> list[dict]:
        k = min(len(dists), top_k)
        if k == 0:
            return []
        idx = np.argpartition(dists, k - 1)[:k]
        idx = idx[np.argsort(dists[idx])]
        return [
            {
                "raw_distance": float(dists[i]),
                "query_identity": records[i]["query_identity"],
                "candidate_identity": records[i]["candidate_identity"],
            }
            for i in idx
        ]

    lbph_report = error_pair_report(
        top_pairs(lbph_d), target_far_ppm=target_far_ppm, explicit_rank=error_pair_rank)
    sface_report = error_pair_report(
        top_pairs(sface_d), target_far_ppm=target_far_ppm, explicit_rank=error_pair_rank)
    return {"lbph": lbph_report, "sface": sface_report}


# --------------------------------------------------------------------------- #
# Top-level summary assembly (mirrors independence_test.py::main)
# --------------------------------------------------------------------------- #
def build_summary(
    merged_iterations: list[dict], n_total: int, iterations: int, thresholds: dict,
    modification: dict | None, rank_reports: dict[str, dict],
) -> dict:
    comparisons_per_iteration = n_total * (n_total - 1)

    mean_fp_percent = {
        k: float(np.mean([it["fp_percent"][k] for it in merged_iterations])) for k in FP_KEYS
    }
    mean_escalation_percent = float(
        np.mean([it["gate"]["escalation_percent"] for it in merged_iterations])
    )
    overlap_ratios = [
        it["error_overlap"]["observed_over_expected"] for it in merged_iterations
        if it["error_overlap"]["observed_over_expected"] is not None
    ]
    error_overlap_mean = float(np.mean(overlap_ratios)) if overlap_ratios else None

    pooled_n = comparisons_per_iteration * iterations
    pool = {k: sum(it["false_accepts"][k] for it in merged_iterations) for k in FP_KEYS}
    pool_union = pool["lbph"] + pool["sface"] - pool["both"]
    pooled = {
        "comparisons": pooled_n,
        "note": "pairs pooled over iterations reuse identities; "
                "see per_iteration for the conservative per-sweep view",
        "fp_rates_ci95": {k: wilson_interval_percent(pool[k], pooled_n) for k in FP_KEYS},
        "diversity": error_diversity(
            pool["both"], pool["lbph"] - pool["both"], pool["sface"] - pool["both"],
            pooled_n - pool_union,
        ),
    }

    dataset_dirs = {it["dataset_dir"] for it in merged_iterations}
    dataset_path = next(iter(dataset_dirs)) if len(dataset_dirs) == 1 else "<multiple - see merge.segments>"

    summary = {
        "dataset": {"path": dataset_path, "identities": n_total},
        "iterations": iterations,
        "comparisons_per_iteration": comparisons_per_iteration,
        "mean_fp_percent": mean_fp_percent,
        "mean_escalation_percent": mean_escalation_percent,
        "error_overlap_observed_over_expected_mean": error_overlap_mean,
        "pooled": pooled,
        "thresholds": thresholds,
        "lbph_rank_thresholds": rank_reports["lbph"],
        "sface_rank_thresholds": rank_reports["sface"],
        "per_iteration": merged_iterations,
    }
    if modification is not None:
        summary["modification"] = modification
    return summary


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    args = parse_args()
    try:
        dirs = _expand_dirs(args.segment_dirs)
        loaded = [_load_segment(d) for d in dirs]

        n_total, iterations, thresholds, modification, by_index = verify_segments(
            loaded, args.expect_count)
        csv_by_index = {s["segment"]["index"]: c for _d, s, c in loaded}

        merged_iterations = merge_per_iteration(by_index, n_total, iterations)

        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        records: list[dict] = []
        csv_out_path = None
        csv_fh = None
        csv_writer = None
        if args.concat_csv:
            csv_out_path = out_dir / "comparisons.csv.gz"
            csv_fh = gzip.open(csv_out_path, "wt", encoding="utf-8", newline="")
            csv_writer = csv.writer(csv_fh)

        per_segment_meta = []
        header_written = False
        try:
            for idx in sorted(by_index):
                d, _summary = by_index[idx]
                csv_path = csv_by_index[idx]
                rows_here = 0
                with _open_csv_text(csv_path) as f:
                    reader = csv.reader(f)
                    header = next(reader)
                    if csv_writer and not header_written:
                        csv_writer.writerow(header)
                        header_written = True
                    for row in reader:
                        if csv_writer:
                            csv_writer.writerow(row)
                        records.append({
                            "query_identity": row[0],
                            "candidate_identity": row[1],
                            "mean_lbph_distance": float(row[2]),
                            "mean_sface_cosine": float(row[3]),
                        })
                        rows_here += 1
                per_segment_meta.append({
                    "index": idx, "dir": str(d), "rows": rows_here,
                    "sha256": _sha256(csv_path),
                })
        finally:
            if csv_fh:
                csv_fh.close()

        rank_reports = compute_rank_reports(records, args.target_far_ppm, args.error_pair_rank)

        summary = build_summary(
            merged_iterations, n_total, iterations, thresholds, modification, rank_reports)
        summary["merge"] = {
            "segment_count": len(by_index),
            "source_dirs": [str(by_index[idx][0]) for idx in sorted(by_index)],
            "segments": per_segment_meta,
            "merged_at": datetime.now(timezone.utc).isoformat(),
            "concat_csv": bool(args.concat_csv),
            "comparisons_csv": str(csv_out_path) if csv_out_path else None,
        }

        with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        fp = merged_iterations[0]["false_accepts"] if merged_iterations else {}
        print(f"[SUCCESS] Merged {len(by_index)} segments -> {out_dir}")
        print(f"  n_total={n_total} iterations={iterations} "
              f"comparisons_per_iteration={summary['comparisons_per_iteration']}")
        if fp:
            print(f"  iteration 1 FP counts: lbph={fp['lbph']} sface={fp['sface']} "
                  f"both={fp['both']} cascade={fp['cascade']}")
        if csv_out_path:
            print(f"  comparisons: {csv_out_path} ({len(records)} rows)")
        return 0
    except MergeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
