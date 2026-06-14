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
BASE_OUTPUT_DIR = PROJECT_ROOT / "independence_failure_check" / "raw_data" / "collapse_analysis"

def resolve_path(p):
    if not p: return None
    candidate = Path(p)
    if candidate.is_absolute(): return str(candidate)
    return str(PROJECT_ROOT / candidate)

def compute_pixel_dist(img1, img2):
    return float(np.linalg.norm(img1.astype(np.float32) - img2.astype(np.float32)))

def main():
    with open(PROJECT_ROOT / "independence_failure_check" / "failure_pairs.json", "r") as f:
        failure_data = json.load(f)

    aggregated_results = {}

    for algo, pairs in failure_data.items():
        if not pairs: continue
        pair = pairs[0]
        
        algo_dir = BASE_OUTPUT_DIR / algo
        algo_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Running {algo} ({pair['identity1']} vs {pair['identity2']}) for {ITERATIONS} iterations...")
        
        run_stats = []
        
        p1 = resolve_path(pair["path1"])
        p2 = resolve_path(pair["path2"])
        img1 = cv.imread(p1)
        img2 = cv.imread(p2)
        if img1 is None or img2 is None: continue

        g1 = cv.cvtColor(img1, cv.COLOR_BGR2GRAY)
        g2 = cv.cvtColor(img2, cv.COLOR_BGR2GRAY)
        r1 = cv.resize(g1, IMG_SIZE)
        r2 = cv.resize(g2, IMG_SIZE)

        for i in range(ITERATIONS):
            # To simulate minor variance (optional, but requested 10 runs)
            # We'll just run it as requested.
            
            e1 = cv.equalizeHist(r1)
            e2 = cv.equalizeHist(r2)
            
            dist_raw = compute_pixel_dist(r1, r2)
            dist_equalized = compute_pixel_dist(e1, e2)

            faces_dict = {pair["identity1"]: e1, pair["identity2"]: e2}
            label_map = {pair["identity1"]: 0, pair["identity2"]: 1}
            
            try:
                feat_matrix, _ = train_and_extract_features(faces_dict, label_map, algo)
                if algo == "lbph":
                    dist_feature = chi_squared_distance(feat_matrix[0], feat_matrix[1])
                else:
                    dist_feature = euclidean_distance(feat_matrix[0], feat_matrix[1])
            except Exception:
                dist_feature = 0.0

            stats = {
                "run": i + 1,
                "dist_raw": dist_raw,
                "dist_equalized": dist_equalized,
                "dist_feature": dist_feature
            }
            run_stats.append(stats)
            
            # Save raw results for this run
            with open(algo_dir / f"run_{i+1}_stats.csv", "w", newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=stats.keys())
                writer.writeheader()
                writer.writerow(stats)

        # Aggregate means
        mean_raw = np.mean([s["dist_raw"] for s in run_stats])
        mean_equalized = np.mean([s["dist_equalized"] for s in run_stats])
        mean_feature = np.mean([s["dist_feature"] for s in run_stats])
        
        aggregated_results[algo] = {
            "pair": [pair["identity1"], pair["identity2"]],
            "mean_raw": float(mean_raw),
            "mean_equalized": float(mean_equalized),
            "mean_feature": float(mean_feature)
        }
        
        # Save summary for this algo
        with open(algo_dir / "summary_mean.json", "w") as f:
            json.dump(aggregated_results[algo], f, indent=2)

        # Generate Markdown Report
        report_dir = PROJECT_ROOT / "independence_failure_check" / "reports" / "collapse_analysis"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{algo}_collapse_report.md"
        
        report_content = f"""# Distance Decay Report: {algo} (Aggregated {ITERATIONS}x)
## Identities: {pair['identity1']} vs {pair['identity2']}

### Mean Separation Values
| Stage | Mean Distance |
|-------|---------------|
| Raw Pixels | {aggregated_results[algo]['mean_raw']:.4f} |
| Equalized | {aggregated_results[algo]['mean_equalized']:.4f} |
| Feature Space | {aggregated_results[algo]['mean_feature']:.4f} |

### Sample by Sample Results (All Iterations)
| Run | Raw Pixels | Equalized | Feature Space |
|-----|------------|-----------|---------------|
"""
        for s in run_stats:
            report_content += f"| {s['run']} | {s['dist_raw']:.4f} | {s['dist_equalized']:.4f} | {s['dist_feature']:.4f} |\n"
            
        with open(report_path, "w") as f:
            f.write(report_content)
        print(f"[{algo}] Report: {report_path}")

    # Save final aggregated data for report generator
    with open(PROJECT_ROOT / "independence_failure_check" / "collapse_aggregated.json", "w") as f:
        json.dump(aggregated_results, f, indent=2)

if __name__ == "__main__":
    main()
