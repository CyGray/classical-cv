import json
import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

# Ensure root paths
SCRIPT_DIR = Path(__file__).resolve().parent
CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent

OUT_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "pairwise-verification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

JSON_PATH = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "accuracy_ratio_verification_full.json"
if not JSON_PATH.exists():
    # Fallback if full json isn't finished yet when testing
    JSON_PATH = CLASSICAL_CV_DIR / "outputs" / "benchmark" / "accuracy_ratio_verification_smoke20.json"


def render_full_bleed_table(headers, data, col_widths, output_path, title=None, tier_column_idx=0):
    """Render a clean, modern, full-bleed table image using matplotlib."""
    num_rows = len(data)
    num_cols = len(headers)
    
    # Calculate height based on rows
    row_height = 0.35
    header_height = 0.5
    title_height = 0.6 if title else 0
    total_height = title_height + header_height + (num_rows * row_height)
    total_width = sum(col_widths)
    
    fig, ax = plt.subplots(figsize=(total_width, total_height), dpi=300)
    fig.patch.set_facecolor('#ffffff')
    ax.axis('off')
    
    # Create table filling the figure (full bleed)
    table = ax.table(
        cellText=data,
        colLabels=headers,
        colWidths=[w / total_width for w in col_widths],
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1]
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    
    # Styling cells
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor('#cbd5e1')
        cell.set_linewidth(0.6)
        
        if r == 0:
            # Header styling
            cell.set_facecolor('#1e293b')
            cell.get_text().set_color('#ffffff')
            cell.get_text().set_weight('bold')
            cell.get_text().set_fontsize(10)
        else:
            # Body cell styling
            row_data = data[r - 1]
            is_even = (r % 2 == 0)
            
            # Default background
            bg_color = '#f8fafc' if is_even else '#ffffff'
            text_color = '#0f172a'
            text_weight = 'normal'
            
            # Highlight summary/header rows if applicable
            if "Overall" in str(row_data[0]) or "Clean" in str(row_data[0]):
                bg_color = '#e2e8f0'
                text_weight = 'bold'
            elif "Tier" in str(row_data[0]):
                bg_color = '#f1f5f9'
                text_weight = 'bold'
                
            cell.set_facecolor(bg_color)
            cell.get_text().set_color(text_color)
            cell.get_text().set_weight(text_weight)
            
            # Text alignment: left for names/tiers, center for numbers
            if c in (0, 1) and not str(row_data[c]).replace('.','').replace('%','').isdigit():
                cell.get_text().set_ha('left')
                cell.set_fontsize(8.5)
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
        
    tau_accept = payload.get("tau_accept", 67.0084)
    
    # -------------------------------------------------------------
    # 1. Summary / Averages Table
    # -------------------------------------------------------------
    summary_headers = [
        "Evaluation Scope / Tier", 
        "LBPH GAR", "LBPH FAR", "LBPH Acc@tau", "LBPH EER",
        "SFace GAR", "SFace FAR", "SFace Acc@tau", "SFace EER"
    ]
    summary_widths = [3.2, 1.3, 1.3, 1.5, 1.3, 1.3, 1.3, 1.5, 1.3]
    
    summary_rows = []
    
    def format_metrics(metric_dict):
        gar = f"{metric_dict['gar_percent']:.2f}%" if metric_dict.get('gar_percent') is not None else "N/A"
        far = f"{metric_dict['far_percent']:.2f}%" if metric_dict.get('far_percent') is not None else "N/A"
        acc = f"{metric_dict['accuracy_percent']:.2f}%" if metric_dict.get('accuracy_percent') is not None else "N/A"
        eer_val = metric_dict.get('eer', {}).get('eer_percent') if metric_dict.get('eer') else None
        eer = f"{eer_val:.2f}%" if eer_val is not None else "N/A"
        return [gar, far, acc, eer]

    # Clean Baseline
    c_lbph = format_metrics(payload["clean"]["lbph"])
    c_sface = format_metrics(payload["clean"]["sface"])
    summary_rows.append(["Clean Baseline"] + c_lbph + c_sface)
    
    # Tiers
    for tier in ("light", "medium", "heavy"):
        if tier in payload.get("tiers", {}):
            t_lbph = format_metrics(payload["tiers"][tier]["lbph"])
            t_sface = format_metrics(payload["tiers"][tier]["sface"])
            summary_rows.append([f"{tier.capitalize()} Tier Modifications"] + t_lbph + t_sface)
            
    # Overall Modified
    o_lbph = format_metrics(payload["overall_modified"]["lbph"])
    o_sface = format_metrics(payload["overall_modified"]["sface"])
    summary_rows.append(["Overall Modified (41 Suite)"] + o_lbph + o_sface)
    
    summary_out = OUT_DIR / "summary_verification_table.png"
    render_full_bleed_table(summary_headers, summary_rows, summary_widths, summary_out)
    
    # -------------------------------------------------------------
    # 2. Per-Modification Per-Tier Table
    # -------------------------------------------------------------
    per_mod_headers = [
        "Tier", "Modification Name", 
        "LBPH GAR", "LBPH FAR", "LBPH Acc@tau", "LBPH EER",
        "SFace GAR", "SFace FAR", "SFace Acc@tau", "SFace EER"
    ]
    per_mod_widths = [1.2, 2.5, 1.3, 1.3, 1.5, 1.3, 1.3, 1.3, 1.5, 1.3]
    
    per_mod_rows = []
    per_mods = sorted(payload.get("per_modification", []), key=lambda r: (r.get("category_tier") or "", r["modification"]))
    
    for m in per_mods:
        tier = (m.get("category_tier") or "N/A").capitalize()
        mod_name = m["modification"] + (" *" if m.get("detector_canonical") else "")
        lbph_m = format_metrics(m["lbph"])
        sface_m = format_metrics(m["sface"])
        per_mod_rows.append([tier, mod_name] + lbph_m + sface_m)
        
    per_mod_out = OUT_DIR / "per_modification_verification_table.png"
    render_full_bleed_table(per_mod_headers, per_mod_rows, per_mod_widths, per_mod_out)
    
    print("[SUCCESS] Exported both full bleed PNG tables successfully.")

if __name__ == "__main__":
    main()
