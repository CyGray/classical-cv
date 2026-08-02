# Frozen hybrid thresholds — do not re-tune without updating this file

*Effective 2026-08-02 for `tau_accept` (previously 2026-07-28, previously
2026-07-20 — see `docs/audits/STATE-08-02.md` and `docs/audits/STATE-07-28.md`
for what changed and why).*

**Separate doc, not merged here:** [`FROZEN_THRESHOLDS_HYBRID.md`](FROZEN_THRESHOLDS_HYBRID.md)
has the joint LBPH+SFace+cascade-derived candidate numbers from `src/hybrid/independence_test.py`.
**Its LBPH `tau_accept` candidate (77.769348) was evaluated and rejected 2026-08-02** —
turned out to be a box-crop-vs-full-frame harness bug (`independence_test.py`
feeds LBPH the whole frame; deployment and the standalone sweep below both
feed it the detected face box), not a legitimate alternate calibration. See
"LBPH `tau_accept`" below and `docs/independence/MASTER_FILE.md` for the
full evidence trail. Its `tau_reject` candidate (88.492676) is likewise
superseded — `gate.tau_reject` was canonized 2026-08-02 to a different value
(140.13) via a different method entirely (see "LBPH `tau_reject`" below, new
section). SFace `l2_genuine`'s standalone-vs-joint gap was also resolved
2026-08-02 (immaterial, no config change) — see `docs/independence/MASTER_FILE.md`
row 5. The pre-existing 1.018-vs-1.0313 SFace provenance question below
("SFace `l2_genuine`" section) is a *different*, still-unresolved history
question, not re-investigated this pass.

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

## The three frozen values

| Threshold | Value | Meaning |
|---|---|---|
| LBPH `tau_accept` (gate) | **67.03325520645528** | LBPH raw distance (native `predict_collect()` scale); below this, LBPH accepts on its own without escalating to SFace. Also `cv_only`'s standalone accept rule — same value, see "Standalone == hybrid" below. |
| LBPH `tau_reject` (gate) | **140.13** | LBPH raw distance; at or above this, LBPH rejects outright without ever calling SFace. Canonized 2026-08-02 — see "LBPH `tau_reject`" below. |
| SFace `l2_genuine` | **1.018** (module constant deployed: **1.0313**, see below) | SFace L2 embedding distance; the dual genuine rule is `cosine >= 0.363 AND l2 <= L2_GENUINE_THRESHOLD`. This table's own row disagrees with the deployed constant — a pre-existing, still-unresolved provenance gap, see "SFace `l2_genuine`" below. Not touched by this pass's `tau_reject`/SFace-hybrid work. |

### LBPH `tau_accept` = 67.03325520645528 (was 67.0084)

- Derived from **LFW1** (`data/lfw-dataset`, all 5,749 identities, zero YuNet
  skips), **box-cropped** to the detected face (matches deployment's
  `LBPHAdapter._normalize`, which uses `sample.face_gray`): the 165th-smallest
  unidirectional unique cross-identity impostor pair (upper-triangle, i<j
  only, 16,522,626 unique pairs) — realized FAR = 9.986 ppm — over
  `reports/independence/lbph_lfw1/native_predict_scale_yunet.json`
  (`scripts/archive/run_lfw_lbph_native_predict_independence.py --unique-rank 165`).
- Native `cv.face.LBPHFaceRecognizer::predict_collect()` scale (radius=1,
  neighbors=8, grid=8x8) — **not** the `independence_common.py` chi-square
  reimplementation, which is a different, non-comparable scale (that
  reimplementation gives 16.7521 raw / 42.09 normalized for the same boundary
  pair — do not confuse the two numbers).
- **Standalone == hybrid, by design decision (2026-08-02):** `cv_only`'s
  accept rule and the cascade's outright-accept rule are the identical
  test (`lbph_distance <= gate.tau_accept`; SFace never runs before this
  gate either way), so there is no principled reason for them to carry
  different values. The joint-hybrid-derived candidate (77.769348,
  `FROZEN_THRESHOLDS_HYBRID.md`) was considered and rejected — it measured
  the LBPH-only marginal distribution too, just on a **buggy full-frame
  crop** instead of the box-crop deployment actually uses. Evidence: this
  standalone re-derivation, run on the *same* YuNet detector as the joint
  test but box-cropped, lands at 67.033 — next to the old Haar-standalone
  67.0084, nowhere near 77.77. That falsifies `FROZEN_THRESHOLDS_HYBRID.md`'s
  original "it's the detector, not noise" explanation for the gap; it's the
  crop. Full trail: `docs/independence/MASTER_FILE.md`, `docs/audits/STATE-08-02.md`.
- **Previously:** 67.0084 (2026-07-28, Haar detector, same rank/FAR target,
  artifact no longer in repo — see `docs/independence/MASTER_FILE.md` row 4's
  history). Before that: 70.6089, derived from LS-DB1 (the rank-8 /
  4th-smallest-unique, 756 ordered pairs, cross-identity impostor distance at
  the ~1% FAR operating point, over
  `reports/independence/hybrid/lsdb1_fixed/_raw_runs/run_1/comparisons.csv`).
  Before that: 73.04, carried from `reports/benchmark/tar_at_far.md` / LFW
  impostors, 100 ppm FAR.

### LBPH `tau_reject` = 140.13 (was 88.4927)

- **Canonized 2026-08-02, advisor sign-off.** The old 88.4927 came from the
  same full-frame joint run as the rejected `tau_accept` candidate
  (77.769348) and carried the identical box-crop harness-bug taint.
- **Not re-derived by a plain impostor-tail rank or a plain genuine
  percentile.** Method: an FRR-vs-escalation trade-off curve —
  `docs/independence/TAU_REJECT_METHOD.md`
  (`scripts/pipeline/tau_reject_tradeoff_curve.py`, sweep 70-170). At every
  candidate tested, genuine-probe escalation and impostor-probe escalation
  track almost 1:1 — **no knee, no separation-favorable region exists in
  this range on wild LFW.**
- Given that, 140.13 (heavy-tier p99 genuine LBPH distance,
  `docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md`) is a **deliberate
  permissive engineering choice**, not a derived separation bound — it makes
  the confident-reject branch functionally near-inert on wild LFW, favoring
  SFace escalation. Does not generalize to La Salle DB1. Full trail:
  `docs/independence/MASTER_FILE.md` row 6.

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

- `src/hybrid/thresholds.json` — `gate.tau_accept`, `gate.tau_reject`, `lbph_far_anchors[1]`, `sface.l2_genuine` (the file actually loaded at runtime).
- `src/hybrid/gate.py` — `_FALLBACK_GATE_DEFAULTS["tau_accept"]` / `["tau_reject"]` (last-resort fallback if `thresholds.json` is missing).
- `src/hybrid/calibrate.py` — `LBPH_TAU_ACCEPT`, `LBPH_TAU_REJECT` (regenerates `thresholds.json`; keep the constants in step with the frozen values so a re-run doesn't clobber them). `LBPH_FAR_ANCHOR_1PCT` is deliberately a *separate* constant from `LBPH_TAU_REJECT` as of 2026-08-02 — `lbph_far_anchors[2]` is a FAR-curve point, not the reject bound; don't re-couple them.
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
