# Pairwise Verification Robustness - Expected Output Guide & Specification

This guide defines the standard expected output format, artifact layout, and reporting protocol for the **1:1 Pairwise Verification Robustness Benchmark** across classical (LBPH) and deep learning (SFace) recognizers.

---

## 1. Expected Output Artifacts & File Locations

All verification runs must produce the following standardized artifacts inside `docs/experiments/pairwise-verification/`:

| Artifact | Path / Filename | Description |
|---|---|---|
| **Summary Table PNG** | `docs/experiments/pairwise-verification/summary_verification_table.png` | Executive full-bleed PNG table showing clean baseline, tier averages, and overall 41-suite AR. |
| **Per-Modification Table PNG** | `docs/experiments/pairwise-verification/per_modification_verification_table.png` | High-resolution full-bleed PNG table detailing per-family per-tier AR for all 41 modifications. |
| **Markdown Document** | `docs/experiments/pairwise-verification/README.md` | Human and LLM-agent readable report with full run metadata, table data, and scientific takeaways. |
| **Raw JSON Payload** | `classical-cv/outputs/benchmark/accuracy_ratio_verification_full.json` | Complete programmatic JSON benchmark payload with GAR, FAR, Accuracy, and EER stats. |
| **Per-Pair CSV Log** | `classical-cv/outputs/benchmark/accuracy_ratio_verification_full_pairs.csv` | Pairwise raw distance log for offline threshold and ROC/EER re-sweeps. |

---

## 2. Table Layout & Formatting Rules

### A. Metric Focus
- Tables must report the **AR %** (Accuracy Ratio / Verification Accuracy at operating threshold $\tau_{accept}$).
- For LBPH: Operating gate is $\tau_{accept} = 67.0084$ (from `src/hybrid/thresholds.json`).
- For SFace: Operating rule is Cosine $\ge 0.363$ & $L_2 \le 1.0313$.

### B. Column Structure & Ordering
The **Per-Modification Table** must follow this exact 4-column layout:

1. **Col 1 (`Modification Family`)**: Public readable family name matching `/docs/41mods_table` (e.g., *Brightness change*, *Blur*, *Gaussian noise*, *Crop*, *Rotation (large-angle)*).
2. **Col 2 (`Severity Tier & Detail`)**: Severity tier name and value detail (e.g., `Light (+10%)`, `Medium (5×5 mask)`, `Heavy (270° canonical)`).
3. **Col 3 (`LBPH Standalone AR (%)`)**: Standalone LBPH verification accuracy percentage.
4. **Col 4 (`SFace Standalone AR (%)`)**: Standalone SFace verification accuracy percentage.

### C. Family Grouping & Row Sorting
- Rows are grouped by **Modification Family** (17 families corresponding to the 41-modification suite).
- Within each family, rows must be ordered strictly from **Light $\to$ Medium $\to$ Heavy** tiers.
- In PNG exports, horizontal group boundary lines separating modification families must be rendered.

---

## 3. Pipeline Execution Workflow

To reproduce or update these standard outputs:

```bash
# 1. Run full 1:1 pairwise verification benchmark (5,749 enrolled, 1,680 probes, 41 mods)
cd classical-cv
python -m src.benchmark.accuracy_ratio_verification \
    --split-manifest data/splits/lfw_ident_split_seed42.json \
    --engines lbph,sface \
    --output-json outputs/benchmark/accuracy_ratio_verification_full.json \
    --output-md reports/benchmark/accuracy_ratio_verification_full.md \
    --pairs-csv outputs/benchmark/accuracy_ratio_verification_full_pairs.csv

# 2. Export full-bleed PNG tables and update docs/experiments/pairwise-verification/README.md
python scripts/export_verification_png_tables.py
```

---

## 4. Canonical Reference Document Links

- Expected Output Folder: [`docs/experiments/pairwise-verification/`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/experiments/pairwise-verification/)
- Markdown Report & Metadata: [`docs/experiments/pairwise-verification/README.md`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/experiments/pairwise-verification/README.md)
- Reference Specification: [`docs/41mods_table/README.md`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/41mods_table/README.md)
- Generator Script: [`classical-cv/scripts/export_verification_png_tables.py`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/classical-cv/scripts/export_verification_png_tables.py)
