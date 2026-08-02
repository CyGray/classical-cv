# GEMINI.md — Computer Vision workspace (USLS CV Group 3, LS-Face / Smart Gate)

This file is the Gemini-CLI mirror of two Claude-Code skills that live under
`.claude/skills/` in this workspace: `cv-workspace-map` (root) and
`robustness-protocol-map` (root), plus `classical-cv/.claude/skills/cv-repo-map`.
Gemini CLI has no skill-trigger mechanism, so this is self-contained prose
rather than a pointer — read the whole file before touching thresholds,
independence tests, or the robustness benchmark, not just the section that
looks relevant. If you are Claude Code reading this file instead of the
skills above: don't use this as your primary reference, it is a condensed
copy — use the skills, they're kept current and this may drift.

*Facts below verified 2026-08-02. Numeric threshold values are quoted here
only to illustrate a known problem (Sec 1) or a dated empirical result (Sec 4)
— never copy a number out of this file into config or a report. Read
`classical-cv/src/hybrid/thresholds.json` for the deployed value, always.*

---

## 0. What this workspace is

Not a git repo itself (`git rev-parse` fails at this root — run git commands
inside a subdirectory). Two independent git repos live under it:

- `classical-cv/` — **the live, runnable project.** LBPH / Eigenfaces /
  Fisherfaces classical recognizers, and the hybrid LBPH+SFace cascade
  (`src/hybrid/`). All real work happens here.
- `deep-learning/` — has commits but **not runnable on this machine**:
  `loader.py` hardcodes a `D:/FILES/...` dataset root and there is no `D:`
  drive here. Treat any DL-side work as plan-only, written into
  `classical-cv/docs/`.

`face-detection-g3/` is empty despite what root `AGENTS.md` claims. Root
`AGENTS.md` also describes a `preprocess/` directory that does not exist —
don't trust its structure section. When `classical-cv/AGENTS.md` and root
`AGENTS.md` disagree, `classical-cv/AGENTS.md` wins.

Python: global Python 3.11 on Windows, no `.venv` in `classical-cv`. Shell:
PowerShell primary, a POSIX bash tool is also available; `rg`/`fd` work.

---

## 1. Threshold trap: one runtime file, several disagreeing docs

**The only threshold value that is actually deployed is whatever
`classical-cv/src/hybrid/thresholds.json` contains at read time** —
`load_thresholds()` reads that file and nothing else. Multiple prose docs in
this repo (root `AGENTS.md`, `classical-cv/docs/READ THIS/FROZEN_THRESHOLDS*.md`,
old report roll-ups) have stated values that did not match it at various
points. **Never quote a threshold from a doc, including this one — read the
JSON file, every time, immediately before you rely on a number.**

As of 2026-08-02, `thresholds.json`'s `gate.tau_accept` reads **67.0084**,
which happens to equal the value documented as the frozen STANDALONE LBPH
threshold (`docs/READ THIS/FROZEN_THRESHOLDS.md`) — but its own
`provenance` field describes it as coming from a JOINT hybrid run. That
mismatch is a known, unresolved documentation gap, not something to "fix" by
editing either side without checking with the project owner first.

## 2. Two non-comparable LBPH distance scales

This repo computes an "LBPH distance" two different ways that produce
**different magnitudes for the same pair** (roughly 4x apart):

- `src/independence_common.py` (`chi2_to_templates`) — a hand-rolled
  chi-square reimplementation over extracted histograms. Used by
  `scripts/pipeline/run_lfw_independence.py` and the streaming/plotting
  scripts. Good for figures/percentiles/ranking, **not** for a deployment
  threshold magnitude.
- `cv.face.LBPHFaceRecognizer::predict_collect()` (OpenCV's own
  implementation) — the **deployment scale**. Everything in
  `thresholds.json` and every `tau_accept`-comparable number must be on this
  scale. Produced by `scripts/archive/run_lfw_lbph_native_predict_independence.py`,
  `LBPHAdapter.score()`, and `src/benchmark/accuracy_ratio_verification.py`.

Before quoting ANY LBPH raw-distance number as a threshold, confirm which of
these two produced it. The two scales agree on ranking/ordering (same
boundary pair, same rank) — just not on magnitude.

## 3. Cropped vs full-frame LBPH tiles — a second, compounding scale difference

LBPH's input tile can be either the whole raw LFW frame (250x250, with
margin) or the YuNet-detected face box cropped out of it. These produce
different distance magnitudes too (~67 cropped vs ~75 full-frame on the same
pairs, measured 2026-08-01). **Deployment and the standalone threshold use
the cropped path** (`assume_cropped=False`, which despite the name means
"use the detector's box, don't assume the whole frame already IS the face" —
`LBPHAdapter._normalize` via `sample.face_gray`). The joint hybrid
independence test historically ran full-frame. Confirm `assume_cropped`
before comparing two LBPH numbers — this and Sec 2's scale difference compound
rather than being alternative explanations for the same gap.

## 4. The robustness-test protocol axis (identification vs verification)

The LFW2 41-modification robustness benchmark (`src/benchmark/modifications.py`
suite, applied via `stable_rng(seed, person, fname, mod_name, level)` so
every script produces bit-identical modified probes) can be scored three
different ways. **These are different questions about the same degraded
images, and their numbers are not interchangeable:**

| Script | Question | Decision rule |
|---|---|---|
| `accuracy_ratio_hybrid.py --split-manifest ...` | 1-to-N open-set identification: is the correct identity the NEAREST of N gallery entries, and does that distance clear the gate? | `argmin_i d(P,G_i)==truth AND d<=tau_accept` |
| `accuracy_ratio_hybrid.py` (no `--split-manifest`) | Legacy same-image "transform sensitivity" — probe is a degraded copy of its own enrolled image | same rule; reported as `transform_sensitivity`, NEVER "Accuracy Ratio" (self-match leak — genuine distance before damage is ~0, produces bogus ~99% numbers if mislabeled) |
| `accuracy_ratio_verification.py` | 1:1 pairwise verification: does THIS probe, compared only to its own gallery image (genuine) and one deterministic other identity (impostor), clear the threshold? | `d(P,G_truth)<=tau` (genuine) and `d(P,G_other)<=tau` (impostor false-accept), scored together |

All three read the same gallery/probe-disjoint split manifest
(`data/splits/lfw_ident_split_seed42.json`, 5,749 identities, 1,680 probes)
and the same modification suite, so a smoke subset is comparable across
scripts IF it uses the same `--limit-identities` prefix rule: keep the first
N *sorted* gallery identities, then intersect probes with that enrolled set
(not truncate probes independently — probe-bearing identities are a
1,680-of-5,749 subset scattered through the sorted order, so an independent
truncation manufactures a guaranteed-miss floor that reads as a real number).

### Genuine-only is not verification

A script that only compares a probe to its OWN gallery image and reports the
accept rate is reporting **GAR (Genuine Accept Rate)**, not verification
accuracy — there is no impostor/FAR term, so there is nothing to compare
against a published verification-accuracy baseline. `accuracy_ratio_verification.py`
always scores a same-seeded impostor pair alongside the genuine one
(`stable_rng(..., mod_name, level, "impostor")`, excluding the true
identity) for exactly this reason.

### Two operating points — every verification number needs one stamped on it

- **`tau_accept`** (deployment gate, ~10 ppm FAR target) — from
  `thresholds.json`, currently 67.0084 (Sec 1). Frozen; don't relax it to
  chase a better accuracy number.
- **EER-swept cutoff** — the threshold where FAR=FRR over one particular
  run's own pooled genuine+impostor scores. **Not frozen, not a config
  value, moves every time the input distribution changes.** Never write it
  into `thresholds.json` or call it "the" threshold.

### Known result (2026-08-02): protocol switch alone did NOT recover the literature ~65-75% figure

An earlier doc (`docs/experiments/IDENTIFICATION_VS_VERIFICATION.md`,
2026-08-01) predicted that scoring under 1:1 verification instead of 1-to-N
identification would recover something near the published 65-75% LFW
classical verification baseline. A follow-up run
(`reports/benchmark/accuracy_ratio_verification_smoke20.md`, 1,150 identities
= 20% of the gallery, superset of an earlier 575-identity identification run)
found:

- At the SAME deployment threshold (`tau_accept`=67.0084), pairwise LBPH
  accuracy was **~50% (chance)** on both clean and 41-mod-degraded probes,
  because Genuine Accept Rate (0.67-0.91%) was almost identical to the
  1-to-N identification Accuracy Ratio (0.91-1.74%) it was meant to explain
  away. False Accept Rate at that threshold was 0.00% both ways.
- **The near-zero identification AR is therefore NOT mainly "correct
  identity loses Rank-1 to a closer impostor among the other N-1."** It is
  that genuine LBPH distances on wild LFW almost never clear 67.0084 at all
  — 1:1 or 1-to-N, the outcome is the same. The identification/verification
  distinction is real but was not the dominant cause here.
- Only at that specific run's own EER-swept cutoff (~86-88 raw distance — a
  DIFFERENT, non-frozen operating point) did pairwise accuracy rise to
  ~58-61%, closer to but still under the literature figure.
- SFace, same protocol, same probes: Genuine Accept Rate 80-92%, Accuracy@tau
  90-96% — confirms this is specifically an LBPH threshold/domain-shift
  finding, not an artifact of the verification protocol itself.

**Trap:** don't state "1:1 verification recovers 65-75% accuracy" without
naming the operating point — at the frozen deployment gate it does not.
`docs/NOTES.md`'s "Option B" (dual reporting of identification + verification
numbers) needs this caveat before it goes into a thesis section.

### Writing a new protocol variant safely

1. Name it for the question it actually answers (Sec 4 table) — don't call a
   genuine-only tool "verification."
2. Reuse `stable_rng` and the manifest loaders
   (`load_split_manifest`/`load_probes_from_manifest`/`load_gallery_from_manifest`
   in `accuracy_ratio_hybrid.py`) — don't re-seed or hand-roll dataset
   loading; that breaks cross-script comparability.
3. Keep `assume_cropped=False` (Sec 3) unless deliberately reproducing the
   full-frame path.
4. If you introduce a NEW way of computing an LBPH distance, spot-check it:
   take one (gallery, probe) pair, compute the distance your new way, and
   compare against `LBPHAdapter.score(sample).all_distances[person]` from an
   existing enrolled model. They must match to float precision —
   `predict_collect()`'s per-label distance doesn't depend on how many other
   labels are in the model, so a correct new codepath reproduces the
   N-gallery number exactly on a throwaway 1- or 2-class model.
5. Document what a detection miss does to EACH side of a pairwise decision —
   genuine and impostor are not symmetric under a strict no-face policy (a
   faceless probe can still count as a genuine reject, but has no embedding
   to test against anyone, so it must be excluded from the impostor/FAR
   denominator rather than silently dropped from both).
6. Report GAR, FAR, and Accuracy@operating-point together, never Accuracy
   alone — it hides which of GAR/FAR is doing the work.

---

## 5. Where things live

- `classical-cv/src/hybrid/thresholds.json` — the ONE deployed threshold source (Sec 1).
- `classical-cv/src/hybrid/recognizer.py` — `LBPHAdapter`, `SFaceAdapter`, `HybridRecognizer`, `detect_sample`.
- `classical-cv/src/benchmark/accuracy_ratio_hybrid.py` — identification / transform-sensitivity (Sec 4).
- `classical-cv/src/benchmark/accuracy_ratio_verification.py` — 1:1 pairwise verification (Sec 4).
- `classical-cv/scripts/pipeline/run_lfw2_robustness.py` — parallel harness + LFW2 enrollment, identification path only.
- `classical-cv/src/benchmark/modifications.py` — the 41-mod suite, `stable_rng`, `DL41_TIER_MAP`.
- `classical-cv/data/splits/lfw_ident_split_seed42.json` — the gallery/probe-disjoint manifest (5,749 identities, 1,680 probes).
- `docs/experiments/IDENTIFICATION_VS_VERIFICATION.md` (workspace root, NOT inside `classical-cv/` — see Sec 0) — the original protocol-confound hypothesis (2026-08-01; superseded in part by Sec 4).
- `docs/experiments/standalone_lbph_robustness/THRESHOLD_CHANGE.md` (workspace root) — the identification-side numbers Sec 4 was checked against.
- `docs/NOTES.md` (workspace root) — open reporting decisions; Sec 4's caveat applies directly.
- `reports/benchmark/accuracy_ratio_verification_smoke20.{json,md}` + `outputs/benchmark/accuracy_ratio_verification_smoke20_pairs.csv` (inside `classical-cv/`) — the 2026-08-02 run backing Sec 4.
- Claude-Code skills this file mirrors: `.claude/skills/cv-workspace-map/SKILL.md`, `.claude/skills/robustness-protocol-map/SKILL.md` (both workspace root), `classical-cv/.claude/skills/cv-repo-map/SKILL.md`.
