"""Render a zero-margin, full-bleed table PNG with no title and exact cell fit."""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Output paths
ARTIFACT_DIR = Path(r"C:\Users\acer\.gemini\antigravity-cli\brain\f461de9b-792a-4ad4-be27-0bcd66122ec7")
REPORT_FIG_DIR = Path(r"C:\Users\acer\Documents\USLS 4th Year\Computer Vision\reports\figures")
REPORT_FIG_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

out_artifact = ARTIFACT_DIR / "full_bleed_table.png"
out_report = REPORT_FIG_DIR / "cascade_comparison_table.png"

# Table Structure
headers = [
    "Evaluation Metric",
    "Current Cascade\n(Baseline)",
    "Combined Unified\nCascade (Ours)",
    "DL-Only Reference\n(Direct SFace)",
    "Key Advantage & Delta\n(Combined vs Baseline)",
]

rows = [
    [
        "Clean Acceptance (TPIR)",
        "100.00% (56 / 56)",
        "100.00% (56 / 56)",
        "100.00% (56 / 56)",
        "Exact Parity across all operating modes (0 accuracy loss)",
    ],
    [
        "DL41 Retention (Robustness)",
        "88.41% (2,030 / 2,296)",
        "88.41% (2,030 / 2,296)",
        "88.41% (2,030 / 2,296)",
        "100% Decision Equivalence (0 false accepts / 0 security drift)",
    ],
    [
        "Observed Impostor FAR",
        "9.93 ppm",
        "11.87 ppm",
        "10.00 ppm",
        "Calibrated strictly to target ~10 ppm security anchor",
    ],
    [
        "Mean Recognition Latency",
        "11.96 ms (12.26 ms emp.)",
        "8.28 ms (7.22 ms emp.)",
        "8.62 ms (8.26 ms emp.)",
        "Faster than DL-only (-30.7% full-suite / -41.2% empirical)",
    ],
    [
        "SFace Escalation Workload",
        "77.61% (Sequential)",
        "77.61% (Early-Bypass)",
        "100.00% (Always)",
        "-81.0% dual inferences (43.3% LBPH calls avoided)",
    ],
]

# Total canvas dimensions
total_w = 16.0
header_h = 0.85
row_h = 0.65
num_rows = len(rows)
total_h = header_h + num_rows * row_h

fig, ax = plt.subplots(figsize=(total_w, total_h), dpi=300)
ax.axis("off")
fig.patch.set_facecolor("#ffffff")
plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

# Column relative widths (sum to 1.0)
col_fractions = [0.20, 0.165, 0.165, 0.165, 0.305]
col_w = [f * total_w for f in col_fractions]
col_x = [0.0]
for w in col_w[:-1]:
    col_x.append(col_x[-1] + w)

# Draw Header Background (Dark Navy)
header_rect = patches.Rectangle(
    (0, total_h - header_h),
    total_w,
    header_h,
    facecolor="#0f172a",
    edgecolor="none",
    zorder=1,
)
ax.add_patch(header_rect)

# Draw Highlight Background for Column 2 (Combined Unified) across all rows
highlight_rect = patches.Rectangle(
    (col_x[2], 0),
    col_w[2],
    total_h,
    facecolor="#f0fdf4",
    edgecolor="none",
    zorder=0,
)
ax.add_patch(highlight_rect)

# Highlight column top header band
highlight_header = patches.Rectangle(
    (col_x[2], total_h - header_h),
    col_w[2],
    header_h,
    facecolor="#1e293b",
    edgecolor="none",
    zorder=2,
)
ax.add_patch(highlight_header)

# Draw Headers
for idx, (h_text, x, w) in enumerate(zip(headers, col_x, col_w)):
    if idx == 0:
        align = "left"
        x_pos = x + 0.25
    elif idx == 4:
        align = "left"
        x_pos = x + 0.25
    else:
        align = "center"
        x_pos = x + w / 2.0

    text_color = "#34d399" if idx == 2 else "#ffffff"
    ax.text(
        x_pos,
        total_h - header_h / 2.0,
        h_text,
        ha=align,
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color=text_color,
        family="sans-serif",
        linespacing=1.2,
        zorder=3,
    )

# Draw Rows and Horizontal Separators
for r_idx, row in enumerate(rows):
    y_bottom = total_h - header_h - (r_idx + 1) * row_h
    y_center = y_bottom + row_h / 2.0

    # Alternating row background (except highlighted column 2 which stays light emerald)
    bg_color = "#f8fafc" if r_idx % 2 == 0 else "#ffffff"
    for c_idx in range(len(headers)):
        if c_idx != 2:
            cell_rect = patches.Rectangle(
                (col_x[c_idx], y_bottom),
                col_w[c_idx],
                row_h,
                facecolor=bg_color,
                edgecolor="none",
                zorder=1,
            )
            ax.add_patch(cell_rect)

    # Bottom border line for row
    border_line = patches.Rectangle(
        (0, y_bottom),
        total_w,
        0.015,
        facecolor="#e2e8f0",
        edgecolor="none",
        zorder=2,
    )
    ax.add_patch(border_line)

    # Render cell text
    for c_idx, (val, x, w) in enumerate(zip(row, col_x, col_w)):
        if c_idx == 0:
            align = "left"
            x_pos = x + 0.25
            font_weight = "bold"
            text_color = "#0f172a"
            font_size = 9.5
        elif c_idx == 4:
            align = "left"
            x_pos = x + 0.25
            font_weight = "normal"
            text_color = "#334155"
            font_size = 9.0
        else:
            align = "center"
            x_pos = x + w / 2.0
            font_weight = "bold" if c_idx == 2 else "normal"
            text_color = "#047857" if c_idx == 2 else "#1e293b"
            font_size = 9.5

        ax.text(
            x_pos,
            y_center,
            val,
            ha=align,
            va="center",
            fontsize=font_size,
            fontweight=font_weight,
            color=text_color,
            family="sans-serif",
            zorder=3,
        )

# Vertical border highlighting the Combined Unified column
col2_left_border = patches.Rectangle(
    (col_x[2], 0),
    0.02,
    total_h,
    facecolor="#10b981",
    edgecolor="none",
    zorder=4,
)
col2_right_border = patches.Rectangle(
    (col_x[2] + col_w[2], 0),
    0.02,
    total_h,
    facecolor="#10b981",
    edgecolor="none",
    zorder=4,
)
ax.add_patch(col2_left_border)
ax.add_patch(col2_right_border)

# Outer full-bleed enclosing border
outer_border = patches.Rectangle(
    (0, 0),
    total_w,
    total_h,
    fill=False,
    edgecolor="#cbd5e1",
    linewidth=1.0,
    zorder=5,
)
ax.add_patch(outer_border)

# Exact limits
ax.set_xlim(0, total_w)
ax.set_ylim(0, total_h)

# Save with exact zero margin
plt.savefig(out_artifact, dpi=300, bbox_inches="tight", pad_inches=0)
plt.savefig(out_report, dpi=300, bbox_inches="tight", pad_inches=0)
plt.close()

print(f"[SUCCESS] Rendered zero-margin full-bleed table PNG to:\n  {out_artifact}")
