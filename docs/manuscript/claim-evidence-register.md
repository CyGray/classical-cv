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
| Paper 1's canonical robustness protocol is a one-image-per-identity SAME-SOURCE self-match test: each of 5,749 enrolled/trained LFW source images is reused to generate 41 controlled modified probes, so the experiment measures within-image degradation retention or transform sensitivity. | `docs/results/robustness_test/SELF_MATCH_ROBUSTNESS_PROVENANCE.md`; `docs/results/robustness_test/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md` | Supported, canonical Paper 1 robustness scope |
| Under that same-source protocol, the recorded overall rates are 86.66% for LBPH, 98.22% for SFace, and 94.69% for the cascade. The run used fallback no-face handling, LBPH-only boundary 76.85, cascade boundaries 67.0084/76.85, and the SFace rule cosine >= 0.363 and L2 <= 1.018. | `docs/results/robustness_test/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md`; `docs/results/robustness_test/SELF_MATCH_ROBUSTNESS_PROVENANCE.md`; `classical-cv/docs/audits/STATE-08-01.md` | Supported, recorded historical configuration; not current deployed thresholds |
| The Paper 1 robustness result supports only same-source transform sensitivity; it is not different-photo identification, pairwise verification, FAR measured by the same experiment, open-set/deployment validation, or evidence that one-image training is generally optimal. | `docs/results/robustness_test/SELF_MATCH_ROBUSTNESS_PROVENANCE.md` | Supported limitation |
| The separate LFW image-disjoint identification result (1.41% LBPH, 80.65% SFace, 80.65% cascade) remains retained with its existing repository provenance but is excluded from Paper 1's selected robustness evidence. | `docs/results/robustness_test/ROBUSTNESS_RESULT_PROVENANCE.md`; `docs/results/robustness_test/SELF_MATCH_ROBUSTNESS_PROVENANCE.md` | Supported, retained outside Paper 1 scope |
| On 2,296 DL41-transformed probes from the 56-image held-out LSDB split, SFace recovered 1,296 of 1,589 thresholded LBPH errors (81.56%, Wilson 95% CI 79.58–83.39%). | `docs/results/complementarity_test/reruns/lsdb_dl41_2026-08-10/complementarity_probes.csv`; `README.md`; `run_provenance.json` | Supported, LSDB transform-sensitivity scope |
| The paired LSDB-DL41 thresholded outcomes have zero LBPH-only successes and 1,296 SFace-only successes; exact two-sided McNemar p < 10^-300. | `docs/results/complementarity_test/reruns/lsdb_dl41_2026-08-10/complementarity_probes.csv`; `README.md` | Supported, LSDB transform-sensitivity scope |
| Gate signals discriminate threshold-free LBPH Rank-1 errors on 2,060 scored LSDB-DL41 probes with distance AUC 0.95019 and negative-margin AUC 0.95319. | `docs/results/complementarity_test/reruns/lsdb_dl41_2026-08-10/gate_operating_curve_probes.csv`; `gate_competence.svg`; `run_provenance.json` | Supported, gate competence only |
| On the LSDB-DL41 timing protocol, the deployed cascade and SFace both achieved 87.24% thresholded correct-identity acceptance; cascade took 11.96 ms/probe versus SFace 8.33 ms and LBPH 5.25 ms. | `docs/results/complementarity_test/reruns/lsdb_dl41_2026-08-10/gate_operating_curve.json`; `README.md`; `run_provenance.json` | Supported, recognition-stage single-pass timing; no speed-gain claim |
| In a post-hoc replay on the same 2,296 LSDB-DL41 transformed probes, preventing quality flags from overriding an LBPH decision inside `tau_accept` while retaining the deployed `margin < 0.05` trigger preserved 87.24% AR, reduced escalation from 71.52% to 59.23%, reduced escalation of thresholded LBPH-correct probes from 289/707 to 7/707, and reduced the stored recognition-stage arithmetic mean from 11.96 to 10.81 ms; direct SFace remained faster at 8.33 ms. | `docs/results/complementarity_test/reruns/gate_accept_protection_descriptive_2026-08-13/results.json`; `policy_summary.csv`; `run_provenance.json` | Supported, `canonical_descriptive_only`; same-data post-hoc known-genuine replay, no independent/open-set/runtime/target-device/speed-over-SFace claim |
| A fresh DL-only LSDB selection campaign evaluated SFace, ArcFace, and FaceNet on 224 fit, 56 calibration, and 56 held-out test images; each model used the 15th of 1,512 cross-identity calibration scores as its acceptance edge (realized FAR 0.9921%). | `docs/results/algo_test/lsdb_selection_dl_trio_2026-08-11/README.md`; `summary.json`; `split_manifest.json`; `run_provenance.json` | Supported, DL-only selection; not a deployment-threshold calibration |
| On the 56 held-out LSDB test images, SFace and FaceNet each achieved 100.00% TAR and 100.00% Rank-1; ArcFace achieved 96.43% TAR and 100.00% Rank-1. SFace was selected among learned candidates by the documented feature-size tie-break (512 B versus 2,048 B). | `docs/results/algo_test/lsdb_selection_dl_trio_2026-08-11/summary.json`; `test_decisions_{sface,facenet,arcface}.csv` | Supported, DL-only selection; do not merge with the classical candidate ranking |

## Publication guardrails

- Before any manuscript claim or figure insertion, check the artifact's record
  in `docs/results/RESULTS_MANIFEST.json` and the status definitions in
  `docs/results/metadata/PROVENANCE_AUDIT.md`.
- Do not present the recorded same-source aggregate LBPH/cascade rates as
  current deployed-threshold results without a rerun.
- Never use an `illustrative_stand_in`, `needs_provenance_review`,
  `historical_rerun_required`, or `rerun_required` artifact as current
  scientific evidence.
- A `canonical_descriptive_only` artifact may be reported only with its exact
  population, post-hoc status, and stated exclusions; it cannot authorize a
  runtime policy or support independent, open-set, target-device, or general
  performance claims.
- Label Rank-1, TPIR/AR, GAR, FAR, and EER with their protocol and operating point; these quantities are not interchangeable.
- For Paper 1, cite 86.66%/98.22%/94.69% only as SAME-SOURCE
  transform-sensitivity or degradation-retention rates and include the
  self-match limitation.
- Do not use the Paper 1 same-source robustness experiment as evidence for
  different-photo identification, pairwise verification, FAR, open-set or
  deployment validity, or general optimality of one-image training.
- Keep the separate 1.41%/80.65%/80.65% image-disjoint identification result
  in the repository with its existing provenance; its exclusion is specific
  to Paper 1.
- Do not use the rejected full-frame LBPH value 77.769348.
- Robustness tables are distinct from complementarity evidence and belong only
  to `docs/results/robustness_test/`.
- Use native Word tables. Do not auto-trace a raster figure; regenerate from a
  recorded, permitted result as SVG/PDF (or EMF on Windows) before camera-ready
  placement.
- Abstract and Introduction are intentionally excluded from this register because they are reserved for Doc Oh.
