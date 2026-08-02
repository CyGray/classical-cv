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

---

## Addendum, same day: `tau_reject` canonized, SFace hybrid threshold resolved

*Follows the `tau_accept` unification above. Advisor sign-off obtained before
any config write (per user instruction).*

### What changed

- `gate.tau_reject` moved **88.4927 → 140.13**.
- `sface.l2_genuine` / `L2_GENUINE_THRESHOLD` — **unchanged, 1.0313**, but the
  question of whether it should move is now formally closed rather than open.
- `calibrate.py` gained a new constant, `LBPH_FAR_ANCHOR_1PCT = 88.4927`,
  decoupling `lbph_far_anchors[2]` from `LBPH_TAU_REJECT` (they used to be the
  same constant; keeping them tied would have silently mislabeled 140.13 as a
  1%-FAR point on the next `calibrate.py` re-run — it isn't one).

### Why — `tau_reject`

`docs/NOTES.md` item 3 asked for the right derivation method, not just a
number. The prior working value (140.13, heavy-tier p99 genuine LBPH
distance from `docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md`) had been
picked but the user explicitly withheld canon status pending a check on
whether a better, separation-based method existed. Advisor review proposed
an FRR-vs-escalation trade-off curve instead of either a plain impostor-tail
rank (the old, box-crop-tainted method) or a plain genuine percentile (the
provisional pick's own method): sweep `tau_reject`, at each candidate
compare the fraction of genuine probes permanently hard-rejected against the
fraction of impostors let into the escalation band.

Result (`scripts/pipeline/tau_reject_tradeoff_curve.py`,
`reports/independence/tau_reject_tradeoff/curve.json`, sweep 70-170 step 5):
**no knee.** Genuine-escalated and impostor-escalated rates track almost 1:1
across the entire range (e.g. at 100: 87.73% vs 86.24%). LBPH does not
separate genuine from impostor distances in this band on wild LFW — the same
conclusion `robustness-protocol-map` §4 reached from the EER-crossover
angle, now confirmed across the full range rather than one point.

Since no candidate is separation-defensible over another, 140.13 was adopted
as a **stated engineering choice**, not a derived bound: make the
confident-reject branch permissive (near-inert on LFW) since LBPH cannot
reject correctly here anyway, and the cascade's headline result depends on
SFace getting a chance to see genuine probes. Consequence — the reject
branch resolves almost nothing on wild LFW — is stated explicitly in
`docs/independence/TAU_REJECT_METHOD.md`, not left implicit.

### Why — hybrid SFace threshold

`docs/NOTES.md` item 4 asked whether a hybrid-specific SFace threshold could
now be derived, contingent on `tau_reject`. A first-pass band-conditioned
diagnostic (`docs/experiments/hybrid_sface_threshold/ANALYSIS.md`,
pre-advisor-review version) filtered the pairwise-verification CSV to LBPH's
escalation band and found L2 barely mattered vs. cosine — **this finding was
backwards**, caught on advisor review: since
`l2 = sqrt(2 - 2·cos)` exactly, `l2 <= 1.0313` (deployed) implies
`cosine >= 0.4682`, well past the 0.363 gate, so L2 alone is the active
constraint and cosine is dead code at current settings. Corrected in place
in the analysis doc.

The corrected framing didn't change the ultimate resolution, though: the
"~97-99% of all probes escalate on LFW" side-finding (already present in the
original diagnostic) means the escalation band is not meaningfully different
from the marginal population the standalone/joint sweeps already measure.
Three independent SFace threshold derivations — joint-deployed (1.0313),
standalone (1.0306278467178345), and this diagnostic's own zero-observed-FA
floor (1.0417) — agree within ~1% of each other. **Decision: no config
change.** `docs/independence/MASTER_FILE.md` row 5 closed as immaterial,
scoped explicitly to LFW (does not hold on La Salle DB1, where the
escalation band is a real, much smaller subset per `docs/PAPER.md`).

### Where these values live (kept in sync this addendum)

- `classical-cv/src/hybrid/thresholds.json` — `gate.tau_reject`,
  `provenance.gate.tau_reject`, `_hybrid_sface_band_diagnostic` (corrected
  finding), `_standalone_reference` (SFace note updated to "resolved").
- `classical-cv/src/hybrid/gate.py` — `_FALLBACK_GATE_DEFAULTS["tau_reject"]`
  and its header comment.
- `classical-cv/src/hybrid/calibrate.py` — `LBPH_TAU_REJECT` (now 140.13),
  new `LBPH_FAR_ANCHOR_1PCT` constant, `lbph_far_anchors` construction,
  `provenance["gate.tau_reject"]` / new `provenance["lbph_far_anchors[2]"]`.
- `docs/independence/TAU_REJECT_METHOD.md` — new, the canon method doc.
- `docs/independence/MASTER_FILE.md` — rows 5 (closed) and 6 (new, closed).
- `docs/NOTES.md` — items 3 and 4 closed; free-text "Current state" section
  updated to drop the `[insert value here]` placeholder.
- `docs/experiments/hybrid_sface_threshold/ANALYSIS.md` — cosine/L2 finding
  corrected in place (struck through where the reasoning changed, not
  silently rewritten), new "Resolution" section added.
- Auto-memory (`frozen-thresholds-stay-frozen.md`) — both threshold
  paragraphs updated, description frontmatter updated, `MEMORY.md` index
  line updated.

**Not touched, deliberately:** `docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md`
(the provisional-value exploration that fed into the canon method — left as
the run record it is, not rewritten to claim it was always the final
method). `reports/independence/hybrid_sface_band/band_conditioned.json` (raw
diagnostic output — the JSON data itself was never wrong, only the prose
interpretation of it in `ANALYSIS.md`/`thresholds.json`, which is what got
corrected).
