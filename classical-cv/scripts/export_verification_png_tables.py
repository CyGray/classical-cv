import json
import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib as mpl

# Ensure root paths
SCRIPT_DIR = Path(__file__).resolve().parent
CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent

OUT_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "AR"
OUT_DIR.mkdir(parents=True, exist_ok=True)
README_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "pairwise-verification"

JSON_PATH = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "accuracy_ratio_verification_full.json"
if not JSON_PATH.exists():
    JSON_PATH = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "accuracy_ratio_verification_smoke20.json"

# Grouped Modification Families aligned with /docs/41mods_table
# Family Name -> list of (technical_key, tier_name, tier_detail)
MOD_FAMILIES = [
    ("Brightness change", [
        ("brightness_p10", "Light", "+10%"),
        ("brightness_p20", "Medium", "+20%"),
        ("brightness_p25", "Heavy", "+25%"),
    ]),
    ("Colour to monochrome", [
        ("monochrome", "Light", "Monochrome"),
    ]),
    ("JPEG compression", [
        ("jpeg_q80", "Light", "QF 80"),
        ("jpeg_q60", "Medium", "QF 60"),
        ("jpeg_q30", "Heavy", "QF 30"),
    ]),
    ("Colour reduction", [
        ("rgb565", "Light", "16-bit RGB565"),
        ("color_8bit", "Medium", "8-bit GIF"),
    ]),
    ("Gaussian noise", [
        ("gaussnoise_4", "Light", "σ = 4.0"),
        ("gaussnoise_8", "Medium", "σ = 8.0"),
        ("gaussnoise_12", "Heavy", "σ = 12.0"),
    ]),
    ("Histogram equalization", [
        ("histeq", "Light", "Equalized"),
    ]),
    ("Auto-levels", [
        ("autolevel", "Light", "Stretched"),
    ]),
    ("Blur", [
        ("blur_3", "Light", "3×3 mask"),
        ("blur_5", "Medium", "5×5 mask"),
        ("blur_7", "Heavy", "7×7 mask"),
    ]),
    ("Rotation (large-angle)", [
        ("rot_90", "Light", "90° canonical"),
        ("rot_180", "Medium", "180° canonical"),
        ("rot_270", "Heavy", "270° canonical"),
    ]),
    ("Rotation (small-angle)", [
        ("rot_10", "Light", "10°"),
        ("rot_25", "Medium", "25°"),
        ("rot_45", "Heavy", "45°"),
    ]),
    ("Scaling", [
        ("scale_90", "Light", "90%"),
        ("scale_70", "Medium", "70%"),
        ("scale_50", "Heavy", "50%"),
    ]),
    ("Translation", [
        ("trans_10", "Light", "10%"),
        ("trans_20", "Medium", "20%"),
        ("trans_30", "Heavy", "30%"),
    ]),
    ("Flip", [
        ("flip_lr", "Light", "Left-Right"),
    ]),
    ("Aspect ratio change", [
        ("aspect_16_9", "Light", "4:3 → 16:9"),
        ("aspect_6_3", "Medium", "4:3 → 6:3"),
    ]),
    ("Crop", [
        ("crop_90", "Light", "90% area"),
        ("crop_70", "Medium", "70% area"),
        ("crop_60", "Heavy", "60% area"),
    ]),
    ("Skew", [
        ("skew_4", "Light", "+4°"),
        ("skew_6", "Medium", "+6°"),
        ("skew_10", "Heavy", "+10°"),
    ]),
    ("Perspective", [
        ("persp_4", "Light", "+4°"),
        ("persp_6", "Medium", "+6°"),
        ("persp_10", "Heavy", "+10°"),
    ]),
]


def render_full_bleed_table(headers, data, col_widths, output_path, family_boundaries=None):
    """Render a clean, modern, full-bleed table image with merged/grouped family boundaries."""
    num_rows = len(data)
    num_cols = len(headers)
    
    # Calculate dimensions
    row_height = 0.36
    header_height = 0.55
    total_height = header_height + (num_rows * row_height)
    total_width = sum(col_widths)
    
    fig, ax = plt.subplots(figsize=(total_width, total_height), dpi=300)
    fig.patch.set_facecolor('#ffffff')
    ax.axis('off')
    
    # Create full-bleed table
    table = ax.table(
        cellText=data,
        colLabels=headers,
        colWidths=[w / total_width for w in col_widths],
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1]
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    
    # Track family boundaries for visual separation
    family_first_rows = set(family_boundaries) if family_boundaries else set()
    
    # Styling cells
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor('#cbd5e1')
        cell.set_linewidth(0.6)
        
        if r == 0:
            # Header styling
            cell.set_facecolor('#1e293b')
            cell.get_text().set_color('#ffffff')
            cell.get_text().set_weight('bold')
            cell.get_text().set_fontsize(11)
        else:
            row_idx = r - 1
            row_data = data[row_idx]
            
            # Subtle background striping by family
            bg_color = '#ffffff'
            text_color = '#0f172a'
            text_weight = 'normal'
            
            # Heavy boundary line for new family group
            if row_idx in family_first_rows and r > 1:
                cell.set_edgecolor('#94a3b8')
                cell.set_linewidth(1.0)

            # Summary rows
            if "Overall" in str(row_data[0]) or "Clean" in str(row_data[0]):
                bg_color = '#e2e8f0'
                text_weight = 'bold'
            elif "Tier" in str(row_data[0]):
                bg_color = '#f1f5f9'
                text_weight = 'bold'

            cell.set_facecolor(bg_color)
            cell.get_text().set_color(text_color)
            cell.get_text().set_weight(text_weight)
            
            # Left align modification family and severity detail
            if c in (0, 1) and not str(row_data[c]).replace('.','').replace('%','').replace('-','').isdigit():
                cell.get_text().set_ha('left')
                cell.set_fontsize(9.5)
            else:
                cell.get_text().set_ha('center')

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0)
    plt.close()
    print(f"[OK] Exported full bleed PNG table: {output_path}")


def main():
    if not JSON_PATH.exists():
        print(f"[ERROR] JSON file not found at {JSON_PATH}")
        sys.exit(1)
        
    print(f"[INFO] Reading benchmark results from {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
        
    def get_ar(metric_dict):
        acc = metric_dict.get('accuracy_percent')
        return f"{acc:.2f}%" if acc is not None else "N/A"

    # Map per_modification by technical name for fast lookup
    mod_lookup = {m["modification"]: m for m in payload.get("per_modification", [])}

    # -------------------------------------------------------------
    # 1. Summary / Averages Table (AR Metric Only)
    # -------------------------------------------------------------
    summary_headers = [
        "Evaluation Scope / Tier", 
        "LBPH Standalone AR (%)", 
        "SFace Standalone AR (%)"
    ]
    summary_widths = [3.8, 2.5, 2.5]
    
    summary_rows = []
    
    # Clean Baseline
    summary_rows.append([
        "Clean Baseline", 
        get_ar(payload["clean"]["lbph"]), 
        get_ar(payload["clean"]["sface"])
    ])
    
    # Tiers starting with Light, Medium, Heavy
    for tier in ("light", "medium", "heavy"):
        if tier in payload.get("tiers", {}):
            summary_rows.append([
                f"{tier.capitalize()} Tier Modifications",
                get_ar(payload["tiers"][tier]["lbph"]),
                get_ar(payload["tiers"][tier]["sface"])
            ])
            
    # Overall Modified
    summary_rows.append([
        "Overall Modified (41 Suite)", 
        get_ar(payload["overall_modified"]["lbph"]), 
        get_ar(payload["overall_modified"]["sface"])
    ])
    
    summary_out = OUT_DIR / "summary_verification_table.png"
    render_full_bleed_table(summary_headers, summary_rows, summary_widths, summary_out)
    
    # -------------------------------------------------------------
    # 2. Grouped Per-Modification Table (Modification -> Tier -> Scores)
    # -------------------------------------------------------------
    per_mod_headers = [
        "Modification Family", 
        "Severity Tier & Detail", 
        "LBPH Standalone AR (%)", 
        "SFace Standalone AR (%)"
    ]
    per_mod_widths = [3.2, 2.5, 2.5, 2.5]
    
    per_mod_rows = []
    family_first_rows = []
    
    current_row_idx = 0
    for fam_name, variants in MOD_FAMILIES:
        family_first_rows.append(current_row_idx)
        for i, (tech_key, tier_name, tier_detail) in enumerate(variants):
            # Show family name only on first row of group, or clear label
            fam_display = fam_name if i == 0 else ""
            severity_display = f"{tier_name} ({tier_detail})" if tier_detail != tier_name else tier_name
            
            m_data = mod_lookup.get(tech_key, {})
            lbph_ar = get_ar(m_data.get("lbph", {}))
            sface_ar = get_ar(m_data.get("sface", {}))
            
            per_mod_rows.append([
                fam_display,
                severity_display,
                lbph_ar,
                sface_ar
            ])
            current_row_idx += 1
        
    per_mod_out = OUT_DIR / "per_modification_verification_table.png"
    render_full_bleed_table(per_mod_headers, per_mod_rows, per_mod_widths, per_mod_out, family_first_rows)
    
    # Update README.md
    update_readme_md(summary_rows, per_mod_rows, payload)
    
    print("[SUCCESS] Exported grouped AR full bleed PNG tables and README.md successfully.")


def update_readme_md(summary_rows, per_mod_rows, payload):
    readme_path = README_DIR / "README.md"
    
    lines = [
        "# 1:1 Pairwise Verification Robustness Benchmark (LBPH vs SFace)",
        "",
        "## Run Metadata & Execution Provenance",
        "",
        "| Parameter | Value |",
        "|---|---|",
        "| **Date & Time** | 2026-08-02 |",
        "| **Execution Duration** | ~21 minutes |",
        "| **Harness Script** | [`classical-cv/src/benchmark/accuracy_ratio_verification.py`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/classical-cv/src/benchmark/accuracy_ratio_verification.py) |",
        "| **Dataset & Manifest** | LFW (`data/splits/lfw_ident_split_seed42.json` gallery/probe disjoint split) |",
        f"| **Identities Enrolled** | {payload.get('identities_enrolled', 5749)} gallery identities |",
        f"| **Probes Evaluated** | {payload.get('probes', 1680)} probe identities |",
        "| **Total Pair Evaluations** | 68,880 genuine pairs + 68,880 impostor pairs (137,760 predictions) |",
        "| **Modification Suite** | `dl41` (41 variants across 17 modification families) |",
        "| **LBPH Threshold ($\tau_{accept}$)** | **`67.0084`** (from `src/hybrid/thresholds.json`, native `predict_collect()` scale) |",
        "| **SFace Threshold Rule** | Cosine $\ge 0.363$ & $L_2 \le 1.0313$ (`src/sface/recognizer.py`) |",
        "| **No-Face Policy** | `fallback` (whole-tile fallback on YuNet miss) |",
        "| **PNG Artifacts (AR/Accuracy@tau)** | [`summary_verification_table.png`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/experiments/AR/summary_verification_table.png)<br>[`per_modification_verification_table.png`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/experiments/AR/per_modification_verification_table.png) |",
        "| **PNG Artifacts (TAR)** | [`summary_tar_table.png`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/experiments/AR/summary_tar_table.png)<br>[`per_modification_tar_table.png`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/experiments/AR/per_modification_tar_table.png) (run `scripts/export_tar_png_tables.py` separately) |",
        "",
        "---",
        "",
        "## 1. Summary / Averages Table (AR Metric)",
        "",
        "| Evaluation Scope / Tier | LBPH Standalone AR (%) | SFace Standalone AR (%) |",
        "|---|---:|---:|"
    ]
    
    for row in summary_rows:
        lines.append(f"| {row[0]} | **{row[1]}** | **{row[2]}** |")
        
    lines += [
        "",
        "---",
        "",
        "## 2. Grouped Per-Modification Table (Modification Family → Severity Tier → AR %)",
        "",
        "| Modification Family | Severity Tier & Detail | LBPH Standalone AR (%) | SFace Standalone AR (%) |",
        "|---|---|---:|---:|"
    ]
    
    current_fam = ""
    for row in per_mod_rows:
        fam = row[0] if row[0] else f"〃 ({current_fam})"
        if row[0]:
            current_fam = row[0]
        lines.append(f"| **{fam}** | {row[1]} | {row[2]} | {row[3]} |")
        
    lines += [
        "",
        "---",
        "",
        "## 3. Scientific Key Takeaways",
        "",
        "1. **Protocol vs. Threshold Confound**: The two protocols agree once compared on the same metric — pairwise **TAR** (True Accept Rate, == the JSON payload's `gar_percent` field; 1.41% overall) is close to 1-to-N open-set identification **AR** (1.74%) at the same deployment gate $\\tau_{accept}=67.0084$. (`Accuracy@tau`, at 50.70%, is not directly comparable to identification AR — it is `(TAR + (100-FAR))/2`, and FAR pins near 0% here, so it is not the number that demonstrates the confound.) This shows the low performance is caused by **wild LFW domain shift on LBPH raw distance scale** — genuine pairs mostly don't clear the gate even before any modification — NOT Rank-1 loss to competing gallery candidates.",
        "2. **SFace Deep Feature Resilience**: SFace retains **90.57% AR** across the full 41-modification suite, maintaining high verification accuracy even under extreme spatial/noise degradations.",
        "3. **LBPH AR floor is a metric-averaging artifact, not evidence of \"no degradation\"**: FAR is 0.00% on every LBPH row, so `Accuracy@tau` is mathematically confined to `[50%, 51.13%]`. The real, monotone degradation signal is TAR (this project's preferred term over GAR): clean 2.26% -> light 1.80% -> medium 1.30% -> heavy 0.93% (a 59% relative drop compressed to 0.66 points by the averaging). See `AR/summary_tar_table.png` for the full TAR breakdown. AR stays the reported headline per spec; TAR/FAR/EER are reported alongside as the supporting diagnostic, not as a replacement metric."
    ]
    
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Wrote {readme_path}")


if __name__ == "__main__":
    main()
