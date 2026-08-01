# Deriving the cascade gate's LBPH thresholds

How `gate.tau_accept` and `gate.tau_reject` should be obtained, why the second
one was being obtained wrongly, and what the corrected derivation measures.

Companion to `docs/audits/STATE-08-01.md` §5a, which first reported the
underlying matcher problem on a 147-probe subset. The numbers here are the
full-scale (1,680-probe, 5,749-identity) confirmation.

Script: `scripts/pipeline/derive_gate_thresholds_lbph.py`.

---

## 1. The two thresholds bound opposite risks

`src/hybrid/gate.py` routes a frame three ways on the LBPH top-1 distance `d1`:

| Condition | Outcome | Is SFace consulted? |
|---|---|---|
| `d1 <= tau_accept` | accept on LBPH | **no** |
| `tau_accept < d1 < tau_reject` | escalate | yes |
| `d1 >= tau_reject` | reject as Unknown | **no** |

Both non-escalating outcomes skip the accelerator, but they fail in opposite
directions:

* **`tau_accept` too high** → an impostor is admitted without SFace ever
  seeing them. The bound that matters is the **impostor** distribution at a FAR
  target. This is what the independence tests measure, and it is correct.
* **`tau_reject` too low** → a genuine, enrolled user is refused without SFace
  ever seeing them. Nothing in the impostor distribution bounds this. The
  relevant quantity is where **mated probes** actually land, traded against how
  much SFace load you are willing to pay.

`thresholds.json` currently derives *both* from the same impostor sweep —
`tau_reject` as the ~1% FAR impostor quantile. That answers "how far out do
impostors sit", when the question `tau_reject` actually poses is "how far out do
my own enrolled users sit before I stop asking the accelerator". The two have no
reason to coincide.

**A second, structural reason the independence tests cannot produce
`tau_reject`:** they enrol one image per identity and compare probes to each
other, so every pair they score is an impostor pair. There are no genuine pairs
in the sweep at all. A threshold whose whole job is bounding genuine-side loss
cannot be read off a measurement containing no genuine data.

## 2. The protocol that can measure it

`data/splits/lfw_ident_split_seed42.json` — gallery/probe-disjoint 1:N
identification (`docs/audits/STATE-08-01.md`): 5,749 identities enrolled from
one image each, 1,680 probes that are *different photographs of enrolled
people*. Every probe is mated, so the false-reject side is measurable.

This is also the deployment comparison shape — a probe scored against an
enrolled gallery — rather than the probe-vs-probe shape of the independence
sweeps.

Scale is native `cv.face.LBPHFaceRecognizer::predict_collect()` throughout, via
`LBPHAdapter.score()`, i.e. the code path the deployed recognizer runs. Not the
`independence_common.py` hand-rolled chi-square (~4x apart — see
`.claude/skills/cv-repo-map` §2).

### Crop families must not be mixed

`--crop-mode` selects which image LBPH normalizes, and the two families are not
comparable:

* **`frame`** (`assume_cropped=True`) — the whole LFW tile. This is how
  `models/lfw2/` was enrolled and how `accuracy_ratio_hybrid.py` probes, and it
  is the family the deployed 77.7693 / 88.4927 pair belongs to.
* **`box`** (`assume_cropped=False`) — the YuNet face box. This is the family of
  the standalone LBPH artifact
  (`reports/independence/lbph_lfw1/native_predict_scale_yunet.json`, 67.0333).

Because `models/lfw2/` is frame-enrolled only, scoring `box` probes against it
would put gallery and probe in different families. `--enroll` builds and caches
the matching gallery instead.

## 3. How each threshold is derived

**`tau_accept`** — unchanged in kind. Take the pooled impostor comparisons
(probe x non-mated gallery) and read off the rank at the FAR target
(`--far-target`, default 1e-5). Per-probe FPIR is also reported, but with only
1,680 probes its resolution floor is 595 ppm, far too coarse to *set* a 10 ppm
threshold.

**`tau_reject`** — the smallest value whose **pre-gate false-reject rate** meets
`--frr-target`, optionally capped by `--escalation-budget`. Raising `tau_reject`
monotonically reduces pre-gate loss and raises SFace load, so this is a
one-dimensional trade-off and the script emits the whole curve, not just the
chosen point. When budget and target conflict, the conflict is reported rather
than silently resolved.

Only the band clause is modelled. The margin and quality clauses escalate
*additional* frames, so band-derived escalation is a **lower bound** on real
SFace load and band-derived pre-gate loss an **upper bound** on real loss.

Everything is a pure function of a cached probe x gallery distance matrix, so
`--from-records` re-derives at a different budget in ~2 seconds without
rescoring.

## 4. Results — `frame` family (the deployed one)

1,680 probes, 5,749 enrolled, YuNet, zero detector misses.

| Quantity | Value |
|---|---|
| Rank-1 accuracy (threshold-free) | **2.92%** |
| Genuine distance p1 / p50 / p99 | 79.76 / 98.63 / 130.88 |
| Top-1 distance `d1` p50 / p95 | 85.95 / 92.03 |
| `tau_accept` at 10 ppm | **75.3266** (rank 96 of 9,656,640) |
| Deployed `tau_accept` 77.7693 | **26.51 ppm**, not the ~10 ppm it is labelled |
| Deployed `tau_reject` 88.4927 | **19.88%** of mated probes refused before SFace is asked |

### The finding underneath the thresholds

**The genuine distribution sits above the impostor top-1 distribution.** Genuine
distances have p1 = 79.76 and median 98.63, while the median *top-1* distance
over the same probes is 85.95 — that top-1 is an impostor in 97% of cases.
LBPH's distance to the correct person is typically *larger* than its distance to
the nearest wrong person, which is what a 2.92% Rank-1 means.

Consequences for the gate, none of which a threshold choice can fix:

* Any `tau_accept` in the 10 ppm regime (75.33) sits below the 1st percentile of
  genuine distances, so `cv_only` TPIR is ~0. This confirms
  `STATE-08-01.md` §5a at full gallery scale (that note measured Rank-1 7.48% on
  a 500-identity subset; against the full 5,749-identity gallery it is 2.92%).
* There is no `tau_reject` that both preserves genuine users and saves
  meaningful SFace calls. Meeting a 1% pre-gate false-reject target requires
  `tau_reject` = 95.4868, at which **97.32%** of frames escalate — the cascade
  degenerates into "always call SFace". Holding escalation to 50% instead costs
  48.27% pre-gate rejects.
* The deployed 88.4927 is one point on that curve: 19.88% pre-gate rejects for
  75.60% escalation.

The trade-off curve (`tau_reject_tradeoff.png`) shows the cost and loss lines
crossing at ~50/50 with no knee — the signature of two distributions that
overlap almost completely, i.e. a matcher that carries almost no usable
information at this operating scale.

## 4b. Results — `box` family (crop-matched to deployment)

Same protocol, same probes, gallery re-enrolled with `--enroll --crop-mode box`
so gallery and probe share the crop family. 5,749 identities, zero YuNet misses.

| Quantity | `frame` | `box` |
|---|---|---|
| Rank-1 accuracy | 2.92% | **5.42%** |
| Genuine distance p1 / p50 | 79.76 / 98.63 | 64.06 / 83.25 |
| Top-1 `d1` p50 | 85.95 | 70.74 |
| `tau_accept` at 10 ppm | 75.3266 | **67.1825** |
| `tau_reject` at 1% pre-gate FRR | 95.4868 (97.32% escalation) | **79.7421** (93.04% escalation) |
| `tau_reject` at 50% escalation budget | 86.0744 (48.27% rejected) | **71.1628** (43.99% rejected) |

Cropping to the YuNet box nearly doubles Rank-1 and lifts genuine distances off
the floor — genuine p1 (64.06) now sits *below* the 10 ppm `tau_accept` (67.18),
so 6.01% of probes are confidently accepted where the frame family accepted
1.73%. It is a real improvement. It is not enough: at 5.42% Rank-1 the
distributions still overlap almost completely and the trade-off curve still has
no knee.

### Mixing the families is catastrophic, quantified

The deployed `tau_accept = 77.7693` is a **frame**-family value. Evaluated
against **box**-family distances it lands at **53,687 ppm** — a 5.4% FAR, with
**97.14%** of probes confidently accepted and almost all of them wrong. In the
other direction the box-family 67.0333 evaluated on frame distances gives
1.86 ppm, far stricter than intended, accepting essentially nothing.

So the family is not a detail to be inferred later. It has to be declared with
every threshold, which is why `--crop-mode` is recorded in every output file.

## 4c. Answering "can we reuse the standalone `tau_accept`?"

**Yes — and it is now corroborated rather than merely reused.**

`reports/independence/lbph_lfw1/native_predict_scale_yunet.json` gives 67.03325
from a probe-vs-probe sweep over 16.5M unique impostor pairs. This run derives
**67.1825** at the same 10 ppm target from a completely different comparison
shape — 1,680 probes against a 5,749-identity enrolled gallery, 9.66M impostor
comparisons. The two agree to within 0.15 distance units (0.2%), and 67.03325
evaluated on this protocol sits at **7.56 ppm**, i.e. the intended order of
magnitude.

Two measurements with different pair structures landing on the same value is
evidence the value is a property of LBPH-on-LFW rather than an artifact of
either protocol. Keep 67.0333.

The caveats that do matter:

1. **It is a `box`-family number.** It is only valid for a pipeline whose
   gallery and probes are both YuNet-box cropped. Pairing it with the deployed
   frame-family `tau_reject` is the mixing error quantified in §4b.
2. **The deployed `tau_accept = 77.7693` is not a 10 ppm value** even within its
   own frame family — it measures 26.51 ppm on this protocol. The 10 ppm label
   in `thresholds.json` provenance overstates it by ~2.6x.

**Is there a better way to get `tau_accept`?** Not materially, in isolation —
the two protocols already agree. The improvement available is not a better
`tau_accept` but a *coherent pair*: derive both thresholds from one run, on one
protocol, in one crop family, which is what this script does. That removes the
class of error where each threshold is individually defensible and the
combination is not.

## 5. What this does and does not license

The derived values are **candidates**. Nothing here writes to
`src/hybrid/thresholds.json`; promoting a value is a separate deliberate act
that must also move `gate.py::_FALLBACK_GATE_DEFAULTS`, `calibrate.py`, and add
a dated `docs/audits/STATE-*.md` entry (`docs/READ THIS/FROZEN_THRESHOLDS.md`).

Promoting a `tau_reject` off this run would be premature while Rank-1 is 2.92%
(`frame`) / 5.42% (`box`): the number would be a faithful measurement of a
matcher that is not working, and tuning the escalation band cannot make it work.
Fix the ranking problem first, then re-derive — `--from-records` makes the
re-derivation nearly free once new scores exist.

The one change this run *does* support on its own evidence is documentary: the
`gate.tau_accept` provenance string in `thresholds.json` claims ~10 ppm for
77.7693, and the measured value on this protocol is 26.51 ppm. That is a label
correction, not a threshold change.

Run records: `reports/independence/lbph_gate_disjoint/{frame,box}/`. The
`records.npz` distance matrices (~32 MB each) are not committed; regenerate with
the commands in the script docstring, or keep them alongside for `--from-records`.
