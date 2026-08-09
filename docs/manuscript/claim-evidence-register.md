# Claim–Evidence Register: *Database Augmentation and Independence Test for Facial Recognition*

This register is the provenance companion for the Springer manuscript. Values are included only where their metric, population, operating point, and source are identified.

| Claim | Evidence | Status |
|---|---|---|
| The current LBPH acceptance threshold is 67.03325520645528 on the native `predict_collect()` scale. | `classical-cv/src/hybrid/thresholds.json`; `docs/results/independence_test/independence/lbph_lfw1/native_predict_scale_yunet.json` | Supported |
| That LBPH threshold is the 165th of 16,522,626 unique LFW impostor pairs, with a realized FAR of 9.986 ppm. | `native_predict_scale_yunet.json` | Supported |
| The standalone SFace boundary is L2 = 1.0306278467178345 at the same rank and realized FAR. | `docs/results/independence_test/independence/sface_lfw1/standalone_l2_yunet.json` | Supported |
| The deployed cascade uses `tau_accept = 67.03325520645528`, `tau_reject = 140.13`, and relative margin `0.05`. | `classical-cv/src/hybrid/thresholds.json`; `classical-cv/src/hybrid/gate.py`; `docs/results/independence_test/MASTER_FILE.md` | Supported |
| `tau_reject = 140.13` is a permissive escalation/FRR trade-off decision, not an impostor-tail FAR threshold. | `thresholds.json` provenance; `docs/results/independence_test/MASTER_FILE.md` | Supported |
| The classical candidate-selection rule is pre-committed: require TAR >= 90% at the La Salle independence operating point, a feature vector < 1 KB, and live FPS >= 3; rank eligible candidates by 41-modification AR, then TAR and model size for ties within 2 points. | `classical-cv/src/benchmark/compare_classical.py` (`SELECTION_RULE`, `apply_selection_rule`) | Supported |
| The dl41 robustness fixture has 87 clean held-out probes and 41 variants per probe, with strict no-face handling. | `docs/results/robustness_test/benchmark/accuracy_ratio_hybrid.md` | Supported |
| Archived dl41 aggregate results were produced under the previous LBPH threshold of 67.0084. | `docs/results/robustness_test/benchmark/accuracy_ratio_hybrid.md` | Supported, historical configuration |

## Publication guardrails

- Before any manuscript claim or figure insertion, check the artifact's record
  in `docs/results/RESULTS_MANIFEST.json` and the status definitions in
  `docs/results/metadata/PROVENANCE_AUDIT.md`.
- Do not present the archived aggregate LBPH/cascade rates as results of the current deployed threshold without a rerun.
- Never use an `illustrative_stand_in`, `needs_provenance_review`,
  `historical_rerun_required`, or `rerun_required` artifact as current
  scientific evidence.
- Label Rank-1, TPIR/AR, GAR, FAR, and EER with their protocol and operating point; these quantities are not interchangeable.
- Do not use the rejected full-frame LBPH value 77.769348.
- Robustness tables are distinct from complementarity evidence and belong only
  to `docs/results/robustness_test/`.
- Use native Word tables. Do not auto-trace a raster figure; regenerate from a
  recorded, permitted result as SVG/PDF (or EMF on Windows) before camera-ready
  placement.
- Abstract and Introduction are intentionally excluded from this register because they are reserved for Doc Oh.
