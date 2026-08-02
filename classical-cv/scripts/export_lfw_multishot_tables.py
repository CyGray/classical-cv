"""PNG table exporter for the LFW multi-shot LBPH diagnostic experiment
(docs/experiments/lfw-multishot-lbph/README.md, workspace root).

Two variants of the legacy transform_sensitivity identification protocol
(src/benchmark/accuracy_ratio_hybrid.py, no --split-manifest), run against
custom multi-shot enrollment (scripts/pipeline/enroll_lfw_multishot.py) over
the 423 LFW identities with >= 5 images:

* ``selfmatch`` - LBPH trained on ALL images per identity; probe == the same
  reference image used for SFace gallery / last-LBPH-image. Self-match leak
  by design -- a reference/ceiling number, NEVER "Accuracy Ratio".
* ``heldout``   - the reference image is excluded entirely from training and
  the SFace gallery; probe = that held-out image. Genuine gallery/probe
  disjoint at the individual-image level -- this is the number that answers
  the actual research question (does multi-shot training alone move AR).

No new table-rendering code: reuses ``render_full_bleed_table`` from
``export_verification_png_tables.py`` (same pattern
``export_hybrid_identification_summary_table.py`` already uses) and the same
``MOD_FAMILIES`` grouping (family display names / tier ordering) so the
per-modification table reads consistently with the pairwise-verification and
AR tables elsewhere in ``docs/experiments/``.

Writes:
  docs/experiments/lfw-multishot-lbph/summary_multishot_table.png
  docs/experiments/lfw-multishot-lbph/per_modification_multishot_table.png
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from export_verification_png_tables import MOD_FAMILIES, render_full_bleed_table  # noqa: E402

CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent
OUT_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "robustness_variants" / "lfw-multishot-lbph"

# Existing main LFW2 1-image gallery/probe-disjoint identification baseline
# (docs/experiments/hybrid-identification/README.md, canon thresholds,
# 5,749 enrolled / 1,680 probes) -- cited here as fixed reference numbers,
# not re-read from a JSON file (that run lives under a different protocol
# entirely, --split-manifest, and is not re-run by this script).
BASELINE_1IMG = {
    "clean_ar": {"cv_only": 2.26, "cascade": 92.02},
    "overall_ar": {"cv_only": 1.41, "cascade": 80.65},
    "escalation": 97.51,
    "n": 1680,
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--selfmatch-json",
        default=str(CLASSICAL_CV_DIR / "outputs" / "benchmark" / "lfw_multishot_selfmatch" / "accuracy_ratio_hybrid.json"),
    )
    p.add_argument(
        "--heldout-json",
        default=str(CLASSICAL_CV_DIR / "outputs" / "benchmark" / "lfw_multishot_heldout" / "accuracy_ratio_hybrid.json"),
    )
    p.add_argument(
        "--singleshot-json",
        default=str(CLASSICAL_CV_DIR / "outputs" / "benchmark" / "lfw_multishot_singleshot" / "accuracy_ratio_hybrid.json"),
        help="1-image-per-identity CONTROL for heldout - same 423-identity population, same "
             "probes, same gallery-size, only training-images-per-identity differs.",
    )
    p.add_argument("--summary-png", default=str(OUT_DIR / "summary_multishot_table.png"))
    p.add_argument("--clean-summary-png", default=str(OUT_DIR / "summary_multishot_clean_table.png"))
    p.add_argument("--per-mod-png", default=str(OUT_DIR / "per_modification_multishot_table.png"))
    return p.parse_args()


def fmt_pct(v) -> str:
    return f"{v:.2f}%" if v is not None else "N/A"


def mean_escalation(payload: dict) -> float:
    mods = payload["modifications"]
    return sum(m["cascade_escalation_percent"] for m in mods) / len(mods)


def build_summary_rows(selfmatch: dict, heldout: dict, singleshot: dict) -> list[list[str]]:
    rows = []
    rows.append([
        "1-image baseline (main LFW2 run, N=5,749 gallery) - LBPH (cv_only)", "AR",
        fmt_pct(BASELINE_1IMG["clean_ar"]["cv_only"]), fmt_pct(BASELINE_1IMG["overall_ar"]["cv_only"]),
        "-", str(BASELINE_1IMG["n"]),
    ])
    rows.append([
        "1-image baseline (main LFW2 run, N=5,749 gallery) - Cascade", "AR",
        fmt_pct(BASELINE_1IMG["clean_ar"]["cascade"]), fmt_pct(BASELINE_1IMG["overall_ar"]["cascade"]),
        fmt_pct(BASELINE_1IMG["escalation"]), str(BASELINE_1IMG["n"]),
    ])
    for label, payload, kind in (
        ("multishot_selfmatch", selfmatch, "SELF-MATCH (reference, NOT AR)"),
        ("multishot_singleshot (control: 423 gallery, 1 img/id)", singleshot, "AR (genuine disjoint, control)"),
        ("multishot_heldout (423 gallery, multi-shot)", heldout, "AR (genuine disjoint)"),
    ):
        n = payload["originals"]
        esc = mean_escalation(payload)
        for mode, mode_label in (("cv_only", "LBPH (cv_only)"), ("cascade", "Cascade")):
            rows.append([
                f"{label} - {mode_label}", kind,
                fmt_pct(payload["clean_acceptance_percent"][mode]),
                fmt_pct(payload["overall_ar_percent"][mode]),
                (fmt_pct(esc) if mode == "cascade" else "-"),
                str(n),
            ])
    return rows


def build_clean_summary_rows(heldout: dict, singleshot: dict) -> list[list[str]]:
    rows = []
    esc_ss = mean_escalation(singleshot)
    rows.append([
        "Control Group (1 img) - LBPH only",
        fmt_pct(singleshot["clean_acceptance_percent"]["cv_only"]),
        fmt_pct(singleshot["overall_ar_percent"]["cv_only"]),
        "-",
    ])
    rows.append([
        "Control Group (1 img) - Hybrid",
        fmt_pct(singleshot["clean_acceptance_percent"]["cascade"]),
        fmt_pct(singleshot["overall_ar_percent"]["cascade"]),
        fmt_pct(esc_ss),
    ])

    esc_ho = mean_escalation(heldout)
    rows.append([
        "5 img / identity - LBPH only",
        fmt_pct(heldout["clean_acceptance_percent"]["cv_only"]),
        fmt_pct(heldout["overall_ar_percent"]["cv_only"]),
        "-",
    ])
    rows.append([
        "5 img / identity - Hybrid",
        fmt_pct(heldout["clean_acceptance_percent"]["cascade"]),
        fmt_pct(heldout["overall_ar_percent"]["cascade"]),
        fmt_pct(esc_ho),
    ])
    return rows


def build_per_mod_rows(selfmatch: dict, heldout: dict, singleshot: dict) -> tuple[list[list[str]], list[int]]:
    sm_lookup = {r["modification"]: r for r in selfmatch["modifications"]}
    ho_lookup = {r["modification"]: r for r in heldout["modifications"]}
    ss_lookup = {r["modification"]: r for r in singleshot["modifications"]}

    def cell(lookup: dict, key: str, mode: str) -> str:
        row = lookup.get(key)
        if not row:
            return "N/A"
        return fmt_pct(row["ar_percent"].get(mode))

    rows = []
    family_first_rows = []
    current_row_idx = 0
    for fam_name, variants in MOD_FAMILIES:
        family_first_rows.append(current_row_idx)
        for i, (tech_key, tier_name, tier_detail) in enumerate(variants):
            fam_display = fam_name if i == 0 else ""
            severity_display = f"{tier_name} ({tier_detail})" if tier_detail != tier_name else tier_name
            rows.append([
                fam_display,
                severity_display,
                cell(sm_lookup, tech_key, "cv_only"),
                cell(ss_lookup, tech_key, "cv_only"),
                cell(ho_lookup, tech_key, "cv_only"),
                cell(ho_lookup, tech_key, "cascade"),
            ])
            current_row_idx += 1
    return rows, family_first_rows


def main() -> None:
    args = parse_args()
    sm_path = Path(args.selfmatch_json)
    ho_path = Path(args.heldout_json)
    if not sm_path.exists():
        print(f"[ERROR] selfmatch JSON not found at {sm_path}")
        sys.exit(1)
    if not ho_path.exists():
        print(f"[ERROR] heldout JSON not found at {ho_path}")
        sys.exit(1)

    ss_path = Path(args.singleshot_json)
    if not ss_path.exists():
        print(f"[ERROR] singleshot JSON not found at {ss_path}")
        sys.exit(1)

    selfmatch = json.loads(sm_path.read_text(encoding="utf-8"))
    heldout = json.loads(ho_path.read_text(encoding="utf-8"))
    singleshot = json.loads(ss_path.read_text(encoding="utf-8"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

def render_clean_summary_table(heldout: dict, singleshot: dict, output_path: Path) -> None:
    """Render a clean, modern, full-bleed table image with adjacent Control and 5-img columns and colored deltas."""
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    # Calculate metrics & deltas
    ss_c_lbph = singleshot["clean_acceptance_percent"]["cv_only"]
    ho_c_lbph = heldout["clean_acceptance_percent"]["cv_only"]
    d_c_lbph = ho_c_lbph - ss_c_lbph

    ss_o_lbph = singleshot["overall_ar_percent"]["cv_only"]
    ho_o_lbph = heldout["overall_ar_percent"]["cv_only"]
    d_o_lbph = ho_o_lbph - ss_o_lbph

    ss_c_casc = singleshot["clean_acceptance_percent"]["cascade"]
    ho_c_casc = heldout["clean_acceptance_percent"]["cascade"]
    d_c_casc = ho_c_casc - ss_c_casc

    ss_o_casc = singleshot["overall_ar_percent"]["cascade"]
    ho_o_casc = heldout["overall_ar_percent"]["cascade"]
    d_o_casc = ho_o_casc - ss_o_casc

    ss_esc = mean_escalation(singleshot)
    ho_esc = mean_escalation(heldout)
    d_esc = ho_esc - ss_esc

    def fmt_val_delta(val: float, delta: float) -> tuple[str, str, str]:
        val_str = f"{val:.2f}%"
        if abs(delta) < 0.005:
            delta_str = " (0.00%)"
            delta_color = "#64748b"
        elif delta > 0:
            delta_str = f" (+{delta:.2f}%)"
            delta_color = "#15803d"  # green
        else:
            delta_str = f" ({delta:.2f}%)"
            delta_color = "#dc2626"  # red
        return val_str, delta_str, delta_color

    rows = [
        {
            "mode": "LBPH only",
            "cells": [
                {"type": "text", "val": "LBPH only", "ha": "left", "weight": "bold"},
                {"type": "text", "val": fmt_pct(ss_c_lbph), "ha": "center"},
                {"type": "delta", "val_tuple": fmt_val_delta(ho_c_lbph, d_c_lbph)},
                {"type": "text", "val": fmt_pct(ss_o_lbph), "ha": "center"},
                {"type": "delta", "val_tuple": fmt_val_delta(ho_o_lbph, d_o_lbph)},
                {"type": "text", "val": "—", "ha": "center"},
                {"type": "text", "val": "—", "ha": "center"},
            ],
            "bg": "#ffffff",
        },
        {
            "mode": "Hybrid",
            "cells": [
                {"type": "text", "val": "Hybrid", "ha": "left", "weight": "bold"},
                {"type": "text", "val": fmt_pct(ss_c_casc), "ha": "center"},
                {"type": "delta", "val_tuple": fmt_val_delta(ho_c_casc, d_c_casc)},
                {"type": "text", "val": fmt_pct(ss_o_casc), "ha": "center"},
                {"type": "delta", "val_tuple": fmt_val_delta(ho_o_casc, d_o_casc)},
                {"type": "text", "val": fmt_pct(ss_esc), "ha": "center"},
                {"type": "delta", "val_tuple": fmt_val_delta(ho_esc, d_esc)},
            ],
            "bg": "#f8fafc",
        },
    ]

    fig_width = 14.0
    fig_height = 2.5
    dpi = 300

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    fig.patch.set_facecolor("#ffffff")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()

    col_widths = [0.16, 0.14, 0.14, 0.14, 0.14, 0.14, 0.14]
    col_lefts = [sum(col_widths[:i]) for i in range(len(col_widths))]

    # Header Level 1
    # Model Mode (Col 0)
    ax.add_patch(patches.Rectangle((col_lefts[0], 0.45), col_widths[0], 0.55, facecolor="#1e293b", edgecolor="#cbd5e1", linewidth=0.8))
    ax.text(col_lefts[0] + col_widths[0]*0.1, 0.725, "Model Mode", color="#ffffff", weight="bold", fontsize=10.5, va="center", ha="left")

    # Group headers
    groups = [
        ("AR % (clean)", 1, 2),
        ("AR % (41-mod avg)", 3, 4),
        ("Escalation %", 5, 6),
    ]
    for title, start_col, end_col in groups:
        w_grp = sum(col_widths[start_col:end_col+1])
        x_grp = col_lefts[start_col]
        ax.add_patch(patches.Rectangle((x_grp, 0.70), w_grp, 0.30, facecolor="#1e293b", edgecolor="#cbd5e1", linewidth=0.8))
        ax.text(x_grp + w_grp*0.5, 0.85, title, color="#ffffff", weight="bold", fontsize=10.5, va="center", ha="center")

    # Subheaders
    sub_titles = [
        "Control (1 img)", "5 img / identity",
        "Control (1 img)", "5 img / identity",
        "Control (1 img)", "5 img / identity",
    ]
    for idx, stitle in enumerate(sub_titles, start=1):
        x_sub = col_lefts[idx]
        w_sub = col_widths[idx]
        ax.add_patch(patches.Rectangle((x_sub, 0.45), w_sub, 0.25, facecolor="#334155", edgecolor="#cbd5e1", linewidth=0.8))
        ax.text(x_sub + w_sub*0.5, 0.575, stitle, color="#f8fafc", weight="bold", fontsize=9.5, va="center", ha="center")

    # Rows
    h_row = 0.225
    y_starts = [0.225, 0.00]
    for r_idx, r_data in enumerate(rows):
        y_b = y_starts[r_idx]
        bg = r_data["bg"]
        for c_idx in range(7):
            x_c = col_lefts[c_idx]
            w_c = col_widths[c_idx]
            ax.add_patch(patches.Rectangle((x_c, y_b), w_c, h_row, facecolor=bg, edgecolor="#cbd5e1", linewidth=0.8))
            
            c_info = r_data["cells"][c_idx]
            y_c = y_b + h_row*0.5
            
            if c_info["type"] == "text":
                x_t = x_c + (w_c*0.1 if c_info["ha"] == "left" else w_c*0.5)
                ax.text(x_t, y_c, c_info["val"], color="#0f172a", fontsize=10, weight=c_info.get("weight", "normal"), va="center", ha=c_info["ha"])
            elif c_info["type"] == "delta":
                val_str, delta_str, delta_color = c_info["val_tuple"]
                x_center = x_c + w_c*0.5
                
                # Measure text width accurately for exact centering
                t_v = ax.text(0, 0, val_str, fontsize=10, weight="normal")
                t_d = ax.text(0, 0, delta_str, fontsize=9.2, weight="bold")
                
                b_v = t_v.get_window_extent(renderer)
                b_d = t_d.get_window_extent(renderer)
                
                w_v = inv.transform((b_v.width, 0))[0] - inv.transform((0, 0))[0]
                w_d = inv.transform((b_d.width, 0))[0] - inv.transform((0, 0))[0]
                
                t_v.remove()
                t_d.remove()
                
                total_w = w_v + w_d
                start_x = x_center - total_w * 0.5
                
                ax.text(start_x, y_c, val_str, color="#0f172a", fontsize=10, weight="normal", va="center", ha="left")
                ax.text(start_x + w_v, y_c, delta_str, color=delta_color, fontsize=9.2, weight="bold", va="center", ha="left")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight", pad_inches=0.04)
    plt.close()
    print(f"[OK] Exported clean summary PNG table: {output_path}")


def main() -> None:
    args = parse_args()
    sm_path = Path(args.selfmatch_json)
    ho_path = Path(args.heldout_json)
    if not sm_path.exists():
        print(f"[ERROR] selfmatch JSON not found at {sm_path}")
        sys.exit(1)
    if not ho_path.exists():
        print(f"[ERROR] heldout JSON not found at {ho_path}")
        sys.exit(1)

    ss_path = Path(args.singleshot_json)
    if not ss_path.exists():
        print(f"[ERROR] singleshot JSON not found at {ss_path}")
        sys.exit(1)

    selfmatch = json.loads(sm_path.read_text(encoding="utf-8"))
    heldout = json.loads(ho_path.read_text(encoding="utf-8"))
    singleshot = json.loads(ss_path.read_text(encoding="utf-8"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_headers = ["Run / Mode", "Kind", "AR % (clean)", "AR % (41-mod avg)", "Escalation %", "N (probes)"]
    summary_widths = [5.6, 2.8, 2.2, 2.5, 2.2, 1.6]
    summary_rows = build_summary_rows(selfmatch, heldout, singleshot)
    render_full_bleed_table(summary_headers, summary_rows, summary_widths, Path(args.summary_png))

    render_clean_summary_table(heldout, singleshot, Path(args.clean_summary_png))

    per_mod_headers = [
        "Modification Family", "Severity Tier & Detail",
        "Selfmatch AR % (ceiling)", "Singleshot AR % (control)",
        "Heldout AR % (multi-shot)", "Heldout Cascade AR %",
    ]
    per_mod_widths = [2.9, 2.5, 2.3, 2.3, 2.3, 2.1]
    per_mod_rows, family_first_rows = build_per_mod_rows(selfmatch, heldout, singleshot)
    render_full_bleed_table(per_mod_headers, per_mod_rows, per_mod_widths, Path(args.per_mod_png), family_first_rows)

    print(f"[SUCCESS] wrote {args.summary_png}")
    print(f"[SUCCESS] wrote {args.clean_summary_png}")
    print(f"[SUCCESS] wrote {args.per_mod_png}")


if __name__ == "__main__":
    main()
