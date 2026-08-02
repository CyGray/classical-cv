# Frozen hybrid thresholds — do not re-tune without updating this file

*Effective 2026-07-28 (previously 2026-07-20 — see `docs/audits/STATE-07-28.md`
for what changed and why).*

**Separate doc, not merged here:** [`FROZEN_THRESHOLDS_HYBRID.md`](FROZEN_THRESHOLDS_HYBRID.md)
has *candidate* thresholds from running LBPH+SFace+cascade jointly (not yet
adopted into `thresholds.json`) — the LBPH values below come from an
LBPH-only sweep (Haar detector), not the deployed joint pipeline (YuNet).

The hybrid gate's `tau_accept` (LBPH) and the SFace genuine-match L2 distance
are **frozen**. Do not recalibrate or overwrite them via `src/hybrid/calibrate.py`
(or by hand) without updating this note, `AGENTS.md`, and every location listed
below.

**Protocol note (2026-07-28):** AGENTS.md's "Frozen thresholds" section states
thresholds are derived once on La Salle DB1 and that LFW is a diagnostic-only
transfer leg, never the derivation basis. `tau_accept` below now breaks that
rule on purpose (re-derived directly on LFW1, on explicit instruction) — see
`docs/audits/STATE-07-28.md` for the full record. AGENTS.md has been updated
to match; if you're reading this expecting LS-DB1-only provenance, don't.

## The two frozen values

| Threshold | Value | Meaning |
|---|---|---|
| LBPH `tau_accept` (gate) | **67.0084** | LBPH raw distance (native `predict_collect()` scale); below this, LBPH accepts on its own without escalating to SFace. |
| SFace `l2_genuine` | **1.018** | SFace L2 embedding distance; the dual genuine rule is `cosine >= 0.363 AND l2 <= 1.018`. |

### LBPH `tau_accept` = 67.0084 (was 70.6089)

- Derived from **LFW1** (`data/lfw-dataset`, 5,703 usable identities after
  Haar misses): the 165th-smallest unidirectional unique cross-identity
  impostor pair (upper-triangle, i<j only, 16,259,253 unique pairs; ordered-space
  rank 330) — realized FAR ≈ 10.15 ppm — over
  `reports/independence/lbph_lfw1/native_predict_scale.json`
  (`scripts/archive/run_lfw_lbph_native_predict_independence.py`).
- Native `cv.face.LBPHFaceRecognizer::predict_collect()` scale (radius=1,
  neighbors=8, grid=8x8) — **not** the `independence_common.py` chi-square
  reimplementation, which is a different, non-comparable scale (that
  reimplementation gives 16.7521 raw / 42.09 normalized for the same boundary
  pair — do not confuse the two numbers).
- **Previously:** 70.6089, derived from LS-DB1 (the rank-8 / 4th-smallest-unique,
  756 ordered pairs, cross-identity impostor distance at the ~1% FAR operating
  point, over `reports/independence/hybrid/lsdb1_fixed/_raw_runs/run_1/comparisons.csv`).
  Before that: 73.04, carried from `reports/benchmark/tar_at_far.md` / LFW
  impostors, 100 ppm FAR. `tau_reject` (76.85) is **unchanged** through all
  three revisions — only `tau_accept` moves.

### SFace `l2_genuine` = 1.018 (was 1.106796)

- **Supplied by the SFace sub-team, 2026-07-28. Not re-derived or verified in
  this repo — trusted as given**, same as the prior value was hardcoded by
  explicit instruction rather than derived here.
- It is still gated by the existing `cosine >= 0.363` condition
  (`COSINE_GENUINE_THRESHOLD`, unchanged), which the AND rule keeps in force —
  see `src/sface/recognizer.py::is_genuine()`.
- **Previously:** 1.106796. Running the LS-DB1 rank rule against
  `threshold_sface.py` does not reproduce either hardcoded value (lands near
  0.84–0.87 for a rank-8-style cutoff); 1.106796 sat close to the LS-DB1
  impostor L2 mean/median (1.1075 / 1.1050) rather than a low-FAR tail
  statistic. Whether 1.018 follows the same rationale or a different one
  wasn't stated when it was supplied — ask the SFace sub-team if the
  provenance matters for the paper.
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
- `scripts/utils/merge_robustness_segments.py` — mirrored `cascade_vs_parallel` merge logic.
- `ui/console/form_fields.py` — the `parallel` option in the hybrid-mode picker.

**Not touched** (left as historical artifacts, by design): old
`reports/benchmark/lfw2_robustness/*` JSON/PNG output that still contains a
`parallel` column, and the report-rendering scripts that read it
(`scripts/reporting/generate_benchmark_table_pngs.py`,
`scripts/reporting/generate_robustness_report.py`, `src/benchmark/evidence_matrix.py`).
Those describe past runs, not the current system, and were not regenerated.

## The robustness comparison table

`src/benchmark/accuracy_ratio_hybrid.py` builds its LBPH/SFace/hybrid table
generically over whatever `MODES` it's given — dropping `parallel` from
`MODES` was sufficient to make the default `--modes` output exactly the
three-way `cv_only` (LBPH) / `dl_only` (SFace) / `cascade` (hybrid) comparison
table, with no separate table-generation code needed.
