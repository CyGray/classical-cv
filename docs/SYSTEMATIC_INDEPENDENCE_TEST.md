# Systematic Single-Modification LFW2 Independence Testing Specification

**Author / Project:** USLS Computer Vision Group 3 (LS-Face / Smart Gate)  
**Version:** 0.81.0  
**Target Leg:** LFW2 (5,749 identities, 41 single-modification suites)  
**Document Status:** Approved Specification & Implementation Blueprint  

---

## 1. Executive Summary & Core Objective

The current independence testing methodology relies on broad, multi-factor synthetic corruption tiers (`light`, `medium`, `heavy`). While these tiers provide a fast high-level overview of transfer degradation, they aggregate heterogeneous image defects into a single empirical distance distribution—potentially obscuring individual failure modes.

This document specifies the **Systematic Single-Modification Independence Sweep Protocol** for LFW2. Instead of mixing multiple image corruptions into coarse tiers, this protocol systematically evaluates **each of the 41 modification variants individually** across the complete $N \times (N-1)/2$ unique impostor pair space of 5,749 identities ($16,522,626$ unique comparisons per variant).

### Primary Benefits
1. **Variable Isolation**: Isolate exact physical failure thresholds for each corruption type (e.g., distinguishing Gaussian Blur $7\times7$ breakdown from Contrast $0.55$ breakdown).
2. **Unidirectional Computational Efficiency**: Eliminating symmetric duplicate pair calculations ($d(A,B) = d(B,A)$) cuts redundant operations by **50%**, reducing computation to $16.52\text{M}$ pairs per modification.
3. **Rigorous Diversity Tracking**: Evaluates pairwise error overlap (Yule's $Q$, Fisher's exact $p$-value) independently for every single corruption parameter, surfacing fine-grained engine complementarity.

---

## 2. Theoretical & Mathematical Framework

### 2.1 Unidirectional vs. Directional Impostor Sweeps

For a dataset of $N$ identities with 1 image per identity:
* **Full Directional Sweep ($N \times (N-1)$)**: Computes ordered pairs $(i, j)$ and $(j, i)$ for $i \neq j$, totaling $5,749 \times 5,748 = 33,045,252$ comparisons.
* **Unidirectional Unique Pair Sweep ($\frac{N(N-1)}{2}$)**: Computes unordered pairs $\{i, j\}$ for $i < j$, totaling $\frac{5,749 \times 5,748}{2} = 16,522,626$ comparisons.

For symmetric distance metrics (e.g., Euclidean distance, Cosine distance, Chi-Square histogram distance):
$$d(\mathbf{x}_i, \mathbf{x}_j) = d(\mathbf{x}_j, \mathbf{x}_i)$$

Evaluating the upper triangle $i < j$ yields an **identical empirical probability density function** to the full matrix, doubling execution throughput with zero loss of statistical precision.

---

### 2.2 Invariant Protocol: Frozen Threshold Anchor

In compliance with the project's core experimental standards (`AGENTS.md` and `docs/PAPER.md`):

> **Thresholds are derived ONCE on La Salle DB1 clean originals and frozen.**

The operational thresholds stored in `src/hybrid/thresholds.json` (derived from La Salle DB1 at $10,582\text{ ppm}$ FAR):
* **LBPH Accept Threshold ($\tau_{\text{accept}}$)**: $73.04$
* **LBPH Reject Threshold ($\tau_{\text{reject}}$)**: $76.85$
* **SFace Cosine Genuine Threshold ($\theta_{\text{cosine}}$)**: $0.363$
* **SFace $L_2$ Genuine Threshold ($\theta_{L2}$)**: $1.128$

Under no circumstances are decision cutoffs re-tuned or re-derived per modification. Every systematic single-modification sweep applies these exact frozen cutoffs to measure true out-of-domain transfer degradation.

---

## 3. Specification of the 41 Systematic Single-Modification Variants

The suite covers 12 modification families across 41 parameter levels (defined in `src/benchmark/modifications.py`):

| # | Modification Family | Parameter Level / Severity | Code Parameter | Total Variants |
|---|---|---|---|:---:|
| 1–4 | **Brightness Up** | `+15`, `+30`, `+45`, `+60` | `_brightness(img, offset)` | 4 |
| 5–8 | **Brightness Down** | `-15`, `-30`, `-45`, `-60` | `_brightness(img, offset)` | 4 |
| 9–11 | **Contrast Up** | `1.15`, `1.30`, `1.45` | `_contrast(img, factor)` | 3 |
| 12–14 | **Contrast Down** | `0.85`, `0.70`, `0.55` | `_contrast(img, factor)` | 3 |
| 15–17 | **Gamma Up** | `1.20`, `1.40`, `1.60` | `_gamma(img, gamma)` | 3 |
| 18–20 | **Gamma Down** | `0.80`, `0.65`, `0.50` | `_gamma(img, gamma)` | 3 |
| 21–24 | **Gaussian Noise** | $\sigma = 5$, $10$, $15$, $20$ | `_gaussian_noise(img, sigma)` | 4 |
| 25–27 | **Gaussian Blur** | $k = 3\times3$, $5\times5$, $7\times7$ | `_gaussian_blur(img, ksize)` | 3 |
| 28–30 | **Motion Blur** | $k = 3$, $5$, $7\text{ px}$ | `_motion_blur(img, ksize)` | 3 |
| 31–34 | **Rotation** | $-10^\circ$, $-5^\circ$, $+5^\circ$, $+10^\circ$ | `_rotation(img, angle)` | 4 |
| 35–38 | **Zoom** | $0.90\times$, $0.95\times$, $1.05\times$, $1.10\times$ | `_zoom(img, zoom)` | 4 |
| 39–41 | **Occlusion** | $7.5\%$, $12.5\%$, $17.5\%\text{ area}$ | `_occlusion(img, fraction)` | 3 |
| **Sum** | **12 Families** | **41 Individual Parameter Sets** | | **41** |

---

## 4. Execution Performance & Hardware Scaling (Intel i5-12450H)

### 4.1 Memory & Compute Budget

* **Identities ($N$)**: 5,749
* **Unique Pair Comparisons per Modification**: $16,522,626$
* **Total Impostor Pair Evaluations (41 Sweeps)**: $41 \times 16,522,626 = \mathbf{677,427,666 \text{ comparisons}}$

### 4.2 Benchmark Speed & Time Budget (Intel Core i5-12450H)
* **Processor Specs**: 8 Cores / 12 Threads (4 Performance-Cores + 4 Efficient-Cores, up to $4.4\text{ GHz}$)
* **Vectorized Pair Comparison Throughput**: $\approx 60,000\text{ to } 80,000\text{ pairs/sec}$
* **Time per 16.5M Single-Modification Sweep**: $\approx 4.0\text{ to } 4.5\text{ minutes}$
* **Total Execution Time for All 41 Modifications**: $\approx \mathbf{2.8 \text{ to } 3.2 \text{ hours}}$

### 4.3 RAM Footprint
* SFace Embeddings ($5,749 \times 128 \times 4\text{ bytes} \approx 2.94\text{ MB}$)
* LBPH Histograms ($5,749 \times 2,048 \times 4\text{ bytes} \approx 47.09\text{ MB}$)
* Total Feature Matrix Footprint: **$< 50\text{ MB}$** (neglectable memory overhead on 16 GB DDR4 RAM).

---

### 4.4 Trade-off Comparison: Tiered Pooled vs. Systematic Per-Variant Suite

| Evaluation Mode | Number of Sweeps | Unique Pairs ($N(N-1)/2$) | Directional Pairs ($N(N-1)$) | Estimated Runtime (i5-12450H) | Primary Analytical Purpose |
|---|---:|---:|---:|---:|---|
| **Tiered Pooled (3 Tiers)** | 3 sweeps (`light`, `medium`, `heavy`) | **49,567,878** | **99,135,756** | **~15 minutes** | High-level transfer degradation overview |
| **Systematic Per-Variant Suite** | **41 sweeps** (all parameter levels) | **677,427,666** | **1,354,855,332** | **~3.0 to 3.2 hours** | ⭐ Pinpoint single-variable corruption breakdown & 41-point Yule's $Q$ spectrum |

---

## 5. Statistical Output & Deliverables

For each of the 41 modification sweeps, the execution engine writes structured artifacts to `reports/independence/systematic_lfw2/<mod_name>/`:

1. **`summary.json`**:
   * **Marginal False Acceptance Rates**: LBPH-only, SFace-only, and Fused Cascade FAR with 95% Wilson Confidence Intervals.
   * **Diversity & Error Overlap**: 
     * Observed vs. Expected Joint False Positive Ratio ($\frac{P(A \cap B)}{P(A)P(B)}$)
     * Yule’s $Q$ Statistic ($\frac{ad - bc}{ad + bc}$)
     * Disagreement Measure ($D$) & Double Fault Rate ($DF$)
     * Fisher's Exact Test $p$-value for error co-occurrence.
   * **Cascade Efficiency**: Escalation percentage and breakdown of gate reasons (Quality, Margin, Ambiguous Band).

2. **Distance & Distribution Plots**:
   * Distance histogram vs. clean LFW1 baseline.
   * FAR operating curve vs. frozen threshold $\tau_{\text{accept}}$.

3. **`systematic_matrix.md` & `systematic_matrix.json`**:
   * Consolidated 41-row master table summarizing degradation-distance compression across all 12 families.

---

## 6. CLI Command & Orchestration Workflow

### 6.1 Running a Single Systematic Modification Leg
```bash
.venv/bin/python -m src.hybrid.independence_test \
    --dataset-dir data/lfw2_41mods/single_mods/motion_blur_k5 \
    --output-dir reports/independence/systematic_lfw2/motion_blur_k5 \
    --thresholds-json src/hybrid/thresholds.json \
    --unidirectional \
    --iterations 1
```

### 6.2 Full 41-Suite Automated Harness
```bash
.venv/bin/python scripts/run_systematic_lfw2_independence.py \
    --lfw-root data/lfw-dataset \
    --output-dir reports/independence/systematic_lfw2 \
    --thresholds-json src/hybrid/thresholds.json \
    --unidirectional \
    --num-workers 8
```

---

## 7. Integration with Deliverables (`docs/PAPER.md`)

The output from this systematic suite directly provides:
1. **Section 4.3 (Robustness & Degradation Transfer)**: Quantifies exact distance distribution compression for each of the 12 corruption families.
2. **Section 4.5 (Joint Error Independence & Diversity)**: Replaces coarse tier averages with a comprehensive 41-point Yule's $Q$ spectrum, proving where CV and DL errors remain independent vs. where they co-occur.
