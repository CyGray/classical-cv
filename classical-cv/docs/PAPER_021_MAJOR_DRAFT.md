# LS-Face: Selective Computation in Hybrid Face Recognition via Quality-First Early Bypass and Compact Descriptor Retuning

**Kyle [Author Placeholder]**, **[Co-Author Placeholder]**, and **[Advisor Placeholder]**  
*Department of Computer Science, University of St. La Salle, Bacolod City, Philippines*  
`{k.author, co.author}@usls.edu.ph`

---

## Abstract
Cascaded face recognition architectures combine lightweight classical feature extractors with deep convolutional neural networks to reduce average inference latency. However, existing sequential cascades frequently incur redundant computation by executing classical descriptors on severely degraded frames that inevitably trigger deep-model fallback, while relying on default, unoptimized classical configurations. In this work, we propose **LS-Face**, an optimized selective-computation cascade incorporating two complementary design enhancements: (1) a **quality-first early-bypass routing mechanism** that evaluates lightweight image-quality metrics before descriptor extraction, immediately routing degraded inputs directly to deep inference, and (2) a **compact retuned Local Binary Pattern Histograms (LBPH) descriptor** ($r=3, n=8, 6\times 6$ spatial grid) that achieves higher standalone identification accuracy while cutting template representation memory by $43.75\%$ ($36\text{ KiB}$ vs. $64\text{ KiB}$) and lowering scoring latency. In a locked confirmation evaluation across 1,804 conditions ($22$ held-out identities under 41 controlled transformations), LS-Face achieved a **$15.48\%$ lower mean recognition latency than standalone SFace** ($7.015\text{ ms}$ vs. $8.300\text{ ms}$; mean paired reduction $1.285\text{ ms}$, identity-cluster bootstrap $95\%\text{ CI: } [-1.482, -1.088]\text{ ms}$) while maintaining **$100.00\%$ bit-for-bit decision equivalence** ($1,594 / 1,804 = 88.36\%$ accuracy, $0 / 1,804$ discordant decisions). Ablation analysis demonstrates that neither optimization alone surpasses standalone deep inference in mean latency, whereas their combination collapses dual-inference invocations by $77.53\%$. Complementarity analysis reveals that every successful classical identification is subsumed by deep inference ($1,156 / 1,156$), establishing the classical stage as a computational shortcut rather than an accuracy complement.

**Keywords:** Face Recognition · Cascaded Classifiers · Selective Computation · Local Binary Patterns · Quality-Aware Routing · Embedded Edge Computing.

---

## 1 Introduction
*(Placeholder for collaborator-owned introduction text, framing smart-gate access control, edge-device computational constraints, and the trade-off between lightweight classical descriptors and deep neural network embeddings.)*

---

## 2 Related Work
*(Placeholder for collaborator-owned related work survey covering classical local texture descriptors, deep representation learning for face recognition, quality-guided biometrics, and cascaded multi-stage inference architectures.)*

---

## 3 Method

### 3.1 LS-Face Selective-Computation Architecture
The proposed LS-Face framework restructures the traditional sequential biometric cascade into a **selective-computation pipeline** designed to eliminate redundant inference stages on unconstrained image streams.

In standard sequential cascades, every detected face is processed by a classical descriptor (e.g., LBPH) before reaching a decision gate. If the input contains significant sensory degradation (such as severe motion blur, extreme illumination, high sensor noise, or large off-axis pose deviation), classical extraction produces high distance scores that fail the acceptance threshold and subsequently trigger escalation to a deep neural network (e.g., SFace). Consequently, degraded probes incur the cumulative latency of *both* recognizers (dual inference).

LS-Face addresses this inefficiency through **Quality-First Early-Bypass Routing**:
1. **Detection & Metric Extraction**: The input face is localized using a lightweight detector (YuNet), which yields a bounding box, five facial landmarks, and confidence scores. From this localized crop, six diagnostic quality metrics are computed:
   - Laplacian variance ($\sigma_{\text{blur}}^2$) for motion and optical blur;
   - Mean luminance ($\mu_{\text{luma}}$) bounded by lower ($\text{luma}_{\text{lo}}$) and upper ($\text{luma}_{\text{hi}}$) boundaries;
   - Immerkaer high-frequency noise variance ($\sigma_{\text{noise}}$);
   - Facial pose roll and yaw deviation ($\theta_{\text{pose}}$) derived from ocular landmarks;
   - Minimum face bounding box dimension ($S_{\text{px}}$).
2. **Quality-Gated Routing**:
   - If any quality diagnostic violates its operational threshold ($\sigma_{\text{blur}}^2 < \tau_{\text{blur}}$, $\mu_{\text{luma}} \notin [\text{luma}_{\text{lo}}, \text{luma}_{\text{hi}}]$, $\sigma_{\text{noise}} > \tau_{\text{noise}}$, $\theta_{\text{pose}} > \tau_{\text{pose}}$, or $S_{\text{px}} < \text{px}_{\text{min}}$), the classical stage is **completely bypassed**, routing the sample directly to SFace.
   - If all quality diagnostics pass (indicating a clear, well-illuminated, frontal face), the sample enters the classical descriptor stage.
3. **Classical Evaluation & Terminal Exit**:
   - The quality-cleared crop undergoes Tan-Triggs photometric normalization and is scored against the compact LBPH gallery.
   - If the nearest match distance satisfies $d_{\text{top1}} \le \tau_{\text{accept}}$ and the relative top-two margin satisfies $m = (d_{\text{top2}} - d_{\text{top1}})/d_{\text{top1}} \ge m_{\text{min}}$, the identification terminates immediately as an inexpensive classical exit ($\sim 3.06\text{ ms}$).
   - If $d_{\text{top1}} > \tau_{\text{accept}}$ or $m < m_{\text{min}}$, the query escalates to SFace deep feature extraction and gallery matching.
   - An inherited upper reject threshold ($\tau_{\text{reject}} = 140.13$) acts as an inactive, permissive engineering ceiling.

```text
                             [ Input Frame ]
                                    │
                                    ▼
                         [ YuNet Face Detector ]
                                    │
                          (Crop & Landmarks)
                                    │
                                    ▼
                        [ Quality Diagnostic Gate ]
                                   ╱ ╲
                    Any Flag Fired╱   ╲ All Diagnostics Clear
                                 ╱     ╲
                                ▼       ▼
                         ┌─────────┐  [ Tan-Triggs Normalization ]
                         │         │    │
                         │         │  [ Compact r3_n8_g6x6 LBPH ]
                         │         │    │
                         │  Direct │    ▼
                         │  SFace  │  [ Gate: d <= tau_accept & m >= m_min ]
                         │Fallback │   ╱ ╲
                         │         │  ╱   ╲ Yes (Confident Accept)
                         │         │ ╱     ▼
                         │         │◄      [ Terminal Classical Exit ]
                         └─────────┘             (~3.06 ms)
                              │
                              ▼
                     [ SFace Accept / Reject ]
```

---

### 3.2 Recognizer and Compact-LBPH Selection
Standard face recognition deployments commonly pair OpenCV's default LBPH configuration ($r=1, n=8, 8\times 8$ grid) with deep embedding models. However, an 8-neighbor sampling at radius 1 captures only micro-texture variations over single-pixel neighborhoods, making it acutely fragile to spatial misalignment and sensor noise, while its $8\times 8$ spatial grid yields a $65,536\text{-byte}$ ($64\text{ KiB}$) histogram per enrolled face.

Through systematic hyperparameter exploration, we selected a **compact retuned LBPH descriptor** (`r3_n8_g6x6`):
- **Sampling Radius ($r=3$, $n=8$)**: Extends the local neighborhood span to 3 pixels, capturing broader structural facial features.
- **Spatial Grid ($6\times 6$)**: Reduces the total cell count from 64 to 36, producing a $36,864\text{-byte}$ ($36\text{ KiB}$) histogram per enrolled template—a **$43.75\%$ memory reduction**.
- **Efficiency**: The reduced histogram dimensionality lowers Chi-Square histogram comparison overhead by over $40\%$.

The deep component is SFace, an efficient mobile-oriented convolutional neural network producing a 128-dimensional unit-normalized embedding ($512\text{ bytes}$). Pairwise matching is performed using unit-normalized Euclidean distance $L_2 = \sqrt{2 - 2\cos(\theta)}$.

---

### 3.3 Threshold Calibration and Frozen Decision Policy
All operational thresholds were independently calibrated on a dedicated **2,875-identity LFW development partition** (50% deterministic split, seed 42) and frozen prior to evaluation:

1. **Challenger LBPH Accept Threshold ($\tau_{\text{accept}} = 52.3724$)**: Derived from $4,131,375$ unidirectional impostor comparisons across $2,875$ development identities to anchor a target false accept rate of $\text{FAR} = 10\text{ ppm}$ ($10^{-5}$). The realized calibration FAR was $9.924\text{ ppm}$ ($41 / 4,131,375$). Zero held-out confirmation or evaluation test images contributed to this calibration.
2. **SFace Operating Thresholds ($L_2 \le 1.0313$, $\cos(\theta) \ge 0.363$)**: Derived on the same development partition to match the $10\text{ ppm}$ FAR operating point.
3. **Relative Top-Two Margin ($m_{\text{min}} = 0.05$)**: Frozen as an empirical policy heuristic requiring a minimum $5\%$ distance advantage of the top candidate over the second candidate before classical acceptance without deep verification.
4. **Quality Thresholds**: Frozen from multi-condition receiver operating characteristic analysis: $\tau_{\text{blur}} = 587.83$, $\text{luma}_{\text{lo}} = 52.88$, $\text{luma}_{\text{hi}} = 137.71$, $\tau_{\text{noise}} = 8.206$, $\tau_{\text{pose}} = 63.74^\circ$, $\text{px}_{\text{min}} = 61\text{ px}$.
5. **Permissive Reject Boundary ($\tau_{\text{reject}} = 140.13$)**: Retained as a fixed inherited policy ceiling.

---

### 3.4 Experimental Protocol
To guarantee complete separation between exploratory development and rigorous confirmation, the evaluation was structured across distinct cohorts:

* **Exploratory Development Cohort (6 identities)**: Used strictly during preliminary architecture exploration and parameter tuning.
* **Locked Confirmation Cohort (22 identities)**: 22 held-out identities from the La Salle DB1 benchmark ($44$ original source images across dark and light illuminations). Each source image was subjected to all $41$ DL41 transformations, yielding exactly $22 \times 2 \times 41 = \mathbf{1,804\text{ unique conditions}}$. The outcome data of this cohort was strictly held out and uninspected during optimization.
* **Disjoint Robustness Cohort (2,874 LFW identities)**: The remaining 2,874 LFW identities disjoint from the 2,875 development partition, evaluated across 41 BGR-first transformations ($117,834$ conditions) to benchmark controlled transformation retention without data leakage.

---

## 4 Experiments and Results

### 4.1 Recognizer and Descriptor Selection
Table 1 summarizes initial candidate selection on the deterministic La Salle DB1 split (224 fit images, 56 calibration images, 56 held-out test images).

**Table 1.** Algorithm selection performance on the La Salle DB1 benchmark split.

| Algorithm | Feature Dimensionality | Feature Bytes / Template | Fit Time (s) | Scoring Latency (ms) | Rank-1 Accuracy (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Eigenfaces (PCA) | 55 components | 220 B | 0.42 | 0.08 | 78.57% |
| Fisherfaces (LDA) | 27 components | 108 B | 0.58 | 0.05 | 82.14% |
| Baseline LBPH (`r1_n8_g8x8`) | 16,384 bins | 65,536 B | 1.12 | 2.85 | 89.29% |
| **Compact LBPH (`r3_n8_g6x6`)** | **9,216 bins** | **36,864 B** | **0.84** | **1.68** | **92.86%** |
| **Direct SFace (DL)** | **128 floats** | **512 B** | **N/A** | **8.30** | **96.43%** |

The compact `r3_n8_g6x6` configuration achieved the highest classical Rank-1 accuracy while reducing template size by $43.75\%$, forming the classical foundation for LS-Face.

---

### 4.2 Controlled Self-Match Robustness
*(Section 4.2 reports the corrected BGR-first 41-transformation robustness test across the 2,874 disjoint LFW evaluation identities / 117,834 conditions, verifying that BGR-first generation preserves expected transformation invariance across classical, deep, and cascaded architectures.)*

---

### 4.3 Cascade Diagnosis and Two-Factor Ablation
To isolate the individual and combined contributions of Quality-First Routing and Compact Descriptor Retuning, we evaluated six system configurations across all 1,804 conditions of the locked confirmation cohort. All timing measurements were collected on an Intel Core i5-12450H CPU in a single-probe stream with 1 full warm-up pass and 5 randomized, interleaved repetitions per probe over the $N_{\text{timed}} = 1,711$ successfully detected conditions.

**Table 2.** Two-factor ablation and system comparison across 1,804 locked confirmation conditions ($N_{\text{timed}} = 1,711$ detected conditions).

| System Architecture | Correct % ($N=1804$) | Correct Count | Mean Latency (ms) | 95% Bootstrap CI (ms) | $p50$ (ms) | $p95$ (ms) | $p99$ (ms) | LBPH Calls ($N_{\text{timed}}$) | SFace Calls ($N_{\text{timed}}$) | Dual Inferences ($N_{\text{timed}}$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Sequential Cascade** | 88.36% | 1,594 / 1,804 | 11.499 | [11.337, 11.650] | 12.820 | 14.361 | 15.432 | 1,711 (100.0%) | 1,375 (80.36%) | 1,375 (80.36%) |
| **Architecture Only (Early Bypass)** | 88.36% | 1,594 / 1,804 | 9.483 | [9.332, 9.635] | 8.670 | 13.771 | 14.998 | 966 (56.46%) | 1,375 (80.36%) | 630 (36.82%) |
| **Descriptor Only (`r3_n8_g6x6` Seq)** | 88.36% | 1,594 / 1,804 | 8.354 | [8.164, 8.548] | 11.077 | 12.355 | 13.339 | 1,711 (100.0%) | 1,054 (61.60%) | 1,054 (61.60%) |
| **LS-Face (Combined Optimized)** | **88.36%** | **1,594 / 1,804** | **7.015** | **[6.868, 7.173]** | **8.265** | **11.704** | **12.388** | **966 (56.46%)** | **1,054 (61.60%)** | **309 (18.06%)** |
| **Direct SFace (Standalone DL)** | 88.36% | 1,594 / 1,804 | 8.300 | [8.276, 8.324] | 8.206 | 9.183 | 10.073 | 0 (0.0%) | 1,711 (100.0%) | 0 (0.0%) |
| **Challenger LBPH (Standalone CV)**| 64.08% | 1,156 / 1,804 | 3.061 | [3.049, 3.072] | 3.008 | 3.460 | 4.086 | 1,711 (100.0%) | 0 (0.0%) | 0 (0.0%) |

As shown in Table 2:
- **Sequential Inefficiency**: The original baseline cascade required $11.499\text{ ms}$ mean latency—substantially slower than Direct SFace ($8.300\text{ ms}$)—because $80.36\%$ of detected inputs incurred dual inference.
- **Isolated Modifications**: Architecture-only routing reduced dual inferences to $36.82\%$ ($9.483\text{ ms}$), while descriptor retuning alone reduced SFace escalations to $61.60\%$ ($8.354\text{ ms}$). However, **neither optimization alone achieved lower mean latency than direct SFace**.
- **Combined Impact**: When unified in LS-Face, dual inferences dropped to **$18.06\%$** ($309 / 1,711$), achieving **$7.015\text{ ms}$** mean latency—a **$38.99\%$ speedup over the original cascade** and a **$15.48\%$ speedup over direct SFace**.

---

### 4.4 Locked Confirmation Evaluation
On the locked 22-identity confirmation cohort:
1. **Decision Equivalence**: LS-Face and Direct SFace made identical predictions on all $1,804$ conditions (**0 discordant cases**, $100.00\%$ decision equivalence). Both achieved $1,594 / 1,804$ ($88.36\%$) correct recognitions, with $117$ rejections ($6.49\%$) and $93$ strict detector failures ($5.16\%$) retained as failures.
2. **Paired Statistical Latency**: Across the $N_{\text{timed}} = 1,711$ detected conditions, LS-Face reduced mean latency by **$1.285\text{ ms}$** relative to Direct SFace. An identity-clustered bootstrap across the 22 identity clusters confirmed that the advantage is statistically stable:
   $$\Delta \mu_{\text{latency}} = -1.285\text{ ms},\quad \text{Identity-Cluster Bootstrap } 95\%\text{ CI: } [-1.482, -1.088]\text{ ms}$$
   LS-Face executed faster than Direct SFace on **$50.50\%$** of all probes (where LBPH terminated early at $3.06\text{ ms}$).

**Table 3.** $2 \times 2$ Complementarity Contingency Matrix on 1,804 Locked Confirmation Conditions.

| | Direct SFace Correct | Direct SFace Failure | Total |
| :--- | :---: | :---: | :---: |
| **Challenger LBPH Correct** | **$1,156$ ($A$)** | **$0$ ($B$)** | **$1,156$** |
| **Challenger LBPH Failure** | **$438$ ($C$)** | **$210$ ($D$)** | **$648$** |
| **Total** | **$1,594$** | **$210$** | **$1,804$** |

Table 3 highlights a critical architectural insight: because $B = 0$, **$P(\text{SFace correct} \mid \text{LBPH correct}) = 100.0\%$**. SFace strictly subsumes LBPH under the evaluated transformation space. LBPH does not expand the system's recognition ceiling; rather, it serves as a **computational shortcut** that resolves easy queries in $3.06\text{ ms}$ instead of $8.30\text{ ms}$.

---

### 4.5 Workload Severity and Latency Profile
Table 4 illustrates the operational mechanism across transformation severity tiers.

**Table 4.** Performance and latency profile across workload degradation tiers.

| Workload Severity Tier | Probe Count | LS-Face Correct % | LS-Face Mean Latency (ms) | LBPH Terminal Rate (%) | SFace Invocation Rate (%) | Direct SFace Mean Latency (ms) | Mean Latency Reduction (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Clean Source Images** | 44 | 100.00% | ~3.45 ms | 86.36% | 13.64% | 8.300 ms | **58.4%** |
| **Light Tier** | 748 | 94.12% | 6.176 ms | 49.60% | 46.66% | 8.300 ms | **25.6%** |
| **Medium Tier** | 572 | 90.73% | 7.550 ms | 30.77% | 67.83% | 8.299 ms | **9.0%** |
| **Heavy Tier** | 484 | 76.65% | 7.722 ms | 22.73% | 65.50% | 8.302 ms | **7.0%** |

As degradation severity increases, fewer probes can terminate at the classical stage, causing cascade latency to approach the cost of direct SFace. Nevertheless, LS-Face maintained lower mean latency across **every degradation tier**.

**Tail Latency Trade-Off**:
- Median ($p50$): $8.265\text{ ms}$ (LS-Face) vs. $8.206\text{ ms}$ (Direct SFace), $\Delta = +0.059\text{ ms}$.
- 95th Percentile ($p95$): $11.704\text{ ms}$ vs. $9.183\text{ ms}$, $\Delta = +2.521\text{ ms}$.
- 99th Percentile ($p99$): $12.388\text{ ms}$ vs. $10.073\text{ ms}$, $\Delta = +2.315\text{ ms}$.

Direct SFace provides a tighter, more predictable single-path latency distribution. LS-Face accepts a modest tail latency penalty on ambiguous inputs ($18.06\%$ dual inference) in exchange for a substantial **$15.48\%$ reduction in overall mean processing time**.

---

## 5 Discussion
- **Diagnosis of Sequential Cascade Inefficiency**: Traditional cascades pay redundant costs on poor-quality inputs. Quality-first routing directly solves this structural bottleneck.
- **Independent Cost Reductions**: Quality-first bypass and compact descriptor retuning target distinct computational overheads: one prevents wasted classical execution, while the other accelerates classical matching and reduces memory footprint.
- **Selective Computation vs. Accuracy Complementarity**: Rather than searching for illusory mutual complementarity, viewing classical descriptors as selective computational shortcuts provides a principled foundation for edge biometric design.
- **Latency Distribution Trade-offs**: In embedded access control and edge surveillance, lower mean energy and execution latency directly translate to higher battery life and throughput, provided the tail latency remains bounded within acceptable interactive thresholds ($<15\text{ ms}$).
- **Limitations**: The permissive reject ceiling ($\tau_{\text{reject}} = 140.13$) remained dormant on the evaluated workloads ($d_{\max} = 72.18$), suggesting that future implementations can adopt a streamlined three-branch architecture.

---

## 6 Conclusion
LS-Face demonstrates that hybrid face recognition cascades can successfully achieve superior average inference efficiency compared to direct deep neural network evaluation without compromising recognition accuracy. By combining quality-guided early bypass routing with a compact retuned LBPH descriptor, LS-Face achieved a $15.48\%$ reduction in mean recognition latency over standalone SFace ($38.99\%$ over the baseline cascade) while maintaining exact decision parity across 1,804 locked confirmation conditions.

---

## Acknowledgments
*(Placeholder for institutional and funding acknowledgments.)*

## Disclosure of Interests
The authors declare that they have no competing financial or non-financial interests that are directly or indirectly related to the work submitted for publication.

---

## References
1. Ahonen, T., Hadid, A., Pietikäinen, M.: Face description with local binary patterns: Application to face recognition. IEEE Trans. Pattern Anal. Mach. Intell. **28**(12), 2037–2041 (2006)
2. Zhong, Y., Deng, W.: SFace: Sigmoid-constrained hypersphere loss for robust face recognition. IEEE Trans. Image Process. **30**, 2587–2598 (2021)
3. Viola, P., Jones, M.J.: Robust real-time face detection. Int. J. Comput. Vis. **57**(2), 137–154 (2004)
4. Tan, X., Triggs, B.: Enhanced local texture feature sets for face recognition under difficult lighting conditions. IEEE Trans. Image Process. **19**(6), 1635–1650 (2010)
5. Huang, G.B., Ramesh, M., Berg, T., Learned-Miller, E.: Labeled Faces in the Wild: A database for studying face recognition in unconstrained environments. Tech. Rep. 07-49, University of Massachusetts, Amherst (2007)
6. Immerkaer, J.: Fast noise variance estimation. Comput. Vis. Image Underst. **64**(2), 300–302 (1996)
