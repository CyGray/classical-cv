# Result Provenance and Rerun Audit

`RESULTS_MANIFEST.json` is per-artifact metadata. This file defines its status fields.

| Status | Meaning | Citation rule |
|---|---|---|
| `canonical_snapshot` | Version-controlled result with no known invalidation. | Cite with manifest metadata. |
| `canonical_descriptive_only` | Reproducible, reviewed post-hoc or diagnostic artifact whose scope is intentionally descriptive. | Cite only the exact recorded population, protocol, and limitation; do not use for deployment authorization, security/open-set claims, or general performance gains. |
| `historical_rerun_required` | Historical result used in current manuscript. | Do not present as current; rerun/redraw before camera-ready. |
| `rerun_required` | Known invalid method/configuration. | Preserve as audit evidence only; never cite as deployed result. |
| `needs_provenance_review` | Artifact lacks enough per-file method metadata. | Confirm script, dataset, threshold, and commit before citation. |
| `illustrative_stand_in` | Presentation/sample image, not scientific result. | Never cite as a result. |
| `reference_specification` | Test-suite specification, not measured output. | Cite only as modification specification. |

## Known reruns

- `independence_test/independence/hybrid/lfw1*/`: rerun with box-cropped LBPH. Existing full-frame values are invalid for deployed comparison.
- Manuscript rasters (`algo_test/fig1_tar_far_roc.png`, `independence_test/fig2_interidentity_hist.png`, `robustness_test/fig3_ar_by_modification.png`, and `classical-cv/docs/figures/fig_hybrid_speed_accuracy.png`): redraw from fully recorded current runs before camera-ready. They use historical operating points or incomplete run provenance.
- `robustness_test/benchmark/lfw2_cropfix_subset/`: verify arm/configuration provenance before use; rerun only if it cannot be reconstructed.

## Vector manuscript policy

All four images embedded in `docs/manuscript/lsface.docm` are PNG rasters. Do not auto-trace them. Regenerate publication figures from recorded data as SVG/PDF after provenance clears, then insert SVG (or Windows EMF fallback) and validate exported PDF.

`robustness_test/standins/hybrid_robustness_tables.png` and preprocessing step images are explicitly non-result stand-ins/illustrations.
