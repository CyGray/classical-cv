"""Band-conditioned SFace threshold diagnostic (NOTES.md item 4).

Filters accuracy_ratio_verification_full_pairs.csv's genuine and impostor
rows to LBPH's escalation band [tau_accept, tau_reject) and reports SFace's
cosine/L2 distributions on that conditioned subpopulation -- the population
SFace actually sees in cascade mode, as opposed to its full marginal
distribution (what dl_only/standalone measures).

NOT a threshold-grade derivation. See docs/experiments/hybrid_sface_threshold/
ANALYSIS.md for why: sample size (a few thousand rows at most, vs. the 16.5M
pairs behind the standalone SFace sweep) and a protocol mismatch (this CSV's
impostor pair is 1:1 against one deterministic identity; real cascade
escalation triggers on a 1-to-N argmin over the full gallery, which this data
cannot reproduce). Diagnostic only -- does not write to thresholds.json's
live sface.* keys or src/sface/recognizer.py's L2_GENUINE_THRESHOLD.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COSINE_GENUINE_THRESHOLD = 0.363  # src/sface/recognizer.py -- fixed policy gate, never FAR-fit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pairs-csv",
        default=str(PROJECT_ROOT / "outputs" / "benchmark" / "accuracy_ratio_verification_full_pairs.csv"),
    )
    parser.add_argument("--tau-accept", type=float, default=67.03325520645528)
    parser.add_argument(
        "--tau-reject",
        type=float,
        nargs="+",
        default=[119.05, 134.17, 140.13],
        help="One or more tau_reject candidates to evaluate (heavy p95 / pooled p99 / heavy p99).",
    )
    parser.add_argument("--output-json", default=str(PROJECT_ROOT / "reports" / "independence" / "hybrid_sface_band" / "band_conditioned.json"))
    return parser.parse_args()


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    idx = min(len(s) - 1, max(0, round(p / 100 * (len(s) - 1))))
    return s[idx]


def summarize(label: str, l2s: list[float], coss: list[float]) -> dict:
    fails_cosine = sum(1 for c in coss if c < COSINE_GENUINE_THRESHOLD)
    return {
        "label": label,
        "n": len(l2s),
        "l2_min": min(l2s) if l2s else None,
        "l2_p50": pct(l2s, 50),
        "l2_p90": pct(l2s, 90),
        "l2_p95": pct(l2s, 95),
        "l2_p99": pct(l2s, 99),
        "l2_max": max(l2s) if l2s else None,
        "cosine_min": min(coss) if coss else None,
        "cosine_p50": pct(coss, 50),
        "n_failing_cosine_genuine_regardless_of_l2": fails_cosine,
        "pct_failing_cosine_genuine_regardless_of_l2": 100.0 * fails_cosine / len(coss) if coss else None,
    }


def main() -> int:
    args = parse_args()
    rows = []
    with open(args.pairs_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    results = {
        "source_csv": args.pairs_csv,
        "n_rows": len(rows),
        "tau_accept": args.tau_accept,
        "candidates": [],
        "caveats": [
            "NOT threshold-grade: band-conditioned impostor n is at most a few thousand "
            "(vs. 16.5M pairs behind the standalone SFace sweep) -- finest resolvable FAR "
            "is order 100 ppm at best, and that is a single-sample estimate, not a rank "
            "statistic.",
            "Protocol mismatch: 'impostor in-band' means this row's 1:1 designated-impostor "
            "pair's LBPH distance falls in [tau_accept, tau_reject). Real cascade escalation "
            "triggers on argmin_i d(P, G_i) over the full N-gallery (1-to-N), which this "
            "1:1-protocol CSV cannot reproduce. A probe's true escalation status may differ "
            "from this proxy.",
        ],
    }

    for tau_reject in args.tau_reject:
        genuine_l2, genuine_cos = [], []
        impostor_l2, impostor_cos = [], []
        for row in rows:
            g_dist = float(row["lbph_genuine_dist"])
            if args.tau_accept <= g_dist < tau_reject:
                genuine_l2.append(float(row["sface_genuine_l2"]))
                genuine_cos.append(float(row["sface_genuine_cos"]))
            i_dist = float(row["lbph_impostor_dist"])
            if args.tau_accept <= i_dist < tau_reject:
                impostor_l2.append(float(row["sface_impostor_l2"]))
                impostor_cos.append(float(row["sface_impostor_cos"]))

        results["candidates"].append(
            {
                "tau_reject": tau_reject,
                "genuine_in_band": summarize("genuine_in_band", genuine_l2, genuine_cos),
                "impostor_in_band": summarize("impostor_in_band", impostor_l2, impostor_cos),
            }
        )

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[INFO] wrote {out_path}")
    for cand in results["candidates"]:
        g, i = cand["genuine_in_band"], cand["impostor_in_band"]
        print(
            f"tau_reject={cand['tau_reject']:.2f}  genuine n={g['n']} (fail-cosine {g['pct_failing_cosine_genuine_regardless_of_l2']:.1f}%)"
            f"  impostor n={i['n']}  impostor L2 min={i['l2_min']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
