"""Lean summary table: hybrid LFW2 identification benchmark, all three modes.

Same full-bleed PNG layout as export_verification_png_tables.py /
export_tar_png_tables.py, but for the 1-to-N IDENTIFICATION protocol
(accuracy_ratio_hybrid.py / run_lfw2_robustness.py), not 1:1 verification --
these are NOT the same metric as docs/experiments/pairwise-verification's
tables, see robustness-protocol-map Sec 0. One compact table, not a
41-row per-modification breakdown: Mode x [AR clean, AR overall-DL41,
escalation %, mean latency].

Escalation % only applies to cascade (cv_only/dl_only never escalate -- shown
as "-", not "0%", since the concept doesn't apply, it isn't zero).

Latency is read from a SEPARATE, isolated single-process run
(--latency-json), not from the main parallel/--reuse-engine-scores run
(--ar-json) -- see docs/experiments/hybrid-identification/README.md for why:
the orchestrator (run_lfw2_robustness.py) unconditionally passes
--reuse-engine-scores for AR/escalation runs (~3x less compute), which makes
per-mode latency numbers meaningless (cascade's "latency" becomes a cache
lookup, not real LBPH+SFace compute). Mixing the two sources without saying
so would misrepresent isolated per-probe cost as parallel-run timing.
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from export_verification_png_tables import render_full_bleed_table  # noqa: E402

CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent
OUT_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "robustness_variants" / "hybrid-identification"

MODE_LABELS = {
    "cv_only": "LBPH (cv_only)",
    "dl_only": "SFace (dl_only)",
    "cascade": "Cascade (hybrid)",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ar-json",
        default=str(CLASSICAL_CV_DIR / "outputs" / "benchmark" / "lfw2_robustness_canon" / "accuracy_ratio_hybrid.json"),
    )
    p.add_argument(
        "--latency-json",
        default=str(CLASSICAL_CV_DIR / "outputs" / "benchmark" / "lfw2_robustness_canon_latency_575" / "accuracy_ratio_hybrid.json"),
    )
    p.add_argument("--output-png", default=str(OUT_DIR / "summary_identification_table.png"))
    return p.parse_args()


def fmt_pct(v) -> str:
    return f"{v:.2f}%" if v is not None else "N/A"


def main() -> None:
    args = parse_args()
    ar_path = Path(args.ar_json)
    lat_path = Path(args.latency_json)
    if not ar_path.exists():
        print(f"[ERROR] AR/escalation JSON not found at {ar_path}")
        sys.exit(1)
    if not lat_path.exists():
        print(f"[ERROR] latency JSON not found at {lat_path}")
        sys.exit(1)

    ar_payload = json.loads(ar_path.read_text(encoding="utf-8"))
    lat_payload = json.loads(lat_path.read_text(encoding="utf-8"))

    clean_ar = ar_payload["clean_acceptance_percent"]
    overall_ar = ar_payload["overall_ar_percent"]
    mods = ar_payload["modifications"]
    mean_escalation = sum(m["cascade_escalation_percent"] for m in mods) / len(mods)
    lat = lat_payload["mean_latency_ms"]

    headers = [
        "Mode",
        "AR % (clean)",
        "AR % (41-mod avg)",
        "Escalation %",
        "Mean latency (ms, isolated)",
    ]
    widths = [3.0, 2.2, 2.5, 2.2, 3.2]

    rows = []
    for mode in ("cv_only", "dl_only", "cascade"):
        esc = f"{mean_escalation:.2f}%" if mode == "cascade" else "-"
        rows.append([
            MODE_LABELS[mode],
            fmt_pct(clean_ar.get(mode)),
            fmt_pct(overall_ar.get(mode)),
            esc,
            f"{lat[mode]:.2f}",
        ])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output_png)
    render_full_bleed_table(headers, rows, widths, out_path)
    print(f"[SUCCESS] wrote {out_path}")
    print(f"[INFO] mean cascade escalation across 41 mods: {mean_escalation:.2f}%")


if __name__ == "__main__":
    main()
