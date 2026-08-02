---
name: robustness-protocol-map
description: >
  Navigation map for the LFW2 41-modification robustness benchmark's PROTOCOL
  axis (LS-Face / Smart Gate, USLS CV Group 3): which script answers "is the
  correct identity the nearest of N gallery entries" (1-to-N identification,
  accuracy_ratio_hybrid.py) vs "does THIS probe/gallery pair clear a
  threshold" (1:1 pairwise verification, accuracy_ratio_verification.py) vs
  the legacy same-image transform_sensitivity path, why the same probes score
  wildly differently under each, and the two operating-point families
  (tau_accept 10ppm gate vs EER-swept cutoff) that every AR/GAR/TPIR/Rank-1/
  EER number must be stamped with before it's comparable to another one. Use
  before running, editing, or writing a variant of accuracy_ratio_hybrid.py,
  accuracy_ratio_verification.py, run_lfw2_robustness.py, or anything under
  docs/experiments/ or docs/NOTES.md; before quoting an AR/GAR/Accuracy@tau/
  EER number in a report or thesis section; before comparing two robustness
  numbers to each other; and before designing a new robustness protocol
  variant (impostor selection, threshold sweep, new engine).
---

# Robustness-test protocol map: identification vs verification vs transform-sensitivity

Read `cv-workspace-map` (workspace root) and `classical-cv/.claude/skills/cv-repo-map`
first for thresholds-from-prose (`cv-workspace-map` Sec 2), the two
non-comparable LBPH distance scales (`cv-repo-map` Sec 2), the two threshold
FAMILIES joint-vs-standalone (`cv-repo-map` Sec 3.1), and crop modes
(`cv-workspace-map` Sec 3.2). This skill does not repeat those - it covers
the layer above them: **which protocol a script is running, and what that
protocol quietly assumes.** That's what actually produced a wrong headline
number in this repo (`docs/experiments/IDENTIFICATION_VS_VERIFICATION.md` at
the WORKSPACE ROOT, 2026-08-01) and what a follow-up experiment (2026-08-02,
see Sec 4) then
showed was itself an incomplete explanation.

## 0. Three protocols, three scripts, the SAME probes

All script/model paths from here on are relative to `classical-cv/` (this
skill itself lives at the workspace root, one level above that repo); `docs/`
paths are the workspace-root `docs/`, a different directory from
`classical-cv/docs/` — see `cv-workspace-map` Sec 4 for that trap.

All three scripts read the SAME gallery/probe-disjoint split manifest
(`data/splits/lfw_ident_split_seed42.json`) and the SAME
`stable_rng(seed, person, fname, mod_name, level)`-seeded 41-modification
suite (`src/benchmark/modifications.py`), so a number from any one of them is
about the SAME degraded images as a number from either other one. That is
what makes cross-protocol comparison meaningful instead of apples-to-oranges
- but it also means a low number from one script and a high number from
another are not automatically a contradiction; they may just be different
questions about identical inputs.

| Script | Question | Decision rule | Needs an N-gallery model? |
|---|---|---|---|
| `src/benchmark/accuracy_ratio_hybrid.py` **with** `--split-manifest` | 1-to-N open-set identification: which of N enrolled identities is nearest, and does THAT distance clear the gate? | `argmin_i d(P, G_i) == truth AND d <= tau_accept` | Yes - full LBPH `.yml` / SFace gallery enrolled over all N identities (`scripts/pipeline/run_lfw2_robustness.py` / `ensure_lfw2_enrollment`). |
| `src/benchmark/accuracy_ratio_hybrid.py` **without** `--split-manifest` | Legacy same-image "transform sensitivity" - probe is a degraded copy of its OWN enrolled image | Same rule, but genuine distance before damage is ~0 | Yes, same as above. Reports as `transform_sensitivity`, never "Accuracy Ratio" - self-match leak produces bogus ~99% numbers if mislabeled (docs/audits/STATE-08-01.md). |
| `src/benchmark/accuracy_ratio_verification.py` | 1:1 pairwise verification: does THIS probe, compared only to its own gallery image (genuine) and one deterministic other identity's gallery image (impostor), clear the threshold? | `d(P, G_truth) <= tau` (genuine), `d(P, G_other) <= tau` (impostor, false accept) | **No.** Trains a throwaway 2-class model per pair (or computes cosine directly for SFace) - O(1) per pair, gallery size never enters the distance. |

**Rule:** a modification/probe/identity subset is comparable ACROSS these
three scripts (same seed, same `--limit-identities` prefix rule - see Sec 3).
It is not comparable to a different modification suite, a different LFW copy
(`cv-workspace-map` Sec 3.3), or a different crop mode.

## 1. Genuine-only is not verification - the mistake that already happened once

"1:1 verification" implies a decision made against BOTH a genuine and an
impostor pair. A script that only ever compares a probe to its OWN gallery
image and reports the accept rate is reporting **GAR (Genuine Accept Rate)**,
not verification accuracy - there is no FAR term, so there is no accuracy
number and nothing to compare against the published 65-75% LFW classical
baseline (`docs/experiments/IDENTIFICATION_VS_VERIFICATION.md` Sec 3.1: 3,000
genuine + 3,000 impostor pairs). `accuracy_ratio_verification.py` always
scores a same-seeded impostor pair (`stable_rng(..., mod_name, level,
"impostor")`, excluding the true identity) alongside the genuine one for
exactly this reason - do not strip the impostor half out of a variant to make
it faster; that turns the script back into a GAR-only tool wearing a
verification label.

## 2. Two operating points - every verification number needs one stamped on it

| Operating point | What it targets | Where it comes from | Stability |
|---|---|---|---|
| `tau_accept` (deployment gate) | ~10 ppm FAR, calibrated on La Salle DB1 frontal crops | `src/hybrid/thresholds.json` `gate.tau_accept` (currently 67.0084 - **read the file, this skill included, per `cv-repo-map` Sec 3**) | Frozen; do not relax to chase a better-looking accuracy number without a provenance note (`docs/READ THIS/FROZEN_THRESHOLDS.md`). |
| EER-swept cutoff | Point where FAR = FRR over THIS run's own pooled genuine+impostor scores | Computed post-hoc per run (`accuracy_ratio_verification.equal_error_rate`) | **Not frozen, not a config value, not comparable across runs with different probes/impostor sampling/mod sets.** It moves every time the input distribution changes - never write it into `thresholds.json` or quote it as "the" LBPH threshold. |

A GAR/FAR/Accuracy number without saying which operating point produced it is
uninterpretable - `tau_accept` and the EER point differ by ~20 raw LBPH
distance units on this dataset (Sec 4), enough to swing accuracy from chance
to something resembling the literature figure.

## 3. The shared probe contract - reuse it, don't re-seed

`stable_rng(seed, *tokens)` (`src/benchmark/modifications.py`) is a CRC32-salted
`np.random.default_rng` - identical tokens always produce the identical
modified image, across every script that calls it with the same tokens. This
is the ONLY reason `accuracy_ratio_hybrid.py`'s and
`accuracy_ratio_verification.py`'s numbers are about the same probes. A new
protocol variant MUST:

- Call `stable_rng(seed, person, fname, mod_name, level)` for the
  modification itself - do not re-implement or re-seed.
- Extend the token tuple for any NEW random choice a variant needs (e.g.
  `accuracy_ratio_verification.py` appends `"impostor"` to pick the impostor
  identity) rather than drawing from a fresh unseeded RNG - otherwise the
  variant's output isn't reproducible and isn't comparable to a rerun.
- Reuse the manifest loaders from `accuracy_ratio_hybrid.py`
  (`load_split_manifest`, `load_probes_from_manifest`,
  `load_gallery_from_manifest`) rather than re-reading
  `data/splits/lfw_ident_split_seed42.json` by hand - the manifest schema
  (`probes` list vs legacy singular `probe`, `singleton`/`demoted` flags) has
  edge cases those functions already handle.
- Use the SAME `--limit-identities` prefix rule for smoke subsets: first N
  *sorted* gallery identities, probes intersected with that enrolled set
  (not independently truncated - a 1,680-of-5,749 probe-bearing subset is
  scattered through the sorted gallery order, so truncating probes
  separately hands most rows an unenrolled identity and manufactures a
  guaranteed-miss floor that reads as a real accuracy number). This also
  makes an N-identity subset a strict superset-comparable slice of any
  smaller prefix run (e.g. the 20% / 1,150-identity run in Sec 4 is a
  superset of the earlier 10% / 575-identity run).

## 4. Known result, 2026-08-02: protocol switch alone did NOT recover the literature number

`docs/experiments/IDENTIFICATION_VS_VERIFICATION.md` (2026-08-01) predicted
that scoring under 1:1 verification instead of 1-to-N identification would
recover something near the published 65-75% LFW classical baseline. The
follow-up run (`reports/benchmark/accuracy_ratio_verification_smoke20.md`,
20% / 1,150-identity subset, superset of the 575-identity identification run)
found otherwise:

- At the SAME deployment threshold (`tau_accept` = 67.0084), pairwise LBPH
  accuracy was **~50% (chance)** on both clean and DL41-modified probes,
  because GAR (0.67-0.91%) was almost identical to the identification AR
  (0.91-1.74%) it was supposed to explain away. FAR at that threshold was
  0.00% both ways.
- **Conclusion: the near-zero identification AR is NOT mainly "correct
  identity loses Rank-1 to a closer impostor among N-1 others."** It is that
  genuine LBPH distances on wild LFW almost never clear 67.0084 at all,
  whether judged 1:1 or 1-to-N. The identification/verification protocol
  distinction is real but was not, on its own, the dominant cause here.
- Only at the run's own EER-swept cutoff (~86-88 raw distance, a DIFFERENT,
  NOT-frozen operating point - see Sec 2) did pairwise accuracy rise to
  ~58-61%, closer to but still below the literature figure.
- SFace, same protocol, same probes: GAR 80-92%, FAR 0.00%, Accuracy@tau
  90-96% - the contrast confirms this is an LBPH threshold/domain-shift
  finding, not an artifact of the verification protocol itself.

**Trap this creates:** don't cite "1:1 verification recovers 65-75%
accuracy" as settled without also stating the operating point. At the frozen
deployment gate, it does not. `docs/NOTES.md` Option B (dual reporting) needs
this caveat before it goes in a thesis section - the two protocols agree at
the deployment threshold; they only diverge at a different, unfrozen cutoff.

## 5. Writing a new protocol variant safely

1. Decide which of the three questions (Sec 0) the variant answers, and name
   it accordingly - don't reuse "verification" for a genuine-only tool (Sec 1)
   or "identification" for a same-image path (Sec 0 row 2).
2. Reuse the manifest/probe-contract functions (Sec 3); don't hand-roll
   dataset loading or RNG seeding.
3. Keep `assume_cropped=False` unless you are deliberately reproducing the
   full-frame joint-test path (`cv-workspace-map` Sec 3.2) - box-crop is what
   matches deployment and the standalone 67.0x scale.
4. If the variant introduces a NEW way of computing an LBPH distance (a new
   codepath, not just a new decision rule over an existing one), **spot-check
   it before trusting any output**: take one (gallery, probe) pair, compute
   the distance your new way, and compare against
   `LBPHAdapter.score(sample).all_distances[person]` from an existing
   enrolled model (e.g. `models/lfw2/lbph_seed42_manifest2ef84e167992_boxcrop.yml`
   via `src/hybrid/recognizer.LBPHAdapter`). They must match to float
   precision - `predict_collect()`'s per-label distance is independent of how
   many OTHER labels are in the model, so a correct new codepath reproduces
   the N-gallery number exactly on a 2-class (or 1-class) throwaway model.
   `accuracy_ratio_verification.py` was validated this way before its first
   real run; redo it for any new distance path, not just once ever.
5. Decide and DOCUMENT what a detection miss (`--no-face-policy strict`)
   does to each side of a pairwise decision - genuine and impostor are not
   symmetric (a probe with no face has no embedding to test against ANYONE,
   so it can still count as a genuine reject but must be excluded from the
   impostor/FAR denominator entirely, not silently dropped from both). Get
   the CLI help text and the code path to agree; they didn't, once, in this
   script's first draft.
6. Report GAR, FAR, and Accuracy@operating-point side by side, never
   Accuracy alone - Accuracy hides which of GAR/FAR is doing the work, the
   same reason `cv-repo-map` Sec 3B insists on reporting Rank-1 alongside
   TPIR/AR.

## 6. Where things live

All `src/`/`scripts/`/`reports/`/`outputs/` paths below are inside
`classical-cv/` (this skill lives at the workspace root, one level above that
repo — see `cv-workspace-map` Sec 1); `docs/` paths below are at the
workspace root itself, a DIFFERENT `docs/` from `classical-cv/docs/`
(`cv-workspace-map` Sec 4).

- `classical-cv/src/benchmark/accuracy_ratio_hybrid.py` - identification / transform-sensitivity, Sec 0.
- `classical-cv/src/benchmark/accuracy_ratio_verification.py` - 1:1 pairwise verification, Sec 0/1/4.
- `classical-cv/scripts/pipeline/run_lfw2_robustness.py` - parallel harness + LFW2 enrollment for the IDENTIFICATION path only; the verification script needs no enrolled model (Sec 0 table) and is not orchestrated through this.
- `classical-cv/src/benchmark/modifications.py` - the 41-mod suite, `stable_rng`, `DL41_TIER_MAP`/`DL41_CATEGORY_TIER`/`DL41_DETECTOR_CANONICAL`.
- `docs/experiments/IDENTIFICATION_VS_VERIFICATION.md` (workspace root) - the original protocol-confound hypothesis (2026-08-01, partially superseded by Sec 4).
- `docs/experiments/standalone_lbph_robustness/THRESHOLD_CHANGE.md` (workspace root) - the identification-side numbers (1.74% AR @ 575 identities) that Sec 4's pairwise run was checked against.
- `docs/NOTES.md` (workspace root) - open reporting decisions; Sec 4's caveat applies directly to its "Option B" item.
- `classical-cv/reports/benchmark/accuracy_ratio_verification_smoke20.{json,md}` + `classical-cv/outputs/benchmark/accuracy_ratio_verification_smoke20_pairs.csv` - the 2026-08-02 run backing Sec 4, with per-pair rows for offline threshold/EER re-sweeps.
