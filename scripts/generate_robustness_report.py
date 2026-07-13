#!/usr/bin/env python3
"""Generate Light/Medium/Heavy robustness tables for Hybrid Models and save as PNG.

This script parses reports/benchmark/accuracy_ratio_hybrid.json,
buckets the 41 modifications into severity tiers (Light, Medium, Heavy)
identical to make_report_figures.py, prints/saves markdown tables, and
renders them to beautiful PNG images using matplotlib.
"""

import argparse
import json
import math
import os
import shutil
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Directories
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
BENCHMARK_DIR = REPORTS_DIR / "benchmark"
FIGURES_DIR = REPORTS_DIR / "figures"

# Display mapping
DISPLAY_MODES = {
    "cv_only": "LBPH (CV Only)",
    "dl_only": "SFace (DL Only)",
    "cascade": "Hybrid Cascade",
    "parallel": "Parallel Hybrid (Ceiling)"
}

# Color palettes for the PNG tables
THEME_COLORS = {
    "cv_only": {"header": "#3f51b5", "header_text": "white", "bg_light": "#e8eaf6"},  # Indigo
    "dl_only": {"header": "#2e7d32", "header_text": "white", "bg_light": "#e8f5e9"},  # Green
    "cascade": {"header": "#ef6c00", "header_text": "white", "bg_light": "#fff3e0"},  # Orange
    "parallel": {"header": "#455a64", "header_text": "white", "bg_light": "#eceff1"}  # Blue Grey
}

SEVERITY = {
    "brightness_up": lambda lv: abs(lv),
    "brightness_down": lambda lv: abs(lv),
    "contrast_up": lambda lv: abs(lv - 1.0),
    "contrast_down": lambda lv: abs(lv - 1.0),
    "gamma_up": lambda lv: abs(math.log(lv)),
    "gamma_down": lambda lv: abs(math.log(lv)),
    "gaussian_noise": lambda lv: abs(lv),
    "gaussian_blur": lambda lv: abs(lv),
    "motion_blur": lambda lv: abs(lv),
    "rotation": lambda lv: abs(lv),
    "zoom": lambda lv: abs(lv - 1.0),
    "occlusion": lambda lv: abs(lv),
}

def tier_ar(modification: str, levels: list[dict], mode: str) -> dict:
    """Bucket a modification's levels into Light/Medium/Heavy by severity.

    Symmetric levels share a severity and land in the same tier.
    """
    sev_fn = SEVERITY[modification]
    sevs = sorted({round(sev_fn(lv["level"]), 9) for lv in levels})
    m = len(sevs)
    buckets = {0: [], 1: [], 2: []}
    for lv in levels:
        s = round(sev_fn(lv["level"]), 9)
        rank = sevs.index(s)
        f = rank / (m - 1) if m > 1 else 0.0
        buckets[int(round(f * 2))].append(lv["ar_percent"])
    out = {}
    for idx, name in [(0, "light"), (1, "medium"), (2, "heavy")]:
        out[name] = float(np.mean(buckets[idx])) if buckets[idx] else None
    out["mean"] = float(np.mean([lv["ar_percent"] for lv in levels]))
    return out

def fmt(x, nd=1, suffix="%"):
    return "-" if x is None else f"{x:.{nd}f}{suffix}"

def main():
    parser = argparse.ArgumentParser(description="Generate Light/Medium/Heavy tables for hybrid models.")
    parser.add_argument("--input-json", default=str(BENCHMARK_DIR / "accuracy_ratio_hybrid.json"),
                        help="Path to the accuracy ratio hybrid JSON file.")
    parser.add_argument("--output-md", default=str(BENCHMARK_DIR / "robustness_tables.md"),
                        help="Path to save the output markdown tables.")
    parser.add_argument("--export-dir", default="/data/data/com.termux/files/home/storage/shared/Pictures/CV_Reports",
                        help="Termux shared folder to export PNGs.")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Error: {input_path} does not exist. Please run src/benchmark/accuracy_ratio_hybrid.py first.")
        return 1

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    
    modes = payload.get("overall_ar_percent", {}).keys()
    if not modes:
        modes = ["cv_only", "dl_only", "cascade", "parallel"]

    # Retrieve modifications from payload
    mods_list = payload["modifications"]
    
    # Sort modifications by LBPH (cv_only) mean AR descending (or keep default order)
    # Let's sort by cv_only mean AR descending to match make_report_figures.py
    cv_means = {}
    for r in mods_list:
        cv_means[r["modification"]] = r["ar_percent"]["cv_only"]
    mods_sorted = sorted(mods_list, key=lambda x: -cv_means[x["modification"]])
    
    # Process tiers for each mode
    tables = {}
    for mode in modes:
        tables[mode] = {}
        for r in mods_sorted:
            mod_name = r["modification"]
            # To get levels for this mode: each level row in JSON has 'ar_percent' dict
            levels_extracted = []
            for lv in r["levels"]:
                levels_extracted.append({
                    "level": lv["level"],
                    "ar_percent": lv["ar_percent"][mode]
                })
            tables[mode][mod_name] = tier_ar(mod_name, levels_extracted, mode)

    # Compute overall average for each tier
    overalls = {}
    for mode in modes:
        overalls[mode] = {
            "light": np.mean([tables[mode][m]["light"] for m in tables[mode] if tables[mode][m]["light"] is not None]),
            "medium": np.mean([tables[mode][m]["medium"] for m in tables[mode] if tables[mode][m]["medium"] is not None]),
            "heavy": np.mean([tables[mode][m]["heavy"] for m in tables[mode] if tables[mode][m]["heavy"] is not None]),
            "mean": payload["overall_ar_percent"][mode]
        }

    # Generate Markdown Output
    md_lines = [
        "# Hybrid Models Robustness - Light / Medium / Heavy Tiers",
        "",
        f"Originals: `{payload['originals_dir']}` ({payload['originals']} tiles) | "
        f"variant count: {payload['variant_count']} | seed={payload['seed']}",
        "",
        "AR = K/M (correct identity AND within thresholds) per (modification, level).",
        "Symmetric levels (e.g. rotation -5deg & +5deg) land in the same tier.",
        "",
    ]

    for mode in modes:
        display_name = DISPLAY_MODES.get(mode, mode)
        md_lines += [
            f"## Table - {display_name}",
            "",
            "| Modification | Light | Medium | Heavy | Mean (All levels) |",
            "| :--- | ---: | ---: | ---: | ---: |"
        ]
        for r in mods_sorted:
            m = r["modification"]
            t = tables[mode][m]
            md_lines.append(
                f"| {m} | {fmt(t['light'])} | {fmt(t['medium'])} | {fmt(t['heavy'])} | {fmt(t['mean'])} |"
            )
        # Overall row
        ov = overalls[mode]
        md_lines.append(
            f"| **Overall** | **{fmt(ov['light'])}** | **{fmt(ov['medium'])}** | **{fmt(ov['heavy'])}** | **{fmt(ov['mean'])}** |"
        )
        md_lines += ["", "---", ""]

    # Write Markdown file
    output_md_path = Path(args.output_md)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[OK] Wrote Markdown tables to {output_md_path}")

    # Generate PNG using Matplotlib
    # We will generate individual PNGs for each model and a single composite 2x2 grid PNG
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate Individual PNGs
    individual_pngs = {}
    for mode in modes:
        display_name = DISPLAY_MODES.get(mode, mode)
        fig, ax = plt.subplots(figsize=(8, 4.3))
        ax.axis("off")
        
        headers = ["Modification", "Light", "Medium", "Heavy", "Mean"]
        cell_text = []
        for r in mods_sorted:
            m = r["modification"]
            t = tables[mode][m]
            cell_text.append([
                m,
                fmt(t['light']),
                fmt(t['medium']),
                fmt(t['heavy']),
                fmt(t['mean'])
            ])
        ov = overalls[mode]
        cell_text.append([
            "Overall",
            fmt(ov['light']),
            fmt(ov['medium']),
            fmt(ov['heavy']),
            fmt(ov['mean'])
        ])
        
        # Color palette setting
        theme = THEME_COLORS.get(mode, {"header": "#333333", "header_text": "white", "bg_light": "#f9f9f9"})
        
        table = ax.table(
            cellText=cell_text,
            colLabels=headers,
            loc="center",
            cellLoc="center",
            colWidths=[0.35, 0.15, 0.15, 0.15, 0.20]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.1, 1.25)
        
        # Style headers and cells
        for col_idx in range(len(headers)):
            cell = table[(0, col_idx)]
            cell.set_facecolor(theme["header"])
            cell.set_text_props(color=theme["header_text"], weight="bold")
            
        for row_idx in range(1, len(cell_text) + 1):
            is_overall = (row_idx == len(cell_text))
            for col_idx in range(len(headers)):
                cell = table[(row_idx, col_idx)]
                if is_overall:
                    cell.set_text_props(weight="bold")
                    cell.set_facecolor("#e0e0e0")
                elif row_idx % 2 == 0:
                    cell.set_facecolor(theme["bg_light"])
                    
        ax.set_title(f"Accuracy Ratio by Severity Tier - {display_name}\n(La Salle Test, 41-mod suite)",
                     fontsize=12, fontweight="bold", pad=10)
        
        fig.tight_layout()
        out_png = FIGURES_DIR / f"robustness_table_{mode}.png"
        fig.savefig(out_png, dpi=180, bbox_inches="tight")
        plt.close(fig)
        individual_pngs[mode] = out_png
        print(f"[OK] Wrote individual PNG to {out_png}")

    # 2. Generate a 2x2 Composite Grid PNG
    fig, axes = plt.subplots(2, 2, figsize=(18, 9.6))
    axes_flat = axes.flatten()
    
    for i, mode in enumerate(modes):
        ax = axes_flat[i]
        ax.axis("off")
        display_name = DISPLAY_MODES.get(mode, mode)
        
        headers = ["Modification", "Light", "Medium", "Heavy", "Mean"]
        cell_text = []
        for r in mods_sorted:
            m = r["modification"]
            t = tables[mode][m]
            cell_text.append([
                m,
                fmt(t['light']),
                fmt(t['medium']),
                fmt(t['heavy']),
                fmt(t['mean'])
            ])
        ov = overalls[mode]
        cell_text.append([
            "Overall",
            fmt(ov['light']),
            fmt(ov['medium']),
            fmt(ov['heavy']),
            fmt(ov['mean'])
        ])
        
        theme = THEME_COLORS.get(mode, {"header": "#333333", "header_text": "white", "bg_light": "#f9f9f9"})
        
        table = ax.table(
            cellText=cell_text,
            colLabels=headers,
            loc="center",
            cellLoc="center",
            colWidths=[0.32, 0.16, 0.16, 0.16, 0.20]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)
        table.scale(1.0, 1.15)
        
        # Style headers and cells
        for col_idx in range(len(headers)):
            cell = table[(0, col_idx)]
            cell.set_facecolor(theme["header"])
            cell.set_text_props(color=theme["header_text"], weight="bold")
            
        for row_idx in range(1, len(cell_text) + 1):
            is_overall = (row_idx == len(cell_text))
            for col_idx in range(len(headers)):
                cell = table[(row_idx, col_idx)]
                if is_overall:
                    cell.set_text_props(weight="bold")
                    cell.set_facecolor("#dcdcdc")
                elif row_idx % 2 == 0:
                    cell.set_facecolor(theme["bg_light"])
                    
        ax.set_title(display_name, fontsize=12, fontweight="bold", pad=8)

    fig.suptitle("Hybrid Models Robustness Comparison by Severity Tier (Light / Medium / Heavy)\nLa Salle held-out test, 41-modification suite",
                 fontsize=16, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    composite_png = FIGURES_DIR / "hybrid_robustness_tables.png"
    fig.savefig(composite_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Wrote composite PNG to {composite_png}")

    # Export to Termux shared Pictures folder
    export_path = Path(args.export_dir)
    try:
        export_path.mkdir(parents=True, exist_ok=True)
        # Copy composite
        shutil.copy(composite_png, export_path / "hybrid_robustness_tables.png")
        # Copy individual
        for mode, path in individual_pngs.items():
            shutil.copy(path, export_path / f"robustness_table_{mode}.png")
        print(f"[OK] Exported all PNGs to Android Gallery folder: {export_path}")
    except Exception as e:
        print(f"[WARN] Failed to export to Android Gallery folder {export_path}: {e}")
        print("[INFO] Files are still available in reports/figures/")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
