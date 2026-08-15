# LBPH `tau_accept`: TAR@FAR operating-point rerun

**Date:** 2026-08-11  
**Status:** Raw, provenance-tracked decision experiment. Not canonical manuscript evidence; no runtime threshold was changed.  
**Question:** Can the LBPH fast-accept edge move from its frozen 10 ppm point to 0.1% FAR to improve hybrid speed while preserving a defensible error rate?

## Decision

No. Keep the frozen LBPH accept edge, `tau_accept = 67.03325520645528`, as the primary robustness operating point. Its rerun-confirmed strict all-41 TAR is **1.4257%** (reported as **1.43%**, consistent with the canonical ~1.41%).

`tau_accept = 71.1717504321251` at 0.1% pairwise FMR is valuable only as a **predeclared standalone sensitivity point**. It raises strict all-41 TAR to **4.3264%**, but did not produce a meaningful hybrid speed benefit: in a matched 1:N smoke test it added two direct accepts out of 7,052 modified probes, one correct and one wrong.

The selection objective must therefore be **correct direct accepts under a system-level false-identification constraint**, not standalone LBPH TAR alone.

## Protocol

### Data and distance scale

- Dataset: original-unfunneled LFW, downloaded from the repository-pinned Figshare archive; archive SHA-256 `055f7d9c632d7370e6fb4afc7468d40f970c34a80d4c6f50ffec63f5a8d536c0`.
- Extraction check: 5,749 identity folders and 13,233 images.
- Detector/crop pipeline: YuNet; native OpenCV `cv.face.LBPHFaceRecognizer.predict_collect()` scale, radius 1, neighbours 8, grid 8×8.
- Impostor calibration: all **16,522,626** unique cross-identity clean pairs. This yields pairwise FMR/FAR thresholds.
- Genuine evaluation: fixed identity-disjoint manifest, seed 42, 5,749 gallery identities and 1,680 probes; manifest triple-list SHA-256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`.
- Perturbations: all 41 `dl41` modifications; strict no-face policy.

`TAR (scorable)` excludes no-face rows. `Strict TAR` uses every genuine probe as its denominator, including no-face failures. The latter is the relevant system result: 67,177 of 68,880 modified probes were scoreable and 1,703 were no-face failures.

### Matched hybrid check

To test whether a higher threshold actually creates a useful fast path, two runs held every other condition constant:

- Stable first-575-identity prefix of the fixed manifest; 172 probes × 41 modifications = 7,052 modified probes.
- `cv_only`, `dl_only`, and deployed cascade logic; all 41 modifications; YuNet boxes; strict no-face policy.
- Only `gate.tau_accept` changed: frozen 10 ppm threshold vs. non-deployed 0.1% candidate threshold.

This is a smoke test for gate events and identification behaviour, not final robustness evidence. The harness reused cached engine scores, so its latency fields are invalid and are not used below.

## Pairwise LBPH TAR@FAR curve

| Pairwise FMR target | Realized FMR | Native `tau_accept` | Clean TAR | Strict TAR, all 41 mods |
|---|---:|---:|---:|---:|
| Frozen point | 9.986 ppm | 67.0333 | 2.2619% | **1.4257%** |
| Sensitivity | 99.984 ppm | 68.8808 | 3.8690% | 2.3592% |
| Sensitivity | 0.1000% | 71.1718 | 7.0833% | **4.3264%** |
| Sensitivity | 1.0000% | 74.3496 | 14.1071% | 9.2349% |
| Sensitivity | 5.0000% | 77.5943 | 23.9881% | 17.2648% |
| Sensitivity | 10.0000% | 79.5150 | 31.2500% | 23.3028% |

The curve confirms a real standalone trade-off: 0.1% FMR increases strict LBPH TAR by 2.9007 points (about 3.0×) relative to 10 ppm. It does **not** prove the candidate is safe or useful as a 1:N cascade fast-accept edge.

## Hybrid finding: 0.1% is not a useful fast-accept point

| `tau_accept` | Cascade all-41 AR | Cascade all-41 Rank-1 | Escalated probes | Direct non-no-face accepts | Correct / wrong direct accepts |
|---:|---:|---:|---:|---:|---:|
| 67.0333 (10 ppm) | 81.9767% | 88.6557% | 6,860 / 7,052 (97.2774%) | 0 | 0 / 0 |
| 71.1718 (0.1%) | 81.9626% | 88.6415% | 6,858 / 7,052 (97.2490%) | 2 (0.0284%) | 1 / 1 |

Both new direct accepts occurred under `gaussnoise_12`. One was correct. The other was wrong at LBPH Rank-1 while SFace was correct, so the looser LBPH gate bypassed a correct SFace rescue. The candidate therefore reduced cascade AR by 0.0142 points and created a directly observed wrong fast identity for negligible avoided SFace work.

The core reason is visible in the event totals: the existing quality gate escalates 97.28% of these modified probes before distance thresholding can provide a fast accept. Moving `tau_accept` alone cannot materially change the speed–accuracy curve under this gate.

## Method for selecting the eventual hybrid operating point

The next study should optimize the deployed system, not the LBPH verifier in isolation.

1. Freeze the system definition: gallery size, detector/crop path, quality flags, margin rule, `tau_reject`, and cache-off latency measurement.
2. Split **identities** into calibration and locked evaluation folds. Use separate un-enrolled identities as negative probes for open-set system FPIR; use separate images of enrolled identities for genuine TPIR/TAR.
3. Use the native all-pairs sweep only to screen candidate `tau_accept` values (10 ppm, 100 ppm, 0.1%, 1%, …). Replay the full deployed gate for each candidate on the calibration fold.
4. Measure, at each candidate:
   - correct direct accepts / all genuine probes;
   - wrong direct accepts / all genuine probes;
   - fast-path FPIR on un-enrolled probes, with a one-sided confidence bound;
   - full cascade TPIR/AR and escalation rate;
   - cache-off mean and tail latency.
5. Select the lowest-cost candidate whose upper confidence bound meets a predeclared **system FPIR** budget, whose total cascade TPIR is non-inferior to the frozen gate, and whose correct-direct-accept gain meets the predeclared latency-saving target. Then lock it before the final 41-modification robustness run.

The expected serial cost is approximately `T_LBPH + P(escalate) × T_SFace` (plus shared detection/preprocessing). Thus the relevant speed measure is the safe reduction in escalation, not the standalone TAR increase.

Pairwise FMR is not system FPIR: a 1:N probe has many chances to form a wrong identity match. It can screen threshold candidates, but it cannot alone authorize a fast accept.

## What to carry into robustness

- **Primary, reported point:** `TAR@9.986 ppm` / `tau_accept = 67.0333`; strict all-41 TAR = **1.43%**.
- **Optional sensitivity analysis:** `TAR@0.1%` / `tau = 71.1718`; strict all-41 TAR = **4.33%**, clearly labelled *standalone pairwise sensitivity, non-deployed*.
- **Do not** describe the 0.1% point as the hybrid's operating point or use it to update `src/hybrid/thresholds.json`.

## Reproducibility and raw artifacts

Raw outputs and exact commands/hashes are in:

- `classical-cv/outputs/provenance_reruns/tar_far_operating_point_2026-08-11/run_provenance.json`
- `classical-cv/outputs/provenance_reruns/tar_far_operating_point_2026-08-11/tar_far_decision.json`
- `classical-cv/outputs/provenance_reruns/tar_far_operating_point_2026-08-11/tar_far_decision.md`
- `classical-cv/outputs/provenance_reruns/tar_far_operating_point_2026-08-11/DECISION_MEMO.md`

The helper `classical-cv/scripts/far_sweep_tar_report.py` was updated so this report is reproducible against explicit rerun paths and emits both scorer-conditional TAR and strict system TAR.

No item above has been promoted into `docs/results/` or added to `docs/results/RESULTS_MANIFEST.json`.
