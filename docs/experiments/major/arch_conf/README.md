# Major Experiment: Combined Optimized Cascade (Quality-First Routing + Retuned LBPH)

> **Status: locked_confirmation_candidate (Verified & Ready for Manuscript Promotion)**  
> **Evaluation Scope**: 22 held-out confirmation identities $\times$ 2 source images $\times$ 41 DL41 transformations = **1,804 conditions**  
> **Execution Date**: 2026-08-16  
> **Hardware**: Intel Core i5-12450H CPU (Single-probe stream, 1 full warm-up pass $+$ 5 randomized/interleaved repetitions per probe)  
> **Outcome Classification**: `PROMISING POSITIVE CASCADE RESULT`

---

## 1. Executive Summary & Primary Confirmation Outcomes

This experiment evaluates the joint combination of **Quality-First Early-Bypass Routing** ([`../architecture/`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/README.md)) with the **compact retuned `r3_n8_g6x6` LBPH descriptor** ([`../lbph_config/`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/README.md)) on the untouched 22-identity / 1,804-condition confirmation set.

### Headline Results
1. **Recognition Accuracy Parity**: Exactly **$1,594 / 1,804$ ($88.36\%$)** correct identifications (**$0$ discordant decisions** vs Direct SFace, $100.00\%$ bit-for-bit decision equivalence).
2. **Mean Recognition-Stage Latency**: **$7.015\text{ ms}$** vs **$8.300\text{ ms}$** for True Direct SFace (**$-1.285\text{ ms}$**, **$15.48\%$ faster**, $p < 10^{-15}$) and **$11.499\text{ ms}$** for Baseline Sequential Cascade (**$-38.99\%$ faster**).
3. **Dual Inferences Reduced by 77.5%**: Dual inferences collapsed from **$1,375 \to 309$** ($80.4\% \to 18.1\%$ of inputs).
4. **Memory Footprint**: Template bytes per identity reduced from **$64\text{ KiB} \to 36\text{ KiB}$ ($-43.75\%$)**.

---

## 2. Full 6-System Ablation Table (1,804 Locked Conditions)

| System | Correct % | Correct / Total | Mean (ms) | 95% Bootstrap CI (ms) | p50 (ms) | p95 (ms) | p99 (ms) | LBPH Calls | SFace Calls | Dual Inferences |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Sequential** | 88.36% | 1,594 / 1,804 | 11.499 | [11.337, 11.650] | 12.820 | 14.361 | 15.432 | 1,711 (100.0%) | 1,375 (80.4%) | 1,375 (80.4%) |
| **Architecture Only** | 88.36% | 1,594 / 1,804 | 9.483 | [9.332, 9.635] | 8.670 | 13.771 | 14.998 | 966 (56.5%) | 1,375 (80.4%) | 630 (36.8%) |
| **Descriptor Only** | 88.36% | 1,594 / 1,804 | 8.354 | [8.164, 8.548] | 11.077 | 12.355 | 13.339 | 1,711 (100.0%) | 1,054 (61.6%) | 1,054 (61.6%) |
| **Combined Optimized** | **88.36%** | **1,594 / 1,804** | **7.015** | **[6.868, 7.173]** | **8.265** | **11.704** | **12.388** | **966 (56.5%)** | **1,054 (61.6%)** | **309 (18.1%)** |
| **Direct SFace** | 88.36% | 1,594 / 1,804 | 8.300 | [8.276, 8.324] | 8.206 | 9.183 | 10.073 | 0 (0.0%) | 1,711 (100.0%) | 0 (0.0%) |
| **Challenger LBPH** | 64.08% | 1,156 / 1,804 | 3.061 | [3.049, 3.072] | 3.008 | 3.460 | 4.086 | 1,711 (100.0%) | 0 (0.0%) | 0 (0.0%) |

---

## 3. Four Pre-Promotion Validation Checks

### Check 1: Identity-Clustered Paired Latency Bootstrap
To account for within-identity probe correlation across the 22 held-out confirmation identities, an **identity-clustered bootstrap** ($2,000$ iterations resampling entire identity clusters with replacement) was computed:
* **Combined Cascade vs. Direct SFace**:
  * Clustered Paired Mean Difference: **$-1.285\text{ ms}$** ($-1.462\text{ ms}$ branch-modeled)
  * Cluster-Robust 95% CI: **$[-1.482, -1.088]\text{ ms}$** ($p < 10^{-15}$)
  * The speed advantage over SFace is statistically stable and holds across identity resampling.
* **Combined Cascade vs. Baseline Sequential Cascade**:
  * Clustered Paired Mean Difference: **$-4.484\text{ ms}$**
  * Cluster-Robust 95% CI: **$[-4.698, -4.269]\text{ ms}$** ($p < 10^{-15}$)

### Check 2: Score Distribution Audit & Reject-Threshold Wording
* **Observed Score Range on 1,711 Detected Probes**:
  * Min Distance: `31.4998`
  * Median Distance: `48.7099`
  * 95th Percentile: `65.8158`
  * 99th Percentile: `68.2112`
  * Max Distance: `72.1824`
* **Count of Scores Reaching $d \ge 140.13$**: **$0 / 1,711$ ($0.00\%$)**.
* **Wording Contract**: The value $\tau_{\text{reject}} = 140.13$ is an **inherited inactive/permissive ceiling** that leaves the confident-reject branch dormant, NOT an active classification trigger. All non-accepted probes escalate directly to SFace.

### Check 3: Top-Two Margin Rule Clarification
* `margin_min = 0.05` is documented strictly as a **frozen empirical policy heuristic** (requiring a 5% relative distance gap between top-1 and top-2 before classical terminal accept), carried over from previous configurations. It is not claimed to be a mathematically derived invariant.

### Check 4: Challenger-LBPH $\times$ SFace Complementarity on 1,804 Locked Rows
The full $2 \times 2$ contingency matrix on the locked 1,804 confirmation conditions:

| | Direct SFace Correct | Direct SFace Failure | Total |
| :--- | :---: | :---: | :---: |
| **Challenger LBPH Correct** | **$1,156$ ($A$)** | **$0$ ($B$)** | **$1,156$** |
| **Challenger LBPH Failure** | **$438$ ($C$)** | **$210$ ($D$)** | **$648$** |
| **Total** | **$1,594$** | **$210$** | **$1,804$** |

* **$B = 0$ (LBPH-Only Successes)**: SFace strictly subsumes LBPH's correct decisions across all 1,804 conditions.
* **Oracle Union Accuracy**: $(A + B + C) / 1804 = 1,594 / 1,804 = \mathbf{88.36\%}$ (identically equal to Direct SFace).
* **Implication**: Classical LBPH provides **speedup and workload reduction**, not an accuracy ceiling expansion over SFace.

---

## 4. Workload & Severity Breakdown

| Workload Severity Group | Total Conditions | Combined Cascade Correct % | Combined Cascade Mean Latency | Combined LBPH Terminal Rate | Direct SFace Mean Latency | Challenger LBPH Correct % | Challenger LBPH Mean Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Clean Sources (Separate)** | 44 images | 100.00% (44/44) | ~3.45 ms | **86.36%** (38/44) | 8.300 ms | 97.73% (43/44) | 3.061 ms |
| **Light Tier** | 748 conditions | 94.12% (704/748) | **6.176 ms** | **49.60%** (371/748) | 8.300 ms | 80.08% (599/748) | 3.044 ms |
| **Medium Tier** | 572 conditions | 90.73% (519/572) | **7.550 ms** | **30.77%** (176/572) | 8.299 ms | 57.87% (331/572) | 3.078 ms |
| **Heavy Tier** | 484 conditions | 76.65% (371/484) | **7.722 ms** | **22.73%** (110/484) | 8.302 ms | 46.69% (226/484) | 3.065 ms |

---

## 5. Descriptor Resource Audit

| Metric | Baseline `r1_n8_g8x8` | Compact Retuned `r3_n8_g6x6` | Net Delta |
| :--- | :---: | :---: | :---: |
| **Template Bytes / Identity** | $65,536\text{ B}$ ($64.0\text{ KiB}$) | **$36,864\text{ B}$ ($36.0\text{ KiB}$)** | **$-43.75\%$ RAM** |
| **Serialized Model File Size** | $33.25\text{ MB}$ ($31.71\text{ MiB}$) | **$22.30\text{ MB}$ ($22.30\text{ MiB}$)** | **$-32.93\%$ disk** |
| **10k Gallery RAM (1 template/ID)** | $625.0\text{ MB}$ | **$351.6\text{ MB}$** | **$-273.4\text{ MB}$ saving** |
| **10k Gallery RAM (10 templates/ID)**| $6.25\text{ GB}$ | **$3.52\text{ GB}$** | **$-2.73\text{ GB}$ saving** |

---

## 6. Directory Artifact Index

- [`README.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/README.md): This report.
- [`REPORT.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/REPORT.md): Full locked confirmation markdown report.
- [`resolved_configuration.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/resolved_configuration.json): Exact frozen thresholds and cryptographic hashes.
- [`locked_manifest.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/locked_manifest.json): 1,804-condition dataset manifest.
- [`summary.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/summary.json): Complete machine-readable summary metrics and bootstrap distributions.
- [`complementarity_2x2.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/complementarity_2x2.json): $2 \times 2$ contingency table results.
- [`severity_workload_breakdown.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/severity_workload_breakdown.json): Per-tier performance metrics.
- [`resource_audit.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/resource_audit.json): Template memory and storage audit.
- [`per_condition_results.csv`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/per_condition_results.csv): Row-level records across all 1,804 conditions.
- [`scripts/run_locked_confirmation_evaluation.py`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/arch_conf/scripts/run_locked_confirmation_evaluation.py): Standalone reproducible evaluation script.
