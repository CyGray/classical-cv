# Classical CV Track — Comprehensive Status & Audit

**Date:** 2026-06-09 · **Scope:** LBPH, Eigenfaces, Fisherfaces (recognition + independence) ·
**Author:** audit pass over current `master` (read-only verification, no retraining)

This document is the honest current state of the classical track: what is implemented, what is
*validated* vs merely *run*, what we got right, what we got wrong (including a correction to my own
first-pass diagnosis), and what to do before each deadline. All numbers were read from current files
or recomputed directly; anything never validly measured is marked **NOT VALIDATED**.

---

## 0. TL;DR

- **All three pipelines run end-to-end** through `main.py` (train → evaluate → independence). The
  plumbing, launcher, dataset-combo bookkeeping, and a genuinely thoughtful independence + failure-check
  analysis already exist. This is a solid base.
- **No trustworthy *recognition* number exists yet for any of the three on a clean held-out La Salle
  split.** Every committed "100 %" is an artifact (train==test leakage, or all-unknown rejection). The
  one honest classical recognition run (Fisherfaces, 23.2 %) is detection-degraded and on a now-swapped
  split.
- **The data is fine.** The alarming "distance 0.0 between two identities" is **not** a duplicate image —
  it is a **min‑max normalization floor** (earlier code) and, for Fisherfaces, a **singular-matrix
  collapse** from 1-image-per-class LDA. Raw chi² minimum is 20.89; the La Salle train/test split is
  image-disjoint. *(I initially mis-flagged this as a data-integrity problem — corrected in §9.)*
- **The independence threshold method does not yet match the spec.** Scripts emit percentile candidates
  (p01/p05/p10), not the spec's rank-based "k-th error pair" (8th for La Salle, 331st for LFW).
- **Footprint is the classical track's real constraint.** LBPH is the most *robust* (best impostor
  separability) but the *heaviest* by far (1–3.8 GB model, ~64 KB feature → fails the <1 KB budget).
  Fisherfaces/Eigenfaces are tiny (8–82 MB, <1 KB feature).

---

## 1. Targets — and a mismatch to flag

Two different target sets are in play:

| Source | Accuracy | Speed | FAR/FRR | Feature |
|---|---|---|---|---|
| Internal `docs/report_docs/GOAL.md` | "100 % on La Salle" | **≥ 3 FPS** | — | — |
| Project spec (current) | TAR 90–95 % | **≥ 30 FPS**, < 100 ms | FAR < 0.01 % (100 ppm), FRR 1–5 % | **< 1 KB** |

The internal goal ("100 % @ ≥3 fps") is far laxer than the spec (10× the FPS, a feature-size budget, and
a verification FAR/FRR framing). It also has a trap: **"100 %" is trivially reachable by train==test
leakage** — which is exactly what one committed result did. We should retire the "100 %" framing and
evaluate against the spec's TAR/FAR/FRR.

---

## 2. The "zero-distance" question — RESOLVED (no data problem)

This caused real concern, so here is the complete reconciliation:

- **What was seen:** `outputs/lbph/independence_test_light_front/summary.json` shows
  `Kenlie_John_Maghari` vs `Yuan_Paulo_Sebastian_Belen` at **normalized distance 0.0**.
- **Why (LBPH/Eigenfaces):** earlier code used **min‑max normalization** → the smallest distance maps to
  0.0 *by construction*, for any data. The **current** `*_light_front.py` scripts use **max‑only**
  normalization (`100*raw/dmax`; `dmin` is computed but unused) → the minimum maps to ~73.74 instead,
  which is what `independence_test/DOC.md` reports. Same data, different scale.
- **Why (Fisherfaces):** a genuine **singular-matrix collapse**. LDA with **one image per identity** has
  zero within-class scatter → non-invertible → 0.0 between distinct identities. `independence_failure_check/`
  already diagnosed this correctly (Multi-Image test: 0.0 at 1 image → recovers with ≥3).
- **Verification on current data:** recomputing the real pipeline gives **raw chi² min = 20.89**
  (Maghari/Belen), **0 exact-zero pairs, 0 identical feature rows**, no decoded-pixel or post-preprocess
  duplicates (336 imgs, all 100×100). `collapse_aggregated.json` independently confirms 20.89.

**Conclusion:** the database is clean. The artifact is a normalization/algorithm property, not a
duplicate or mislabel. **Action is to standardize normalization and regenerate the stale summary, not to
touch data.**

---

## 3. Data & dataset plumbing — current state

- **La Salle (`data/lasalle_db1_processed`):** 28 identities × 12 images (poses ×2 lighting:
  `{dark,light}_{front,left,right,up,down,name}.jpg`), all pre-cropped to 100×100. Clean.
- **La Salle split (`data/split_backup_before_lfw_20260423_132556`, via `split_lasalle` symlink):**
  28 ids, **train = 10 / test = 2 per identity**, and **filename overlap = ∅ for all 28** → the split is
  **image-disjoint** (leakage check 4a passes for the base split). The 2 test images are
  `dark_name.jpg` + `light_name.jpg`; the other 10 are train.
- **LFW (`data/lfw-dataset`):** exactly **5749 identity folders** → ordered N×(N-1) = **33,045,252**
  (this is the exact number the spec's LFW threshold assumes).
- **Symlink swap mechanism:** `data/split` is the *active* split; `split_lfw → data/split`,
  `split_lasalle → split_backup_…`. **Right now `data/split` = LFW** (train folders are LFW celebrities,
  not La Salle). The launcher's dataset manager swaps these. **Consequence:** committed reports were
  produced against *different* underlying datasets at different times; you cannot tell which split a
  report used without the symlink state at run time. **Pin/record the active target per report.**
- **Gap:** the base **split-creation script is not in the repo** (only `augment_split_light_medium.py`,
  which *consumes* an existing split and correctly augments per-split, so augmented copies of a train
  image cannot leak into test — check 4b passes *given* a clean base split).

---

## 4. Script-by-script state

| Script | State | Notes |
|---|---|---|
| `src/lbph/{trainer,evaluate,preprocess,detect}.py` | **Works** | Haar→eye-align→equalize→resize 100×100. Trainer always folds in augmented split unless disabled. |
| `src/lbph/independence_test.py` (plain) | **Stale/buggy** | defaults to **raw** `lasalle_db1` with `ASSUME_INPUTS_ARE_CROPPED=True`; summary omits `comparison` block and mislabels `selected_identities`. |
| `src/lbph/independence_test_light_front.py` | **Works (canonical)** | one image/identity, N×(N-1) ordered, max-norm, percentile thresholds; has streaming/segmented LFW path. |
| `src/eigenfaces/{trainer,evaluate,detect}.py` | **Works** | Haar **detect-or-fallback** (no eye-align); `--assume-processed-are-cropped` bypasses detection. |
| `src/eigenfaces/independence_test*.py` | **Works, minor bug** | PCA fine on 1 image/identity; `selected_identities` count bug (`len(all_runs_records[0][0])`). |
| `src/fisherfaces/{trainer,evaluate,detect}.py` | **Works** | same eval shape as Eigenfaces. |
| `src/fisherfaces/independence_test*.py` | **Runs but ill-posed at 1 img/id** | LDA singular-matrix collapse (documented). Needs ≥2 imgs/identity to be meaningful. |
| `src/independence_common.py` | **Works** | shared train→extract→pairwise; `normalize_distances_0_100` is **max-only**. |
| `src/reporting/identity.py` | **Works** | `attach_entity_identity` / `build_dataset_profile` give the shared `entity_key` schema. |
| `main.py` launcher | **Works, sophisticated** | dataset prompts, auto artifact slugs, duplicate-combo warnings, LFW segmenting. Only training/eval/light-front get preset args; the *plain* independence action runs bare defaults. |
| `augment_split_light_medium.py` | **Works, leakage-safe** | augments `train/`→`train/`, `test/`→`test/` separately. |
| `independence_failure_check/*` | **Works + self-critical** | collapse/multi-image/regional/occlusion suite; reports correctly flag their own apples-to-oranges magnitude comparisons. |

---

## 5. Recognition results — VALIDATED vs NOT

| Report | Dataset | Number | Verdict |
|---|---|---|---|
| `lbph_eval.json` | `lasalle_db1_processed` (train==eval) | 100 % @ all thresholds, 0 unknowns | **INVALID — train==test leakage.** Model trained on processed incl. these images. |
| `lbph_eval_entity_check.json` | `split/test` (then = LFW) | "100 %"/420 | **INVALID — `known_total=0`.** All test ids unknown to the model → 100 % *rejection*, not recognition. |
| `eigenfaces_eval.json` | `lfw-dataset` | 0 % (13,233 skipped unseen) | **INVALID — identity mismatch.** Model labels ≠ eval ids. |
| `fisherfaces_eval.json` | `split/test` (La Salle) | **23.2 %** (det 12 / fallback 44 of 56) | **Honest but degraded** (Haar failed on most test imgs) and on a now-swapped split; report also lacks the `entity_key` block (stale). |

**Bottom line: no model has a valid clean-split recognition score.** The leakage is in the *runs* that
pointed at `lasalle_db1_processed` for both train and eval — not in the split itself.

---

## 6. Independence test & threshold — methodology status

- **Inter-identity design is correct:** one image/identity, N×(N-1) ordered comparisons, self-comparison
  excluded; La Salle = 28×27 = **756** ✓.
- **Documented results** (`independence_test/DOC.md`, max-normalized): LBPH min **73.74** / p05 79.82;
  Eigenfaces min 44.35 / p05 54.49; Fisherfaces min 51.72 / p05 58.70 → **LBPH has the widest impostor
  margin** (best for low FAR), holistic methods overlap more.
- **Threshold method does NOT match spec (highest-impact gap for 7/15).** Spec = rank-based: La Salle
  threshold = distance of the **8th** error pair (8/756 ≈ 10⁴ ppm); LFW = **331st** over **33,045,252**
  ordered (≈10 ppm). Code instead emits **percentile** candidates (p01/p05/p10/p25, mean−1σ). At p01 the
  La Salle run happens to give 8/756, but that's coincidental, not the rule.
- **LFW path shape differs:** the streaming multiprocess worker counts **unique pairs C(N,2)** (≈16.5 M,
  half of 33 M) and supports identity caps; it won't reproduce 33,045,252 ordered or a 331st-pair
  threshold without rework. (Also: the `workers==1` streaming branch writes N−1 entries/row into a
  C(N,2)-sized buffer → would `IndexError`; default `workers=4` avoids it.)
- **Normalization is inconsistent across artifacts** (min‑max in older outputs, max‑only in current
  scripts; `dmin` left as dead code). This makes cross-artifact/cross-algorithm distance numbers
  non-comparable until standardized.

---

## 7. Spec compliance (footprint / speed)

| Target | LBPH | Eigenfaces | Fisherfaces |
|---|---|---|---|
| Feature < 1 KB | ❌ ~**64 KB** (8×8×256 float) | ✅ ≤50 floats (~0.4 KB) | ✅ ≤(classes−1) floats (~0.2 KB) |
| Model file | ❌ **1.06 GB** (proc+l+m), **3.79 GB** (LFW); 42 MB (proc only) | ⚠️ 16 MB (La Salle) / 82 MB (LFW) | ✅ **8.2 MB** |
| Live FPS (desktop loop) | 19.9 | **29.0** | 27.8 |
| ≥30 FPS / <100 ms | not met | ~met | ~met |
| TAR/FAR/FRR | NOT VALIDATED | NOT VALIDATED | NOT VALIDATED |

- LBPH model size scales with #training images (it stores every histogram) → augmentation explodes it to
  multi-GB. Its `predict` also compares against all stored histograms → slowest classical (19.9 fps).
- **The FPS gap is a detection problem, not a recognizer problem.** Classical `predict` is sub-ms; the
  live loop is bottlenecked by Haar detection (shared pipeline). Relevant to the **6/16 detection lock**.
- **Lightest for the Pi port: Fisherfaces (8 MB, <1 KB feature), then Eigenfaces.** LBPH cannot meet the
  feature-size budget as-is.

---

## 8. What we did RIGHT

- End-to-end, launcher-driven pipelines for all three with consistent preprocessing and reproducible
  artifact naming; dataset-combo + duplicate-run guards in `main.py`.
- A correct inter-identity independence design (N×(N-1), self-excluded, 756 for La Salle).
- A **leakage-safe augmentation** script (per-split augmentation).
- A genuinely rigorous **failure-check suite** that found the Fisherfaces 1-image LDA collapse **and**
  honestly documented the limits of its own magnitude comparisons.
- A clean, image-disjoint La Salle train/test split exists (in the backup target).
- Shared `entity_key`/`dataset_profile` reporting scaffold to keep cross-dataset runs from mixing.

## 9. What we did WRONG / risks (ranked)

1. **Leakage in the headline LBPH run** (train==eval on `lasalle_db1_processed`) produced an illusory
   100 %. No valid held-out recognition score exists for any model.
2. **Threshold methodology not implemented to spec** (percentile vs rank-based 8th/331st). This is the
   core of the 7/15 deliverable.
3. **Dataset state is fluid (symlink swap)** and the base split-creation script is missing → reports
   aren't reproducible without recording the active target.
4. **Two report schemas** (LBPH `overall_accuracy_percent`+`known_vs_unknown`+`data_hygiene` vs
   Eigen/Fisher `hit_rate_percent`+`skipped_unseen_identity`); some committed reports are stale (Fisher
   lacks the `entity_key` block).
5. **Normalization inconsistency** (min-max vs max-only) across artifacts/scripts.
6. **Fisherfaces independence at 1 image/identity is ill-posed** (must use ≥2 imgs/id).
7. **Detection fallback** (44/56 on Fisherfaces eval) silently feeds full frames to the recognizer,
   depressing accuracy — a preprocessing-contract issue to settle before 6/16.
8. **Docs/README aspirational** ("100 % @ ≥3 fps"), inconsistent with the spec.

### 9b. Correction to my own first-pass diagnosis (transparency)
My initial audit listed "duplicate/mislabeled images in `lasalle_db1_processed`" as a high-priority
data-integrity issue, citing the 0.0 distance. **That was wrong.** The 0.0 is a min‑max normalization
floor (LBPH/Eigen) and a singular-matrix collapse (Fisherfaces 1-image LDA); the DB is clean (raw min
20.89, no duplicates). I had relied on a saved summary file; direct recomputation corrected it. No data
cleaning is needed.

---

## 10. Recommendation for the hybrid (caveated)

- **For impostor robustness / low FAR (the gate's core risk): LBPH is the strongest classical** — widest
  inter-identity margin (min 73.74 vs 44.35 / 51.72). This is the team's documented pick and it directly
  serves FAR < 0.01 %.
- **For the Pi footprint budget: LBPH is the worst** (multi-GB model, 64 KB feature → fails < 1 KB);
  **Fisherfaces/Eigenfaces fit easily.**
- **For accuracy: undecided** — needs one clean held-out La Salle evaluation (none valid today).
- **Net:** treat the choice as *separability (LBPH) vs footprint (Fisher/Eigen)*. Decide based on how the
  hybrid uses the classical signal: if it's a verification/gating score where a per-identity 64 KB
  template is acceptable, LBPH; if the Pi feature/model budget is hard, Eigenfaces/Fisherfaces (after the
  ≥2-image fix and a clean eval). **Do not finalize until all three have a valid ID + TAR@FAR number on
  the clean split.**

---

## 11. What we can do next (mapped to deadlines)

**This week — before the 6/16 preprocessing lock**
- Standardize normalization (pick max-only *or* min-max, apply everywhere) and **regenerate** the stale
  independence summary on current data.
- Settle the classical **preprocessing contract** (cropped+aligned face size/equalization) so the locked
  detector reflects what classical needs — the Fisherfaces 44/56 fallback shows the current Haar path is
  too lossy on La Salle.
- **Pin the active La Salle split** and record the dataset target in every report.

**By 6/30 — recognizer selection (metric: both ID + TAR@FAR, confirmed)**
- Produce one clean held-out La Salle evaluation for all three on the *same* split + preprocessing +
  unified schema (`attach_entity_identity` everywhere).
- Report (a) closed-set identification hit-rate and (b) verification **TAR @ spec FAR** with FRR; select
  on footprint + validated accuracy.

**By 7/15 — independence test + threshold (scope: La Salle now, LFW path ready, confirmed)**
- Implement the **rank-based k-th-error-pair** threshold (La Salle = 8th/756; LFW = 331st/33,045,252,
  ordered, no identity cap). Build the ordered full-LFW path now but keep its (long) execution **gated**.
- Re-run La Salle (756) independence + threshold; record threshold and resulting FAR.
- Use ≥2 images/identity for the **Fisherfaces** independence run to avoid the LDA collapse.

---

## 12. Appendix — key verified numbers & sources

- Feature dim LBPH = 16384 (recomputed); model sizes from `models/{lbph,eigenfaces,fisherfaces}/*.yml`.
- FPS from `reports/benchmark/live_fps/aggregate_summary.json`.
- Recognition reports: `reports/evaluation/{lbph,lbph_eval_entity_check,eigenfaces,fisherfaces}_eval.json`.
- Independence: `outputs/lbph/independence_test_light_front/summary.json` (stale min‑max),
  `docs/report_docs/independence_test/DOC.md` (max-norm), `independence_failure_check/collapse_aggregated.json`.
- Split layout: `data/split_backup_before_lfw_20260423_132556/{train,test}` (28 ids, 10/2, overlap ∅);
  `data/lfw-dataset` = 5749 ids.
- Related prior docs: `docs/report_docs/GOAL.md`, `independence-algo-report.md`,
  `independence_failure_check/DOC.md`, root `FULL_TECHNICAL_REPORT.md`, `RESULTS_DISCUSSION_CONCLUSION.md`.
