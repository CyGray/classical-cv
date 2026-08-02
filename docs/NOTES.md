# Project Notes & Open Decisions

**Last Updated:** 2026-08-01

1. Confirm the threshold for SFace-standalone -- where did we get this? Can we get the same result? What configs were used?
2. Is the LBPH-standalone threshold the same for the LBPH-hybrid?
3. Create and run the test to determine the `tau_reject` for the hybrid
4. With items 1~3 finished, determine the optimal hybrid SFace threshold
5. With item 4 finished, run the robustness test (hybrid)

Current state: 
The robustness test (standalone only) is NOT presentible to the adviser as of yet of yet

## Open Decisions for Tomorrow (2026-08-02)

### 1. Dual Reporting of Standalone LBPH Metrics in Final Thesis / Report
- **Issue:** Standalone LBPH exhibits **1.74% AR** under strict 1-to-N open-set gate threshold (`tau_accept = 67.0084`, $\sim 10\text{ ppm}$ FAR) vs. **65–75% Accuracy** on standard LFW 1:1 pairwise verification.
- **Option A (Cascade Focus Only):** Report only 1-to-N open-set identification numbers (1.74% AR clean, 0.91% DL41) to justify SFace cascade escalation.
- **Option B (Dual Baseline Reporting - Recommended):** 
  - Report 1:1 Pairwise Verification (65–75% Accuracy / EER) to benchmark against published classical baselines (Ahonen et al., 2006).
  - Report 1-to-N Open-Set Identification (1.74% AR @ 67.0084) to show operational gate performance under 10 ppm FAR constraints.
- **Reference Doc:** [`docs/experiments/IDENTIFICATION_VS_VERIFICATION.md`](file:///C:/Users/acer/Downloads/USLS%204th%20Year/Computer%20Vision/docs/experiments/IDENTIFICATION_VS_VERIFICATION.md)

### 2. Standalone LBPH Threshold Preservation
- **Status:** `tau_accept = 67.0084` remains frozen for standalone LBPH tests.
- **Note:** Do not alter or relax `67.0084` to `76.7922` in `thresholds.json` or standalone scripts, as `67.0084` is calibrated for native `predict_collect` scale on DB1 frontal-crop tolerances.
 of yet