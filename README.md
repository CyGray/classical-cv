# Face Detection & Recognition — Group 3

A multi-algorithm face recognition research platform comparing classical CV methods against deep learning approaches, built for the USLS Computer Vision course. The goal is ≥100% accuracy at ≥3 FPS on the La Salle dataset.

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

**Environment override** — to use a specific Python interpreter:
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

## Independence Testing

Classical models (LBPH, Eigenfaces, Fisherfaces) include independence tests that verify the model's recognition is not inflated by data leakage between train/test identities. Tests run against the La Salle processed set or LFW segments (up to 6 cross-slice segments for Eigenfaces/Fisherfaces).

The **hybrid** has a joint independence test (`src/hybrid/independence_test.py`, Hybrid menu → "independence test"): one N×(N-1) impostor sweep scored by LBPH, SFace, and the gated cascade at once. Besides each engine's false-accept rate and rank-based threshold, it reports the **error overlap** — whether the two engines false-accept the *same* impostor pairs — which is the direct evidence for (or against) CV/DL complementarity. Every rate carries a 95% Wilson confidence interval, and the error 2×2 table gets Fisher's exact test plus the standard classifier-diversity measures (Yule's Q, disagreement, double-fault — Kuncheva & Whitaker 2003) from `src/stats_utils.py` (pure stdlib, no scipy). `src/sface/independence_test.py` separately re-checks parity with the DL track's LFW number.

`scripts/independence_failure_check/` contains post-hoc failure analysis scripts: occlusion analysis, regional collapse detection, multi-image verification, and visual report generation. Their raw data and generated reports live in `reports/independence_failure_check/`.

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
