# Classical Track — Spec-Sheet Compliance Comparison

**Date:** 2026-06-11 · **Scope:** LBPH / Eigenfaces / Fisherfaces vs the project spec sheet
(BRIEFING.md §6) · **Protocol:** leakage-free clean loop — train `data/split_lasalle/train`
(28 ids × 10), evaluate held-out `data/split_lasalle/test` (28 × 2), impostors = full LFW
(13,149 Haar-cropped probes → FAR resolvable to 76 ppm). All numbers are from actual runs
(provenance in §6); nothing is extrapolated.

---

## 1. Targets

| Metric | Spec sheet | Stage-1 (CV-based) plan |
|---|---|---|
| TAR (accuracy) | 90–95 % | accuracy ↑ 90 % |
| FAR | < 0.01 % (100 ppm) | — |
| FRR | 1–5 % | — |
| Latency (capture → result) | < 100 ms | — |
| Speed | ≥ 30 fps | 1 face/s |
| Feature vector | < 1 KB | — |

The spec sheet is the Stage-3 (hybrid, Pi 5, real-time) bar; the staged master plan only asks
Stage 1 for accuracy ↑90 % at 1 face/s. Both views are scored below.

---

## 2. Spec scorecard (deployed/unedited recognizers)

LBPH runs with **Tan-Triggs** illumination normalization (its measured-best preprocessing);
Eigen/Fisher run with histogram equalization (their measured-best). Thresholds are calibrated
at the spec FAR budget against 13,149 LFW impostors.

| Spec metric | Target | **LBPH (Tan-Triggs)** | Eigenfaces | Fisherfaces |
|---|---|---|---|---|
| TAR @ FAR ≤ 100 ppm | 90–95 % | **98.21 % — PASS** | 23.21 % — FAIL | 10.71 % — FAIL |
| FAR achieved | < 0.01 % | **0.0076 % — PASS** | 0.0076 % (TAR collapses) | 0.0076 % (TAR collapses) |
| FRR @ that FAR | 1–5 % | **1.79 % — PASS** | 76.79 % — FAIL | 89.29 % — FAIL |
| Rank-1 (closed-set, held-out) | (90–95 % read) | **100 %** | 75.0 % | 66.1 % |
| EER (context, no target) | — | **0.07 %** | 31.8 % | 35.7 % |
| Accuracy Ratio (41-mod suite) | (robustness view) | **85.4 %** | 47.7 % | 30.5 % |
| Feature vector | < 1 KB | 64 KB — **FAIL** (960 B option: §4) | 1,120 B — FAIL (400 B option: §4) | **108 B — PASS** |
| Model / template store | (Pi context) | 33.3 MB | 82.6 MB | 8.2 MB |
| Speed (desktop live loop) | ≥ 30 fps | 19.9 — FAIL¹ | 29.0 — borderline¹ | 27.8 — borderline¹ |
| Speed (Stage-1: 1 face/s) | ≥ 1 fps | **PASS** | **PASS** | **PASS** |
| Latency | < 100 ms | not instrumented² | not instrumented² | not instrumented² |
| Deployable threshold (predict scale) | — | **73.0** | 4,308 | 738 |
| Independence threshold (La Salle DB1, 8th pair, raw) | — | 21.35 (chi², TT scale) | 8,098.5 | 5,446.5 |

¹ FPS predates the Tan-Triggs switch (logged 2026-04/05 runs) and the bottleneck is the shared
Haar detector, not the recognizer; re-measure with a webcam run before quoting.
² Best available estimate: ≈ 1000/FPS ≈ 50 ms per processed frame on desktop, which suggests
< 100 ms is reachable, but capture→result latency was never separately instrumented.

---

## 3. Discussion

**Why two accuracy readings, and which one counts.** Closed-set rank-1 ("is the nearest
enrolled identity the right one?") ignores impostors entirely; a gate cannot. The deciding
metric is verification TAR at the FAR budget, which the independence test fixes — this is the
spec's own framing ("AR at a pre-determined false-positive rate"). On that metric only LBPH
survives: holding FAR at 76 ppm costs it 1.79 % of genuine attempts, while Eigenfaces loses
77 % and Fisherfaces 89 %. The 41-modification Accuracy Ratio tells the same story under
capture corruptions (85 % vs 48 % / 31 %).

**LBPH's pass is a preprocessing result.** With plain equalization LBPH was at TAR 96.4 % /
EER 3.6 %; Tan-Triggs (gamma → difference-of-Gaussians → contrast equalization — designed for
exactly LBP-type features) lifts it to 100 % rank-1 / EER 0.07 %, and the gain holds against
13k impostors and the 41-mod suite. Eigen/Fisher get *worse* under Tan-Triggs (it removes the
low-frequency content their subspaces encode) — there is no shared "best" preprocessing, which
is why the per-family contract lives in `RecognizerSpec`.

**Why the training set stays un-augmented (and why not "processed + aug_light + aug_mid").**
Training on the full processed folder is the retired leakage recipe: it contains all 12 images
per identity, including the 2 held out as test, and LBPH stores a template per training image —
the audit marks that run "INVALID — train==test leakage" (the deprecated `*-plm` models were
exactly processed + light + medium). The leakage-free version of the idea — split first, then
augment the train side only — *was* trained and measured (`lasalle_clean_aug_light`): LBPH
drops from 100 % to 98.2 % rank-1 and its single error flips from a safe below-threshold
rejection to a **wrong-identity accept at the deployed threshold** (72.9 < 73), with the model
tripling to 101 MB; Fisherfaces drops 66.1 % → 60.7 %; Eigenfaces gains 2 probes (within the
±1.8 %-per-probe noise) at 3× model size. Mechanistically this is expected: these recognizers
do not learn invariance from augmented examples the way a CNN does — LBPH prediction is
nearest-neighbor over stored templates, so augmented copies are just noisier gallery entries,
and Tan-Triggs already neutralizes the brightness/contrast part of what the augmentation
simulates. The medium tier (occlusion, motion blur, σ 10–20 noise) is strictly harsher and was
never trained on; its job — like the light tier's — is **test-side**: they feed the
41-modification robustness suite. Canonical training data therefore remains
`data/split_lasalle/train` as-is.

**Eigenfaces/Fisherfaces cannot be configured out of failure.** Three sweeps say so:
(a) component caps and CLAHE/Tan-Triggs (config sweep), (b) matcher upgrades — dropping leading
PCA components, Mahalanobis whitening, cosine distance, centroid galleries (variant benchmark),
and (c) the modification suite. Best variant deltas: Fisherfaces + centroid gallery raises
TAR@1.058 % from 35.7 % → 41.1 % (and its gallery shrinks to 3 KB); a 100-component Eigenfaces
matches the full model's TAR with a 400 B (< 1 KB) feature. Both remain ~50 points below spec.
Their genuine/impostor distance distributions overlap intrinsically on this data — more
training images per identity is the only plausible lever left, and the dataset is fixed.

**The feature-size budget is LBPH's real cost.** The 64 KB histogram is inherent to the
algorithm (8×8 cells × 256 bins × float32). The `docs/SUGGESTION.md` route — keep only the
important parts — was implemented and measured (§4): restricting to eyebrow/eye/nose/mouth grid
cells *does* beat unrestricted selection at equal budget (TAR 87.5 % vs 73.2 % at 960 B), so
the suggestion is directionally right; but the best < 1 KB template still gives up ~12 points
of TAR at 1 % FAR and ~21 points at 100 ppm versus the full histogram. Compression is a real
trade, not a free win.

**Speed and latency are open, not failed.** The classical predict is sub-millisecond; Haar
detection dominates. The live loops support detection downscaling, detect-every-N and (LBPH)
optical-flow tracking — a tuned webcam re-run is needed for honest post-Tan-Triggs FPS, and a
simple capture→result timestamp would close the latency line. On the staged plan, Stage 1's
1 face/s is met by all three with an order of magnitude to spare.

**Robustness weak spots (from the AR suite).** LBPH's failures concentrate in heavy Gaussian
noise (AR 47.8 %), motion blur (68.5 %) and strong brightness drops (73.7 %); occlusion,
gamma and moderate lighting shifts barely dent it (≥ 97 %). Deployment mitigations: favor
sensor exposure/gain control and a steady mount over algorithmic fixes.

**Threats to validity.** 56 genuine probes ⇒ ~1.8 % TAR granularity (the AR suite's 2,296
probes back the headline up at higher resolution); the 100 ppm FAR claim rests on 13,149
impostors (floor 76 ppm) — the gated full-LFW independence run (33 M ordered comparisons,
331st error pair) is the protocol-grade confirmation; the 41-modification list is a documented
stand-in pending the team's official list; FPS numbers are stale; results are one split — a
k-fold over pose choices would tighten the claim.

---

## 4. Feature-size / accuracy options (unedited vs variants)

Full table: `reports/benchmark/variant_comparison.md` (all 19 LBPH + 49 Eigen + 16 Fisher
rows). These are **opt-in backups, not replacements** — selected rows:

| Family | Option | Feature B | Rank-1 | TAR@1.058 % | TAR@100 ppm | EER |
|---|---|---:|---:|---:|---:|---:|
| lbph | **unedited (64 KB, Tan-Triggs)** | 65,536 | **100 %** | **100 %** | **98.2 %** | **0.07 %** |
| lbph | top-960 landmark cells, uint8 (best < 1 KB) | **960** | 91.1 % | 87.5 % | 76.8 % | 12.5 % |
| lbph | top-480 all cells, uint8 | **480** | 91.1 % | 75.0 % | 35.7 % | 12.5 % |
| eigenfaces | unedited (280 comps) | 1,120 | 75.0 % | 53.6 % | 23.2 % | 31.8 % |
| eigenfaces | 100 comps (same TAR, < 1 KB) | **400** | 71.4 % | 53.6 % | 23.2 % | 33.9 % |
| fisherfaces | unedited (27 comps) | 108 | 66.1 % | 35.7 % | 10.7 % | 35.7 % |
| fisherfaces | + centroid gallery (best variant) | 108 | 69.6 % | **41.1 %** | 12.5 % | 32.1 % |

Sanity check: the custom full-histogram matcher reproduces the unedited LBPH numbers exactly
(same TAR/EER), so the variant harness is faithful to the deployed representation.

Other compression ideas not yet implemented (next candidates if < 1 KB becomes a hard
requirement for the classical leg): uniform-LBP binning (256 → 59 bins, ~4× smaller before
selection), coarser grids (4×4), and product quantization of the selected dimensions.

---

## 5. Conclusion

1. **Recognizer selection (6/30): LBPH with Tan-Triggs, unedited.** It is the only classical
   model that passes the spec's accuracy block — TAR 98.21 % / FRR 1.79 % at FAR 76 ppm,
   EER 0.07 %, AR 85.4 % — and it also clears Stage 1's accuracy/speed bar outright.
2. **Thresholds (7/15 input):** deployable predict-scale threshold **73.0** at the 100 ppm
   spec budget (76.85 at the La Salle independence operating point, 1.058 %); independence
   feature-scale threshold 21.35 (8th error pair, 756 comparisons). The LFW 331st-pair run is
   built and gated; execute it to certify the 10 ppm operating point.
3. **Eigenfaces and Fisherfaces should not advance** as verification gates: no preprocessing,
   component, or matcher configuration brings them within ~50 points of the TAR target.
   Fisherfaces' 108 B feature is not worth a 89 % FRR.
4. **Feature budget:** carry the 64 KB LBPH template into the hybrid as the accuracy
   reference, with the **960 B landmark-uint8 compact template as the documented Pi-budget
   fallback** (cost: −21 pts TAR at 100 ppm). If the hybrid design only consumes the classical
   *score* (not the stored template), the 64 KB number never ships to the Pi at all — settle
   this with the team before optimizing further.
5. **Before the hybrid handoff:** re-measure live FPS (post-Tan-Triggs) and instrument
   capture→result latency; run the gated full-LFW independence pass; confirm the official
   41-modification list.

---

## 6. Provenance

| Artifact | Source |
|---|---|
| Rank-1 / hit@thr / footprint | `reports/evaluation/{lbph,eigenfaces,fisherfaces}_eval[_aug_light].json` |
| TAR / FAR / FRR / EER | `reports/benchmark/tar_at_far.{json,md}` (13,149 LFW impostors) |
| Accuracy Ratio (41-mod) | `reports/benchmark/accuracy_ratio.{json,md}` |
| Variant comparison | `reports/benchmark/variant_comparison.{json,md}` |
| Config sweep (Tan-Triggs evidence) | `reports/benchmark/classical_config_sweep.{json,md}` |
| Independence thresholds (La Salle DB1) | `reports/benchmark/independence_thresholds.{json,md}` |
| Independence thresholds (LFW smoke) | `reports/benchmark/independence_thresholds_lfw.{json,md}` |
| Live FPS (stale, pre-Tan-Triggs) | `reports/benchmark/live_fps/aggregate_summary.json` |
| Spec comparison table (machine-readable) | `reports/benchmark/classical_comparison.{json,md}` |
