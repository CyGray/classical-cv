# `tau_reject` — genuine-distribution analysis and open decision point

*2026-08-02. Follows the LBPH `tau_accept` unification (`docs/results/independence_test/MASTER_FILE.md`,
`classical-cv/docs/audits/STATE-08-02.md`) and `docs/NOTES.md` item 3.*

## Why this doc exists

`tau_reject` is the cascade's confident-*reject* bound: `lbph_distance >=
tau_reject` rejects a probe outright, without ever calling SFace. Unlike
`tau_accept` (a single-engine, impostor-FAR question — see the unification
decision above), `tau_reject`'s real cost is on the **genuine** side: any
probe rejected here permanently loses its shot at the SFace rescue path that
the cascade exists to provide. A plain impostor-tail rank (the way the
currently-deployed 88.4927 was derived — same full-frame `independence_test.py`
run whose `tau_accept` sibling was rejected for a box-crop harness bug) never
measures this cost at all.

**No new independence-test run was needed for this analysis.** The genuine
LBPH distances already exist, on the correct pipeline, in an artifact
produced for an unrelated purpose.

## Data source

`classical-cv/outputs/benchmark/accuracy_ratio_verification_full_pairs.csv` —
the full pairwise-verification run (`classical-cv/reports/benchmark/accuracy_ratio_verification_full.md`),
`lbph_genuine_dist` column. 70,560 genuine-pair rows: 1,680 gallery/probe-disjoint
identities × (41 DL41 modifications + clean).

**Pipeline match confirmed, not assumed:** `robustness-protocol-map` §4's
"Checked for a pipeline bug (2026-08-02) — none found" already verified this
run uses the same detector (YuNet), same crop mode (`assume_cropped=False`,
box-cropped `face_gray`, not full-frame), same `SPECS["lbph"].default_equalization`,
and the same `data/lfw-dataset` path as the standalone artifact that backs
`tau_accept` — so these genuine distances are on the identical pipeline as
the 67.03325520645528 impostor-side derivation, not a different scale that
needs re-normalizing.

**Genuine pair definition:** probe (clean or DL41-modified) vs. that same
identity's *distinct* gallery photo, from the gallery/probe-disjoint split
manifest — not a same-image self-match (the leak documented in
`robustness-protocol-map` §0/§1 that produced the bogus ~99% AR numbers
elsewhere in this repo).

**Provenance caveat:** the source run itself executed scoring at the
then-deployed `tau_accept = 67.0084` (`accuracy_ratio_verification_full.json`'s
`tau_accept`/`tau_accept_source` fields) — irrelevant to this analysis, since
raw `lbph_genuine_dist` values are threshold-independent, but noted so this
derived `tau_reject` isn't later mistaken for something measured under a
newer config.

## Genuine LBPH distance percentiles, by tier

| Tier | n | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| clean | 1,680 | 94.28 | 96.52 | 102.02 | 122.12 |
| light | 28,560 | 97.53 | 104.01 | 134.23 | 167.46 |
| medium | 21,840 | 98.33 | 101.91 | 111.50 | 167.41 |
| heavy | 18,480 | 108.60 | 119.05 | 140.13 | 169.52 |
| all_modified (light+medium+heavy) | 68,880 | 100.87 | 107.82 | 134.36 | 169.52 |
| pooled (all tiers + clean) | 70,560 | 100.67 | 107.57 | 134.17 | 169.52 |

Tier sizes are uneven by design (17 light / 13 medium / 11 heavy mods, per
`DL41_CATEGORY_TIER`) — **pooled is not tier-balanced**; it's dominated by
light (28,560 of 70,560 rows, 40%) more than heavy (18,480, 26%). A naive
pooled percentile therefore under-weights the heavy tier relative to an
equal-weighting-per-tier statistic. Sample-size note: clean's 1,680 rows make
its p99 noisy (one or two data points at that tail) — don't push past p99 on
clean specifically.

## What the current and new deployed values actually do to this distribution

| tau_reject candidate | clean rejected | light rejected | medium rejected | heavy rejected | pooled rejected |
|---|---:|---:|---:|---:|---:|
| **88.4927** (currently deployed) | 28.33% | 33.80% | 42.04% | **51.09%** | 40.75% |
| 67.03325520645528 (for reference — this is `tau_accept`, not a serious `tau_reject` candidate) | 97.74% | 98.18% | 98.67% | 99.07% | 98.55% |

"Rejected" = outright-rejected without ever reaching SFace. The deployed
88.4927 cuts off over half of genuine **heavy**-tier probes before SFace gets
a look — directly undercutting the rescue-path result `docs/PAPER.md` reports
(SFace recovers 78.6% of LBPH's misses; degraded rank-1 5.10%→97.96%), since
that rescue can only happen for probes that reach the escalation band, not
ones hard-rejected first. This is on top of 88.4927's box-crop-harness-bug
taint (`docs/audits/STATE-08-02.md`) — even setting that aside, the value is
wrong for the job it's supposed to do.

## The decision point

Two independent choices, both policy calls — not something to pick silently:

1. **Which tier(s) to anchor on.** Clean-only badly under-serves the DL41
   robustness test (the whole point of the cascade is the degraded case).
   Heavy-tier-specific directly targets the hardest, most rescue-dependent
   case, at the cost of being the least statistically confident tier data
   here (18,480 samples, still plenty for p99, but the smallest of the four).
   Pooled is a reasonable middle ground but under-weights heavy for the
   uneven-tier-size reason above.
2. **Which percentile (FRR budget).** p90/p95/p99 of the chosen tier(s) is a
   direct trade: higher percentile → fewer genuine probes wrongly hard-rejected,
   but more impostors escalate into the SFace-dependent band. Unlike
   `tau_accept`'s FAR target, there's no existing project convention for this
   number — it needs an explicit pick, analogous to how 10 ppm was picked for
   `tau_accept`.

## Known unknown — not resolved here

**The impostor-side cost of raising `tau_reject` is not precisely quantified
yet.** The standalone LBPH impostor artifact
(`docs/results/independence_test/independence/lbph_lfw1/native_predict_scale_yunet.json`)
only stores curve snapshots up to rank 1024 (raw threshold 68.48, 61.98 ppm) —
nowhere near the 94–140 range these `tau_reject` candidates sit in, so the
fraction of the 16.5M-pair impostor sweep that would fall *below* a candidate
`tau_reject` (and therefore escalate to SFace, inheriting SFace's own FAR on
that subpopulation) can't be read off an existing artifact. A crude
two-point linear interpolation over `thresholds.json`'s `lbph_far_anchors`
(anchors at (88.4927, 1%) and (200, 100%)) was tried and discarded as
unreliable — that gap is too wide and the true curve shape in it is unknown.
**Before freezing any specific `tau_reject` value, re-run
`scripts/archive/run_lfw_lbph_native_predict_independence.py`'s underlying
sorted-distance array (or a targeted percentile query against it) to get the
real FAR-at-escalation number for the chosen candidate.** `docs/PAPER.md`
already establishes LBPH/SFace false accepts are positively correlated, so
this isn't a free trade — it should be measured, not assumed small.

## Suggestion

**Anchor on the heavy tier, target p99 → `tau_reject` ≈ 140.13.**

Reasoning: the cascade's stated purpose is rescuing degraded genuine probes
via SFace (`docs/PAPER.md`'s rescue numbers) — heavy is the tier that
purpose is actually for, and pooled statistics under-represent it. p99 (not
p95 or p90) because this is a genuinely final rejection with no recourse in
`cascade` mode — a 1%-of-heavy-genuine-probes FRR budget at this single stage
is a defensible ceiling for a non-recoverable decision; p90's ~11% would mean
roughly 1 in 9 hard-degraded real users never get a chance at the deep model,
which seems too aggressive for a "confident reject" bound.

Fallback if heavy-anchoring is judged too permissive for the impostor side
once that's measured: **pooled p99 ≈ 134.17** is the next most defensible
number — still a large improvement over the current 88.4927 (which already
rejects 41% of pooled genuine probes outright), and it's tier-blind rather
than heavy-specific, so a slightly more conservative middle ground.

**Do not adopt either number into `thresholds.json` yet.** Both are
provisional pending the impostor-side FAR measurement above — that's the one
open technical question standing between this analysis and a freeze
decision; the tier/percentile choice is a policy call for whoever owns the
threshold freeze.

## Cross-references

- `docs/NOTES.md` item 3 — the task this doc answers.
- `docs/results/independence_test/MASTER_FILE.md` — `tau_accept`'s parallel derivation and
  why it's a single-engine impostor-FAR question, unlike this one.
- `classical-cv/docs/audits/STATE-08-02.md` — why the current 88.4927 is
  additionally suspect (box-crop harness bug, same root cause as the
  rejected `tau_accept` candidate).
- `.claude/skills/robustness-protocol-map` §4 — the pipeline-bug check that
  confirms this CSV's LBPH distances are on the same scale as `tau_accept`.
- `classical-cv/reports/benchmark/accuracy_ratio_verification_full.md` /
  `.json` — the source run's own report.
