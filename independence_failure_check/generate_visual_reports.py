import json
import os
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def plot_decay(algo, data):
    output_dir = PROJECT_ROOT / "independence_failure_check" / "reports" / "collapse_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stages = ["Raw Pixels", "Equalized", "Feature Space"]
    # Normalize relative to Equalized = 100
    norm_factor = 100.0 / data["mean_equalized"]
    values = [
        data["mean_raw"] * norm_factor,
        data["mean_equalized"] * norm_factor,
        data["mean_feature"] * norm_factor
    ]
    
    plt.figure(figsize=(8, 5))
    plt.plot(stages, values, marker='o', linestyle='-', linewidth=2, markersize=8, color='steelblue')
    plt.title(f"Distance Decay Curve: {algo.capitalize()}")
    plt.ylabel("Normalized Distance (0-100)")
    plt.ylim(-5, 110)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    for i, v in enumerate(values):
        plt.text(i, v + 3, f"{v:.1f}", ha='center')
        
    plt.savefig(output_dir / f"{algo}_decay_plot.png")
    plt.close()

def plot_regional(algo, data):
    output_dir = PROJECT_ROOT / "independence_failure_check" / "reports" / "regional_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    regions = list(data.keys())
    values = list(data.values())
    
    plt.figure(figsize=(10, 6))
    plt.bar(regions, values, color='salmon', alpha=0.8)
    plt.title(f"Regional Separation Analysis: {algo.capitalize()}")
    plt.ylabel("Distance")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i, v in enumerate(values):
        plt.text(i, v, f"{v:.2f}", ha='center', va='bottom')
        
    plt.savefig(output_dir / f"{algo}_regional_plot.png")
    plt.close()

def plot_multi_image(data):
    output_dir = PROJECT_ROOT / "independence_failure_check" / "reports" / "multi_image_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    counts = sorted([int(k) for k in data.keys()])
    values = [data[str(c)] for c in counts]
    
    # Normalize relative to max
    max_val = max(values)
    norm_values = [v * 100.0 / max_val for v in values]
    
    plt.figure(figsize=(10, 6))
    plt.plot(counts, norm_values, marker='s', linestyle='-', linewidth=2, color='forestgreen')
    plt.title("Fisherfaces Separation Restoration Trend")
    plt.xlabel("Number of Images per Identity")
    plt.ylabel("Normalized Distance (0-100)")
    plt.ylim(-5, 110)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    for i, v in enumerate(norm_values):
        plt.text(counts[i], v + 3, f"{v:.1f}", ha='center')
        
    plt.savefig(output_dir / "fisherfaces_multi_image_plot.png")
    plt.close()

def main():
    # 1. Collapse Analysis Plots
    collapse_path = PROJECT_ROOT / "independence_failure_check" / "collapse_aggregated.json"
    if collapse_path.exists():
        with open(collapse_path, "r") as f:
            collapse_data = json.load(f)
        for algo, data in collapse_data.items():
            plot_decay(algo, data)
            
    # 2. Regional Analysis Plots
    regional_path = PROJECT_ROOT / "independence_failure_check" / "regional_aggregated.json"
    if regional_path.exists():
        with open(regional_path, "r") as f:
            regional_data = json.load(f)
        for algo, data in regional_data.items():
            plot_regional(algo, data)
            
    # 3. Multi-Image Trend Plot
    multi_path = PROJECT_ROOT / "independence_failure_check" / "multi_image_aggregated.json"
    if multi_path.exists():
        with open(multi_path, "r") as f:
            multi_data = json.load(f)
        plot_multi_image(multi_data)

if __name__ == "__main__":
    main()
