"""Pull exact-rank unidirectional thresholds from a src.hybrid.independence_test
run's cached records.npz, computed against the TRUE unique-pair count.

Why this exists: src/hybrid/independence_test.py's own rank report
(lbph_rank_thresholds / sface_rank_thresholds in summary.json) caps its
FAR%% math at a 500,000-pair top-k pool - on full LFW1 (16.5M unique pairs)
the reported realized_far_ppm is only valid for ranks <= 500,000, and its
default --target-far-ppm auto-rank-selection is computed against that same
capped pool, not the true unique-pair count (see the [WARN] the test itself
prints when this applies). This script re-derives exact ranks directly from
records.npz, sidestepping the cap entirely.

Usage:
    python scripts/archive/extract_hybrid_unidirectional_ranks.py \\
        --npz reports/independence/hybrid/lfw1_2026-07-28/_raw_runs/run_1/records.npz \\
        --rank 165 --rank 165226
"""
from __future__ import annotations

import argparse

import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--npz", required=True, help="Path to a run_N/records.npz from src.hybrid.independence_test.")
    p.add_argument("--rank", type=int, action="append", required=True,
                   help="Unidirectional unique-pair rank(s) to report (repeatable).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    d = np.load(args.npz, allow_pickle=True)
    qi, cj = d["query_idx"], d["candidate_idx"]
    names = list(d["names"])
    lbph = d["lbph_distance"].astype(np.float64)
    cos = d["sface_cosine"].astype(np.float64)
    l2 = d["sface_l2"].astype(np.float64)

    mask = qi < cj
    n = len(names)
    n_unique = int(mask.sum())
    print(f"identities={n}  ordered={len(lbph)}  unique={n_unique}  expected_unique={n * (n - 1) // 2}")
    assert n_unique == n * (n - 1) // 2, "non-symmetric distance would corrupt the unidirectional mapping"

    qi_u, cj_u, lbph_u, cos_u, l2_u = qi[mask], cj[mask], lbph[mask], cos[mask], l2[mask]

    def report(label: str, values: np.ndarray, ascending: bool, rank: int) -> None:
        order = np.argsort(values) if ascending else np.argsort(-values)
        idx = order[rank - 1]
        far_ppm = 1.0e6 * rank / n_unique
        print(f"  [{label}] rank={rank} far_ppm={far_ppm:.4f}  value={values[idx]:.6f}  "
              f"pair=({names[int(qi_u[idx])]!r} vs {names[int(cj_u[idx])]!r})")

    for rank in args.rank:
        print(f"\n=== rank {rank} (unidirectional, far_ppm={1.0e6 * rank / n_unique:.4f}) ===")
        report("LBPH raw distance (lower = closer)", lbph_u, True, rank)
        report("SFace L2 distance (lower = closer)", l2_u, True, rank)
        report("SFace cosine (higher = closer)", cos_u, False, rank)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
