"""TAR-only variant of export_verification_png_tables.py.

Renders the same full-bleed table layout, but the metric column is TAR (True
Accept Rate == GAR, the genuine-pair accept rate) instead of Accuracy@tau.
TAR is this project's preferred term over GAR going forward (see
ar-is-mandated-metric memory / robustness-protocol-map skill) - AR
(Accuracy@tau) stays the mandated headline metric elsewhere; this table is a
deliberate, separately-labeled diagnostic view, not a replacement for it.
"""
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from export_verification_png_tables import MOD_FAMILIES, render_full_bleed_table  # noqa: E402

CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent

OUT_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "AR"
OUT_DIR.mkdir(parents=True, exist_ok=True)

JSON_PATH = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "accuracy_ratio_verification_full.json"
if not JSON_PATH.exists():
    JSON_PATH = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "accuracy_ratio_verification_smoke20.json"


def get_tar(metric_dict: dict) -> str:
    tar = metric_dict.get("gar_percent")
    return f"{tar:.2f}%" if tar is not None else "N/A"


def main() -> None:
    if not JSON_PATH.exists():
        print(f"[ERROR] JSON file not found at {JSON_PATH}")
        sys.exit(1)

    print(f"[INFO] Reading benchmark results from {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    mod_lookup = {m["modification"]: m for m in payload.get("per_modification", [])}

    # -------------------------------------------------------------
    # 1. Summary / Averages Table (TAR Metric Only)
    # -------------------------------------------------------------
    summary_headers = [
        "Evaluation Scope / Tier",
        "LBPH Standalone TAR (%)",
        "SFace Standalone TAR (%)",
    ]
    summary_widths = [3.8, 2.5, 2.5]

    summary_rows = [[
        "Clean Baseline",
        get_tar(payload["clean"]["lbph"]),
        get_tar(payload["clean"]["sface"]),
    ]]

    for tier in ("light", "medium", "heavy"):
        if tier in payload.get("tiers", {}):
            summary_rows.append([
                f"{tier.capitalize()} Tier Modifications",
                get_tar(payload["tiers"][tier]["lbph"]),
                get_tar(payload["tiers"][tier]["sface"]),
            ])

    summary_rows.append([
        "Overall Modified (41 Suite)",
        get_tar(payload["overall_modified"]["lbph"]),
        get_tar(payload["overall_modified"]["sface"]),
    ])

    summary_out = OUT_DIR / "summary_tar_table.png"
    render_full_bleed_table(summary_headers, summary_rows, summary_widths, summary_out)

    # -------------------------------------------------------------
    # 2. Grouped Per-Modification Table (Modification -> Tier -> TAR)
    # -------------------------------------------------------------
    per_mod_headers = [
        "Modification Family",
        "Severity Tier & Detail",
        "LBPH Standalone TAR (%)",
        "SFace Standalone TAR (%)",
    ]
    per_mod_widths = [3.2, 2.5, 2.5, 2.5]

    per_mod_rows = []
    family_first_rows = []
    current_row_idx = 0
    for fam_name, variants in MOD_FAMILIES:
        family_first_rows.append(current_row_idx)
        for i, (tech_key, tier_name, tier_detail) in enumerate(variants):
            fam_display = fam_name if i == 0 else ""
            severity_display = f"{tier_name} ({tier_detail})" if tier_detail != tier_name else tier_name

            m_data = mod_lookup.get(tech_key, {})
            lbph_tar = get_tar(m_data.get("lbph", {}))
            sface_tar = get_tar(m_data.get("sface", {}))

            per_mod_rows.append([fam_display, severity_display, lbph_tar, sface_tar])
            current_row_idx += 1

    per_mod_out = OUT_DIR / "per_modification_tar_table.png"
    render_full_bleed_table(per_mod_headers, per_mod_rows, per_mod_widths, per_mod_out, family_first_rows)

    print("[SUCCESS] Exported TAR-only full bleed PNG tables.")


if __name__ == "__main__":
    main()
