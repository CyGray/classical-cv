# Changelog - 2026-08-02

## 0169818 — feat: initialize root workspace repository structure
- Files changed: 634
- Scope: .gitignore:1; classical-cv/.gitattributes:1; classical-cv/.gitignore:1; classical-cv/AGENTS.md:1; classical-cv/data:1; classical-cv/docs:66; classical-cv/haar:1; classical-cv/main.py:1; classical-cv/models:10; classical-cv/README.md:1; classical-cv/reports:308; classical-cv/requirements.txt:1; classical-cv/requirements-batch.txt:1; classical-cv/scratch.py:1; classical-cv/scratch_git_log.txt:1; classical-cv/scripts:30; classical-cv/src:60; classical-cv/threshold_lbph.py:1; classical-cv/threshold_sface.py:1; classical-cv/ui:107; deep-learning:16; docs:7; reports:15; scripts:1
- Sample files: .gitignore, classical-cv/.gitattributes, classical-cv/.gitignore, classical-cv/AGENTS.md, classical-cv/data/README.md, classical-cv/docs/audits/2026-07-08_improvement_spec_implementation.md, classical-cv/docs/audits/2026-07-09_dl_track_detection_gap.md, classical-cv/docs/audits/IMPROVEMENT_SPEC.md, classical-cv/docs/audits/RUNS-07-19.md, classical-cv/docs/audits/STATE-07-10.md, classical-cv/docs/audits/STATE-07-21.md, classical-cv/docs/audits/STATE-07-28.md

## f82c730 — docs: add 1:1 pairwise verification robustness guide, markdown report, full bleed tables, and exporter script
- Files changed: 6
- Scope: .gitignore:1; classical-cv/scripts:1; docs:4
- Sample files: .gitignore, classical-cv/scripts/export_verification_png_tables.py, docs/experiments/pairwise-verification/GUIDE.md, docs/experiments/pairwise-verification/per_modification_verification_table.png, docs/experiments/pairwise-verification/README.md, docs/experiments/pairwise-verification/summary_verification_table.png

## cf15362 — feat(hybrid): unify LBPH tau_accept threshold, update FAR sweep harness, and reorganize experiment deliverables
- Files changed: 35
- Scope: classical-cv/data:1; classical-cv/docs:4; classical-cv/reports:3; classical-cv/scripts:6; classical-cv/src:4; docs:17
- Sample files: classical-cv/data/README.md, classical-cv/docs/audits/STATE-08-02.md, classical-cv/docs/READ THIS/FROZEN_THRESHOLDS.md, classical-cv/docs/READ THIS/FROZEN_THRESHOLDS_HYBRID.md, classical-cv/docs/reports/ROBUSTNESS_TEST_OVERVIEW.md, classical-cv/reports/independence/hybrid_sface_band/band_conditioned.json, classical-cv/reports/independence/lbph_lfw1/far_sweep.json, classical-cv/reports/independence/sface_lfw1/standalone_l2_yunet.json, classical-cv/scripts/export_far_sweep_png_table.py, classical-cv/scripts/export_tar_png_tables.py, classical-cv/scripts/export_verification_png_tables.py, classical-cv/scripts/far_sweep_impostor_thresholds.py

## 50a69aa — refactor(cleanup): prune raw outputs and consolidate legacy reports/scripts into classical-cv
- Files changed: 45
- Scope: classical-cv/outputs:1; classical-cv/reports:25; classical-cv/scripts:2; docs:1; reports:15; scripts:1
- Sample files: classical-cv/outputs/HISTORY_STUB.md, classical-cv/reports/independence/lbph/old/lbph_lasalle_fixed/lbph_lasalle_fixed_distance_curve_plot.png, classical-cv/reports/independence/lbph/old/lbph_lasalle_fixed/lbph_lasalle_fixed_distance_curve_plot_tight.png, classical-cv/reports/independence/lbph/old/lbph_lasalle_fixed/lbph_lasalle_fixed_distance_histogram.png, classical-cv/reports/independence/lbph/old/lbph_lasalle_fixed/lbph_lasalle_fixed_distance_histogram_tight.png, classical-cv/reports/independence/lbph/old/lbph_lasalle_fixed/lbph_lasalle_fixed_far_curve.png, classical-cv/reports/independence/lbph/old/lbph_latest/lfw1_distance_curve_plot.png, classical-cv/reports/independence/lbph/old/lbph_latest/lfw1_distance_histogram.png, classical-cv/reports/independence/lbph/old/lbph_latest/lfw2_distance_curve_plot.png, classical-cv/reports/independence/lbph/old/lbph_latest/lfw2_far_curve.png, classical-cv/reports/independence/lbph/old/lbph_latest/lsdb1_distance_curve_plot.png, classical-cv/reports/independence/lbph/old/lbph_latest/lsdb1_distance_histogram.png

## a55f192 — feat(hybrid): canonize tau_reject threshold to 140.13 and update gate calibration
- Files changed: 14
- Scope: classical-cv/AGENTS.md:1; classical-cv/docs:3; classical-cv/src:3; docs:7
- Sample files: classical-cv/AGENTS.md, classical-cv/docs/audits/STATE-08-02.md, classical-cv/docs/READ THIS/FROZEN_THRESHOLDS.md, classical-cv/docs/READ THIS/FROZEN_THRESHOLDS_HYBRID.md, classical-cv/src/hybrid/calibrate.py, classical-cv/src/hybrid/gate.py, classical-cv/src/hybrid/thresholds.json, docs/experiments/standalone_lbph_robustness/THRESHOLD_CHANGE.md, docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md, docs/experiments/thresholds/standalone_lbph_robustness/THRESHOLD_CHANGE.md, docs/experiments/thresholds/tau_reject/THRESHOLD_ANALYSIS.md, docs/independence/MASTER_FILE.md

## 67102ee — feat(pipeline): add multi-shot enrollment support and dataset pipeline scripts
- Files changed: 7
- Scope: classical-cv/scripts:6; classical-cv/src:1
- Sample files: classical-cv/scripts/pipeline/enroll_att_faces.py, classical-cv/scripts/pipeline/enroll_lasalle_db1.py, classical-cv/scripts/pipeline/enroll_lasalle_db1_clean10.py, classical-cv/scripts/pipeline/enroll_lfw_multishot.py, classical-cv/scripts/utils/make_controlled_ident_split.py, classical-cv/scripts/utils/make_lasalle_clean10_split.py, classical-cv/src/benchmark/accuracy_ratio_hybrid.py

## 9ef7ce0 — feat(reporting): add table exporters and reporting scripts for evaluation suites
- Files changed: 7
- Scope: classical-cv/scripts:7
- Sample files: classical-cv/scripts/export_controlled_identification_tables.py, classical-cv/scripts/export_far_sweep_png_table.py, classical-cv/scripts/export_hybrid_identification_summary_table.py, classical-cv/scripts/export_lfw_multishot_tables.py, classical-cv/scripts/export_training_test_table.py, classical-cv/scripts/export_verification_png_tables.py, classical-cv/scripts/far_sweep_tar_report.py

## 6799c3a — docs(experiments): restructure experiment deliverables into robustness_variants
- Files changed: 37
- Scope: docs:37
- Sample files: docs/experiments/hybrid_sface_threshold/ANALYSIS.md, docs/experiments/IDENTIFICATION_VS_VERIFICATION.md, docs/experiments/pairwise-verification/EMAIL.txt, docs/experiments/pairwise-verification/GUIDE.md, docs/experiments/pairwise-verification/lfw-results/AR/per_modification_verification_table.png, docs/experiments/pairwise-verification/lfw-results/AR/summary_verification_table.png, docs/experiments/pairwise-verification/lfw-results/README.md, docs/experiments/pairwise-verification/lfw-results/SWEEP/summary-table.png, docs/experiments/pairwise-verification/lfw-results/TAR/per_modification_tar_table.png, docs/experiments/pairwise-verification/lfw-results/TAR/summary_tar_table.png, docs/experiments/pairwise-verification/TODO.md, docs/experiments/robustness_variants/att-faces-identification/per_modification_identification_table.png

