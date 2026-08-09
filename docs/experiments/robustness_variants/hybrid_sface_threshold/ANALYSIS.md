# Hybrid (band-conditioned) SFace threshold — resolved: no change, band ≈ marginal on LFW

*2026-08-02. Answers `docs/NOTES.md` item 4. Original diagnostic used the
provisional `tau_reject` from
[`docs/experiments/thresholds/tau_reject/THRESHOLD_ANALYSIS.md`](../../thresholds/tau_reject/THRESHOLD_ANALYSIS.md)
(140.13); `tau_reject` has since been canonized (see
[`docs/results/independence_test/TAU_REJECT_METHOD.md`](../../../independence_test/TAU_REJECT_METHOD.md))
but the resolution below does not depend on the exact candidate — see "Unplanned
finding" and "Resolution" sections. **Corrected 2026-08-02, post advisor
review: the original cosine/L2 finding below had the two gates' relationship
backwards — see "Does raising L2_genuine... " section for the fix.***

## Answer to "can we now get the hybrid SFace threshold?"

**Yes — it's the standalone one. No separate hybrid-specific derivation is
needed or defensible on LFW.** The band-conditioned characterization below
was run first and is diagnostic, not threshold-grade on its own — it is not
comparable in confidence to the 16.5M-pair standalone SFace sweep, for two
compounding reasons stated up front, not buried:

1. **Sample size ceiling.** Band-conditioned n is ~69,000-70,000 (out of the
   verification run's 70,560 total rows) — not 16.5M. Finest resolvable FAR
   is order 100 ppm at best, and even that is a single-observation estimate
   (the smallest observed in-band impostor L2), not a rank statistic with a
   defined confidence interval the way the standalone sweep's rank-165 is.
2. **Protocol mismatch.** This data's "impostor in-band" means: this row's
   1:1 designated-impostor pair's LBPH distance falls in
   `[tau_accept, tau_reject)`. Real cascade escalation triggers on
   `argmin_i d(P, G_i)` over the full N-identity gallery (1-to-N) — a
   different event that this 1:1-protocol CSV cannot reproduce
   (`robustness-protocol-map` §0 exists specifically to catch this class of
   mix-up). A probe's true escalation status under deployment may differ
   from this proxy.

Script: `classical-cv/scripts/pipeline/derive_hybrid_sface_threshold.py`
(new, tracked — deliberately not placed under `scripts/archive/`, which is
gitignored repo-wide). Data source: `accuracy_ratio_verification_full_pairs.csv`
(same run used for the `tau_reject` analysis). Validated before use: the
CSV's `sface_*_l2` and `sface_*_cos` columns satisfy `l2 = sqrt(2 - 2·cos)`
exactly across all 141,120 checked values — same vectorized scale
spot-checked against real `cv.FaceRecognizerSF.match()` earlier this session,
so these are trustworthy raw SFace distances, not a new untested codepath.

## Method

For each `tau_reject` candidate, filter to rows where the relevant LBPH
distance (genuine or impostor column) falls in `[tau_accept, tau_reject)`,
then look at that subpopulation's SFace `cosine`/`l2` distribution — the
population SFace actually sees under cascade escalation, as opposed to its
full marginal distribution (what `dl_only`/standalone measures, and what the
existing `l2_genuine` candidates — 1.0313 deployed, 1.0306278467178345
standalone — were both derived from).

Run at three `tau_reject` candidates from the sibling analysis (heavy p95 /
pooled p99 / heavy p99), per the reasoning that everything derived here is
contingent on a still-provisional number — if the SFace picture is stable
across all three, that's informative on its own.

## Results

Band membership barely moves across the three `tau_reject` candidates — see
why below — so results are reported at 140.13 (the agreed candidate) with
the range noted.

| Candidate `tau_reject` | genuine in-band n | impostor in-band n |
|---:|---:|---:|
| 119.05 | 67,740 | 68,689 |
| 134.17 | 68,835 | 69,866 |
| 140.13 | 69,169 | 70,208 |

**Unplanned finding, bigger than the SFace question itself: at
`tau_accept = 67.03325520645528`, essentially the entire wild-LFW population
falls in the escalation band, at every `tau_reject` candidate tested.**
97-99% of genuine and impostor probes exceed `tau_accept` (established in the
`tau_reject` sibling doc), and virtually none exceed even the tightest
`tau_reject` candidate (119.05) either — so ~96-98% of *all* probes,
genuine and impostor alike, land in `[tau_accept, tau_reject)` regardless of
which candidate is picked. On wild LFW, with these thresholds, the cascade's
"cheap LBPH-only fast path" resolves almost nothing on its own — nearly
everything escalates to SFace. This is a different regime from the
`docs/PAPER.md` clean-split numbers (75% kept on the cheap path, La Salle
DB1-calibrated) and worth flagging on its own, separate from the SFace
question below.

### Genuine, in-band (tau_reject = 140.13, n = 69,169)

| Stat | Value |
|---|---:|
| L2 min / p50 / p90 / p95 / p99 / max | 0.34 / 0.85 / 1.22 / 1.35 / 1.44 / 1.58 |
| **Fail `cosine >= 0.363` regardless of L2** | **12.31%** |

### Impostor, in-band (tau_reject = 140.13, n = 70,208)

| Stat | Value |
|---|---:|
| L2 min / p50 / p90 / p95 / p99 / max | 1.04 / 1.35 / 1.44 / 1.46 / 1.50 / 1.61 |
| **Fail `cosine >= 0.363` regardless of L2** | **99.90%** |

Restricting to the 68 impostor-in-band pairs that *pass* `cosine >= 0.363`
(the ones where L2 actually matters, since the accept rule is an AND): same
L2 floor, 1.0417 (`Gus_Van_Sant` vs `John_Henry`, `scale_70` modification) —
the global impostor-in-band L2 minimum already happens to be a cosine-passing
pair, so restricting to the AND-relevant subset didn't change the floor.

### Does raising L2_genuine toward the observed floor (1.0417) actually help?

**Corrected 2026-08-02 — the original version of this section had the
cosine/L2 relationship backwards.** Both distances come from the same
unit-normalized embeddings via the exact identity verified above
(`l2 = sqrt(2 - 2·cos)`, `src/sface/recognizer.py:170`), which means the two
gates in the dual rule are the same quantity read two ways, not two
independent constraints:

- `cosine >= 0.363` ⟺ `l2 <= sqrt(2 - 2·0.363) ≈ 1.1287`
- `l2 <= 1.0313` (deployed) ⟺ `cosine >= 1 - 1.0313²/2 ≈ 0.4682`

Since `1.0313 < 1.1287`, **the L2 gate is strictly tighter and always fires
first — cosine at 0.363 is dead code at the currently deployed L2 value.**
Passing `l2 <= 1.0313` already implies `cosine >= 0.4682`, well clear of
0.363; the cosine test never has anything left to reject. This is directly
confirmable from this sample's own two numbers without new computation: if
cosine bound, `fail(AND)` would equal `fail(cosine only)` = 12.31%. It
doesn't — `fail(AND) = 100 - 81.58 = 18.42%` — a strict superset, which is
exactly what "L2 is the tighter gate" predicts (everything failing cosine
also fails L2, since failing cosine means `l2 > 1.1287 > 1.0313`, but not
vice versa).

| L2 threshold | Genuine in-band SFace-accepts (cosine AND L2) |
|---:|---:|
| 1.0313 (currently deployed) | 56,430 / 69,169 = **81.58%** |
| 1.0417 (this sample's zero-observed-FA ceiling) | 57,068 / 69,169 = **82.51%** |
| 1.05 | 57,586 / 69,169 = 83.25% |
| 1.10 | 59,923 / 69,169 = 86.63% |
| 1.1287 (= cosine 0.363, the point cosine finally starts to bind) | 69,169 - 8,515 = 60,654 / 69,169 = **87.69%** (cosine's own ceiling — the 12.31% cosine-only failures) |

**The finding: L2 is the sole active constraint at current settings, and
there is real headroom (81.58% → 87.69%, ~6pp) before cosine would ever
start to bind.** The <1pp gain from 1.0313→1.0417 reported in the original
version of this doc was correctly computed but wrongly attributed — it's
small because 1.0417 is only a 1% move past 1.0313, not because cosine was
absorbing the rest. `cosine_genuine = 0.363` remains documented elsewhere as
"a fixed policy gate, never FAR-fit" and this analysis does not propose
changing it — but the practical takeaway is the opposite of what was
originally written: L2 is the parameter that matters here, not cosine.

## Resolution: no config change, closes MASTER_FILE row 5

**Corrected framing, 2026-08-02, after advisor review.** The original
"Suggestion" section below proposed re-deriving `L2_genuine` from this
diagnostic. That direction was wrong for a reason independent of the
cosine/L2 correction above: **the escalation band is not a meaningfully
different population from the marginal one on wild LFW.**

`docs/experiments/robustness_variants/hybrid_sface_threshold/ANALYSIS.md`'s own "unplanned
finding" (below) already established that ~97-99% of all LFW probes —
genuine and impostor alike — land in `[tau_accept, tau_reject)` regardless of
which `tau_reject` candidate is used. That means band-conditioning barely
filters anything: **the band-conditioned SFace population *is*, for
practical purposes, the marginal SFace population this run measures.**
Band-conditioning cannot materially shift the impostor tail relative to the
unconditioned sweep, so there is no basis for a hybrid-specific SFace
operating point that differs from the standalone one.

This is corroborated by three independently-derived numbers landing within
~1% of each other:

| Value | Source |
|---|---:|
| 1.0313 | Deployed (joint-hybrid derivation, 2026-08-01) |
| 1.0306278467178345 | Standalone sweep, added 2026-08-02 (16.5M pairs) |
| 1.0417 | This band-conditioned diagnostic's zero-observed-FA floor (~69k pairs) |

Three derivations, three different methods and sample sizes, agreeing to
within 0.0111 absolute (~1%) — stronger evidence for "these are the same
number, noise aside" than a fourth, more expensive joint 1-to-N run would add.

**Decision: no change to `sface.l2_genuine`/`L2_GENUINE_THRESHOLD`.**
`docs/results/independence_test/MASTER_FILE.md` row 5 (joint-vs-standalone SFace split) is
closed as: difference (0.0007, ~0.07%) judged immaterial, band ≈ marginal on
this dataset.

**Scope explicitly to LFW.** This argument depends on the ~97-99%
escalation-band finding, which is itself LFW-specific (wild, uncontrolled
photos push nearly everything past `tau_accept`). On La Salle DB1, where
`docs/PAPER.md` reports ~75% resolved on the cheap LBPH-only path, the
escalation band is a real, much smaller subset of the population — band ≈
marginal does **not** hold there, and this resolution should not be quoted
as if it were dataset-independent.

## Suggestion (superseded — kept for the record)

*Everything below this point is the original, pre-correction suggestion.
Superseded by the "Resolution" section above — kept only so the reasoning
trail isn't silently rewritten.*

~~**Diagnostic only, not for adoption:** if this analysis's ~69k-sample
ceiling is judged acceptable for a working value, `L2_genuine ≈ 1.04` (just
under the observed 1.0417 floor, for margin) is the honest ceiling this data
supports — a marginal move from the deployed 1.0313, gaining under 1
percentage point of genuine escalation-band accept rate. **Not recommended
for promotion to canon** for the same two reasons stated at the top (sample
size, protocol mismatch) plus a third: it's contingent on a `tau_reject` the
user has explicitly not canonized yet.~~

**What would make a hybrid-specific SFace threshold-grade, if the band ≈
marginal argument above is ever judged insufficient:** a real joint
independence run at LFW1 identification scale (1-to-N argmin escalation, not
1:1 pairwise) — `src/hybrid/independence_test.py`, box-cropped (not its
current full-frame default — see `docs/audits/STATE-08-02.md`), scored
against the canon `tau_accept`/`tau_reject`, with both engines' distances
recorded per probe. Not run here — the band≈marginal argument above is judged
sufficient to close this question on LFW without it.

## What was NOT changed

Per explicit scope: `src/sface/recognizer.py`'s `L2_GENUINE_THRESHOLD` and
`thresholds.json`'s `sface.l2_genuine`/`cosine_genuine` are **untouched**.
`thresholds.json` gained a diagnostic-only informational block
(`_hybrid_sface_band_diagnostic`) pointing here — not a config value, not
read by any runtime path.

## Cross-references

- `docs/NOTES.md` item 4 — the task this doc answers.
- `docs/experiments/thresholds/tau_reject/THRESHOLD_ANALYSIS.md` — the `tau_reject`
  candidates this analysis is contingent on.
- `docs/results/independence_test/MASTER_FILE.md` row 5 — the joint-vs-standalone
  SFace `l2_genuine` split (1.0313 vs 1.0306278467178345), **closed by this
  analysis** as immaterial (band ≈ marginal on LFW).
- `reports/independence/hybrid_sface_band/band_conditioned.json` — raw
  output of `scripts/pipeline/derive_hybrid_sface_threshold.py`, all three
  `tau_reject` candidates, full percentile detail.
- [`docs/experiments/hybrid-identification/README.md`](../hybrid-identification/README.md) —
  **confirmed 2026-08-02** by a real 1-to-N identification run (not the 1:1
  proxy this doc relies on): 97.51% mean escalation, corroborating the
  band≈marginal argument above with the actual escalation event.
