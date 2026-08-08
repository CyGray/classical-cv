"""Full-bleed PNG table for the LBPH FAR-target sweep (far_sweep_tar_report.py),
per docs/experiments/pairwise-verification/GUIDE.md's full-bleed table
convention. Reuses render_full_bleed_table rather than duplicating it.
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from export_verification_png_tables import render_full_bleed_table  # noqa: E402

CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent

REPORT_JSON = CLASSICAL_CV_DIR / "reports" / "benchmark" / "far_sweep_tar_report.json"

OUT_PATHS = [
    WORKSPACE_ROOT / "docs" / "experiments" / "robustness_variants" / "pairwise-verification" / "lfw-results" / "SWEEP" / "summary-table.png",
    WORKSPACE_ROOT / "docs" / "experiments" / "robustness_variants" / "pairwise-verification" / "summary-table.png",
    WORKSPACE_ROOT / "docs" / "experiments" / "pairwise-verification" / "lfw-results" / "SWEEP" / "summary-table.png",
]



def format_far(ppm) -> str:
    if ppm is None:
        return "—"
    pct = ppm / 10000.0
    if ppm < 100:
        return f"{ppm:.2f} ppm ({pct:.4f}%)"
    elif ppm < 1000:
        return f"{ppm:.2f} ppm ({pct:.3f}%)"
    elif ppm < 10000:
        return f"{ppm:,.0f} ppm ({pct:.2f}%)"
    else:
        return f"{ppm:,.0f} ppm ({pct:.1f}%)"


def format_op_label(row: dict) -> str:
    label = row["label"]
    if row.get("family") == "far_target":
        target_ppm = row.get("target_far_ppm")
        if target_ppm is not None:
            pct = target_ppm / 10000.0
            if pct < 0.01:
                return f"{label} ({pct:.3f}%)"
            elif pct < 0.1:
                return f"{label} ({pct:.2f}%)"
            else:
                return f"{label} ({pct:.1f}%)"
    return label


def render_far_sweep_table(headers, data, col_widths, output_path, family_boundaries=None, row_ppms=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    num_rows = len(data)
    row_height = 0.36
    header_height = 0.55
    total_height = header_height + (num_rows * row_height)
    total_width = sum(col_widths)

    fig, ax = plt.subplots(figsize=(total_width, total_height), dpi=300)
    fig.patch.set_facecolor("#ffffff")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    table = ax.table(
        cellText=data,
        colLabels=headers,
        colWidths=[w / total_width for w in col_widths],
        cellLoc="center",
        loc="center",
        bbox=[0, 0, 1, 1],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    family_first_rows = set(family_boundaries) if family_boundaries else set()

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#cbd5e1")
        cell.set_linewidth(0.6)

        if r == 0:
            cell.set_facecolor("#1e293b")
            cell.get_text().set_color("#ffffff")
            cell.get_text().set_weight("bold")
            cell.get_text().set_fontsize(10.5)
            cell.get_text().set_ha("center" if c > 0 else "left")
        else:
            row_idx = r - 1
            bg_color = "#ffffff"
            text_color = "#0f172a"
            text_weight = "normal"

            if row_idx in family_first_rows and r > 1:
                cell.set_edgecolor("#94a3b8")
                cell.set_linewidth(1.0)

            # Check if Realized FAR (col 1) >= 5% (50,000 ppm)
            if c == 1 and row_ppms and row_idx < len(row_ppms):
                ppm_val = row_ppms[row_idx]
                if ppm_val is not None and (ppm_val / 10000.0) >= 4.99:
                    text_color = "#dc2626"  # Red
                    text_weight = "bold"

            cell.set_facecolor(bg_color)
            cell.get_text().set_color(text_color)
            cell.get_text().set_weight(text_weight)

            if c == 0:
                cell.get_text().set_ha("left")
                cell.set_fontsize(9.5)
            else:
                cell.get_text().set_ha("center")
                cell.set_fontsize(10.0)

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(output_path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()
    print(f"[OK] Exported FAR sweep table: {output_path}")


def main() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    headers = ["Operating Point", "Realized FAR", "Raw Threshold", "Clean TAR (%)", "Overall TAR (%)"]
    col_widths = [4.5, 3.2, 1.8, 1.8, 1.8]

    data = []
    row_ppms = []
    family_boundaries = []
    last_family = None
    for row in payload["rows"]:
        if row["family"] != last_family and last_family is not None:
            family_boundaries.append(len(data))
        last_family = row["family"]
        data.append(
            [
                format_op_label(row),
                format_far(row["realized_far_ppm"]),
                f"{row['raw_threshold']:.4f}",
                f"{row['clean_tar_percent']:.2f}%",
                f"{row['overall_tar_percent']:.2f}%",
            ]
        )
        row_ppms.append(row.get("realized_far_ppm"))

    for out_path in OUT_PATHS:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        render_far_sweep_table(headers, data, col_widths, str(out_path), family_boundaries=family_boundaries, row_ppms=row_ppms)
        print(f"[SAVE] {out_path}")



if __name__ == "__main__":
    main()
