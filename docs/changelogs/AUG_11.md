# Changelog - 2026-08-11

## Session 2026-08-11 16:37:18 +08:00 — SFace-only precursor

### Status correction

- Added the initial fresh SFace same-split campaign and its canonical evidence
  folder, `docs/results/algo_test/lsdb_selection_dl_2026-08-11/`.
- It remains auditable SFace characterization only. It is **superseded for DL
  model selection** by the trio campaign below.
- Do not use its single-model result to imply that ArcFace and FaceNet were
  compared or unavailable forever.

## Session 2026-08-11 17:30:46 +08:00 — LSDB deep-learning trio recovery and selection

### Scope

- Corrected candidate set from deprecated DL selection materials:
  **SFace, ArcFace, FaceNet**.
- Excluded MobileNetV2 from selection. It exists in `deep-learning/models.py`
  and archived vectors, but is not named by the original selection artifact.
- Kept classical LBPH/Eigenfaces/Fisherfaces evidence separate. This is a
  DL-only ranking, not a cross-weight-class accuracy contest.

### Runtime/model recovery

- Recovered usable Python 3.12 runtime for the archived package definitions.
  Archive preserved package trees but no virtual-environment interpreter and
  incomplete TensorFlow binary import.
- Matched archived package versions:
  - TensorFlow `2.21.0`; Keras `3.14.1`; `tf-keras` `2.21.0`;
  - DeepFace `0.0.100`; `keras-facenet` `0.3.2`.
- Materialized package-defined pretrained weights and recorded SHA-256 in
  `run_provenance.json`:
  - ArcFace `arcface_weights.h5`:
    `6336979c0c602cae08d1122a66f4dfb862d059bbcd8ef80306aef2b2249b0c93`;
  - FaceNet `20180402-114759-weights.h5`:
    `8b71e7045497e841c00ee568f031d1a4d30908fceadf6884aef2dec4d545202b`.
- Archived feature vectors remain diagnostics only: they match training
  identifiers after legacy-name normalization, have zero held-out test
  identifiers, and lack per-image pixel-hash binding.

### Scorer and protocol

- Replaced SFace-only
  `classical-cv/scripts/pipeline/score_lsdb_dl_selection.py` with canonical
  DL-trio scorer.
- Shared deterministic cohort per candidate:
  - 224 fit images (28 identities × 8) for enrolment;
  - 56 calibration images (28 × 2) for threshold choice;
  - 56 untouched held-out test images (28 × 2).
- Shared image contract: YuNet largest face (`score >= 0.50`),
  `FaceRecognizerSF.alignCrop`, LAB-CLAHE (`clipLimit=2.0`, 8×8), and fail-run
  handling for any unreadable/no-face/invalid record.
- Native model scoring retained:
  - SFace: unit-normalized Euclidean L2;
  - ArcFace: unit-normalized `1 - cosine`;
  - FaceNet: legacy raw-vector Euclidean L2.
- Every model has a calibration-only rank-15 edge over 1,512 cross-identity
  scores, giving 15/1,512 = 0.9921% realized FAR. Test set never tunes edge.

```powershell
$env:PYTHONUTF8 = '1'
& C:\Users\acer\AppData\Local\Temp\lsface-dl-selection-20260811\Scripts\python.exe `
  classical-cv\scripts\pipeline\score_lsdb_dl_selection.py `
  --output-dir classical-cv\outputs\provenance_reruns\candidate_selection_lsdb_dl_trio_2026-08-11 `
  --deepface-home C:\Users\acer\AppData\Local\Temp\lsface-dl-selection-20260811\assets\deepface `
  --facenet-cache C:\Users\acer\.keras-facenet
```

### Fresh DL-only result

| Candidate | Feature bytes | Calibration edge | Calibration TAR | Test TAR | Test Rank-1 |
|---|---:|---:|---:|---:|---:|
| SFace | 512 | 1.03246903 | 96.43% | 100.00% | 100.00% |
| ArcFace | 2,048 | 0.36933035 | 69.64% | 96.43% | 100.00% |
| FaceNet | 2,048 | 0.68705863 | 92.86% | 100.00% | 100.00% |

- Selection rule: held-out TAR, then held-out Rank-1, then smaller float32
  feature vector.
- Result: SFace and FaceNet tie at 100.00% TAR/Rank-1; SFace wins footprint
  tie-break (512 B versus 2,048 B). ArcFace ranks third at 96.43% TAR.

### Validation and canonical evidence

- Independently recomputed each family from raw CSVs: 1,568 calibration rows,
  1,512 impostor rows, 1,568 test rows, 56 decisions, rank-15 threshold, FAR,
  TAR, Rank-1, and all promoted artifact hashes.
- Repeated complete 336-image extraction/run. All 21 text artifacts and six
  NPZ array payloads were exactly identical; repeat remains raw confirmation.
- Added canonical
  `docs/results/algo_test/lsdb_selection_dl_trio_2026-08-11/` (30 artifacts):
  summary, split/pixel manifest, all model embeddings/galleries, calibration
  and test scores/decisions, archive diagnostics, provenance, and hashes.
- Updated selection READMEs and `scripts/pipeline/README_lsdb_model_selection.md`
  to point to DL trio and label SFace-only folder as precursor.
- Regenerated `docs/results/RESULTS_MANIFEST.json`: 154 artifacts total;
  all 30 new trio entries are `canonical_snapshot` with source provenance.

### Commit status

- No commit, tag, version bump, or push requested.

## Session 2026-08-11 19:07:09 +08:00 -- Manuscript Section 4.1 DL-only selection integration

### Manuscript and evidence

- Updated `docs/manuscript/lsface.docm` Section 4.1 with a distinct
  DL-only candidate-selection table for SFace, ArcFace, and FaceNet. The
  classical LBPH/Eigenfaces/Fisherfaces table remains a separate ranking.
- Recorded the shared deterministic 224/56/56 LSDB cohort, the calibration-only
  rank-15 edge from 1,512 cross-identity scores (0.992% realized FAR), and the
  model-native-score caveat. This is not framed as a cross-family accuracy
  contest or a deployment-threshold recalibration.
- Added the held-out result and selection rule: SFace and FaceNet tie at
  100.00% TAR and Rank-1; SFace wins the 512 B versus 2,048 B feature-size
  tie-break; ArcFace reaches 96.43% TAR and 100.00% Rank-1.
- Added the corresponding claim-evidence-register rows pointing to
  `docs/results/algo_test/lsdb_selection_dl_trio_2026-08-11/`.

### Document integrity

- Archived the live pre-edit manuscript as
  `010_lsface_before-dl-trio-selection.docm` and the final output as
  `014_lsface_dl-trio-selection-final-verified.docm`.
- Repaired inherited caption placement in the later Section 4 tables,
  renumbered affected tables/figures, and kept the Figure 1 lead with its
  figure.
- Rendered and inspected the affected spreads. All six tables fit the text
  block, captions match the reference template, the final manuscript remains
  14 pages, and the VBA project hash matches the pre-edit manuscript.

### Commit status

- No commit, tag, version bump, or push requested.
