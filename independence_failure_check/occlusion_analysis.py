import json
import os
import sys
from pathlib import Path

import cv2 as cv
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.independence_common import train_and_extract_features, chi_squared_distance, euclidean_distance

IMG_SIZE = (100, 100)
ITERATIONS = 10
OUTPUT_DIR = PROJECT_ROOT / "independence_failure_check" / "reports" / "occlusion_analysis"
RAW_DATA_DIR = PROJECT_ROOT / "independence_failure_check" / "raw_data" / "occlusion_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

OCCLUSIONS = {
    "None": None,
    "Eyes Blocked": (15, 20, 70, 30),
    "Nose Blocked": (35, 45, 30, 30),
    "Mouth Blocked": (25, 70, 50, 25)
}

def resolve_path(p):
    if not p: return None
    candidate = Path(p)
    if candidate.is_absolute(): return str(candidate)
    return str(PROJECT_ROOT / candidate)

def generate_report(algo, pair, mean_results, all_run_results):
    baseline = mean_results["None"]
    impacts = {name: (baseline - val) for name, val in mean_results.items() if name != "None"}
    most_impactful = max(impacts.items(), key=lambda x: x[1])[0]

    report_content = f"""# Occlusion Impact Report: {algo} (Aggregated {ITERATIONS}x)
## Identities: {pair['identity1']} vs {pair['identity2']}

### High-Level Summary
This report measures how blocking specific facial regions affects the mathematical separation between identities. Data is aggregated over {ITERATIONS} runs.

### Technical Data (Mean Impact on Distance)
| Occlusion | Mean Distance | Drop from Baseline |
|-----------|---------------|-------------------|
| None (Baseline) | {mean_results['None']:.4f} | - |
"""
    for name, val in mean_results.items():
        if name == "None": continue
        drop = baseline - val
        report_content += f"| {name} | {val:.4f} | {drop:.4f} |\n"

    report_content += f"""
### Sample by Sample Results (All Iterations)
| Run | None | Eyes Blocked | Nose Blocked | Mouth Blocked |
|-----|------|--------------|--------------|---------------|
"""
    for i in range(ITERATIONS):
        row = f"| {i+1} "
        for name in ["None", "Eyes Blocked", "Nose Blocked", "Mouth Blocked"]:
            val = all_run_results[name][i]
            row += f"| {val:.4f} "
        report_content += row + "|\n"

    report_content += f"""
### Results & Discussion
The baseline separation of **{baseline:.4f}** is most affected by **{most_impactful}**. 

This confirms that the **{algo}** algorithm's feature vectors are highly dependent on the structures in the **{most_impactful.replace(' Blocked', '')}** region.

### Conclusion
To ensure robust identity separation for **{algo}**, high-quality capture of the **{most_impactful.replace(' Blocked', '')}** is critical.
"""
    report_path = OUTPUT_DIR / f"{algo}_occlusion_report.md"
    with open(report_path, "w") as f:
        f.write(report_content)
    return report_path

def plot_occlusions(algo, results):
    names = list(results.keys())
    values = [v if v is not None else 0 for v in results.values()]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(names, values, color='orchid', alpha=0.8)
    plt.title(f"Mean Impact of Spatial Occlusion on Separation: {algo} ({ITERATIONS}x)")
    plt.ylabel("Distance (Lower means Less Separation)")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, f"{yval:.2f}", ha='center', va='bottom')
        
    plot_path = OUTPUT_DIR / f"{algo}_occlusion_plot.png"
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def main():
    import csv
    with open(PROJECT_ROOT / "independence_failure_check" / "failure_pairs.json", "r") as f:
        failure_data = json.load(f)

    # Use Eigenfaces for occlusion
    algo = "eigenfaces"
    if algo not in failure_data or not failure_data[algo]: return
    pair = failure_data[algo][0]
    
    p1 = resolve_path(pair["path1"])
    p2 = resolve_path(pair["path2"])
    
    img1 = cv.imread(p1)
    img2 = cv.imread(p2)
    if img1 is None or img2 is None: return

    g1 = cv.cvtColor(img1, cv.COLOR_BGR2GRAY)
    g2 = cv.cvtColor(img2, cv.COLOR_BGR2GRAY)
    r1 = cv.resize(g1, IMG_SIZE)
    r2 = cv.resize(g2, IMG_SIZE)

    all_run_results = {name: [] for name in OCCLUSIONS.keys()}

    algo_raw_dir = RAW_DATA_DIR / algo
    algo_raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running occlusion analysis for {algo} for {ITERATIONS} iterations...")
    for i in range(ITERATIONS):
        iteration_stats = {"run": i + 1}
        for name, box in OCCLUSIONS.items():
            occ1 = cv.equalizeHist(r1.copy())
            occ2 = cv.equalizeHist(r2.copy())
            if box:
                x, y, w, h = box
                occ1[y:y+h, x:x+w] = 0
                occ2[y:y+h, x:x+w] = 0
                
            faces_dict = {"id1": occ1, "id2": occ2}
            label_map = {"id1": 0, "id2": 1}
            
            try:
                feat_matrix, _ = train_and_extract_features(faces_dict, label_map, algo)
                dist = euclidean_distance(feat_matrix[0], feat_matrix[1])
            except Exception:
                dist = 0.0
            
            all_run_results[name].append(dist)
            iteration_stats[name] = dist
            
        # Save raw results for this run
        with open(algo_raw_dir / f"run_{i+1}_stats.csv", "w", newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=iteration_stats.keys())
            writer.writeheader()
            writer.writerow(iteration_stats)

    # Aggregate means
    aggregated_results = {name: float(np.mean(vals)) for name, vals in all_run_results.items()}

    plot_path = plot_occlusions(algo, aggregated_results)
    report_path = generate_report(algo, pair, aggregated_results, all_run_results)
    
    with open(algo_raw_dir / "summary_mean.json", "w") as f:
        json.dump(aggregated_results, f, indent=2)
        
    print(f"[{algo}] Plot: {plot_path}")
    print(f"[{algo}] Report: {report_path}")

if __name__ == "__main__":
    main()
