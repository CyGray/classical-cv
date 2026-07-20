# Frozen hybrid thresholds — do not re-tune without updating this file

*Effective 2026-07-20.*

The hybrid gate's `tau_accept` (LBPH) and the SFace genuine-match L2 distance
are **frozen**. Do not recalibrate or overwrite them via `src/hybrid/calibrate.py`
(or by hand) without updating this note, `AGENTS.md`, and every location listed
below.

## The two frozen values

| Threshold | Value | Meaning |
|---|---|---|
| LBPH `tau_accept` (gate) | **70.6089** | LBPH raw distance; below this, LBPH accepts on its own without escalating to SFace. |
| SFace `l2_genuine` | **1.106796** | SFace L2 embedding distance; the dual genuine rule is `cosine >= 0.363 AND l2 <= 1.106796`. |

### LBPH `tau_accept` = 70.6089

- Derived from LS-DB1: the rank-8 (4th-smallest-unique, 756 ordered pairs)
  cross-identity impostor distance at the ~1% FAR operating point, over
  `reports/independence/hybrid/lsdb1_fixed/_raw_runs/run_1/comparisons.csv`.
- Matches the canonical `70.6089` LBPH figure already referenced in
  `scripts/build_independence_native_predict.py` (native
  `cv.face.LBPHFaceRecognizer::predict_collect()` scale — not the
  `independence_common.py` chi-square reimplementation, which is a different,
  non-comparable scale).
- Replaces the previous carried value (73.04, from
  `reports/benchmark/tar_at_far.md` / LFW impostors, 100 ppm FAR). `tau_reject`
  (76.85) is **unchanged** — only `tau_accept` was reset.

### SFace `l2_genuine` = 1.106796

- **Hardcoded by explicit instruction, not re-derived from this dataset.**
  Running the same rank rule against LS-DB1's SFace L2 impostor distances
  (`threshold_sface.py` in the repo root) does **not** reproduce this number —
  it lands near **0.84–0.87** for a rank-8-style cutoff. 1.106796 instead sits
  close to the **mean/median** of the full LS-DB1 impostor L2 distribution
  (mean 1.1075, median 1.1050 over the 378 unique cross-identity pairs), i.e.
  it is not a low-FAR tail statistic the way the LBPH value is.
- It is still gated by the existing `cosine >= 0.363` condition
  (`COSINE_GENUINE_THRESHOLD`, unchanged), which the AND rule keeps in force —
  see `src/sface/recognizer.py::is_genuine()`.
- If this value is ever revisited, first fix the rank-rule mismatch between
  `threshold_lbph.py` (uses the 4th-smallest-unique / rank-8-ordered value) and
  `threshold_sface.py` (currently uses the 8th-smallest-unique value) so both
  engines are measured the same way.

## Where these values live (keep in sync)

- `src/hybrid/thresholds.json` — `gate.tau_accept`, `lbph_far_anchors[1]`, `sface.l2_genuine` (the file actually loaded at runtime).
- `src/hybrid/gate.py` — `_FALLBACK_GATE_DEFAULTS["tau_accept"]` (last-resort fallback if `thresholds.json` is missing).
- `src/hybrid/calibrate.py` — `LBPH_TAU_ACCEPT` (regenerates `thresholds.json`; keep the constant in step with the frozen value so a re-run doesn't clobber it).
- `src/sface/recognizer.py` — `L2_GENUINE_THRESHOLD` (the actual runtime enforcement point for the SFace genuine rule).

## Parallel ensemble mode: removed

The `parallel` hybrid mode (run LBPH and SFace on every frame, SFace wins on
accept) has been **completely dropped** from the codebase. `HYBRID_MODES` is
now `("cascade", "cv_only", "dl_only")` everywhere. Affected:

- `src/hybrid/recognizer.py` — `HYBRID_MODES`, the `mode == "parallel"` branch in `HybridRecognizer.predict()`, and the sface-required-mode checks.
- `main.py` — `HYBRID_MODES` and the interactive mode picker.
- `src/benchmark/accuracy_ratio_hybrid.py` — `MODES`, and all `cascade_vs_parallel` comparison logic.
- `scripts/merge_robustness_segments.py` — mirrored `cascade_vs_parallel` merge logic.
- `ui/console/form_fields.py` — the `parallel` option in the hybrid-mode picker.

**Not touched** (left as historical artifacts, by design): old
`reports/benchmark/lfw2_robustness/*` JSON/PNG output that still contains a
`parallel` column, and the report-rendering scripts that read it
(`scripts/generate_benchmark_table_pngs.py`,
`scripts/generate_robustness_report.py`, `src/benchmark/evidence_matrix.py`).
Those describe past runs, not the current system, and were not regenerated.

## The robustness comparison table

`src/benchmark/accuracy_ratio_hybrid.py` builds its LBPH/SFace/hybrid table
generically over whatever `MODES` it's given — dropping `parallel` from
`MODES` was sufficient to make the default `--modes` output exactly the
three-way `cv_only` (LBPH) / `dl_only` (SFace) / `cascade` (hybrid) comparison
table, with no separate table-generation code needed.
