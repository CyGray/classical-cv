# Major Experiments & Candidate Improvements

This directory contains version-controlled, fully characterized **major experiments and architectural candidates** that have demonstrated strong empirical advantages over baseline configurations but remain in **unpromoted candidate status** awaiting formal advisor sign-off, runtime threshold recalibration, or manuscript integration.

---

## Directory Index

| Subdirectory | Experiment Name | Primary Improvement | Status | Key Artifacts |
| :--- | :--- | :--- | :---: | :--- |
| [`architecture/`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/README.md) | **Quality-First Early-Bypass Routing** | **$-43.29\%$ LBPH calls**, **$-55.8\%$ dual inferences**, **$-18.27\%$ cascade latency** ($11.96\text{ ms} \to 9.77\text{ ms}$), **100% bit-for-bit decision equivalence** ($0/2296$ mismatches) | Ready for Promotion | [`README.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/README.md), [`summary.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/summary.json), [`per_condition_results.csv`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/architecture/per_condition_results.csv) |
| [`lbph_config/`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/README.md) | **Multi-Scale `r3_n8_g6x6` LBPH Descriptor** | **$+11.07\text{ pp}$ LSDB CV Rank-1**, **$+4.05\text{ pp}$ LFW Rank-1**, **$-43.75\%$ memory** ($64\text{ KB} \to 36\text{ KB}$), **$-42\%$ scoring latency** | Ready for Calibration | [`README.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/README.md), [`FINDINGS.md`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/FINDINGS.md), [`summary.json`](file:///C:/Users/acer/Documents/USLS%204th%20Year/Computer%20Vision/docs/experiments/major/lbph_config/summary.json) |

---

## 1. Quality-First Early-Bypass Routing (`architecture/`)

- **Hypothesis**: The current sequential cascade runs LBPH before checking image quality. When severe image degradation (heavy blur, extreme darkness, high sensor noise, large off-angle pose, tiny face crop) is present, the quality flag triggers SFace escalation regardless of LBPH distance. Since quality checks are independent of LBPH, evaluating quality first allows poor-quality probes to bypass LBPH entirely.
- **Empirical Confirmation (Full 2,296 Conditions)**:
  - **Decision Equivalence**: **0 / 2,296 mismatches** (100% exact parity with sequential cascade).
  - **Workload Reduction**: **994 LBPH calls eliminated** ($43.29\%$ of all inputs).
  - **Dual Inference Rate**: Cut from **$77.61\% \to 34.32\%$**.
  - **Mean Recognition Latency**: Reduced from **$11.955\text{ ms} \to 9.771\text{ ms}$** (**$18.27\%$ saving**).
  - **Median ($p50$) Latency**: Reduced from **$13.113\text{ ms} \to 9.041\text{ ms}$** (**$31.05\%$ saving**).

---

## 2. Multi-Scale `r3_n8_g6x6` Descriptor (`lbph_config/`)

- **Hypothesis**: The default OpenCV LBPH configuration (`r1_n8_g8x8`, Radius 1, 8 Neighbors, $8\times 8$ Grid) uses a very small 1-pixel sampling radius that is highly sensitive to noise and high-frequency distortion, while its $8\times 8$ grid produces large $64\text{ KiB}$ histograms. Exploring larger radii ($r \in \{1, 2, 3\}$) and coarser grids ($g \in \{4, 6, 8, 10\}$) can improve spatial tolerance and efficiency.
- **Empirical Confirmation (12 Configurations)**:
  - **Challenger Selected**: **`r3_n8_g6x6`** (Radius 3, 8 Neighbors, $6\times 6$ Grid).
  - **Accuracy Gains**: Mean Rank-1 increased by **$+11.07\text{ pp}$** on LSDB development folds and **$+4.05\text{ pp}$** on locked LFW test images ($p = 1.08\times 10^{-9}$).
  - **Efficiency Gains**: Memory reduced by **$-43.75\%$** ($64\text{ KiB} \to 36\text{ KiB}$ per enrolled face), scoring time reduced by **$-41.93\%$** ($36.32\text{ ms} \to 21.09\text{ ms}$).

---

## Promotion Protocol

Before promoting an experiment from this directory to canonical results (`docs/results/`) or runtime deployment (`src/hybrid/thresholds.json`):
1. **Safety**: Verify no breaking changes to downstream APIs or uncalibrated threshold reuse.
2. **Provenance**: Ensure full dataset manifests, git commit hashes, model SHA-256 hashes, and per-condition CSV records are committed.
3. **Approval**: Obtain project owner / advisor approval before updating manuscript prose (`docs/PAPER.md`) or live threshold configuration files.
