# Major Experiment: LBPH Hyperparameter Optimization & Multi-Scale Descriptor Selection

> **Status: Candidate Improvement (Waiting for Promotion)**  
> **Evaluation Scope**: 12-configuration parameter grid evaluated on deterministic La Salle DB1 development folds + locked LFW test splits.  
> **Execution Date**: 2026-08-14  
> **Key Finding**: The multi-scale candidate **`r3_n8_g6x6`** (Radius $=3$, Neighbors $=8$, Grid $=6\times 6$) decisively outperforms the deployed baseline **`r1_n8_g8x8`** across all datasets, while **reducing template memory by 43.75%** ($64\text{ KiB} \to 36\text{ KiB}$) and **cutting Chi-Square prediction latency by ~42%** ($36.32\text{ ms} \to 21.09\text{ ms}$).

---

## 1. 12-Configuration Ablation Grid Design

The hyperparameter sweep systematically evaluated 12 candidate configurations holding $N=8$ neighbors and $100\times 100$ Tan-Triggs photometric normalization constant:

$$\text{Radius } r \in \{1, 2, 3\} \quad \times \quad \text{Grid } g \in \{4\times 4, 6\times 6, 8\times 8, 10\times 10\}$$

Template memory scales quadratically with grid size:
$$\text{Memory} = g^2 \times 2^N \times 4\text{ bytes} = g^2 \times 256 \times 4\text{ bytes} = g^2\text{ KiB}$$
- $4\times 4 \implies 16\text{ KiB}$
- $6\times 6 \implies 36\text{ KiB}$
- $8\times 8 \implies 64\text{ KiB}$ (Deployed baseline)
- $10\times 10 \implies 100\text{ KiB}$

Every candidate configuration received its own distinct calibrated $\tau_{\text{accept}}$ threshold derived from native OpenCV `predict_collect` Chi-Square distance distributions.

---

## 2. Empirical Results & Performance Comparison

| Evaluation Cohort | Performance Metric | Baseline `r1_n8_g8x8` | Challenger `r3_n8_g6x6` | Relative Delta |
| :--- | :--- | :---: | :---: | :---: |
| **LSDB Development (CV Folds)** | Mean Rank-1 Identification | 25.00% | **36.07%** | **$+11.07\text{ pp}$** |
| **LSDB Development (CV Folds)** | Mean TPIR @ Threshold | 9.29% | **17.50%** | **$+8.21\text{ pp}$** |
| **LSDB Historical Test (56 Probes)** | Rank-1 Identification | 100.00% (56/56) | **100.00%** (56/56) | Parity |
| **LSDB Historical Test (56 Probes)** | TPIR @ Threshold | 96.43% (54/56) | **100.00%** (56/56) | $+3.57\text{ pp}$ |
| **LFW Development Split (840 Probes)** | Rank-1 Identification | 6.79% (57/840) | **8.81%** (74/840) | $+2.02\text{ pp}$ |
| **LFW Development Split (840 Probes)** | TPIR @ Threshold | 3.10% (26/840) | **4.05%** (34/840) | $+0.95\text{ pp}$ |
| **LFW Locked Split (840 Probes)** | Rank-1 Identification | 5.95% (50/840) | **10.00%** (84/840) | **$+4.05\text{ pp}$** ($p = 1.08\times 10^{-9}$) |
| **LFW Locked Split (840 Probes)** | TPIR @ Threshold | 1.43% (12/840) | **3.81%** (32/840) | **$+2.38\text{ pp}$** ($p = 1.10\times 10^{-5}$) |
| **LFW Locked Impostor FAR** | False Accept Rate | 9.93 ppm | 11.87 ppm | $\sim 10\text{ ppm}$ target |
| **Memory Footprint** | Template Bytes / Identity | 64 KiB | **36 KiB** | **$-43.75\%$** |
| **Scoring Latency** | Mean Score Time (840 Probes) | 36.32 ms | **21.09 ms** | **$-41.93\%$** |

---

## 3. Statistical Significance & Paired McNemar Analysis

On the 840 locked held-out LFW probes:
- **Rank-1 Accuracy**: `r3_n8_g6x6` gained 35 successes and lost only 1 compared to baseline ($p = 1.08 \times 10^{-9}$, exact two-sided McNemar).
- **Thresholded TPIR**: `r3_n8_g6x6` gained 21 successes and lost only 1 compared to baseline ($p = 1.10 \times 10^{-5}$).

---

## 4. Structure of this Directory

- [`README.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/README.md): This summary report.
- [`FINDINGS.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/FINDINGS.md): Detailed findings from the 12-configuration ablation run.
- [`summary.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/summary.json): Complete machine-readable summary metrics across all 12 configurations.
- [`paired_locked_analysis.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/paired_locked_analysis.json): Paired McNemar contingency tables.
- [`run_provenance.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/run_provenance.json): Hashes and run provenance.
- [`lsdb_development.csv`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/lsdb_development.csv): Cross-validation scores on La Salle DB1 development folds.
- [`lfw_locked.csv`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/lfw_locked.csv): Locked test split evaluation per probe.
- [`scripts/run_lbph_descriptor_ablation.py`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/scripts/run_lbph_descriptor_ablation.py): Full standalone reproducible ablation script.

---

## 5. Promotion Checklist

To promote `r3_n8_g6x6` to the active deployed runtime configuration:
- [x] Hyperparameter ablation completed and `r3_n8_g6x6` selected.
- [x] Codebase integration tests created (`tests/test_lbph_config.py`, `tests/test_lbph_threshold_compatibility.py`).
- [ ] Retrain production LBPH model on full La Salle training split using `r3_n8_g6x6`.
- [ ] Calibrate full-dataset LFW $\tau_{\text{accept}}$ and $\tau_{\text{reject}}$ specifically for `r3_n8_g6x6`.
- [ ] Revalidate joint hybrid cascade operating point in `src/hybrid/thresholds.json`.
- [ ] Run full 41-modification DL41 suite comparing baseline vs challenger under identical conditions.
