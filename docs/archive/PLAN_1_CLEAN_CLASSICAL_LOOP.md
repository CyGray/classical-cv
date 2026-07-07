Clean Classical CV Loop — Train → Evaluate → Live → Compare
Context
We own the classical CV track (LBPH, Eigenfaces, Fisherfaces) of the LS-Face / Smart Gate project. Per docs/READ THIS/BRIEFING.md and CLASSICAL_TRACK_AUDIT.md, the pipelines run end-to-end but no trustworthy held-out recognition number exists for any of the three, and the three have drifted apart because they are ~80% copy-pasted. This blocks the 6/30 recognizer-selection deliverable.

Root causes confirmed by reading the code + data:

Train==test leakage / no clean loop. The clean image-disjoint La Salle split already exists at data/split_lasalle/{train,test} (28 ids; 10 cropped 100×100 train imgs/person; 2 held-out "name"-pose test imgs/person). But it is not wired in: the launcher's "La Salle" option points both train and eval at raw data/lasalle_db1 (full 12 imgs) → leakage; the evaluator CLI default points at data/split/test, which is currently LFW (symlink-swapped) → all-unknown artifact.
Wrong preprocessing contract. Split inputs are pre-cropped 100×100 faces, yet the evaluators force Haar detection on them. Haar fails on a 100×100 face → Eigen/Fisher silently fall back to the full image (the "44/56 fallback" degradation); LBPH counts them as no-face. The correct contract for cropped inputs is "the image is the face" (assume_already_cropped).
Two divergent report schemas + semantics. LBPH = open-set (overall_accuracy_percent, known/unknown, balanced) and does not skip unseen; Eigen/Fisher = closed-set (hit_rate_percent) and skip unseen identities entirely. The comparison tools then mix open-set vs closed-set numbers.
Drifted live paths. LBPH detect.py uses the good shared preprocessing (eye-align + equalize on the ROI). Eigen/Fisher detect.py are copy-paste twins that equalize the whole frame then crop, no alignment — so their live input doesn't even match their own training.
Comparison tooling doesn't reflect the spec. aggregate_evaluation_reports.py only reports a (mixed-schema) hit rate; compare_models.py is hardcoded to a non-existent src/yunet_mobilefacenet/ path. Neither shows model size, feature-vector size, FPS, or spec pass/fail.
Severe duplication / dead code. root_path, resolve_path, detect_face_or_fallback, Stats, print_progress, compute_threshold_sweep, gather_dataset_entries, etc. are copy-pasted across all 6 files. src/classical_faces/common.py was meant to unify them but is imported nowhere and itself carries the bad full-image fallback.
Intended outcome: one leakage-free, reproducible train→evaluate→live loop shared by all three recognizers under an identical preprocessing + reporting contract, plus a spec-oriented comparison table that says which classical model fits the spec best.

Decisions (locked with user)
Refactor scope: consolidate the duplicated trainer/evaluator logic into a real src/classical_faces/ package so all three are identical and cannot re-drift.
Train data: produce both a no-augmentation baseline and a leakage-safe train-only light-aug variant per model, side by side.
Entry point: fix main.py's La Salle option to use the clean split and add a one-command orchestration script that trains+evals all three and writes the comparison table.
Canonical clean-loop contract (pin this; do not rely on the mutable data/split symlink)
Train: data/split_lasalle/train (cropped 100×100) → assume_cropped → equalize → resize 100×100.
Test (held-out): data/split_lasalle/test (cropped 100×100, "name" pose) → same preprocessing.
Train-only aug variant: regenerate from data/split_lasalle with the existing augment_split_light_medium.py (--split-root data/split_lasalle --output-root data/split_augmented41mods_lasalle_clean), which writes <level>/train/... and <level>/test/... separately (leakage-safe). Train uses only /train; eval always stays on the real held-out test (never the augmented test) so the headline number is honest.
Cropped inputs ⇒ no Haar detection, no full-image fallback. Eye-alignment off by default for the cropped offline loop (faces are pre-centered; the eye detector is unreliable at 100×100), configurable. Haar detection remains the contract for raw photos and the live webcam path only.
Implementation plan
Phase 1 — Shared src/classical_faces/ package (the backbone)
Replace the dead common.py with a cohesive package; all three pipelines import from it.

src/classical_faces/preprocess.py — move the good preprocessing out of src/lbph/preprocess.py: IMG_SIZE, FacePreprocessResult, resolve_eye_cascade_path, maybe_downscale, detect_largest_face_box, align_face_by_eyes, normalize_face, and a generalized extract_classical_face(...) (today's extract_lbph_face, already supports assume_already_cropped). Keep src/lbph/preprocess.py as a thin re-export shim (from src.classical_faces.preprocess import * plus extract_lbph_face = extract_classical_face) so detect.py, the independence_test*.py scripts, and src/benchmark/algo_check_processed_same_folder.py keep working unchanged.
src/classical_faces/datasets.py — single copy of is_image_file, person-dir gathering, gather_training_entries, gather_dataset_entries, stable_person_seed, wired to src/dataset_layout.py.
src/classical_faces/pipeline.py — the shared engine:
RecognizerSpec = family name + cv.face.*_create factory + default unknown-threshold + default sweep
feature-size formula.
run_training(spec, cfg) → extract faces (shared preprocessing) → recognizer.train → save .yml + labels .json + per-bucket/person counts.
run_evaluation(spec, cfg) → shared loop → unified report (schema below).
Shared Stats, summarize_bucket, bucket_to_dict, threshold_metrics (rejection-aware), compute_threshold_sweep, print_progress, format_seconds.
Phase 2 — Thin trainer/evaluator wrappers
Rewrite each src/{lbph,eigenfaces,fisherfaces}/trainer.py and evaluate.py (~400 lines each today) down to a small argparse + RecognizerSpec + call into pipeline. This removes the Eigen/Fisher full-image fallback and the unseen-skip, and unifies defaults (same aug-split handling, same --assume-cropped, same sweep mechanics). Algorithm-specific bits that remain: recognizer factory, default --unknown-threshold (LBPH 55 / Eigen 4000 / Fisher 800), and default model/label paths.

Phase 3 — Unified report schema (reports/evaluation/<family>_eval*.json)
One schema for all three, via attach_entity_identity + build_dataset_profile (already shared):

Identity block: model_family, model_variant, dataset_profile, dataset_key, entity_key, run_tag.
overall + per-buckets: standardize on hit_rate_percent as the primary closed-set ID metric (so aggregate_evaluation_reports.py and main.py:extract_hit_rate_percent read all three identically); keep the open-set fields (known_*, unknown_rejection_rate_percent, balanced_accuracy_percent) present but 0/None when there are no impostors (the split_lasalle loop is purely closed-set).
detection: detected / aligned / skipped_no_face / skipped_too_small + rates.
footprint: model_file_bytes, feature_vector_bytes (LBPH grid_x·grid_y·256 ≈ 64 KB; Eigen/Fisher = n_components·4 B). Gives the comparison table its spec columns.
threshold_sweep: rejection-aware threshold_metrics for all three.
Phase 4 — Align the three live detect.py (light touch, not a rewrite)
Replace the inline per-frame face normalization in Eigen/Fisher detect.py with the shared extract_classical_face/normalize_face on the detected ROI (+ optional align), so live preprocessing matches training. Leave LBPH's loop (already correct, has optical-flow tracking) as the reference; do not force the others to grow tracking. Keep existing FPS logging.

Phase 5 — Leakage-safe augmentation
Run augment_split_light_medium.py --split-root data/split_lasalle --output-root data/split_augmented41mods_lasalle_clean to produce train-only light/medium aug for the aug variant. (Reading its CLI: it already augments train/→train/ and test/→test/ separately, so no leak by construction.)

Phase 6 — Spec comparison table + orchestration script
src/benchmark/compare_classical.py (replaces the broken compare_models.py use): reads the three latest *_eval.json for the clean entity + FPS from reports/benchmark/live_fps/aggregate_summary.json + footprint, and writes reports/benchmark/classical_comparison.{json,md}. Columns mapped to the spec (docs/READ THIS/BRIEFING.md §6): Model | Hit-rate (held-out) | Best-sweep acc | Model size | Feature size | <1 KB? | Live FPS | ≥30 fps? | Verdict. Notes section records that TAR@FAR/FRR need impostors (independence test, the separate 7/15 deliverable) and that the FPS bottleneck is shared Haar detection.
scripts/run_classical_clean_loop.py — one command: (optional) regenerate aug → train all three (baseline + aug) on split_lasalle/train → eval all three on split_lasalle/test → run compare_classical.py. Reuses main.py:get_python_command() style subprocess invocation.
Phase 7 — Launcher wiring (main.py)
Add a dataset-source option in prompt_core_dataset_args for "La Salle clean split (held-out)" that sets --base-data-dir data/split_lasalle, --raw-dir-name train (train) / test (eval), and the --assume-cropped flag — making the menu loop leakage-free by default.
Add a Benchmark action "compare classical (spec table)" → compare_classical.py; retire the broken compare_models.py menu entry.
Phase 8 — Cleanup
Delete dead src/classical_faces/common.py (superseded). Remove the now-unused duplicated helpers from the six pipeline files. Drop the ignored --assume-processed-are-cropped no-op in favor of the real --assume-cropped. Refresh docs/changelogs/CHANGELOG.md.

Critical files
New: src/classical_faces/{preprocess,datasets,pipeline}.py, src/benchmark/compare_classical.py, scripts/run_classical_clean_loop.py.
Rewrite (thin): src/{lbph,eigenfaces,fisherfaces}/{trainer,evaluate}.py.
Edit: src/lbph/preprocess.py (→ shim), src/{eigenfaces,fisherfaces}/detect.py (preprocessing), main.py (clean-split option + benchmark action), src/benchmark/aggregate_evaluation_reports.py (read unified hit_rate_percent).
Reuse as-is: src/reporting/identity.py, src/dataset_layout.py, augment_split_light_medium.py, src/lbph/detect.py (reference live loop).
Verification (end-to-end)
Unit smoke: python -c "from src.classical_faces.pipeline import run_training" imports clean; the src.lbph.preprocess shim still exports extract_lbph_face, normalize_face, etc. (independence + detect scripts import OK).
Clean loop, all three via scripts/run_classical_clean_loop.py (or python main.py → each model → train → evaluate using the new clean-split option). Confirm in each report: dataset_profile.label mentions split=train/test + La Salle, known_total==evaluated, unknown_total==0, detection/fallback counts show no full-image fallback, and a plausible held-out hit_rate_percent (a real number, not 100% and not 0%).
No leakage: assert train and test image sets are disjoint for all 28 ids (filename check, as in the audit) and that eval never reads an augmented folder.
Comparison table: compare_classical.py writes reports/benchmark/classical_comparison.md with all three rows, model/feature sizes, and spec verdicts; sanity-check LBPH feature ≈ 64 KB (fails <1 KB), Eigen/Fisher < 1 KB.
Live (manual): run one detect.py per model against a webcam; confirm it loads the clean-split model, recognizes a trained identity, and appends an FPS summary that the table then picks up.
Out of scope (flag for later)
Independence test + rank-based k-th-error-pair threshold (the 6/15–7/15 deliverable) — untouched here; the independence_test*.py and trainer_light_front.py scripts keep working via the preprocessing shim.
Full LFW recognition runs and TAR@FAR verification (needs impostors).
Retraining/curating the existing mismatched models/ artifacts beyond the clean-split outputs.