import csv
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.independence_common import _read_projections

IMG_SIZE = (100, 100)
ITERATIONS = 10
BASE_OUTPUT_DIR = PROJECT_ROOT / "independence_failure_check" / "raw_data" / "multi_image_analysis"

def resolve_path(p):
    if not p: return None
    candidate = Path(p)
    if candidate.is_absolute(): return str(candidate)
    return str(PROJECT_ROOT / candidate)

def main():
    id1 = "Daniel_Ramos"
    id2 = "Joseph_Andrew_Ong"
    algo = "fisherfaces"
    
    algo_dir = BASE_OUTPUT_DIR / algo
    algo_dir.mkdir(parents=True, exist_ok=True)
    
    dir1 = resolve_path(f"data/lasalle_db1_processed/{id1}")
    dir2 = resolve_path(f"data/lasalle_db1_processed/{id2}")
    
    imgs1 = sorted(list(Path(dir1).glob("*.jpg")))
    imgs2 = sorted(list(Path(dir2).glob("*.jpg")))
    
    proc1 = [cv.equalizeHist(cv.resize(cv.cvtColor(cv.imread(str(p)), cv.COLOR_BGR2GRAY), IMG_SIZE)) for p in imgs1]
    proc2 = [cv.equalizeHist(cv.resize(cv.cvtColor(cv.imread(str(p)), cv.COLOR_BGR2GRAY), IMG_SIZE)) for p in imgs2]
    
    aggregated_results = {}
    
    for count in [1, 3, 5, 7, 10]:
        print(f"Running multi-image ({count} images) for {ITERATIONS} iterations...")
        run_vals = []
        
        for i in range(ITERATIONS):
            train_faces = []
            train_labels = []
            for j in range(min(count, len(proc1), len(proc2))):
                train_faces.append(proc1[j])
                train_labels.append(0)
                train_faces.append(proc2[j])
                train_labels.append(1)
                
            model = cv.face.FisherFaceRecognizer_create()
            try:
                model.train(train_faces, np.array(train_labels))
                tmp = tempfile.NamedTemporaryFile(suffix=".yml", delete=False)
                tmp_name = tmp.name
                tmp.close()
                try:
                    model.save(tmp_name)
                    projections, labels = _read_projections(tmp_name, "opencv_fisherfaces")
                    idx1 = np.where(labels == 0)[0][0]
                    idx2 = np.where(labels == 1)[0][0]
                    dist = float(np.linalg.norm(projections[idx1] - projections[idx2]))
                    run_vals.append(dist)
                finally:
                    if os.path.exists(tmp_name): os.unlink(tmp_name)
            except Exception:
                run_vals.append(0.0)
                
            # Save raw run data
            run_data = {"run": i + 1, "images_per_id": count, "distance": run_vals[-1]}
            with open(algo_dir / f"run_img{count}_{i+1}_stats.csv", "w", newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=run_data.keys())
                writer.writeheader()
                writer.writerow(run_data)

        aggregated_results[count] = float(np.mean(run_vals))

    with open(algo_dir / "summary_mean.json", "w") as f:
        json.dump(aggregated_results, f, indent=2)

    # Generate Markdown Report
    report_dir = PROJECT_ROOT / "independence_failure_check" / "reports" / "multi_image_analysis"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{algo}_multi_image_report.md"
    
    report_content = f"""# Multi-Image Separation Report: {algo} (Aggregated {ITERATIONS}x)
## Identities: {id1} vs {id2}

### Mean Separation Values per Sample Count
| Images/Identity | Mean Distance |
|-----------------|---------------|
"""
    for count, mean_val in aggregated_results.items():
        report_content += f"| {count} | {mean_val:.4f} |\n"

    report_content += f"""
### Sample by Sample Results (All Iterations)
| Images/ID | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Run 6 | Run 7 | Run 8 | Run 9 | Run 10 |
|-----------|-------|-------|-------|-------|-------|-------|-------|-------|-------|--------|
"""
    for count in [1, 3, 5, 7, 10]:
        row = f"| {count} "
        for i in range(ITERATIONS):
            # Read from CSV to get the raw values if not stored in memory
            with open(algo_dir / f"run_img{count}_{i+1}_stats.csv", "r") as csvfile:
                reader = csv.DictReader(csvfile)
                for csv_row in reader:
                    row += f"| {float(csv_row['distance']):.4f} "
        report_content += row + "|\n"
        
    with open(report_path, "w") as f:
        f.write(report_content)
    print(f"[{algo}] Report: {report_path}")

    with open(PROJECT_ROOT / "independence_failure_check" / "multi_image_aggregated.json", "w") as f:
        json.dump(aggregated_results, f, indent=2)

if __name__ == "__main__":
    main()
