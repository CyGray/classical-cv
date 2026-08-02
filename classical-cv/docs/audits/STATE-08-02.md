# STATE-08-02 — LBPH `tau_accept` unified (standalone == hybrid), joint-hybrid candidate rejected

*Effective 2026-08-02. Follows `STATE-08-01.md`.*

## What changed

`gate.tau_accept` moved **67.0084 → 67.03325520645528**. `cv_only`'s
standalone threshold and the cascade's outright-accept threshold are now the
same number, sourced from the same artifact.

## Why

`docs/NOTES.md` item 2 asked whether the LBPH-standalone threshold should
equal the LBPH-hybrid one, or whether a separate figure was warranted. Two
candidates existed for "the hybrid one":

1. The previously-deployed **67.0084** — itself provenance-broken: its own
   `provenance.gate.tau_accept` string in `thresholds.json` claimed "LFW1
   YuNet joint hybrid run," but 67.0084 does not match the actual joint-run
   output (77.769348, `FROZEN_THRESHOLDS_HYBRID.md`). It instead matched (to
   ~0.025) an older **Haar**-detector standalone sweep whose artifact
   (`native_predict_scale.json`, no `_yunet` suffix) no longer exists in the
   repo — reproducible-but-mislabeled, or unreproducible-but-close, depending
   on how charitably you read it.
2. The joint-hybrid candidate **77.769348** (`FROZEN_THRESHOLDS_HYBRID.md`,
   generated 2026-07-28, explicitly marked "candidate, not adopted").

## Structural argument for unification

`cv_only`'s accept rule and the cascade's outright-accept rule are the
identical test: `lbph_distance <= gate.tau_accept`. SFace never runs before
this gate is evaluated either way — it's a single-engine LBPH-marginal-
distribution question in both modes, not something the joint pipeline has
any special claim to recalibrate. There is no cascade-specific information
that should make `cv_only`'s LBPH threshold and the cascade's LBPH
outright-accept threshold different numbers.

**Objection checked and ruled out:** could a whole-system FAR budget require
`tau_accept` to be tighter than a plain 10 ppm rank, to leave headroom for
false accepts that leak through the escalated `[tau_accept, tau_reject]` band
(where SFace also sometimes falsely accepts)? `docs/PAPER.md`'s LS-DB1 result
answers this: the cascade's own combined rate (98 ppm) already **undercuts**
either engine run alone (LBPH-only 867 ppm, SFace-only 190 ppm), despite the
engines' false accepts being positively correlated. The project's design
assumption is per-engine FAR targets with the cascade net-improving for free,
not a budget split requiring one branch to be tightened below its own target.
No rank-tightening applies to `tau_accept`.

## Why 77.769348 was rejected, not just left uninvestigated

`FROZEN_THRESHOLDS_HYBRID.md`'s original explanation for the 77.77 vs 67.01
gap was **detector mismatch** (the frozen 67.0084 baseline used Haar, the
joint run used YuNet). This session isolated detector as a single variable by
re-running the standalone box-cropped LBPH script
(`scripts/archive/run_lfw_lbph_native_predict_independence.py`) with YuNet
instead of Haar — same detector as the joint run, same dataset, same seed,
box-cropped instead of full-frame. Result: **67.03325520645528**
(`reports/independence/lbph_lfw1/native_predict_scale_yunet.json`, rank-165
unidirectional unique pair, N=5,749, zero YuNet skips, 9.986 ppm FAR) —
landing right next to the old Haar-standalone 67.0084, nowhere near 77.77.
Swapping the detector alone does not reproduce the gap.

What *does* differ between the two `tau_accept`-producing runs is crop mode:
`src/hybrid/independence_test.py` feeds LBPH the **whole frame**
(`normalize_face(gray, ...)`, line ~302), while both the standalone scripts
and actual deployment (`LBPHAdapter._normalize`,
`src/hybrid/recognizer.py:190`, uses `sample.face_gray`) feed it the
**detected face box**. A direct crop-mode A/B on the same detector, same
dataset (documented pre-existing in `cv-workspace-map` §3.2, re-confirmed
here): cropped 67.03 vs full-frame 74.64 — accounting for most of this run's
77.77 gap, plausibly with the small remainder from sampling/rank differences.

**Conclusion: 77.769348 measures a box-crop harness bug in
`independence_test.py`, not a legitimate YuNet-driven recalibration.**
Rejected, not adopted.

## What did NOT change

- **SFace `l2_genuine`** — still split into joint-hybrid (1.0313, deployed)
  and standalone (1.0306278467178345, not adopted) families. Unlike LBPH,
  this split has not been investigated or resolved this session — see
  `docs/independence/MASTER_FILE.md` row 5, `docs/NOTES.md` item 4.
- **`tau_reject`** (88.4927) — unchanged, but now **suspect** for the same
  box-crop-vs-full-frame reason `tau_accept`'s joint candidate was rejected,
  since it comes from the identical `independence_test.py` run. Not
  re-derived this session. See `docs/NOTES.md` item 3 for the scoping of
  what a re-derivation needs (likely not a plain impostor-tail rank — see
  that item for why).

## Where these values live (kept in sync this session)

- `classical-cv/src/hybrid/thresholds.json` — `gate.tau_accept`,
  `lbph_far_anchors[1]`, `provenance.gate.tau_accept`.
- `classical-cv/src/hybrid/gate.py` — `_FALLBACK_GATE_DEFAULTS["tau_accept"]`.
- `classical-cv/src/hybrid/calibrate.py` — `LBPH_TAU_ACCEPT`,
  `LBPH_TAU_ACCEPT_PROVENANCE`.
- `classical-cv/src/hybrid/recognizer.py` — a stale inline comment citing the
  old value.
- `classical-cv/docs/READ THIS/FROZEN_THRESHOLDS.md`,
  `FROZEN_THRESHOLDS_HYBRID.md` — corrected in place (detector explanation
  struck through, correction appended, not silently rewritten).
- `AGENTS.md` (root), `classical-cv/AGENTS.md` — canonical-value callouts and
  provenance tables updated.
- `classical-cv/docs/reports/ROBUSTNESS_TEST_OVERVIEW.md`,
  `classical-cv/data/README.md` — value references updated.
- `docs/NOTES.md` items 2 (closed) and 3 (rescoped).
- `docs/independence/MASTER_FILE.md` rows 1, 3, 4 and cross-reference.
- `.claude/skills/cv-workspace-map`, `classical-cv/.claude/skills/cv-repo-map`,
  `.claude/skills/robustness-protocol-map` — navigation docs updated.
- Auto-memory (`frozen-thresholds-stay-frozen.md`) updated.

**Not touched, deliberately** (run records — rewriting them would fabricate
history of what those runs actually executed at): `docs/audits/STATE-07-28.md`,
`docs/audits/STATE-08-01.md`, `docs/experiments/**`,
`classical-cv/reports/**`, `classical-cv/outputs/**`, worktree checkouts
under `classical-cv/.claude/worktrees/`, and the `.gemini/skills` /
`GEMINI.md` mirrors (untracked, out of scope this pass).
