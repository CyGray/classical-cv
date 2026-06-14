import csv
import json
import os
import sys
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.independence_common import train_and_extract_features, chi_squared_distance, euclidean_distance

IMG_SIZE = (100, 100)
ITERATIONS = 10
BASE_OUTPUT_DIR = PROJECT_ROOT / "independence_failure_check" / "raw_data" / "regional_analysis"

REGIONS = {
    "full_face": (0, 0, 100, 100),
    "eyes": (15, 20, 70, 30),
    "nose": (35, 45, 30, 30),
    "mouth": (25, 70, 50, 25)
}

def resolve_path(p):
    if not p: return None
    candidate = Path(p)
    if candidate.is_absolute(): return str(candidate)
    return str(PROJECT_ROOT / candidate)

def main():
    with open(PROJECT_ROOT / "independence_failure_check" / "failure_pairs.json", "r") as f:
        failure_data = json.load(f)

    aggregated_results = {}

    for algo, pairs in failure_data.items():
        if not pairs: continue
        pair = pairs[0]
        
        algo_dir = BASE_OUTPUT_DIR / algo
        algo_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Running regional analysis for {algo} for {ITERATIONS} iterations...")
        
        run_stats_per_region = {reg: [] for reg in REGIONS.keys()}
        
        p1 = resolve_path(pair["path1"])
        p2 = resolve_path(pair["path2"])
        img1 = cv.imread(p1)
        img2 = cv.imread(p2)
        if img1 is None or img2 is None: continue

        g1 = cv.cvtColor(img1, cv.COLOR_BGR2GRAY)
        g2 = cv.cvtColor(img2, cv.COLOR_BGR2GRAY)
        r1 = cv.equalizeHist(cv.resize(g1, IMG_SIZE))
        r2 = cv.equalizeHist(cv.resize(g2, IMG_SIZE))

        for i in range(ITERATIONS):
            iteration_stats = {"run": i + 1}
            for region_name, (rx, ry, rw, rh) in REGIONS.items():
                roi1 = cv.resize(r1[ry:ry+rh, rx:rx+rw], IMG_SIZE)
                roi2 = cv.resize(r2[ry:ry+rh, rx:rx+rw], IMG_SIZE)
                
                faces_dict = {"id1": roi1, "id2": roi2}
                label_map = {"id1": 0, "id2": 1}
                
                try:
                    feat_matrix, _ = train_and_extract_features(faces_dict, label_map, algo)
                    dist = chi_squared_distance(feat_matrix[0], feat_matrix[1]) if algo == "lbph" else euclidean_distance(feat_matrix[0], feat_matrix[1])
                except Exception:
                    dist = 0.0

                run_stats_per_region[region_name].append(dist)
                iteration_stats[region_name] = dist

            # Save raw results for this run
            with open(algo_dir / f"run_{i+1}_stats.csv", "w", newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=iteration_stats.keys())
                writer.writeheader()
                writer.writerow(iteration_stats)

        # Aggregate means
        aggregated_results[algo] = {reg: float(np.mean(vals)) for reg, vals in run_stats_per_region.items()}
        
        with open(algo_dir / "summary_mean.json", "w") as f:
            json.dump(aggregated_results[algo], f, indent=2)

        # Generate Markdown Report
        report_dir = PROJECT_ROOT / "independence_failure_check" / "reports" / "regional_analysis"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{algo}_regional_report.md"
        
        report_content = f"""# Regional Separation Report: {algo} (Aggregated {ITERATIONS}x)
## Identities: {pair['identity1']} vs {pair['identity2']}

### Mean Separation Values per Region
| Region | Mean Distance |
|--------|---------------|
"""
        for reg, mean_val in aggregated_results[algo].items():
            report_content += f"| {reg} | {mean_val:.4f} |\n"

        report_content += f"""
### Sample by Sample Results (All Iterations)
| Run | Full Face | Eyes | Nose | Mouth |
|-----|-----------|------|------|-------|
"""
        for i in range(ITERATIONS):
            report_content += f"| {i+1} | {run_stats_per_region['full_face'][i]:.4f} | {run_stats_per_region['eyes'][i]:.4f} | {run_stats_per_region['nose'][i]:.4f} | {run_stats_per_region['mouth'][i]:.4f} |\n"
            
        with open(report_path, "w") as f:
            f.write(report_content)
        print(f"[{algo}] Report: {report_path}")

    with open(PROJECT_ROOT / "independence_failure_check" / "regional_aggregated.json", "w") as f:
        json.dump(aggregated_results, f, indent=2)

if __name__ == "__main__":
    main()
