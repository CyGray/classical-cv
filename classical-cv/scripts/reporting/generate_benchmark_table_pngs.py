import json
import matplotlib.pyplot as plt
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = ROOT / "outputs" / "benchmark" / "lfw2_robustness" / "accuracy_ratio_hybrid.json"
if not JSON_PATH.exists():
    alt_path = ROOT / "reports" / "benchmark" / "lfw2_robustness" / "accuracy_ratio_hybrid.json"
    if alt_path.exists():
        JSON_PATH = alt_path
OUT_DIR = ROOT / "reports" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load data
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# Style setup
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

# -------------------------------------------------------------
# Table 1: Overall System Performance
# -------------------------------------------------------------
t1_headers = ["System Mode", "Clean Acceptance", "Overall AR (Robustness)", "Mean Latency (Speed)", "Key Characteristic"]

modes_meta = [
    ("Classical CV (LBPH)", "cv_only", "94.35 ms", "Slower; sensitive to noise/rotation"),
    ("Deep Learning (SFace)", "dl_only", "19.82 ms", "High accuracy; moderate speed"),
    ("Hybrid Cascade", "cascade", "3.61 ms", "Fastest (~3.6ms); retains ~94.7% AR"),
    ("Parallel Ensemble", "parallel", "7.14 ms", "Highest accuracy (98.26%); dual engine")
]

t1_rows = []
for label, mode_key, lat_str, feat in modes_meta:
    clean = f"{data['clean_acceptance_percent'][mode_key]:.2f}%"
    ar = f"{data['overall_ar_percent'][mode_key]:.2f}%"
    t1_rows.append([label, clean, ar, lat_str, feat])

# Color definitions for Table 1
t1_colors = [
    ["#f8f9fa", "#c8e6c9", "#ffe0b2", "#ffcdd2", "#f8f9fa"], # cv_only
    ["#f8f9fa", "#e8f5e9", "#a5d6a7", "#fff9c4", "#f8f9fa"], # dl_only
    ["#f8f9fa", "#a5d6a7", "#c8e6c9", "#81c784", "#f8f9fa"], # cascade (leader in latency)
    ["#f8f9fa", "#e8f5e9", "#66bb6a", "#c8e6c9", "#f8f9fa"], # parallel (leader in AR)
]

fig, ax = plt.subplots(figsize=(14, 3.8), dpi=300)
ax.axis('tight')
ax.axis('off')

tbl1 = ax.table(
    cellText=t1_rows,
    colLabels=t1_headers,
    cellColours=t1_colors,
    loc='center',
    cellLoc='center',
    colWidths=[0.20, 0.16, 0.20, 0.18, 0.26]
)

tbl1.auto_set_font_size(False)
tbl1.set_fontsize(10.5)
tbl1.scale(1.0, 2.0)

# Header styling
for col_idx in range(len(t1_headers)):
    cell = tbl1[(0, col_idx)]
    cell.set_facecolor("#1e293b")
    cell.get_text().set_color("white")
    cell.get_text().set_weight("bold")
    cell.set_height(0.18)

# Border and cell styling
for (row, col), cell in tbl1.get_celld().items():
    cell.set_edgecolor("#cbd5e1")
    cell.set_linewidth(1.0)
    if row > 0:
        if col == 0:
            cell.get_text().set_weight("bold")
            cell.get_text().set_ha("left")
        elif col == 4:
            cell.get_text().set_ha("left")

# Bold the leader cells
tbl1[(1, 1)].get_text().set_weight("bold") # CV clean leader 100%
tbl1[(4, 2)].get_text().set_weight("bold") # Parallel AR leader 98.26%
tbl1[(3, 3)].get_text().set_weight("bold") # Cascade Latency leader 3.61ms

plt.title("LFW2 Benchmark: Overall System Performance & Efficiency", fontsize=14, weight='bold', pad=15, color='#0f172a')
plt.tight_layout()
out_t1 = OUT_DIR / "lfw2_overall_performance_table.png"
plt.savefig(out_t1, bbox_inches='tight', dpi=300)
plt.close()
print(f"Saved {out_t1}")

# -------------------------------------------------------------
# Table 2: Per-Modification Breakdown (12 Modifications)
# -------------------------------------------------------------
t2_headers = ["Modification", "Classical CV", "Deep Learning", "Hybrid Cascade", "Parallel Ensemble", "Category Leader"]

t2_rows = []
t2_colors = []

# Heatmap helper for accuracy values
def get_acc_color(val, is_max=False):
    if is_max:
        return "#81c784" # Bright leader green
    if val >= 99.0:
        return "#c8e6c9" # Soft green
    elif val >= 95.0:
        return "#e8f5e9" # Light green
    elif val >= 80.0:
        return "#fff9c4" # Soft yellow
    elif val >= 60.0:
        return "#ffe0b2" # Light orange
    else:
        return "#ffcdd2" # Soft red

for mod in data["modifications"]:
    name = mod["modification"].replace("_", " ").title()
    cv_val = mod["ar_percent"]["cv_only"]
    dl_val = mod["ar_percent"]["dl_only"]
    cas_val = mod["ar_percent"]["cascade"]
    par_val = mod["ar_percent"]["parallel"]
    winner = mod["winner"]
    
    max_val = max(cv_val, dl_val, cas_val, par_val)
    
    if winner == "tie":
        winner_str = "Tie (Equal)"
    elif winner == "dl_stronger":
        winner_str = "DL Stronger"
    elif winner == "cv_stronger":
        winner_str = "CV Stronger"
    else:
        winner_str = winner.title()
        
    row_text = [
        name,
        f"{cv_val:.1f}%",
        f"{dl_val:.1f}%",
        f"{cas_val:.1f}%",
        f"{par_val:.1f}%",
        winner_str
    ]
    t2_rows.append(row_text)
    
    row_cols = [
        "#f8f9fa",
        get_acc_color(cv_val, cv_val == max_val),
        get_acc_color(dl_val, dl_val == max_val),
        get_acc_color(cas_val, cas_val == max_val),
        get_acc_color(par_val, par_val == max_val),
        "#e2e8f0" if winner != "tie" else "#f1f5f9"
    ]
    t2_colors.append(row_cols)

fig, ax = plt.subplots(figsize=(14, 8.5), dpi=300)
ax.axis('tight')
ax.axis('off')

tbl2 = ax.table(
    cellText=t2_rows,
    colLabels=t2_headers,
    cellColours=t2_colors,
    loc='center',
    cellLoc='center',
    colWidths=[0.22, 0.15, 0.15, 0.15, 0.16, 0.17]
)

tbl2.auto_set_font_size(False)
tbl2.set_fontsize(10.5)
tbl2.scale(1.0, 1.8)

# Header styling
for col_idx in range(len(t2_headers)):
    cell = tbl2[(0, col_idx)]
    cell.set_facecolor("#1e293b")
    cell.get_text().set_color("white")
    cell.get_text().set_weight("bold")
    cell.set_height(0.06)

# Cell styling
for (row, col), cell in tbl2.get_celld().items():
    cell.set_edgecolor("#cbd5e1")
    cell.set_linewidth(1.0)
    if row > 0:
        if col == 0:
            cell.get_text().set_weight("bold")
            cell.get_text().set_ha("left")

plt.title("LFW2 Benchmark: Robustness Breakdown across 12 Image Modifications", fontsize=14, weight='bold', pad=15, color='#0f172a')
plt.tight_layout()
out_t2 = OUT_DIR / "lfw2_per_modification_table.png"
plt.savefig(out_t2, bbox_inches='tight', dpi=300)
plt.close()
print(f"Saved {out_t2}")
