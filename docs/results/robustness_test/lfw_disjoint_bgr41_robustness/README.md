# Corrected Controlled LFW Robustness Evaluation (BGR-First, Calibration-Disjoint)

> **Status: canonical_snapshot (Verified & Leakage-Free)**  
> **Evaluation Scope**: 2,874 held-out evaluation identities $\times$ 41 DL41 transformations = **117,834 modified conditions** ($+$ 2,874 clean probes)  
> **Calibration Partition**: 2,875 development identities (50% deterministic split, seed 42)  
> **Execution Date**: 2026-08-16  
> **Execution Time**: 2,306.01 s (38.43 minutes across 8 worker processes)

---

## 1. Executive Summary

This benchmark replaces the historical Section 4.3 grayscale-first 235,709-condition run with a **strictly calibration-disjoint, BGR-first evaluation**:
1. **Calibration/Evaluation Separation**: Thresholds were calibrated exclusively on the 2,875-identity development partition. The 2,874 evaluation identities contributed zero calibration pairs.
2. **BGR-First Transformations**: All 41 DL41 transformations were generated directly in 3-channel color before recognizer-specific grayscale conversion.
3. **Headline Results**:
   - **Clean Self-Match Retention**: **$99.97\%$** across Challenger LBPH, SFace, and Combined Cascade ($2,873 / 2,874$).
   - **All-41 Macro Mean Retention**:
     - **Combined Optimized Cascade**: **$89.55\%$**
     - **Direct SFace**: **$89.55\%$**
     - **Baseline Sequential Cascade**: **$89.55\%$**
     - **Challenger LBPH**: **$81.19\%$**
   - **37 Non-Rotational Macro Mean Retention (Exclude-Canonical)**:
     - **Combined Optimized Cascade**: **$96.54\%$**
     - **Direct SFace**: **$96.54\%$**
     - **Baseline Sequential Cascade**: **$96.54\%$**
     - **Challenger LBPH**: **$89.78\%$**
   - **Strict Detector Failures**: $2,931 / 117,834$ (**$2.49\%$**), strictly retained as failures.
   - **Dual-Inference Elimination**: Quality-first bypass collapsed dual inferences to **$0.26\%$** across the 117,834 conditions.

---

## 2. Threshold Governance (Development-Partition Calibrated)

- **Challenger LBPH Accept Threshold ($\tau_{\text{accept}}$)**: `52.372394898355424` (Derived on 2,875 dev identities at $10\text{ ppm}$ target FAR; realized $9.924\text{ ppm}$).
- **Baseline LBPH Accept Threshold ($\tau_{\text{accept}}$)**: `67.0132357790767`
- **SFace $L_2$ Threshold**: `1.0313`
- **SFace Cosine Threshold**: `0.363`
- **Reject Threshold ($\tau_{\text{reject}}$)**: `140.13` (Inherited permissive policy)
- **Margin Threshold ($\text{margin}_{\text{min}}$)**: `0.05` (Frozen heuristic)

---

## 3. Artifact Index

- [`summary.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/results/robustness_test/lfw_disjoint_bgr41_robustness/summary.json): Complete machine-readable summary statistics.
- [`per_modification_results.csv`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/results/robustness_test/lfw_disjoint_bgr41_robustness/per_modification_results.csv): Per-transformation breakdown across all 41 conditions.
