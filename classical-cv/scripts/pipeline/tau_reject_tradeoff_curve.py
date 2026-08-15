"""tau_reject FRR-vs-escalation trade-off curve (docs/independence method).

For a sweep of candidate tau_reject values, computes -- from the same
pairwise-verification CSV already used for the tau_accept unification and the
hybrid SFace band diagnostic -- two pooled quantities:

* genuine_hard_reject_pct: fraction of genuine probes with
  lbph_genuine_dist >= tau_reject -- permanently rejected pre-SFace, the
  cascade's real cost for this parameter (see docs/experiments/tau_reject/
  THRESHOLD_ANALYSIS.md).
* impostor_escalated_pct: fraction of impostor probes with
  lbph_impostor_dist in [tau_accept, tau_reject) -- impostors that get a
  shot at fooling SFace instead of being hard-rejected by LBPH alone.

The point of sweeping instead of picking one candidate is to check for a
knee -- a tau_reject range where genuine rescue improves fast without much
impostor-escalation cost. No new independence run is needed: this is the
same threshold-independent raw-distance data tau_accept and tau_reject's
percentile analysis already used.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hybrid.recognizer import DEFAULT_THRESHOLDS_PATH, load_thresholds
from src.independence_common import lbph_config_metadata, resolve_lbph_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pairs-csv",
        default=str(PROJECT_ROOT / "outputs" / "benchmark" / "accuracy_ratio_verification_full_pairs.csv"),
    )
    parser.add_argument(
        "--lbph-config", default="deployed",
        help="LBPH descriptor alias/ID (deployed, selected, or rN_nN_gNxN).",
    )
    parser.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument(
        "--tau-accept", type=float, default=None,
        help="Override the threshold file's tau_accept (diagnostic only).",
    )
    parser.add_argument(
        "--sweep-start", type=float, default=70.0, help="First tau_reject candidate (just above tau_accept)."
    )
    parser.add_argument("--sweep-stop", type=float, default=170.0, help="Last tau_reject candidate.")
    parser.add_argument("--sweep-step", type=float, default=5.0)
    parser.add_argument(
        "--output-json",
        default=str(PROJECT_ROOT / "reports" / "independence" / "tau_reject_tradeoff" / "curve.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    descriptor_config = resolve_lbph_config(args.lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)
    threshold_cfg = load_thresholds(
        args.thresholds_json,
        expected_lbph_config=descriptor_config,
    )
    tau_accept = (
        float(args.tau_accept)
        if args.tau_accept is not None
        else float(threshold_cfg.get("gate", {}).get("tau_accept"))
    )
    genuine_dists: list[float] = []
    impostor_dists: list[float] = []
    with open(args.pairs_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            genuine_dists.append(float(row["lbph_genuine_dist"]))
            impostor_dists.append(float(row["lbph_impostor_dist"]))

    n_genuine = len(genuine_dists)
    n_impostor = len(impostor_dists)

    points = []
    tau_reject = args.sweep_start
    while tau_reject <= args.sweep_stop + 1e-9:
        genuine_hard_rejected = sum(1 for d in genuine_dists if d >= tau_reject)
        impostor_escalated = sum(1 for d in impostor_dists if tau_accept <= d < tau_reject)
        genuine_escalated = sum(1 for d in genuine_dists if tau_accept <= d < tau_reject)
        points.append(
            {
                "tau_reject": round(tau_reject, 2),
                "genuine_hard_reject_pct": round(100.0 * genuine_hard_rejected / n_genuine, 4),
                "genuine_escalated_pct": round(100.0 * genuine_escalated / n_genuine, 4),
                "impostor_escalated_pct": round(100.0 * impostor_escalated / n_impostor, 4),
            }
        )
        tau_reject += args.sweep_step

    max_genuine_dist = max(genuine_dists)
    max_impostor_escalatable_dist = max(impostor_dists)

    out = {
        "source_csv": args.pairs_csv,
        "n_genuine": n_genuine,
        "n_impostor": n_impostor,
        "lbph_config": descriptor_metadata,
        "thresholds_json": str(args.thresholds_json),
        "tau_accept": tau_accept,
        "max_observed_genuine_dist": max_genuine_dist,
        "max_observed_impostor_dist_in_csv": max_impostor_escalatable_dist,
        "points": points,
        "note": (
            "genuine_hard_reject_pct + genuine_escalated_pct + genuine_accepted_outright_pct "
            "(not shown, = accept fraction at tau_accept, constant across the sweep) always "
            "sum to 100. impostor_escalated_pct is a 1:1-protocol proxy per the same caveat "
            "as the hybrid SFace band diagnostic -- not the real 1-to-N escalation event."
        ),
    }

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[INFO] wrote {out_path}")
    print(f"[INFO] max observed genuine dist: {max_genuine_dist:.2f}  (tau_reject above this = 0% hard-reject)")
    for p in points:
        print(
            f"tau_reject={p['tau_reject']:>7.2f}  genuine_hard_reject={p['genuine_hard_reject_pct']:>6.2f}%  "
            f"genuine_escalated={p['genuine_escalated_pct']:>6.2f}%  impostor_escalated={p['impostor_escalated_pct']:>6.2f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
