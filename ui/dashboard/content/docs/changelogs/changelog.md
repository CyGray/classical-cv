# Changelog

## June 14, 2026 — Hybrid CV + DL gated cascade (LBPH + SFace)

One `HybridRecognizer` that runs an **LBPH fast path** and escalates hard frames
to **SFace** behind a quality/score gate — the gated cascade from
`docs/ARCHITECTURE_IMPLEMENTATION_PLAN.md` (Phases 1–5). Reachable from the
launcher like every other family; live detect shows the CV→DL hand-off on screen.

### NEW: `src/sface/` (SFace wrapper, ported from the DL track)
- `recognizer.py`: `cv.FaceRecognizerSF` over the vendored
  `models/sface/face_recognition_sface_2021dec.onnx` — `alignCrop`→`feature`
  (128-D float32 = **512 B**), the exact `cosine ≥ 0.363 ∧ L2 ≤ 1.128` match rule,
  plus `SFaceGallery` (per-identity mean embedding) and `SFaceFarModel` (empirical
  FAR from the LFW impostor cosines).
- `independence_test.py`: reproduces the DL headline from inside the CV repo —
  **LFW FP = 0.0747%** (24,128 / 32,313,540), DL reference 0.07% → parity PASS.

### NEW: `src/hybrid/` (protocol + gate + fused predict)
- `recognizer.py`: the `Recognizer` protocol, additive **LBPH adapter** (wraps the
  clean-split model + `RecognizerSpec`, no `pipeline.py` change) and **SFace
  adapter**, the shared `FaceSample`/`detect_sample` YuNet front-end, and
  `HybridRecognizer.predict()` with four modes — `cascade` (default), `parallel`,
  `cv_only` (no-accelerator fallback), `dl_only`.
- `quality.py`: blur / low-light / noise / off-pose / small-face probes on the
  crop LBPH already holds (YuNet landmarks for pose).
- `gate.py`: escalate on ambiguous band, near-tie **relative** top-1/top-2 margin,
  or any quality flag (a quality flag overrides a confident LBPH score).
- `calibrate.py` → `thresholds.json`: SFace operating cosines measured from the
  LFW impostors; LBPH gate edges carried from `tar_at_far.md`; quality edges from
  the clean-crop probe distributions — every value measured or provenance-stamped.
- `enroll.py`: builds the SFace gallery from the same crops LBPH trained on and
  **asserts the two label sets match** (two-gallery consistency).
- `evaluate.py` + `src/benchmark/compare_hybrid.py`: fused TAR/FAR/FRR, escalation
  rate, and per-stage latency; hybrid vs LBPH-only vs SFace-only.
- `detect.py`: live gated cascade — YuNet detect + optical-flow tracking +
  temporal voting, deciding-engine/escalated overlay, FPS summary written with
  `algorithm="hybrid"` so `aggregate_live_fps.py` and the Benchmark overview pick
  it up automatically.

### Measured (held-out clean split + LFW impostors)
- **Clean** `reports/benchmark/hybrid_comparison.md`: hybrid rank-1 **100%**, FAR
  **0%**, escalation **25%**, ~**97 fps** (vs SFace-only ~50 fps, LBPH-only ~174 fps).
- **Degraded** `reports/benchmark/hybrid_comparison_degraded.md` (41-mod medium):
  LBPH-only **5.10%** vs hybrid **97.96%** — the gate escalates every degraded
  frame and recovers LBPH's collapse.

### Vendored / launcher
- `models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx` (checksum-matched)
  and `models/sface/` (SFace ONNX + LFW/DB impostor arrays).
- `main.py`: new **Hybrid** group (enroll / evaluate / live detect / calibrate /
  compare) + `MODEL_INFO_CONFIG` + Benchmark-overview row + `fps_algorithm="hybrid"`.

## June 14, 2026

Toggle-able face detector: **YuNet (CNN)** as a drop-in alternative to
**Viola-Jones (Haar cascade)** for the classical recognizers, plus a measured
head-to-head report.

### NEW: `src/classical_faces/detection.py` (detector abstraction)
- One tiny interface — `FaceDetector.detect()/detect_largest()` returning
  `(x, y, w, h)` boxes in full-res coords — with two backends: `HaarFaceDetector`
  (`cv.CascadeClassifier`) and `YuNetFaceDetector` (`cv.FaceDetectorYN`, reusing
  the already-vendored `models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx`).
  Factory `create_face_detector("haar"|"yunet", ...)`. YuNet also exposes a
  confidence score + 5 landmarks.
- Backend resolves: explicit `--detector` flag → `FACE_G3_DETECTOR` env → `haar`.
  Default stays **Haar**, so existing runs reproduce unchanged.

### Wiring (toggle on every classical surface)
- `extract_classical_face` + `pipeline.build_detectors` thread a detector object
  through train / evaluate; the legacy raw-cascade path still works (wrapped into
  a Haar detector internally), so independence-test / sweep / TAR@FAR scripts are
  untouched. New flags: `--detector`, `--yunet-model-path`,
  `--yunet-score-threshold`, `--yunet-nms-threshold` (via `add_preprocess_args`).
- All three live loops (`src/{lbph,eigenfaces,fisherfaces}/detect.py`) take
  `--detector`; YuNet uses the colour frame, Haar the grayscale.
- Reports now record `config.detector_backend` / `detector_detail` and
  `detection.detector_backend` (self-describing; cropped runs record `none`).
- `main.py`: a detector prompt for classical raw/LFW train-eval and live detect,
  and a Benchmark menu entry "compare detectors (haar vs yunet)".

### NEW: `src/benchmark/compare_detectors.py` + `docs/DETECTOR_COMPARISON.md`
- Measures detection rate, false-positive proxy, speed, face-size yield,
  confidence and model footprint; writes
  `reports/benchmark/detector_comparison_<dataset>.{json,md}`.
- Headlines (full report in `docs/DETECTOR_COMPARISON.md`):
  - **La Salle raw (336, controlled):** YuNet **100% detection / 0 false positives
    / 48.6 fps**, vs Haar **86.9% / 43 FPs / 37.2 fps**. YuNet model is ~4× smaller
    (227 KB vs 941 KB).
  - **LFW (600, in-the-wild):** both ≈saturate recall (Haar 98.7%, YuNet 100%);
    YuNet 359 vs 129 fps. YuNet's extra LFW boxes are mostly real bystanders, not
    FPs (controlled La Salle is the clean FP measure).
  - Both clear 30 fps at a 640 px detection size — the detector is **not** the FPS
    bottleneck. The cropped clean-split rank-1 headline is unchanged (it skips
    detection).

## June 12, 2026

Dataset-composition matrix: every classical family trained on five training
recipes from the same DB and compared inter-/intra-model.

### NEW: `scripts/run_dataset_matrix.py` + `docs/DATASET_MATRIX.md`
- One reproducible suite: 3 families (lbph, eigenfaces, fisherfaces) x 5
  training recipes from the leakage-free La Salle split - `clean` (280),
  `aug_light` (840), `aug_light_medium` (1,400), `light_only` (140),
  `dark_only` (140; the light_/dark_ filename-prefix halves, copied into
  `data/matrix_subsets/`). Canonical clean/aug_light models are reused so the
  matrix stays bit-identical with SPEC_COMPARISON.md.
- Every model evaluated on three held-out probe sets (full 56 / light 28 /
  dark 28) -> `reports/evaluation/dataset_matrix/` (45 JSONs), plus TAR@FAR /
  EER vs the full LFW impostor set (13,149 faces, Haar-cropped once, shared by
  all 15 models; incremental + `--tarfar-resume`) ->
  `reports/benchmark/dataset_matrix_tar_far.{json,md}` and auto-summary
  `reports/benchmark/dataset_matrix.md`.
- Headlines (full analysis in `docs/DATASET_MATRIX.md`):
  - **Clean wins every column for every family**; no recipe re-orders the
    families (LBPH stays selected).
  - Train-side augmentation: LBPH TAR@100ppm 98.21 -> 89.29% (thr 73.04 ->
    70.37); the medium tier changes NOTHING measurable vs light alone for LBPH
    (+70 MB, +56% predict time); Fisherfaces collapses 66.07 -> 48.21% rank-1,
    EER 53.57%; Eigenfaces moves within noise at 452 MB.
  - Single-lighting training caps opposite-condition rank-1 at 89.29% (LBPH);
    both real lighting conditions in the clean split are what buy 100%.
    If forced to one condition, dark generalizes better (TAR@100ppm 92.86% vs
    80.36% - LFW impostors are well-lit).
- 9 new model artifacts: `models/<family>/lasalle_{clean_aug_light_medium,light_only,dark_only}.yml`.

## June 11, 2026

Variant options (feature-size / accuracy), the spec-compliance document, and the
launcher's switch to the clean artifacts.

### NEW: opt-in variants + comparison (`docs/SUGGESTION.md` implemented)
- `src/classical_faces/variants.py`:
  - **CompactLBPH** - "keep only the important parts of the feature": Fisher-score
    top-K histogram dimensions, optionally restricted to the eyebrow/eye/nose/
    mouth cells of the 8x8 grid, at <1 KB byte budgets (float32 or uint8),
    chi-square matching vs centroid or all-template galleries.
  - **SubspaceMatcher** - Eigen/Fisher matcher upgrades: drop leading PCA
    components, eigenvalue whitening (Mahalanobis), cosine distance, centroid
    galleries; features stay the standard OpenCV projections.
- `scripts/compare_variants.py` benchmarks unedited vs all variants on the clean
  split with 13,149 LFW impostors -> `reports/benchmark/variant_comparison.{json,md}`
  (84 rows). Headlines:
  - Custom full-histogram matcher reproduces unedited LBPH EXACTLY (harness is
    faithful).
  - Best <1 KB LBPH: **top-960 landmark-cells uint8 - 960 B, rank-1 91.1%,
    TAR 87.5% @ 1.058% FAR, 76.8% @ 100 ppm** (landmark restriction beats
    unrestricted selection at equal budget, confirming the suggestion's
    direction; still ~21 pts under the 64 KB original at 100 ppm).
  - Eigenfaces @ 100 components: same TAR as 280 comps with a 400 B (<1 KB)
    feature; still FAIL overall. Fisherfaces + centroid gallery: TAR 35.7 ->
    41.1% (best variant); still FAIL.
  - Verdict: no variant changes the recognizer selection; compact LBPH is the
    documented Pi-budget BACKUP, not a replacement.
- These are options only - the deployed pipeline still runs the unedited
  recognizers. Launcher: Benchmark > "variants: unedited vs compact/upgraded".

### NEW: docs/SPEC_COMPARISON.md
- The spec-sheet scorecard for all three models (TAR/FAR/FRR/EER/AR, feature +
  model size, FPS, latency status, thresholds) with discussion, threats to
  validity, the variant options table, and the conclusion/recommendation
  (LBPH+Tan-Triggs unedited; threshold 73.0 @ 100 ppm; compact template as
  fallback). Built strictly from run artifacts (provenance table inside).

### Launcher now uses the clean artifacts (deprecated models retired)
- `main.py` clean-split menu runs now train/evaluate the CANONICAL
  `models/<family>/lasalle_clean[_aug_light].yml` (+labels) instead of the
  legacy `trainer_<slug>` names, so the menu loop, the clean loop, the
  benchmarks and live detect all share one artifact set.
- Artifact pickers list the clean pair first ("CLEAN - recommended"), tag old
  combos "(legacy)", and now discover `lasalle_clean*.yml` at all (the old glob
  only matched `trainer*.yml`).
- Model-info panel markers/sizes point at the clean model file, not folder
  totals inflated by deprecated artifacts.
- Deleted (user-approved, C: was 100% full and blocking all FileStorage IO):
  `models/lbph/trainer_lfw-lm.yml` (3.6 GB) and
  `models/lbph/trainer_processed-plm.yml` (1.0 GB) - both deprecated,
  regenerable via the legacy combos. Freed 4.6 GB.

### Fixes
- `lbph_histograms_from_tiles` (shared by the variant benchmark and the LFW
  independence path): batch-capped at 250 images per temp model and switched
  the round-trip to XML; the apparent cv2.FileStorage "parsing errors" were
  ultimately caused by the FULL DISK truncating writes - with space restored
  the extraction is verified at 600+ tiles.
- `run_lfw_independence.py` now delegates histogram extraction to the shared
  (capped) helper; `--lbph-batch` default 500 -> 250.

## June 10, 2026 - second pass (pipeline audit follow-up)

Audited why "no classical model fits the specs", improved the pipeline from
measurements, and implemented the remaining spec benchmarks. Headline: **LBPH
with Tan-Triggs preprocessing now passes the spec's accuracy block end-to-end -
TAR 98.21% / FRR 1.79% at FAR 76 ppm (spec: TAR 90-95%, FAR < 100 ppm,
FRR 1-5%) against 13,149 LFW impostors,** with 100% rank-1 on the clean
held-out split and EER 0.07%. The remaining spec misses for LBPH are the
inherent 64 KB feature vector and the <30 fps live loop (a Stage-3 hybrid
target; Stage-1 "accuracy >90% @ 1 face/s" is comfortably met).

### Measured pipeline improvement: Tan-Triggs for LBPH
- New `scripts/sweep_classical_configs.py` sweeps (family x num_components x
  equalization) on the clean split with LFW impostors ->
  `reports/benchmark/classical_config_sweep.{json,md}`. Findings:
  - **LBPH + tan-triggs: 100% rank-1, EER 0.04-0.07%** (from 96.4% / 3.6%).
  - Eigen/Fisher are NOT config-rescuable: component caps and CLAHE/Tan-Triggs
    all hurt or fail TAR (Tan-Triggs strips the low-frequency content their
    subspaces need). Verdict: their genuine/impostor overlap is intrinsic here.
- Added `tan-triggs` to `src/classical_faces/preprocess.py` (gamma -> DoG ->
  two-stage contrast equalization, fixed [-tau,tau] -> [0,255] mapping) and made
  it the LBPH default.

### Per-family contract now single-sourced in `RecognizerSpec`
- `default_equalization` and `default_num_components` live on the spec;
  trainers, evaluators, live `detect.py`, the independence tests, TAR@FAR and
  the AR benchmark all read them, so train/eval/live/threshold stages cannot
  drift again. Eigen/Fisher trainers expose `--num-components`.
- Live `detect.py` x3 no longer hardcode equalization/threshold; they default to
  the spec contract (eigen/fisher previously equalized differently than training
  and used stale thresholds).

### TAR@FAR rebuilt to spec resolution
- `src/benchmark/tar_at_far.py` now defaults to the FULL LFW set as impostors
  (13,149 usable probes -> FAR resolvable to 76 ppm, vs the old 605-probe ~0.17%
  floor), Haar-crops impostors ONCE shared across families, and reports the
  0.1% / 0.01% (spec) operating points alongside the independence ~1.058% point.
- Results (baseline models): LBPH TAR 100%/FRR 0% @ 1.06% FAR and TAR
  98.21%/FRR 1.79% @ 76 ppm -> PASS; Eigenfaces 53.6% -> 23.2% and Fisherfaces
  35.7% -> 10.7% across the same range -> FAIL.

### Calibrated deployable thresholds (predict scale, from the 100 ppm point)
- LBPH **73.0** (tan-triggs scale), Eigenfaces **4308**, Fisherfaces **738** are
  now the spec defaults + sweep anchors; evaluator hit@thr and live detect use
  them. (Old values 55/4000/800 were uncalibrated.)

### NEW: Accuracy-Ratio benchmark (the spec's DB2 method, was unimplemented)
- `src/benchmark/accuracy_ratio.py` implements AR = K/M per (modification,
  level) at the deployable threshold: 12 deterministic modification types, 41
  (type, level) variants per original (seeded noise/occlusion), held-out
  originals by default (56 x 41 = 2,296 probes; `--include-train` reproduces the
  literal 280 x 41 = 11,480 DB2 scheme). The existing `augmented41mods` folders
  were random light/medium composites, not the 41-modification protocol.
- Results @ FAR~1% threshold: **LBPH overall AR 85.4%** (weakest: heavy gaussian
  noise 47.8%, motion blur 68.5%, strong brightness-down 73.7%), Eigenfaces
  47.7%, Fisherfaces 30.5%. Confirm the official 41-modification list with the
  team spec sheet - the suite is a documented stand-in with matching counts.

### NEW: gated full-LFW independence path (7/15 deliverable, second half)
- `scripts/run_lfw_independence.py` implements the ordered N x (N-1) LFW DB1
  protocol (5,749 ids -> 33,045,252 comparisons, threshold = 331st error pair
  ~ 10 ppm) via a streaming unique-pair top-K (33M records never materialized).
  LBPH histograms batch-extracted exactly from OpenCV; Eigen basis trained on a
  capped probe subset; Fisher basis trained on multi-image identities (2/id) so
  the LDA is well-posed; probes projected manually. Full run is GATED
  (`--confirm-full`; LBPH pass is multi-hour); smoke-validated at 300 ids
  (89,700 ordered comparisons) for all three families ->
  `reports/benchmark/independence_thresholds_lfw.{json,md}`.
- `error_pair_report` now uses **ceil** for the rank: ceil reproduces BOTH spec
  anchors (756 x 10,000 ppm -> 8; 33,045,252 x 10 ppm -> 331), where round()
  gave 330. Added `error_pair_report_from_topk` for the streamed path.

### Independence-test fixes (La Salle re-run under the new contracts)
- **Fisherfaces now trains its independence LDA on 2 images/identity**
  (`--images-per-identity`, comparisons stay N x (N-1) with one probe/identity) -
  the 1-image LDA was the documented degenerate collapse. New La Salle
  thresholds (8th error pair, 756 comparisons): LBPH **21.35** raw chi-square
  (tan-triggs scale, norm 85.88), Eigenfaces **8098.46** (norm 71.00),
  Fisherfaces **5446.46** (norm 66.38, well-posed).
- Re-runs are now verified **bit-exact reproducible** (same seeds -> identical
  thresholds). The June-10 morning Eigen value (7899.40) differed from today's
  deterministic re-run; provenance of the old number can't be reconstructed
  (audit's symlink-fluidity caveat) - the committed summaries are the canonical
  ones going forward.
- Fixed the `selected_identities` mislabel in all three summaries (reported the
  record count, e.g. 756, instead of 28).

### Comparison + loop + launcher wiring
- `compare_classical.py`: adds the 100 ppm operating-point table (with spec
  verdict) and the AR-robustness table; FRR below the 1-5% band now counts as
  PASS (0% FRR was marked FAIL).
- `run_classical_clean_loop.py`: runs accuracy_ratio after TAR@FAR
  (`--skip-ar`), and `--quick-tar-far` keeps the old small impostor pass.
- `main.py` Benchmark menu: added independence thresholds (La Salle + gated
  LFW), TAR@FAR, accuracy ratio, and the config sweep.

### Honest notes / watch items
- LBPH aug-light now scores BELOW baseline (98.21% vs 100% rank-1) - train-only
  augmentation does not help the tan-triggs model; the baseline is the pick.
- The 56-probe genuine set gives ~1.8% TAR granularity; AR (2,296 probes) is the
  higher-resolution genuine-side view. The 100 ppm FAR claim rests on 13,149
  impostors (granularity 76 ppm) - the full-LFW independence run remains the
  gated confirmation.
- LFW smoke run flagged the same boundary pair (Andrew_Caldecott vs
  Andrew_Gilligan) for all three families - eyeball those images for the
  known LFW annotation-error failure mode before trusting full-run thresholds.
- BRIEFING.md S9 says "78,120" modified images for La Salle DB2; S7 says
  280 x 41 = 11,480. 78,120 = 280 x 279 (an N x (N-1) figure) - looks like the
  same doc garbling the audit warned about; confirm with the team.

## June 10, 2026

Closed the independence-test methodology gap and determined the per-model match
threshold (the threshold-determination half of the 7/15 deliverable).

### Rank-based k-th-error-pair threshold
- Added the **spec method** to `src/independence_common.py` (`error_pair_threshold`,
  `error_pair_report`, `format_error_pair_report`): sort the N x (N-1) cross-identity
  (impostor) distances ascending; the **k-th smallest sets the threshold at FAR =
  k / N**. La Salle DB1 (756 comparisons) -> **8th error pair (~10,000 ppm)**;
  LFW DB1 -> 331st (~10 ppm). This replaces the old percentile heuristic
  (p01/p05/p10) flagged in the audit; percentiles are kept as exploratory output.
- Wired it into all three `independence_test.py` scripts (LBPH / Eigenfaces /
  Fisherfaces) with `--target-far-ppm` (default 10000) and `--error-pair-rank`
  (explicit k). Each run now prints the spec operating point, the boundary
  impostor pair, and a FAR-vs-threshold curve.
- New `scripts/run_independence_thresholds.py` runs all three on La Salle DB1 and
  writes `reports/benchmark/independence_thresholds.{json,md}`.

### Determined thresholds (La Salle DB1, 28 ids, 756 comparisons, 8th error pair)
- LBPH: raw chi-square threshold **25.39** (norm 83.03).
- Eigenfaces: raw euclidean threshold **7899.40** (norm 70.01).
- Fisherfaces: raw euclidean threshold **6345.72** (norm 67.66).
- Realized FAR = 8/756 = **10,582 ppm (1.058%)** for all three (La Salle cannot
  resolve finer than ~1,300 ppm; the spec's 100/10 ppm need LFW DB1).

### End-to-end TAR @ FAR / FRR / EER (recognizer native scale)
- New `src/benchmark/tar_at_far.py` measures the real verification operating point
  on each recognizer's own `predict()` scale (not the independence feature scale):
  **held-out La Salle genuine vs LFW impostors** (Haar-cropped to match framing),
  full-resolution ROC, with the threshold set at the independence FAR (~1%).
- Writes `reports/benchmark/tar_at_far.{json,md}`; the numbers are now folded into
  `compare_classical.py` (new "Verification operating point" table) and the loop
  (`run_classical_clean_loop.py` runs it before the comparison).
- **Result at FAR ~1% (605 LFW impostors, 56 genuine):**
  - **LBPH: TAR 96.43% / FRR 3.57%, EER 3.60%, threshold 112.55 -> PASS** (spec
    TAR 90-95%, FRR 1-5%).
  - Eigenfaces: TAR 53.57% / FRR 46.43%, EER 31.77% -> FAIL.
  - Fisherfaces: TAR 41.07% / FRR 58.93%, EER 35.71% -> FAIL.
- This overturns the closed-set reading: rank-1 made Eigen/Fisher look merely
  "behind" (75% / 66%), but with real impostors their genuine/impostor distances
  overlap so heavily that holding FAR at ~1% rejects roughly half the genuine
  probes. **LBPH is the decisive classical pick** for the FAR-controlled gate.

### Honest scope note
- La Salle DB1 (756 comparisons / 605 impostor probes) resolves FAR only to ~1%;
  the spec's 100 ppm / 10 ppm operating points need LFW DB1. The 56-probe genuine
  set gives TAR ~2% granularity - the larger DB2 Accuracy-Ratio test is the
  higher-resolution follow-up. Each independence-test threshold remains on its own
  feature scale; the deployable `--unknown-threshold` is the one in the TAR@FAR
  table (e.g. LBPH 112.55).

## June 9, 2026

Reproduced a clean, leakage-free **train -> evaluate -> live -> compare** loop for
the three classical recognizers (LBPH, Eigenfaces, Fisherfaces) and consolidated
their previously copy-pasted code into one shared backbone.

### 1) Shared classical backbone (`src/classical_faces/`)
- New package replaces the dead, never-imported `common.py` (deleted):
  - `preprocess.py` - the single source of truth for face normalization
    (`extract_classical_face`). **No more silent full-image fallback**: a Haar
    miss is reported as `no_face`, never fed to the recognizer as a whole frame.
  - `datasets.py` - one copy of dataset enumeration / per-person capping / seeding.
  - `pipeline.py` - shared `run_training` / `run_evaluation`, a `RecognizerSpec`
    per family, the unified `Stats`, threshold sweep, and report schema.
- `src/lbph/preprocess.py` is now a thin re-export shim (keeps `extract_lbph_face`
  and the independence-test / detect imports working unchanged).

### 2) Thin, identical trainer/evaluator wrappers
- All six `trainer.py` / `evaluate.py` are now small argparse wrappers over the
  shared pipeline (down from ~400 lines each). They cannot drift apart again.
- **Removed the Eigen/Fisher "skip unseen identity" behavior** - all three now use
  one open-set loop (unseen = impostor), so the numbers are comparable.
- Default loop is leakage-free: train on `data/split_lasalle/train`, evaluate on
  the held-out `data/split_lasalle/test`, both with `--assume-cropped` (the tiles
  are pre-cropped 100x100 faces).

### 3) Unified, honest report schema
- One schema for all three: `hit_rate_percent` (primary), a closed-set
  **`rank1`** block (nearest-neighbour, threshold-independent), open-set
  known/unknown/balanced fields, a `detection` block (no fallback), and a
  `footprint` block (model bytes + feature-vector bytes).
- Feature-vector size is measured correctly per family (LBPH grid x 2^neighbours
  histogram bins; Eigen/Fisher = retained components x 4 B).

### 4) Live detection now matches training
- `eigenfaces/detect.py` and `fisherfaces/detect.py` no longer equalize the whole
  frame then crop; they detect on raw grayscale and normalize **per detected ROI**
  (via the shared `normalize_face`), matching how faces were normalized in training.
- All three live loops default to the clean `lasalle_clean` model + `--no-align`
  (the clean model was trained without eye-alignment).

### 5) Leakage-safe La Salle augmentation
- Regenerated train-only augmentation into `data/split_augmented41mods_lasalle_clean`
  (augments `train/`->`train/` and `test/`->`test/` separately). Evaluation always
  stays on the real held-out test, never augmented images.

### 6) Spec comparison table + one-command loop
- New `src/benchmark/compare_classical.py` writes
  `reports/benchmark/classical_comparison.{json,md}` with spec columns: rank-1 /
  best-sweep / hit@thr / model size / feature size / <1 KB? / live FPS / >=30 fps?
  / verdict (FAR/FRR noted as pending the independence test).
- New `scripts/run_classical_clean_loop.py` trains+evaluates all three (baseline
  and a train-only light-aug variant) and writes the table in one command.

### 7) Launcher wiring (`main.py`)
- New dataset option **"La Salle CLEAN split (held-out, recommended)"** that wires
  `--base-data-dir data/split_lasalle` + `--assume-cropped` (classical only).
- Benchmark menu: added **"run clean classical loop"** and **"compare classical
  (spec table)"**; retired the broken `compare models` entry (it pointed at a
  non-existent script).
- Benchmark overview / report aggregation now prefer closed-set rank-1 so an
  uncalibrated unknown-threshold no longer makes a recognizer read as 0%.

### 8) First trustworthy held-out numbers (La Salle, 28 ids, 2 held-out/person)
- Rank-1 on the held-out test split: **LBPH 96.43%**, Eigenfaces 75.0% (78.6% with
  light aug), Fisherfaces 66.1% (60.7% with light aug).
- Feature vector vs the <1 KB spec: LBPH 64 KB (fail), Eigenfaces 1120 B (fail),
  Fisherfaces 108 B (pass).
- FAR/FRR and the operating threshold remain the separate independence-test
  deliverable; the table marks them pending rather than inventing them.

## April 23, 2026

This document summarizes all updates completed today.

### 1) New recognition models added
- Added full **Eigenfaces** pipeline:
  - training script
  - evaluation script
  - live camera detection script
- Added full **Fisherfaces** pipeline:
  - training script
  - evaluation script
  - live camera detection script
- Both new model families are now available in the main launcher.

### 2) Main launcher and dashboard improvements
- Updated `main.py` so users can run Eigenfaces and Fisherfaces directly from the menu.
- Added a new benchmark menu action to **aggregate evaluation reports**.
- Improved benchmark overview output:
  - now shows hit rate, accuracy, average FPS, and model size
  - now sorts rows by best performance
  - now shows evaluation entities (model variant + dataset profile)
- Improved execution reliability by ensuring project `PYTHONPATH` is set when running scripts from launcher.
- Added guided dataset prompts for train/evaluate actions to make selection of raw/processed/augmented data easier.

### 3) Unified dataset handling across models
- Added shared dataset utilities (`src/dataset_layout.py`) so all models use the same logic when reading augmented split folders.
- Updated ArcFace, EdgeFace, MobileFaceNet, LBPH, Eigenfaces, and Fisherfaces to use this shared dataset layout behavior.
- Added automatic split targeting (`train`/`test`) for augmented folders when applicable.

### 4) Stronger report identity and traceability
- Added shared reporting identity helper (`src/reporting/identity.py`).
- Evaluation reports now include:
  - model family
  - model variant
  - dataset profile and dataset key
  - entity key
  - optional run tag
- This makes cross-run comparison safer and clearer (same model on different datasets is now clearly separated).

### 5) New report aggregation utility
- Added `src/benchmark/aggregate_evaluation_reports.py`.
- This script scans evaluation JSON reports, groups them by entity, and writes:
  - aggregated JSON summary
  - aggregated Markdown summary

### 6) Benchmark comparison report enhancement
- Updated `src/benchmark/compare_models.py` to include entity context in markdown output.
- Comparison now shows dataset/entity metadata for LBPH and YuNet+MobileFaceNet results.

### 7) ArcFace, EdgeFace, MobileFaceNet upgrades
- Updated trainer defaults to use `data` base layout with improved raw/processed/augmented handling.
- Updated evaluation scripts to:
  - include run tagging
  - include threshold sweep defaults when not provided
  - include dataset/entity identity metadata in saved reports
- EdgeFace evaluation now includes explicit threshold sweep computation in report output.

### 8) LBPH major preprocessing and evaluation upgrade
- Added shared LBPH preprocessing module (`src/lbph/preprocess.py`) with:
  - optional eye-based alignment
  - histogram equalization or CLAHE
  - optional downscale before detection
  - standardized face extraction result metadata
- Updated LBPH trainer to use the new preprocessing pipeline and improved dataset handling.
- Added deterministic sampling controls and clearer per-bucket statistics during training.
- Upgraded LBPH live detection:
  - optional tracking between detector passes
  - stability gating before accepting recognition
  - richer live metrics (FPS, recognition FPS, detections, recognitions, tracking updates)
  - optional per-session JSON log output
- Upgraded LBPH evaluation:
  - better known-vs-unknown metrics and balanced accuracy
  - threshold sweep output
  - improved misclassification reporting
  - explicit skipped-reason reporting
  - added dataset overlap warning note when augmented data can affect fairness

### 9) Data augmentation utility added
- Added `augment_split_light_medium.py` to generate light/medium augmented datasets from split data.
- Supports reproducible generation, overwrite controls, optional cleanup, and optional horizontal flips.

### 10) Project structure additions
- Added new module folders and entry points for:
  - `src/eigenfaces/`
  - `src/fisherfaces/`
  - `src/classical_faces/`
  - `src/reporting/`

### 11) Launcher dataset source selection improved
- Updated the first dataset prompt in the launcher to support:
  - `1) La Salle only`
  - `2) LFW only`
  - `3) Both`
- Wired the choices directly into runtime arguments so train/evaluate flows can run against the selected source combination without manual argument editing.

### 12) Launcher model management made smarter
- The launcher now shows detected saved dataset combinations per model (from existing evaluation entities), including variant and hit-rate summary.
- Before running train/evaluate, the launcher now checks whether the selected model + dataset combination already exists.
- If a matching combination already exists, the launcher asks for confirmation before continuing, to avoid accidental duplicate runs.

### 13) Model artifact overwrite prevention and faster LBPH evaluation start
- Launcher now auto-generates dataset-combination-specific model artifact filenames by default, so switching between dataset combinations does not overwrite previous trained outputs.
- Evaluation actions now auto-select the matching combo-specific artifacts when available, while still allowing manual override through extra args.
- LBPH evaluation now uses streaming progress (no long full pre-count pass), so large processed-only LFW evaluations show activity immediately.

### 14) Evaluation artifact picker in launcher
- Evaluation actions now prompt for a specific trained artifact before run.
- The picker shows:
  - auto dataset-matched artifact
  - discovered existing trained artifacts for that model
- Supports paired artifacts for LBPH/Eigenfaces/Fisherfaces (`trainer*.yml` + `labels*.json`) and enrollment artifacts for ArcFace/MobileFaceNet/EdgeFace (`enrollment*.json`).
- Explicit extra args (`--model-path`, `--labels-path`, `--enrollment-path`) still take priority and skip the picker.

### Notes
- No git commits were recorded today, so this changelog is based on today’s current working updates present in the repository.
