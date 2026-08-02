"""PNG table exporter for training=test (same-image self-match reference runs).

Generates a clean full-bleed summary table comparing the main 5,749-identity
legacy same-image benchmark against the 423-identity multi-shot self-match run.
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from export_verification_png_tables import render_full_bleed_table  # noqa: E402

CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent
OUT_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "robustness_variants" / "lfw-multishot-lbph"

MAIN_LEGACY_JSON = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "lfw2_robustness" / "accuracy_ratio_hybrid.json"
SELFMATCH_JSON = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "lfw_multishot_selfmatch" / "accuracy_ratio_hybrid.json"


def fmt_pct(v) -> str:
    return f"{v:.2f}%" if v is not None else "N/A"


def mean_escalation(payload: dict) -> float:
    mods = payload.get("modifications", [])
    if not mods:
        return 0.0
    return sum(m.get("cascade_escalation_percent", 0.0) for m in mods) / len(mods)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_png = OUT_DIR / "summary_training_test_table.png"

    rows = []

    # 1. Main legacy same-image baseline (N=5,749)
    if MAIN_LEGACY_JSON.exists():
        legacy_data = json.loads(MAIN_LEGACY_JSON.read_text(encoding="utf-8"))
        clean_legacy = legacy_data["clean_acceptance_percent"]
        overall_legacy = legacy_data["overall_ar_percent"]
        esc_legacy = mean_escalation(legacy_data)
        n_legacy = legacy_data.get("originals", 5749)

        for mode, label in [("cv_only", "LBPH (cv_only)"), ("dl_only", "SFace (dl_only)"), ("cascade", "Cascade (hybrid)")]:
            rows.append([
                f"Main LFW2 Baseline (N={n_legacy:,}) - {label}",
                fmt_pct(clean_legacy.get(mode)),
                fmt_pct(overall_legacy.get(mode)),
                fmt_pct(esc_legacy) if mode == "cascade" else "—",
                f"{n_legacy:,}",
            ])

    # 2. Multishot self-match (N=423)
    if SELFMATCH_JSON.exists():
        selfmatch_data = json.loads(SELFMATCH_JSON.read_text(encoding="utf-8"))
        clean_sm = selfmatch_data["clean_acceptance_percent"]
        overall_sm = selfmatch_data["overall_ar_percent"]
        esc_sm = mean_escalation(selfmatch_data)
        n_sm = selfmatch_data.get("originals", 423)

        for mode, label in [("cv_only", "LBPH (cv_only)"), ("cascade", "Cascade (hybrid)")]:
            rows.append([
                f"Multi-Shot Self-Match (N={n_sm:,}) - {label}",
                fmt_pct(clean_sm.get(mode)),
                fmt_pct(overall_sm.get(mode)),
                fmt_pct(esc_sm) if mode == "cascade" else "—",
                f"{n_sm:,}",
            ])

    headers = ["Run / Mode (training=test)", "Clean AR %", "41-Mod Avg AR %", "Escalation %", "N (probes)"]
    widths = [5.6, 2.2, 2.5, 2.2, 1.8]

    render_full_bleed_table(headers, rows, widths, out_png)
    print(f"[SUCCESS] Wrote training=test table PNG to {out_png}")


if __name__ == "__main__":
    main()
