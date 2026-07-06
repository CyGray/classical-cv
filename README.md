# Face Detection & Recognition — Group 3

A multi-algorithm face recognition research platform comparing classical CV methods against deep learning approaches, built for the USLS Computer Vision course. The goal is ≥100% accuracy at ≥3 FPS on the La Salle dataset.

---

## Algorithms

| Algorithm | Type | Detection | Recognition |
|---|---|---|---|
| **LBPH** | Classical | Haar cascade | OpenCV LBPHFaceRecognizer |
| **Eigenfaces** | Classical | Haar cascade | OpenCV EigenFaceRecognizer |
| **Fisherfaces** | Classical | Haar cascade | OpenCV FisherFaceRecognizer |
| **MobileFaceNet** | Deep learning | YuNet (ONNX) | MobileFaceNet (ONNX) |
| **EdgeFace** | Deep learning | YuNet (ONNX) | EdgeFace-XS (ONNX) |
| **ArcFace** | Deep learning | InsightFace | buffalo_s ArcFace |
| **ArcFace MobileNet INT8** | Deep learning (quantized) | InsightFace | buffalo_s INT8 |

Classical models train a `.yml` model file + `.json` label map. Deep learning models build an enrollment JSON of face embeddings (identity centroids).

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
  mobilefacenet/            # YuNet + MobileFaceNet pipeline
  edgeface/                 # YuNet + EdgeFace pipeline
  arcface/                  # ArcFace pipeline
  arcface_mobilenet_int8/   # INT8-quantized ArcFace pipeline
  benchmark/                # Cross-model comparison & aggregation
  dataset_layout.py         # Shared dataset/augmentation utilities
  reporting/identity.py     # Shared report identity helpers
  independence_common.py    # Shared independence test utilities
data/
  lasalle_db1/              # Raw La Salle identity images
  lasalle_db1_processed/    # Cropped/aligned La Salle images
  lfw-dataset/              # LFW dataset (processed)
  split_augmented41mods*/   # Augmented splits (light / medium)
models/                     # Saved model artifacts (gitignored)
reports/
  evaluation/               # Per-model JSON evaluation reports
  benchmark/                # Aggregated comparison reports
independence_failure_check/ # Post-hoc independence failure analysis
docs/                       # Design notes and setup guides
```

Each pipeline has the same four scripts: `trainer.py`, `evaluate.py`, `detect.py` (or `face_detect.py`), and optionally `independence_test.py`.

---

## Datasets

- **La Salle (`lasalle_db1`)** — primary dataset; raw + processed (cropped/aligned) variants
- **LFW** — supplementary; processed only
- **Augmented splits** — generated via `augment_split_light_medium.py`; `light` and `medium` augmentation tiers applied to train/test splits

The launcher guides dataset selection interactively. Evaluation reports embed a `dataset_profile` so cross-dataset runs are never mixed.

---

## Evaluation & Benchmarking

Each evaluator writes a structured JSON report to `reports/evaluation/` with:
- `hit_rate_percent`, threshold sweep, per-identity breakdown
- `dataset_profile`, `model_variant`, `entity_key`, `run_tag`

Benchmark utilities:
- `src/benchmark/compare_models.py` — side-by-side model comparison
- `src/benchmark/aggregate_evaluation_reports.py` — groups reports by entity, writes summary JSON + Markdown
- `src/benchmark/aggregate_live_fps.py` — aggregates live-detect FPS logs

The launcher's **Benchmark** menu shows a live overview table (hit rate, accuracy, FPS, model size) across all evaluated models.

---

## Independence Testing

Classical models (LBPH, Eigenfaces, Fisherfaces) include independence tests that verify the model's recognition is not inflated by data leakage between train/test identities. Tests run against the La Salle processed set or LFW segments (up to 6 cross-slice segments for Eigenfaces/Fisherfaces).

The **hybrid** has a joint independence test (`src/hybrid/independence_test.py`, Hybrid menu → "independence test"): one N×(N-1) impostor sweep scored by LBPH, SFace, and the gated cascade at once. Besides each engine's false-accept rate and rank-based threshold, it reports the **error overlap** — whether the two engines false-accept the *same* impostor pairs — which is the direct evidence for (or against) CV/DL complementarity. Every rate carries a 95% Wilson confidence interval, and the error 2×2 table gets Fisher's exact test plus the standard classifier-diversity measures (Yule's Q, disagreement, double-fault — Kuncheva & Whitaker 2003) from `src/stats_utils.py` (pure stdlib, no scipy). `src/sface/independence_test.py` separately re-checks parity with the DL track's LFW number.

`independence_failure_check/` contains post-hoc failure analysis scripts: occlusion analysis, regional collapse detection, multi-image verification, and visual report generation.

## 41-Modification Robustness (Accuracy Ratio)

The 41 deterministic (modification, level) variants live in `src/benchmark/modifications.py` and are shared by two benchmarks so their probes are bit-identical:

- `src/benchmark/accuracy_ratio.py` — classical families (LBPH / Eigenfaces / Fisherfaces) at the independence-derived threshold
- `src/benchmark/accuracy_ratio_hybrid.py` — **CV (LBPH) vs DL (SFace) vs the hybrid cascade vs parallel** (run-both ceiling) side by side, with Wilson CIs, per-modification winner tags, the cascade's escalation rate, and cascade-vs-parallel deltas — the robustness half of the complementarity argument

## Evidence Matrix (frozen-threshold generalization)

`src/benchmark/evidence_matrix.py` (Benchmark menu → "evidence matrix") proves the generalization claim the defensible way: thresholds are derived **once** on La Salle DB1, frozen (SHA-256 recorded in the report), and applied unchanged to every dataset leg — LS-DB1 (independence), LS-DB2/41-mods (accuracy ratio), LFW1 and LFW2/41-mods (independence; `--lfw-max-identities` gives a tractable seeded subset). Legs whose dataset directory is absent are marked SKIPPED, never silently dropped. Output: `reports/benchmark/evidence_matrix.{json,md}`; `--dry-run` previews the exact commands.

`src/benchmark/compare_classical.py` additionally applies a **pre-committed selection rule** (eligibility gates on TAR@FAR, feature size, FPS; winner by 41-mod AR with a TAR tie-break) so the choice of classical engine is mechanical, not post-hoc.

---

## ArcFace INT8 Setup

The INT8 pipeline requires a one-time setup (download FP32 weights → quantize):

```bash
python src/arcface/setup_model.py
python src/arcface_mobilenet_int8/quantize_model.py
```

The launcher will offer to run this automatically on first use.

---

## Dependencies

See [requirements.txt](requirements.txt). Key packages: `opencv-contrib-python`, `insightface`, `onnxruntime`, `numpy`, `scikit-learn`, `tqdm`.
