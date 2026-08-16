import csv
from pathlib import Path

p_comp = Path("../docs/results/complementarity_test/reruns/lsdb_dl41_2026-08-10/complementarity_probes.csv")
p_new = Path("outputs/quality_first_eval_2296_2026-08-16/per_condition_results.csv")

with p_comp.open(encoding="utf-8") as f:
    old_rows = [r for r in csv.DictReader(f) if r["modification"] != "clean"]

with p_new.open(encoding="utf-8") as f:
    new_rows = list(csv.DictReader(f))

print(f"Old rows: {len(old_rows)}, New rows: {len(new_rows)}")

old_dict = {}
for r in old_rows:
    key = (r["person"], r["file"], r["modification"])
    old_dict[key] = r

new_dict = {}
for r in new_rows:
    key = (r["identity"], r["source_image"], r["transformation"])
    new_dict[key] = r

print(f"Old keys: {len(old_dict)}, New keys: {len(new_dict)}")

divergences = []
first_divergence = None

for idx, (key, old_r) in enumerate(old_dict.items()):
    new_r = new_dict.get(key)
    if not new_r:
        continue
    
    diffs = []
    old_no_face = old_r["no_face"] == "True"
    new_no_face = new_r["detector_success"] == "False"
    if old_no_face != new_no_face:
        diffs.append(f"no_face: old={old_no_face} vs new={new_no_face}")
        
    old_esc = old_r["escalated"] == "True"
    new_esc = new_r["seq_cascade_sface_invoked"] == "True"
    if old_esc != new_esc:
        diffs.append(f"escalated: old={old_esc} (reason={old_r.get('gate_reason')}) vs new={new_esc} (reason={new_r.get('seq_cascade_reason')})")
        
    old_d1_str = old_r["lbph_distance"]
    new_d1_str = new_r["lbph_distance"]
    old_d1 = float(old_d1_str) if old_d1_str and old_d1_str != "None" else None
    new_d1 = float(new_d1_str) if new_d1_str and new_d1_str != "None" else None
    if old_d1 is not None and new_d1 is not None:
        if abs(old_d1 - new_d1) > 0.01:
            diffs.append(f"lbph_distance: old={old_d1} vs new={new_d1}")
    elif (old_d1 is None) != (new_d1 is None):
        diffs.append(f"lbph_distance presence: old={old_d1} vs new={new_d1}")

    old_cascade_correct = (old_r["dl_correct"] == "True") if old_esc else (old_r["cv_correct"] == "True")
    new_cascade_correct = new_r["seq_cascade_correct"] == "True"
    if old_cascade_correct != new_cascade_correct:
        diffs.append(f"cascade_correct: old={old_cascade_correct} vs new={new_cascade_correct}")

    if diffs:
        divergences.append((idx, key, diffs, old_r, new_r))
        if first_divergence is None:
            first_divergence = (idx, key, diffs, old_r, new_r)

print(f"\nTotal diverging rows: {len(divergences)} / 2296 ({len(divergences)/2296*100:.2f}%)")

# Categorize divergences
div_categories = {}
for idx, key, diffs, old_r, new_r in divergences:
    for d in diffs:
        cat = d.split(":")[0]
        div_categories[cat] = div_categories.get(cat, 0) + 1

print("\nDivergence categories breakdown:")
for cat, count in div_categories.items():
    print(f"  {cat}: {count}")

if first_divergence:
    idx, key, diffs, old_r, new_r = first_divergence
    print(f"\n========================================================")
    print(f"FIRST POINT OF DIVERGENCE (Row {idx+1} in old canonical / Key: {key})")
    print(f"========================================================")
    for d in diffs:
        print("  -", d)
    print("\nOld Canonical Row:")
    for k, v in old_r.items():
        print(f"  {k}: {v}")
    print("\nNew Evaluated Row:")
    fields_to_show = [
        "condition_idx", "identity", "source_image", "transformation", 
        "detector_success", "quality_any_flag", "quality_blur_var", 
        "quality_luma_mean", "quality_noise_sigma", "quality_pose_angle", 
        "quality_face_px", "lbph_name", "lbph_distance", "lbph_margin", 
        "sface_name", "sface_cosine", "seq_cascade_pred", "seq_cascade_correct", 
        "seq_cascade_reason", "seq_cascade_sface_invoked"
    ]
    for k in fields_to_show:
        print(f"  {k}: {new_r.get(k)}")

# Also look at the next 3 divergences to see the pattern
print("\n--- NEXT 3 DIVERGENCES ---")
for idx, key, diffs, old_r, new_r in divergences[1:4]:
    print(f"\nRow {idx+1} / Key: {key}")
    for d in diffs:
        print("  -", d)
