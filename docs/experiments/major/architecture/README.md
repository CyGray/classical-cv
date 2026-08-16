# Major Experiment: Quality-First Early-Bypass Routing Architecture

> **Status: Candidate Improvement (Waiting for Promotion)**  
> **Evaluation Scope**: Full held-out La Salle DB1 test split (56 source images across 28 identities $\times$ 41 DL41 transformations = **2,296 conditions**).  
> **Execution Date**: 2026-08-16  
> **Key Finding**: Reordering image quality checks before LBPH **eliminates 43.29% of LBPH calls** and **cuts dual inference from 77.61% to 34.32%**, speeding up cascade mean latency by **18.27%** ($11.96\text{ ms} \to 9.77\text{ ms}$) and median ($p50$) latency by **31.05%** ($13.11\text{ ms} \to 9.04\text{ ms}$) while providing **100% bit-for-bit mathematical and decision equivalence** ($0$ mismatches across all 2,296 conditions).

---

## 1. Core Hypothesis & Architectural Shift

The current sequential LS-Face cascade executes LBPH inference unconditionally on every input before computing image quality flags:
$$\text{Input Tile} \longrightarrow \mathbf{LBPH} \longrightarrow \mathbf{Quality\ Check} \longrightarrow \mathbf{Gate\ Decision} \longrightarrow \mathbf{SFace\ (if\ escalated)}$$

When an image is degraded by severe blur, extreme low-light, high sensor noise, large off-angle pose, or tiny face crop, the quality gate triggers escalation regardless of LBPH distance. In the sequential cascade, the system always pays the latency of LBPH before discovering that the quality flag already required SFace.

Because all five quality signals (`blur_var`, `luma_mean`, `noise_sigma`, `pose_angle`, `face_px`) are computed strictly from the YuNet crop tile and 5 facial landmarks **independently of LBPH**, the quality checks can be moved to the front:
$$\text{Input Tile} \longrightarrow \mathbf{Quality\ Check} \longrightarrow \begin{cases} \mathbf{Poor\ Quality:} & \mathbf{Direct\ SFace}\ (\text{LBPH bypassed completely}) \\ \mathbf{Clear\ Quality:} & \mathbf{LBPH} \longrightarrow \begin{cases} \text{Ambiguous / Weak Margin:} & \mathbf{SFace} \\ \text{Confident Accept / Reject:} & \mathbf{Terminate} \end{cases} \end{cases}$$

---

## 2. Invariant Equivalence Proof

Across all **2,296 evaluated conditions** on the full held-out La Salle DB1-DL41 suite:

1. **Final Decision Equivalence**: **0 / 2,296 mismatches** ($100.00\%$ bit-for-bit match).
2. **SFace Escalation Set Equivalence**: **0 / 2,296 mismatches** (exact same $1,782$ probes routed to SFace).
3. **Acceptance / Rejection Equivalence**: **0 / 2,296 mismatches** (identical $88.41\%$ accuracy, matching direct SFace).

---

## 3. Comprehensive Performance Benchmark across All 5 Modes

*Evaluated with 1 warmup pass $+$ 5 interleaved, per-probe randomized timing repetitions on Intel Core i5-12450H CPU.*

| Mode | Correct Acceptance (TPIR) | Correct Rate (%) | SFace Invocations | LBPH Invocations | Dual Inferences | Mean Latency (ms) | Median / p50 (ms) | p95 (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Always LBPH** | 704 / 2,296 | 30.66% | 0 (0.0%) | 2,189 (95.34%) | 0 (0.0%) | 4.733 ms | 4.632 ms | 5.490 ms |
| **Direct SFace** | 2,030 / 2,296 | 88.41% | 2,189 (95.34%) | 0 (0.0%) | 0 (0.0%) | 8.623 ms | 8.444 ms | 9.952 ms |
| **Current Cascade (Sequential)** | 2,030 / 2,296 | 88.41% | 1,782 (77.61%) | 2,189 (95.34%) | 1,782 (77.61%) | 11.955 ms | 13.113 ms | 15.298 ms |
| **Quality-Only Router** | 1,355 / 2,296 | 59.02% | 994 (43.29%) | 1,195 (52.05%) | 0 (0.0%) | 6.684 ms | 5.398 ms | 9.715 ms |
| **Quality-First Early Bypass** | **2,030 / 2,296** | **88.41%** | **1,782 (77.61%)** | **1,195 (52.05%)** | **788 (34.32%)** | **9.771 ms** | **9.041 ms** | **14.269 ms** |

---

## 4. Latency Decomposition by Branch

$$\begin{array}{lcccc}
\hline
\textbf{Early-Bypass Execution Branch} & \textbf{Conditions / Share} & \textbf{Mean (ms)} & \textbf{p50 (ms)} & \textbf{p95 (ms)} \\
\hline
\text{1. Quality-Triggered } \to \text{ Direct SFace} & 994\text{ (}43.29\%\text{)} & 8.869\text{ ms} & 8.690\text{ ms} & 10.235\text{ ms} \\
\text{2. Quality-Clear } \to \text{ LBPH Terminal} & 407\text{ (}17.73\%\text{)} & 4.811\text{ ms} & 4.680\text{ ms} & 5.577\text{ ms} \\
\text{3. Quality-Clear } \to \text{ LBPH } \to \text{ SFace (Dual)} & 788\text{ (}34.32\%\text{)} & 13.469\text{ ms} & 13.189\text{ ms} & 15.219\text{ ms} \\
\text{Detector Failure (Strict Policy)} & 107\text{ (}4.66\%\text{)} & 0.000\text{ ms} & 0.000\text{ ms} & 0.000\text{ ms} \\
\hline
\textbf{Total / Overall} & \mathbf{2,296\text{ (}100.0\%\text{)}} & \mathbf{9.771\text{ ms}} & \mathbf{9.041\text{ ms}} & \mathbf{14.269\text{ ms}} \\
\hline
\end{array}$$

---

## 5. Quality Diagnostic Contingency Matrix

```text
                     LBPH Correct    LBPH Failure    Total
Quality Clear        415             780             1,195
Quality Flagged      289             705             994
Total                704             1,485           2,189
```

- **Recall of LBPH Failures by Quality Flags Alone**: **$47.47\%$** ($705 / 1,485$).
- **False Alarm (Unnecessary Flag on LBPH-Correct Cases)**: **$41.05\%$** ($289 / 704$).
- **Fundamental Finding**: Quality-only routing collapses accuracy from **$88.41\% \to 59.02\%$** because quality flags miss **$52.53\%$ of LBPH failures** (780 cases where image quality appeared completely normal but LBPH misidentified the subject). The cascade rescues all 780 cases via LBPH-derived distance and margin uncertainty. Thus, **LBPH uncertainty signals are mathematically indispensable**.

---

## 6. Structure of this Directory

- [`README.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/README.md): This architectural report.
- [`REPORT.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/REPORT.md): Full evaluation markdown report.
- [`summary.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/summary.json): Complete machine-readable summary metrics.
- [`resolved_configuration.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/resolved_configuration.json): Exact deployed thresholds, code hashes, and git commit.
- [`source_manifest.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/source_manifest.json): 56 source test image filepaths across 28 identities.
- [`subset_manifest.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/subset_manifest.json): 10% smoke test subset manifest.
- [`timing_control_summary.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/timing_control_summary.json): Paired timing control pass verifying zero difference in dual-inference components under interleaving.
- [`per_condition_results.csv`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/per_condition_results.csv): Row-level results across all 2,296 conditions.
- [`scripts/`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/scripts/): Standalone executable scripts for reproduction (`run_quality_first_smoke.py`, `timing_control_pass.py`, `run_quality_first_full_2296.py`, `compare_canonical_divergence.py`).

---

## 7. Promotion Checklist

To promote this architectural improvement into production / runtime:
- [x] Invariant bit-for-bit decision equivalence proven across all 2,296 DL41 conditions.
- [x] Timing isolation and interleaved benchmark executed across 5 repetitions.
- [x] Quality independence verified (quality metrics computed prior to and independent of LBPH).
- [ ] Update `HybridRecognizer.predict()` in `classical-cv/src/hybrid/recognizer.py` to evaluate quality first when `mode == "cascade"`.
- [ ] Update documentation and manuscript latency discussions in `docs/PAPER.md` upon advisor sign-off.
