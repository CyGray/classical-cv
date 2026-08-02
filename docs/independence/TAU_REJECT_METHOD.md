# `tau_reject` — canon method: FRR-vs-escalation trade-off curve

*Canonized 2026-08-02, advisor sign-off. Value: `gate.tau_reject = 140.13` in
`classical-cv/src/hybrid/thresholds.json`. Supersedes the box-crop-harness-bug-tainted
88.4927 (`docs/READ THIS/FROZEN_THRESHOLDS_HYBRID.md`). Follows
[`docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md`](../experiments/tau_reject/THRESHOLD_ANALYSIS.md)
(the genuine-percentile exploration that proposed 140.13 as a working value)
and closes `docs/NOTES.md` item 3.*

## Why this is not a percentile recipe

`tau_reject` is the cascade's confident-*reject* bound:
`lbph_distance >= tau_reject` rejects a probe outright, without ever calling
SFace. Unlike `tau_accept` (a single-engine impostor-FAR question, answered
the same way on LFW: pick a false-accept-rate target and read off the
distance rank), `tau_reject`'s cost structure is asymmetric:

- Raising it recovers genuine probes that would otherwise be hard-rejected
  before SFace gets a chance to rescue them.
- Raising it also lets more impostors reach the escalation band, where they
  get a shot at fooling SFace instead of being turned away by LBPH alone.

A plain impostor-tail-rank derivation (how the old 88.4927 was made) only
measures the second cost, and a plain genuine-percentile pick (the
`THRESHOLD_ANALYSIS.md` p99 proposal) only measures the first. **The method
that actually answers "where should this bound sit" measures both at once,
across a sweep, and asks whether there's a range where the trade is
favorable — a knee in the curve.** If genuine rescue and impostor escalation
move together at every candidate, no percentile choice is more defensible
than any other on separation grounds alone, and the decision becomes a
different kind of engineering call (see "What the curve actually shows"
below).

## Method

For a sweep of `tau_reject` candidates, compute two pooled rates directly
from the same threshold-independent raw LBPH distances used for `tau_accept`
(`accuracy_ratio_verification_full_pairs.csv`, 70,560 genuine-pair rows /
70,560 impostor-pair rows, gallery/probe-disjoint LFW, box-cropped YuNet — no
new independence run needed):

- **`genuine_hard_reject_pct`** — fraction of genuine probes with
  `lbph_genuine_dist >= tau_reject`: permanently lost the SFace rescue
  chance. This is the real cost of setting `tau_reject` too low.
- **`impostor_escalated_pct`** — fraction of impostor probes with
  `lbph_impostor_dist` in `[tau_accept, tau_reject)`: get a shot at fooling
  SFace instead of being turned away outright. This is the real cost of
  setting `tau_reject` too high.

Script: `classical-cv/scripts/pipeline/tau_reject_tradeoff_curve.py`. Output:
`classical-cv/reports/independence/tau_reject_tradeoff/curve.json`
(21-point sweep, `tau_reject` from 70 to 170 in steps of 5).

**Caveat carried over from the sibling SFace band diagnostic:**
`impostor_escalated_pct` is a 1:1-protocol proxy (this row's designated
impostor pair), not the real 1-to-N `argmin` escalation event — see
`docs/experiments/hybrid_sface_threshold/ANALYSIS.md`. It's adequate here
because the conclusion below doesn't depend on the exact escalation
mechanism, only on whether genuine and impostor distance distributions
separate in this range at all.

## What the curve actually shows

| tau_reject | genuine hard-reject | genuine escalated | impostor escalated |
|---:|---:|---:|---:|
| 70 | 96.78% | 1.78% | 0.02% |
| 80 | 74.87% | 23.69% | 8.26% |
| 90 | 35.40% | 63.15% | 51.68% |
| 100 | 10.83% | 87.73% | 86.24% |
| 110 | 4.12% | 94.43% | 95.43% |
| 120 | 2.45% | 96.10% | 97.47% |
| 130 | 1.41% | 97.14% | 98.54% |
| **140** | **0.54%** | **98.01%** | **99.49%** |
| 150 | 0.10% | 98.46% | 99.91% |
| 160 | 0.02% | 98.54% | 99.99% |
| 170 | 0.00% | 98.55% | 100.00% |

**There is no knee.** `genuine_escalated_pct` and `impostor_escalated_pct`
track each other almost 1:1 across the entire sweep — from 90 onward,
impostor escalation is consistently *equal to or higher than* genuine
escalation, never meaningfully lower. At every candidate tested, raising
`tau_reject` to rescue one more genuine probe lets in an impostor at
essentially the same rate. This is a straight-line trade, not a curve with a
favorable region — the publishable finding this method exists to surface:

**LBPH's genuine and impostor distance distributions do not separate in the
70-170 range on wild LFW.** This is the same domain-shift finding
`robustness-protocol-map` §4 already established from a different angle (the
EER-swept cutoff sits at ~86-88, right where genuine and impostor curves
cross) — this curve confirms it holds across the entire plausible
`tau_reject` range, not just at one crossover point.

## Decision, given no separation exists

Since no candidate trades favorably against another on separation grounds,
the choice is a different kind of call: **given that the confident-reject
branch cannot be made to separate genuine from impostor on this dataset, is
it better to make that branch permissive (favor escalation, rely on SFace)
or restrictive (favor cheap rejection, accept heavy genuine loss)?**

**Canon: 140.13 — permissive, chosen to make the reject branch functionally
inert on LFW.** At 140.13, genuine hard-reject drops to 0.54% (heavy tier
alone: ~1%, by construction — it's that tier's own p99), down from the old
88.4927's 51.09% heavy-tier hard-reject rate
(`THRESHOLD_ANALYSIS.md`). 140.13 sits above the clean/light/medium genuine
distributions' near-entirety and above the observed max genuine distance for
most tiers — **this is not a derived separation bound, it is a deliberate
engineering choice** that the cascade's headline result (SFace rescuing
78.6% of LBPH's misses, `docs/PAPER.md`) should get the chance to operate on
as much of the genuine population as possible, since LBPH alone cannot be
trusted to reject correctly in this range anyway.

**Consequence, stated plainly:** on wild LFW, `tau_reject` at 140.13 barely
filters anything (98.55% of impostors also escalate at 170, the sweep's
ceiling) — the cascade's confident-reject stage is nearly a no-op here. The
system's actual FAR control on wild LFW comes almost entirely from SFace's
own gate, not LBPH's. This should be stated in the thesis/report alongside
any cascade-architecture claim that LBPH provides a meaningful first filter
on wild, uncontrolled photos — it does for `tau_accept` (deciding what's
cheap-accepted) but not for `tau_reject` (deciding what's cheap-rejected).

**Does not generalize to La Salle DB1.** `docs/PAPER.md` reports ~75% of
La Salle DB1 probes resolved on the cheap LBPH-only path — a regime where
LBPH's genuine/impostor separation is real (controlled capture conditions).
This curve and its "no knee" conclusion are LFW-specific; re-run the same
method on La Salle DB1 data before assuming the same reasoning applies there.

## Reproducing this

```
python scripts/pipeline/tau_reject_tradeoff_curve.py \
  --pairs-csv outputs/benchmark/accuracy_ratio_verification_full_pairs.csv \
  --tau-accept 67.03325520645528 \
  --sweep-start 70 --sweep-stop 170 --sweep-step 5
```

## Cross-references

- `docs/NOTES.md` item 3 — closed by this canonization.
- `docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md` — the genuine-percentile
  exploration that proposed 140.13 as a working value before this method
  confirmed no better candidate exists on separation grounds.
- `docs/experiments/hybrid_sface_threshold/ANALYSIS.md` — the SFace-side
  resolution that also depends on this canonization (band ≈ marginal
  argument), and the source of the 1:1-protocol-proxy caveat reused here.
- `.claude/skills/robustness-protocol-map` §4 — the EER-swept-cutoff finding
  (~86-88) that this curve's "no separation" conclusion is consistent with.
- `classical-cv/src/hybrid/thresholds.json` — `provenance.gate.tau_reject`,
  the canon value.
- `classical-cv/reports/independence/tau_reject_tradeoff/curve.json` — raw
  sweep output.
- [`docs/experiments/hybrid-identification/README.md`](../experiments/hybrid-identification/README.md) —
  **confirmed 2026-08-02** by a real 1-to-N identification run: 97.51% mean
  escalation across 41 mods, matching this doc's 1:1-proxy-based prediction.
