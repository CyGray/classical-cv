# Classical CV Raw Output Execution History & Archival Stub

**Created & Purged**: 2026-08-02
**Purpose**: Preserves metadata, execution provenance, and structural summaries of historical raw output dumps and multi-run raw CSV/PNG artifacts that were pruned to keep repository storage lean.

---

## 1. Summary of Purged Raw Run Dumps

| Output Directory Path | Date / Execution Range | Engine / Dataset Scope | Content Description & Reason for Cleanup |
|---|---|---|---|
| `outputs/lbph/independence_test_light_front/lasalle_db1_processed_20260517_202034` | 2026-05-17 | Standalone LBPH on La Salle DB1 | Legacy `threshold_sweep.csv` raw dump from early Tan-Triggs/CLAHE experiments. Superseded by LFW1 YuNet sweeps. |
| `outputs/lbph/independence_test_light_front/lasalle_db1_processed_20260517_202459` | 2026-05-17 | Standalone LBPH on La Salle DB1 | Raw `distance_curve_plot.png` & threshold sweep output. Superseded. |
| `outputs/lbph/independence_test_light_front/lasalle_db1_processed_20260719_121754` | 2026-07-19 | Standalone LBPH on La Salle DB1 | Multi-run `_raw_runs` CSV dumps (run_7, run_8). Superseded by unified LFW1 independence testing. |
| `outputs/independence/hybrid/lsdb2_medium_i10/_raw_runs/` | 2026-07-20 | Hybrid Cascade on LS-DB2 Medium (i10) | Intermediate chunk comparison CSVs (`run_1` to `run_4`). Aggregated metrics stored in `reports/independence/hybrid/lsdb2_medium_i10/`. |
| `outputs/independence/lbph/old/` | 2026-07-20 to 2026-07-28 | LBPH Standalone on LS-DB1 / DB2 | Legacy `_raw_runs` and intermediate CSVs. Superseded by YuNet LFW1 box-crop sweeps. |
| `outputs/independence/lbph_lfw1/native_predict_scale_yunet_smoke.json` | 2026-08-01 | LBPH YuNet LFW1 | Diagnostic smoke-run JSON (20 identities). Canonical sweep stored in `docs/results/independence_test/independence/lbph_lfw1/native_predict_scale_yunet.json`. |

---

## 2. Canonical Active Output / Report References

For active runtime thresholds and canonical experiment results, refer to:

- **Deployed threshold source of truth:** `classical-cv/src/hybrid/thresholds.json`
- **Independence master audit:** `docs/results/independence_test/MASTER_FILE.md`
- **2026-08-02 audit trail:** `classical-cv/docs/audits/STATE-08-02.md`
- **Pairwise verification results:** `docs/experiments/pairwise-verification/lfw-results/`
- **Per-artifact status and rerun flag:** `docs/results/RESULTS_MANIFEST.json`
