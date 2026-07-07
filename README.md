# Face Detection & Recognition - Group 3

A multi-algorithm face recognition research platform for the USLS Computer Vision course, built around a **gated hybrid cascade** whose design is grounded in **independence testing** - the key supporting methodology that drives model selection, threshold calibration, and error detection. Independence testing performs exhaustive N x (N-1) cross-identity comparisons to construct the full empirical impostor distance distribution, deriving match thresholds via order statistics rather than tuning on a small validation split.

The formal mathematical foundation - including the probability model, the k-th error pair rule, extreme-value connections, and comparison with the LFW sampled-pair protocol - is documented in `docs/report_docs/independence_test/MATHEMATICAL_FOUNDATION.md`.

The goal: a Smart Gate access control system that runs on a Raspberry Pi 5, combining classical CV speed (LBPH, Eigenfaces, Fisherfaces) with deep learning robustness (SFace) via the gated hybrid cascade, with all thresholds and model selections driven by independence testing results.

---

## Algorithms

| Algorithm | Type | Detection | Recognition |
|---|---|---|---|
| **LBPH** | Classical | Haar cascade / YuNet | OpenCV LBPHFaceRecognizer |
| **Eigenfaces** | Classical | Haar cascade / YuNet | OpenCV EigenFaceRecognizer |
| **Fisherfaces** | Classical | Haar cascade / YuNet | OpenCV FisherFaceRecognizer |
| **Hybrid (LBPH → SFace)** | Classical + DL cascade | YuNet (ONNX) | LBPH fast path, SFace escalation |

Classical models train a `.yml` model file + `.json` label map. The hybrid's SFace half builds an enrollment gallery of face embeddings (identity centroids). SFace exists only as the hybrid's escalation engine, not as a standalone track.

---

## Quickstart

```bash
pip install -r requirements.txt
python main.py
```

`main.py` is an interactive launcher. Select a model, then an action (train / evaluate / live detect / independence test). The launcher handles dataset selection, artifact paths, and duplicate-run warnings automatically.

**Environment override** - to use a specific Python interpreter:
```bash
set FACE_G3_PYTHON=path/to/python  # Windows
python main.py
```

---

## Project Layout

```
main.py                     # Interactive launcher (entry point)
src/
  lbph/                     # LBPH pipeline
  eigenfaces/               # Eigenfaces pipeline
  fisherfaces/              # Fisherfaces pipeline
  classical_faces/          # Shared classical pipeline core
  sface/                    # SFace embeddings (the hybrid's DL half)
  hybrid/                   # LBPH -> SFace cascade
  benchmark/                # Cross-model comparison & aggregation
  dataset_layout.py         # Shared dataset/augmentation utilities
  reporting/identity.py     # Shared report identity helpers
  independence_common.py    # Shared independence test utilities
  stats_utils.py            # Wilson CIs, Fisher exact, diversity measures
scripts/
  augment_split_light_medium.py   # Light/medium augmented split generator
  independence_failure_check/     # Post-hoc failure analysis scripts
  run_*.py, make_*_figures.py, …  # Orchestration & figure scripts
data/
  lasalle_db1/              # Raw La Salle identity images
  lasalle_db1_processed/    # Cropped/aligned La Salle images
  lfw-dataset/              # LFW dataset (processed)
  split_augmented41mods*/   # Augmented splits (light / medium)
models/                     # Trained artifacts (paper-essential ones tracked)
  yunet/                    # Shared YuNet detector ONNX
reports/
  evaluation/               # Per-model JSON evaluation reports
  benchmark/                # Aggregated comparison reports
  independence/             # Independence test results (per model x dataset)
  independence_failure_check/  # Failure-analysis raw data, JSON, plots
  figures/                  # Paper figures
docs/
  PAPER.md                  # The IW-FCV 2026 paper draft
  READ THIS/                # Briefing, audit, paper instructions, CFP
  reports/                  # Finished write-ups (architecture, comparisons, …)
  figures/, changelogs/
  archive/                  # Superseded plans and prior report drafts
```

Each classical pipeline has the same scripts: `trainer.py`, `evaluate.py`, `detect.py`, and `independence_test.py`.

---

## Datasets

- **La Salle (`lasalle_db1`)** — primary dataset; raw + processed (cropped/aligned) variants
- **LFW** — supplementary; processed only
- **Augmented splits** — generated via `scripts/augment_split_light_medium.py`; `light` and `medium` augmentation tiers applied to train/test splits

The launcher guides dataset selection interactively. Evaluation reports embed a `dataset_profile` so cross-dataset runs are never mixed.

---

## Evaluation & Benchmarking

Each evaluator writes a structured JSON report to `reports/evaluation/` with:
- `hit_rate_percent`, threshold sweep, per-identity breakdown
- `dataset_profile`, `model_variant`, `entity_key`, `run_tag`

Benchmark utilities:
- `src/benchmark/compare_classical.py` — spec-table comparison of the three classical families
- `src/benchmark/aggregate_evaluation_reports.py` — groups reports by entity, writes summary JSON + Markdown
- `src/benchmark/aggregate_live_fps.py` — aggregates live-detect FPS logs

The launcher's **Benchmark** menu shows a live overview table (hit rate, accuracy, FPS, model size) across all evaluated models.

---

## Independence Testing (Key Supporting Methodology)

Independence testing is the key supporting methodology behind the gated hybrid cascade - a protocol that ties threshold derivation, model selection, and error detection into one rigorous framework. It performs exhaustive N x (N-1) cross-identity comparisons on a one-image-per-identity gallery, constructing the complete empirical impostor distance distribution. The k-th error pair rule selects match thresholds directly from the order statistics of this distribution, at a specified false acceptance rate (La Salle DB1: 8th of 756 at 10,582 ppm; LFW: 331st of 33M at 10 ppm).

Classical models (LBPH, Eigenfaces, Fisherfaces) and the SFace model each include independence test pipelines. Tests run against the La Salle processed set (28 identities, 756 comparisons) or LFW (5,749 identities, ~33M comparisons in streaming mode). The results determine:
- Which recognizers can hold the 100 ppm false acceptance budget (LBPH passes at 98.21% TAR; Eigenfaces and Fisherfaces fail)
- The deployable match thresholds (tau_accept=73.04, tau_reject=76.85 for the hybrid gate)
- Whether the database contains annotation errors (La Salle: clean; LFW: the known Caldecott-Gilligan near-duplicate flagged)

The formal mathematical foundation is in `docs/report_docs/independence_test/MATHEMATICAL_FOUNDATION.md`. The experimental results with figures are in `outputs/lbph/independence_test_light_front/lasalle_db1_processed_tan_triggs/`.

The **hybrid** has a joint independence test (`src/hybrid/independence_test.py`, Hybrid menu → "independence test"): one N×(N-1) impostor sweep scored by LBPH, SFace, and the gated cascade at once. Besides each engine's false-accept rate and rank-based threshold, it reports the **error overlap** — whether the two engines false-accept the *same* impostor pairs — which is the direct evidence for (or against) CV/DL complementarity. Every rate carries a 95% Wilson confidence interval, and the error 2×2 table gets Fisher's exact test plus the standard classifier-diversity measures (Yule's Q, disagreement, double-fault — Kuncheva & Whitaker 2003) from `src/stats_utils.py` (pure stdlib, no scipy). `src/sface/independence_test.py` separately re-checks parity with the DL track's LFW number.

`scripts/independence_failure_check/` contains post-hoc failure analysis scripts: occlusion analysis, regional collapse detection, multi-image verification, and visual report generation. Their raw data and generated reports live in `reports/independence_failure_check/`.

### Key Results from the Independence Tests

**LBPH (Tan-Triggs) on La Salle DB1** - 756 ordered comparisons, normalized 0-100 scale:
- Min: 72.90 | Mean: 88.15 ± 5.02 | 5th percentile: 78.75 | 8th error pair: 85.88
- No annotation errors - the closest impostor pair (Mary Jade Jakosalem vs Thea Ganza at 72.90) is well-separated
- The only classical recognizer that can hold the 100 ppm FAR budget (TAR 98.21%)

**SFace on La Salle DB1** - 20 false positive pairs out of 756 (2.65% FPR)
**SFace on LFW** - 24,128 false positives out of 32,313,540 comparisons (0.0747% FPR)

See `docs/PAPER.md` Section 4 for the complete results. The SFace LFW-scale independence analysis was performed on the separate `../face-detection-g3-dl` repository (authored by Mr. John); the SFace wrapper in this repo validates parity with those results.

## 41-Modification Robustness (Accuracy Ratio)

The 41 deterministic (modification, level) variants live in `src/benchmark/modifications.py` and are shared by two benchmarks so their probes are bit-identical:

- `src/benchmark/accuracy_ratio.py` — classical families (LBPH / Eigenfaces / Fisherfaces) at the independence-derived threshold
- `src/benchmark/accuracy_ratio_hybrid.py` — **CV (LBPH) vs DL (SFace) vs the hybrid cascade vs parallel** (run-both ceiling) side by side, with Wilson CIs, per-modification winner tags, the cascade's escalation rate, and cascade-vs-parallel deltas — the robustness half of the complementarity argument

## Evidence Matrix (frozen-threshold generalization)

`src/benchmark/evidence_matrix.py` (Benchmark menu → "evidence matrix") proves the generalization claim the defensible way: thresholds are derived **once** on La Salle DB1, frozen (SHA-256 recorded in the report), and applied unchanged to every dataset leg — LS-DB1 (independence), LS-DB2/41-mods (accuracy ratio), LFW1 and LFW2/41-mods (independence; `--lfw-max-identities` gives a tractable seeded subset). Legs whose dataset directory is absent are marked SKIPPED, never silently dropped. Output: `reports/benchmark/evidence_matrix.{json,md}`; `--dry-run` previews the exact commands.

`src/benchmark/compare_classical.py` additionally applies a **pre-committed selection rule** (eligibility gates on TAR@FAR, feature size, FPS; winner by 41-mod AR with a TAR tie-break) so the choice of classical engine is mechanical, not post-hoc.

---

## Dependencies

See [requirements.txt](requirements.txt). Key packages: `opencv-contrib-python` (recognizers + YuNet + SFace), `numpy`, `scikit-learn`, `matplotlib`, `tqdm`.
