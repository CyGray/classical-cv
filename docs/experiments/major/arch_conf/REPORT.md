# Locked Confirmation Evaluation Report: Combined Optimized Cascade

> **Status: locked_confirmation_candidate**  
> **Evaluation Scope**: 22 held-out confirmation identities $\times$ 2 source images $\times$ 41 DL41 transformations = **1,804 conditions**  
> **Execution Date**: 2026-08-16  
> **Hardware**: Intel Core i5-12450H CPU (Single-probe stream, 1 warmup + 5 randomized/interleaved timing repetitions per probe)  
> **Outcome Classification**: `PROMISING POSITIVE CASCADE RESULT`

---

## 1. Executive Summary

On the untouched 22-identity / 1,804-condition confirmation set, the **Combined Optimized Cascade** (`r3_n8_g6x6` compact retuned LBPH + Quality-First Early Bypass Routing) decisively verified the exploratory smoke findings:

1. **Mean Recognition-Stage Latency**: **$7.015\text{ ms}$** vs **$8.300\text{ ms}$** for True Direct SFace (**$-1.285\text{ ms}$**, **$15.48\%$ faster than SFace**, $95\%\text{ CI: } [-1.434, -1.125]\text{ ms}$, $p < 10^{-15}$) and **$11.499\text{ ms}$** for the Baseline Sequential Cascade (**$-38.99\%$ faster**).
2. **Recognition Accuracy**: Exactly **$1,594 / 1,804$ ($88.36\%$)** correct identifications across all 1,804 conditions (**$0$ discordant decisions** vs Direct SFace, $100.00\%$ bit-for-bit decision equivalence).
3. **Dual-Inference Collapse**: Dual inferences reduced from **$1,375 \to 309$ ($-77.53\%$ relative reduction)**.
4. **Standalone Classical Competency**: Compact challenger LBPH standalone accuracy reached **$1,156 / 1,804$ ($64.08\%$)** at **$3.061\text{ ms}$** per call with **$-43.75\%$ memory footprint**.

---

## 2. Full 6-System Ablation Table

| System | Correct % | Correct / Total | Mean (ms) | 95% CI Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | LBPH Use | SFace Use | Dual Inference |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Sequential** | 88.36% | 1,594 / 1,804 | 11.499 | [11.337, 11.650] | 12.820 | 14.361 | 15.432 | 1,711 (100.0%) | 1,375 (80.4%) | 1,375 (80.4%) |
| **Architecture Only** | 88.36% | 1,594 / 1,804 | 9.483 | [9.332, 9.635] | 8.670 | 13.771 | 14.998 | 966 (56.5%) | 1,375 (80.4%) | 630 (36.8%) |
| **Descriptor Only** | 88.36% | 1,594 / 1,804 | 8.354 | [8.164, 8.548] | 11.077 | 12.355 | 13.339 | 1,711 (100.0%) | 1,054 (61.6%) | 1,054 (61.6%) |
| **Combined Optimized** | **88.36%** | **1,594 / 1,804** | **7.015** | **[6.868, 7.173]** | **8.265** | **11.704** | **12.388** | **966 (56.5%)** | **1,054 (61.6%)** | **309 (18.1%)** |
| **Direct SFace** | 88.36% | 1,594 / 1,804 | 8.300 | [8.276, 8.324] | 8.206 | 9.183 | 10.073 | 0 (0.0%) | 1,711 (100.0%) | 0 (0.0%) |
| **Challenger LBPH** | 64.08% | 1,156 / 1,804 | 3.061 | [3.049, 3.072] | 3.008 | 3.460 | 4.086 | 1,711 (100.0%) | 0 (0.0%) | 0 (0.0%) |

---

## 3. Complementarity & Ceiling Analysis

### 2x2 Contingency Matrix: Challenger LBPH vs. Direct SFace

```text
                         Direct SFace Correct    Direct SFace Failure    Total
Challenger LBPH Correct  1,156 (A)               0 (B)                   1,156
Challenger LBPH Failure  438 (C)                 210 (D)                 648
Total                    1,594                   210                     1,804
```

- **A (Both Correct)**: 1,156
- **B (LBPH-only Correct)**: **0**
- **C (SFace-only Correct)**: 438
- **D (Both Failure)**: 210 (Includes 93 detector failures + 117 extreme sensor degradations)
- **Oracle Union Accuracy**: $(A + B + C) / 1804 = 1,594 / 1,804 = \mathbf{88.36\%}$.
- **Finding**: Because $B = 0$, every single probe correctly recognized by the challenger LBPH is also correctly recognized by Direct SFace. SFace strictly subsumes LBPH under the tested DL41 space. Therefore, score fusion cannot elevate top-1 accuracy beyond SFace's ceiling; the primary value of LBPH in the cascade is computational efficiency.

---

## 4. Severity & Workload Breakdown

| Severity Group | Total Conditions | Combined Cascade Correct % | Combined Cascade Mean Latency | Combined LBPH Terminal Rate | Direct SFace Mean Latency | Challenger LBPH Correct % | Challenger LBPH Mean Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Clean Sources** | 44 images | 100.00% (44/44) | ~3.45 ms | **86.36%** (38/44) | 8.30 ms | 97.73% (43/44) | 3.06 ms |
| **Light Tier** | 748 conditions | 94.12% (704/748) | **6.176 ms** | **49.60%** (371/748) | 8.300 ms | 80.08% (599/748) | 3.044 ms |
| **Medium Tier** | 572 conditions | 90.73% (519/572) | **7.550 ms** | **30.77%** (176/572) | 8.299 ms | 57.87% (331/572) | 3.078 ms |
| **Heavy Tier** | 484 conditions | 76.65% (371/484) | **7.722 ms** | **22.73%** (110/484) | 8.302 ms | 46.69% (226/484) | 3.065 ms |

---

## 5. Descriptor Resource Audit

- **Baseline `r1_n8_g8x8`**: $64.0\text{ KiB}$ ($65,536\text{ B}$) per enrolled template. Serialized gallery: $33.25\text{ MB}$.
- **Challenger `r3_n8_g6x6`**: **$36.0\text{ KiB}$** ($36,864\text{ B}$) per enrolled template. Serialized gallery: **$23.39\text{ MB}$** (**$-43.75\%$ memory reduction**).
- **10,000-Identity Gallery RAM**: $351.6\text{ MB}$ (singleshot) / $3.52\text{ GB}$ (10-shot) vs $625.0\text{ MB}$ / $6.25\text{ GB}$ for baseline.
