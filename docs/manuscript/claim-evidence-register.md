# Claim–Evidence Register: *Database Augmentation and Independence Test for Facial Recognition*

This register is the provenance companion for the Springer manuscript. Values are included only where their metric, population, operating point, and source are identified.

| Claim | Evidence | Status |
|---|---|---|
| The current LBPH acceptance threshold is 67.03325520645528 on the native `predict_collect()` scale. | `classical-cv/src/hybrid/thresholds.json`; `classical-cv/reports/independence/lbph_lfw1/native_predict_scale_yunet.json` | Supported |
| That LBPH threshold is the 165th of 16,522,626 unique LFW impostor pairs, with a realized FAR of 9.986 ppm. | `native_predict_scale_yunet.json` | Supported |
| The standalone SFace boundary is L2 = 1.0306278467178345 at the same rank and realized FAR. | `classical-cv/reports/independence/sface_lfw1/standalone_l2_yunet.json` | Supported |
| The deployed cascade uses `tau_accept = 67.03325520645528`, `tau_reject = 140.13`, and relative margin `0.05`. | `classical-cv/src/hybrid/thresholds.json`; `classical-cv/src/hybrid/gate.py`; `docs/independence/MASTER_FILE.md` | Supported |
| `tau_reject = 140.13` is a permissive escalation/FRR trade-off decision, not an impostor-tail FAR threshold. | `thresholds.json` provenance; `docs/independence/MASTER_FILE.md` | Supported |
| The dl41 robustness fixture has 87 clean held-out probes and 41 variants per probe, with strict no-face handling. | `classical-cv/reports/benchmark/accuracy_ratio_hybrid.md` | Supported |
| Archived dl41 aggregate results were produced under the previous LBPH threshold of 67.0084. | `classical-cv/reports/benchmark/accuracy_ratio_hybrid.md` | Supported, historical configuration |

## Publication guardrails

- Do not present the archived aggregate LBPH/cascade rates as results of the current deployed threshold without a rerun.
- Label Rank-1, TPIR/AR, GAR, FAR, and EER with their protocol and operating point; these quantities are not interchangeable.
- Do not use the rejected full-frame LBPH value 77.769348.
- Abstract and Introduction are intentionally excluded from this register because they are reserved for Doc Oh.
