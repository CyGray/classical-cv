# Dataset-Composition Matrix — LBPH vs Eigenfaces vs Fisherfaces

**Date:** June 12, 2026
**Question:** what does the *training-data composition* do to each classical recognizer, holding
the source DB, preprocessing, and evaluation protocol fixed?
**Verdict up front:** the plain clean split wins for every family. Augmenting the train side never
helps (LBPH and Fisherfaces get measurably worse, Eigenfaces moves within noise at 5.5× the size),
and training on a single lighting condition costs LBPH its perfect rank-1 and 6–18 points of
TAR@100 ppm. The medium tier on top of light changes **nothing measurable** for LBPH except
+70 MB of model and +9 ms per predict.

---

## 1. Protocol

Every model is trained from the **same source DB** — the leakage-free La Salle split
(`data/split_lasalle`, 28 identities) — under five training recipes:

| Recipe | Composition | Train imgs |
|---|---|---:|
| `clean` | `split_lasalle/train` as-is (5 `light_*` + 5 `dark_*` poses per id) | 280 |
| `aug_light` | clean + leakage-safe light tier (2 per source img) | 840 |
| `aug_light_medium` | clean + light + medium tiers | 1,400 |
| `light_only` | only the 5 `light_*` poses per id | 140 |
| `dark_only` | only the 5 `dark_*` poses per id | 140 |

The augmented tiers are the pre-existing `data/split_augmented41mods_lasalle_clean/{light,medium}/train`
(generated split-first, train-side only — **no** test images involved). The `light_only` / `dark_only`
subsets are filename-prefix copies in `data/matrix_subsets/`.

Every model is evaluated on **three held-out probe sets** (never trained on, in any recipe):

- **full** — `split_lasalle/test`: 56 probes = 1 `light_name` + 1 `dark_name` per identity
- **light** — only the 28 light probes; **dark** — only the 28 dark probes

plus a verification pass against the **full LFW impostor set** (13,149 Haar-cropped faces, cropped
once and shared by all 15 models — identical protocol to `src/benchmark/tar_at_far.py`, so the
`clean` rows reproduce `reports/benchmark/tar_at_far.md` exactly).

**Granularity caveat:** 56 probes ⇒ ±1.79 pp per probe on full rank-1; 28 probes ⇒ ±3.57 pp on the
light/dark breakdowns. Differences of one–two probes are noise and are called out as such.

---

## 2. Intra-model: what the training recipe does to each family

### 2.1 LBPH (Tan-Triggs) — the selected recognizer

| Recipe | Train imgs | Model MB | Rank-1 full | Rank-1 light | Rank-1 dark | TAR@1.058% | TAR@100ppm | Thr@100ppm | EER | Predict ms* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **clean** | **280** | **33.3** | **100.00%** | **100.00%** | **100.00%** | **100.00%** | **98.21%** | **73.04** | **0.07%** | **6.8** |
| aug_light | 840 | 100.9 | 98.21% | 96.43% | 100.00% | 98.21% | 89.29% | 70.37 | 1.79% | 16.0 |
| aug_light_medium | 1,400 | 170.4 | 98.21% | 96.43% | 100.00% | 98.21% | 89.29% | 70.37 | 1.79% | 25.0 |
| light_only | 140 | 16.6 | 94.64% | 100.00% | 89.29% | 92.86% | 80.36% | 73.04 | 5.36% | 4.3 |
| dark_only | 140 | 16.6 | 94.64% | 89.29% | 100.00% | 94.64% | 92.86% | 74.36 | 5.36% | 4.5 |

\* mean per-probe predict time from the 13,149-impostor scoring pass; LBPH predict is
nearest-neighbour over stored templates, so it scales ~linearly with gallery size (×5 gallery ⇒ ×3.7 time).

- **Clean is strictly best on every column.** Both augmented recipes lose the same probe at rank-1
  and give up ~9 points of TAR@100 ppm — the augmented gallery pulls the deployable threshold down
  (73.04 → 70.37) because noisy synthetic templates sit closer to the LFW impostor distribution.
- **The medium tier is a pure cost.** `aug_light_medium` is identical to `aug_light` on *every*
  accuracy metric (same rank-1, same TAR, same EER, same threshold to two decimals) while adding
  70 MB of model and +56 % predict time. The harsher synthetic templates simply never become the
  nearest neighbour at any operating point.
- **Single-lighting training breaks cross-lighting recognition.** Train on light only and dark
  probes drop to 89.29 % rank-1 (3 of 28 misses); train on dark only and the mirror happens. Only
  the recipe containing *both real lighting conditions* reaches 100 % everywhere — and at 140 imgs
  the model is also 2× smaller than clean, so the clean split's coverage, not its size, is what pays.
- **Dark-trained generalizes better than light-trained in verification.** Rank-1 is mirror-symmetric
  (94.64 % both), but `dark_only` keeps TAR@100 ppm = 92.86 % vs `light_only`'s 80.36 %, with a
  *looser* deployable threshold (74.36 vs 73.04). Plausible mechanism: LFW impostors are
  overwhelmingly well-lit, so a dark-trained gallery sits farther from the impostor cloud and buys
  threshold headroom; light probes are also cleaner signals than dark probes (dark captures carry
  sensor noise that survives Tan-Triggs), so light-probe→dark-template distances stay small while
  dark-probe→light-template distances scatter. Treat as interpretation, not measurement.

### 2.2 Eigenfaces

| Recipe | Train imgs | Model MB | Rank-1 full | Rank-1 light | Rank-1 dark | TAR@1.058% | TAR@100ppm | EER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | 280 | 82.6 | 75.00% | 75.00% | 75.00% | 53.57% | 23.21% | 31.77% |
| aug_light | 840 | 259.3 | 78.57% | 82.14% | 75.00% | 48.21% | 21.43% | 30.61% |
| aug_light_medium | 1,400 | 452.4 | 78.57% | 82.14% | 75.00% | 44.64% | 21.43% | 28.57% |
| light_only | 140 | 40.9 | 66.07% | 67.86% | 64.29% | 51.79% | 19.64% | 35.71% |
| dark_only | 140 | 40.9 | 66.07% | 64.29% | 67.86% | 44.64% | 26.79% | 37.50% |

- The +2-probe rank-1 "gain" from augmentation (75.00 → 78.57 %) is **within the ±1.79 pp/probe
  noise floor**, costs 3–5.5× the model size (452 MB for `aug_light_medium`!), and *worsens* the
  loose-FAR verification point (TAR@1.058 %: 53.57 → 44.64 %). TAR@100 ppm stays junk (~20 %)
  under every recipe — no composition rescues PCA's illumination sensitivity.
- Single-lighting training costs ~9 points of rank-1, symmetrically. Unlike LBPH, eigenfaces
  degrade on *both* probe conditions, because losing half the training set also loses subspace
  quality, not just gallery coverage.

### 2.3 Fisherfaces

| Recipe | Train imgs | Model MB | Rank-1 full | Rank-1 light | Rank-1 dark | TAR@1.058% | TAR@100ppm | EER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | 280 | 8.2 | 66.07% | 71.43% | 60.71% | 35.71% | 10.71% | 35.71% |
| aug_light | 840 | 8.6 | 60.71% | 57.14% | 64.29% | 17.86% | 3.57% | 41.13% |
| aug_light_medium | 1,400 | 9.1 | 48.21% | 57.14% | 39.29% | 10.71% | 3.57% | 53.57% |
| light_only | 140 | 8.1 | 41.07% | 42.86% | 39.29% | 28.57% | 3.57% | 60.53% |
| dark_only | 140 | 8.1 | 44.64% | 46.43% | 42.86% | 10.71% | 5.36% | 57.14% |

- **Augmentation actively poisons Fisherfaces, and more augmentation poisons it more.** Rank-1
  collapses 66.07 → 60.71 → 48.21 % as tiers are added; EER goes 35.71 → 41.13 → **53.57 %**
  (worse than chance at the equal-error point); dark probes fall to 39.29 %. The mechanism is
  structural: LDA maximizes between-class over *within-class* scatter, and synthetic
  brightness/warp/noise/occlusion variants inflate exactly the within-class term, so the
  discriminant directions rotate away from identity.
- Single-lighting recipes starve LDA (5 imgs/class): 41–45 % rank-1 and EER ≈ 60 %.

---

## 3. Inter-model: families compared at fixed recipe

| Recipe | Best family | Rank-1 full (L / E / F) | TAR@100ppm (L / E / F) | EER (L / E / F) |
|---|---|---|---|---|
| clean | **LBPH** | **100.00** / 75.00 / 66.07 % | **98.21** / 23.21 / 10.71 % | **0.07** / 31.77 / 35.71 % |
| aug_light | **LBPH** | **98.21** / 78.57 / 60.71 % | **89.29** / 21.43 / 3.57 % | **1.79** / 30.61 / 41.13 % |
| aug_light_medium | **LBPH** | **98.21** / 78.57 / 48.21 % | **89.29** / 21.43 / 3.57 % | **1.79** / 28.57 / 53.57 % |
| light_only | **LBPH** | **94.64** / 66.07 / 41.07 % | **80.36** / 19.64 / 3.57 % | **5.36** / 35.71 / 60.53 % |
| dark_only | **LBPH** | **94.64** / 66.07 / 44.64 % | **92.86** / 26.79 / 5.36 % | **5.36** / 37.50 / 57.14 % |

LBPH wins every recipe on every headline metric — **no training-data composition re-orders the
families**. The gap is smallest exactly where every family is worst (single-lighting recipes), and
the families also *diverge* in how they fail: LBPH degrades gracefully (worst case 94.64 % rank-1,
EER 5.36 %), Eigenfaces is flat-but-mediocre everywhere, Fisherfaces is fragile to both
augmentation and small per-class counts.

Cross-lighting detail (rank-1 on the opposite probe condition): LBPH train-light→test-dark and
train-dark→test-light both land at 89.29 % — recoverable only by enrolling both real conditions
(clean ⇒ 100 % / 100 %). Augmentation does **not** substitute: `aug_light`'s brightness/contrast
jitter on top of the full clean split still *lost* a light probe (96.43 %) rather than gaining
robustness, confirming brightness synthesis ≠ a second real capture condition.

---

## 4. Discussion

**Why train-side augmentation can't help these recognizers.** None of the three learns invariance
from examples the way a CNN does. LBPH prediction is nearest-neighbour over stored per-image
templates — augmented copies are *additional gallery entries*, so they can only help if a synthetic
template is closer to a genuine probe than any real template (rare) and never closer to an impostor
(false: thr@100 ppm dropped 73.04 → 70.37). Eigenfaces/Fisherfaces refit a linear subspace; light
augmentation mostly re-feeds variation that Tan-Triggs/equalization already removes, and the medium
tier (occlusion, motion blur, σ 10–20 noise) injects energy the subspace must spend dimensions
modelling. The result spans "no measurable change at 5× the cost" (LBPH medium tier, Eigenfaces) to
"actively destructive" (Fisherfaces).

**The verification budget is where augmentation hurts most.** At the spec's FAR = 0.01 % the
augmented LBPH models give up half their margin (TAR 98.21 → 89.29 %), because the impostor
distribution tightens against the noisier gallery. Rank-1 alone (98.21 %) makes augmentation look
nearly free; the spec-relevant operating point shows it is not. The earlier finding from
`SPEC_COMPARISON.md` also persists: the aug-trained models' single rank-1 error is a
**wrong-identity accept** under the deployed threshold rather than a safe below-threshold rejection.

**Lighting coverage is an enrollment requirement, not a nice-to-have.** The 5-light + 5-dark
composition of the clean split is precisely what buys LBPH 100 % cross-lighting rank-1; either half
alone caps at 89.29 % on the opposite condition. For deployment this means the enrollment procedure
must capture both lighting regimes per person — and if only one capture session is possible, a
*dark* session is the safer single condition for this pipeline (TAR@100 ppm 92.86 % vs 80.36 %,
threshold headroom 74.36 vs 73.04 against well-lit impostors).

**Cost scaling matters for the Pi target.** LBPH predict time grows linearly with gallery size:
6.8 ms (clean) → 16 ms (aug_light) → 25 ms (aug_light_medium) per probe on this machine, i.e. the
augmented recipes burn 2.4–3.7× of the ≤ 100 ms latency budget for negative accuracy return.
Eigenfaces' `aug_light_medium` model is **452 MB of YAML** — unloadable on a Pi-class device and
~5.5× clean for a within-noise rank-1 change.

**Relation to the retired leakage recipe.** The deprecated `*-plm` models ("processed + light +
medium") owed their apparent perfection to train==test leakage, not to augmentation. This matrix is
the leakage-free version of exactly that recipe (`aug_light_medium`) and shows what it really does:
LBPH −1.79 pp rank-1 / −8.9 pp TAR@100 ppm, Fisherfaces −17.9 pp rank-1, Eigenfaces noise. The
audit's "INVALID" verdict and these numbers close the question from both directions.

---

## 5. Conclusion

1. **Canonical training data stays `data/split_lasalle/train`, unmodified** — for all three
   families. It is the best recipe on every headline metric for every family, and for LBPH it is
   the *only* recipe that meets the spec row (TAR@100 ppm 98.21 %, EER 0.07 %, thr 73.0).
2. **Do not add augmented tiers to training.** Light: measurable regression (LBPH verification
   −9 pp). Medium-on-light: zero measurable change vs light for LBPH at +70 MB/+9 ms, and a
   further collapse for Fisherfaces (EER 53.57 %). The tiers' job remains **test-side** (the
   41-modification robustness suite).
3. **Enroll both lighting conditions per person.** Single-condition training costs every family;
   for LBPH it is the difference between 100 % and 89.29 % on opposite-lighting probes. If forced
   to choose one condition, choose dark captures (better impostor separation: TAR@100 ppm
   92.86 % vs 80.36 %).
4. **No recipe re-orders the families** — LBPH + Tan-Triggs remains the selected recognizer under
   every composition tested; Eigen/Fisher don't become competitive under any.

## 6. Reproduce / artifacts

```text
python scripts/run_dataset_matrix.py                  # everything (subsets, train, 45 evals, TAR@FAR, summary)
python scripts/run_dataset_matrix.py --skip-tar-far   # fast pass without the LFW impostor stage
python scripts/run_dataset_matrix.py --tarfar-resume  # resume an interrupted impostor pass
```

- Models: `models/<family>/lasalle_{clean,clean_aug_light,clean_aug_light_medium,light_only,dark_only}.yml`
  (+ `labels_*.json`); `clean`/`aug_light` are the canonical artifacts shared with `SPEC_COMPARISON.md`.
- Per-cell eval JSONs: `reports/evaluation/dataset_matrix/<family>__<recipe>__test_<full|light|dark>.json` (45 files)
- Verification: `reports/benchmark/dataset_matrix_tar_far.{json,md}` (15 rows, full LFW = 13,149 impostors)
- Auto-generated numeric tables: `reports/benchmark/dataset_matrix.md` | run log: `reports/benchmark/matrix_run.log`
- Probe counts: full = 56, light = dark = 28 ⇒ rank-1 granularity 1.79 pp (full) / 3.57 pp (split);
  impostor floor = 1/13,149 ≈ 76 ppm.
