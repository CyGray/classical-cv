# Hybrid (band-conditioned) SFace threshold — diagnostic, not adoption-grade

*2026-08-02. Answers `docs/NOTES.md` item 4, contingent on the provisional
`tau_reject` from [`docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md`](../tau_reject/THRESHOLD_ANALYSIS.md)
(agreed: heavy-tier p99 ≈ 140.13 — **not promoted to canon**, per the user).*

## Answer to "can we now get the hybrid SFace threshold?"

**Partially, and the honest limits matter more than the point estimate.**
Yes for a genuine-side, exploratory characterization; the resulting number
is **diagnostic, not threshold-grade** — it is not comparable in confidence
to the 16.5M-pair standalone SFace sweep, for two compounding reasons stated
up front, not buried:

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

Barely.

| L2 threshold | Genuine in-band SFace-accepts (cosine AND L2) |
|---:|---:|
| 1.0313 (currently deployed) | 56,430 / 69,169 = **81.58%** |
| 1.0417 (this sample's zero-observed-FA ceiling) | 57,068 / 69,169 = **82.51%** |
| 1.05 | 57,586 / 69,169 = 83.25% |
| 1.10 | 59,923 / 69,169 = 86.63% |

Moving L2_genuine from 1.0313 to the tightest value this sample can still
defend (1.0417, zero observed false accepts among 68 cosine-passing
impostors) buys under **one percentage point** of genuine accept-rate gain.

**The finding: `cosine_genuine = 0.363` is the dominant constraint on this
population, not L2.** 12.31% of genuine in-band pairs fail cosine alone,
before L2 is even evaluated — re-deriving L2 cannot recover those. Pushing L2
further (1.05, 1.10) buys more genuine accepts, but at those levels the
sample can no longer certify zero false accepts (the impostor floor here is
1.0417 among 68 dual-hard-passing impostors out of ~70,000 — a number this
small does not license moving much past it with confidence). `cosine_genuine`
is documented elsewhere as "a fixed policy gate, never FAR-fit" — not
something this analysis proposes changing, but it's the actual lever, and
that's worth stating rather than quietly re-deriving L2 as if it were.

## Suggestion

**Diagnostic only, not for adoption:** if this analysis's ~69k-sample ceiling
is judged acceptable for a working value, `L2_genuine ≈ 1.04` (just under the
observed 1.0417 floor, for margin) is the honest ceiling this data supports —
a marginal move from the deployed 1.0313, gaining under 1 percentage point of
genuine escalation-band accept rate. **Not recommended for promotion to
canon** for the same two reasons stated at the top (sample size, protocol
mismatch) plus a third: it's contingent on a `tau_reject` the user has
explicitly not canonized yet.

**What would make this threshold-grade:** a real joint independence run at
LFW1 identification scale (1-to-N argmin escalation, not 1:1 pairwise) —
`src/hybrid/independence_test.py`, box-cropped (not its current full-frame
default — see `docs/audits/STATE-08-02.md`), scored against the working
`tau_accept`/`tau_reject`, with both engines' distances recorded per probe.
That would fix both caveats at once: real escalation semantics, and enough
pairs (up to 16.5M, matching the standalone sweeps) to resolve a genuine
10-ppm-grade impostor floor. Not run here — flagged as the next step if this
threshold is to be taken further.

## What was NOT changed

Per explicit scope: `src/sface/recognizer.py`'s `L2_GENUINE_THRESHOLD` and
`thresholds.json`'s `sface.l2_genuine`/`cosine_genuine` are **untouched**.
`thresholds.json` gained a diagnostic-only informational block
(`_hybrid_sface_band_diagnostic`) pointing here — not a config value, not
read by any runtime path.

## Cross-references

- `docs/NOTES.md` item 4 — the task this doc answers.
- `docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md` — the `tau_reject`
  candidates this analysis is contingent on.
- `docs/independence/MASTER_FILE.md` row 5 — the existing joint-vs-standalone
  SFace `l2_genuine` split (1.0313 vs 1.0306278467178345), unaffected by
  this analysis.
- `reports/independence/hybrid_sface_band/band_conditioned.json` — raw
  output of `scripts/pipeline/derive_hybrid_sface_threshold.py`, all three
  `tau_reject` candidates, full percentile detail.
