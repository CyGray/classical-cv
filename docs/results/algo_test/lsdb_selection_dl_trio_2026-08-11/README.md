# LSDB deep-learning trio selection — 2026-08-11

This is canonical fresh **deep-learning-only** algorithm-selection campaign.
Candidates are three models named by deprecated DL selection materials:
**SFace, ArcFace, FaceNet**. MobileNetV2 exists in old source tree but was not
selection candidate.

## Protocol

All candidates use same current deterministic LSDB cohort: 224 fit images
(28 identities × 8), 56 disjoint calibration images, and 56 untouched test
images. Every candidate receives its own calibration-only acceptance edge from
rank-15 score among 1,512 cross-identity calibration comparisons. Realized FAR
is 15/1,512 = 0.9921% for every model. No test result set threshold.

Shared image path recreates deprecated extractor contract: YuNet largest-face
detection (score >= 0.50), `FaceRecognizerSF.alignCrop`, then LAB-CLAHE
(`clipLimit=2.0`, 8×8). SFace uses unit-vector L2, ArcFace uses unit-vector
cosine distance, FaceNet retains legacy raw-vector L2 score. Each identity
enrolment is mean of eight fit vectors (post-mean unit normalization for SFace
and ArcFace).

## Result

| Candidate | Feature bytes | Calibration threshold | Calibration TAR | Test TAR | Test Rank-1 |
|---|---:|---:|---:|---:|---:|
| SFace | 512 | 1.03246903 | 96.43% | 100.00% | 100.00% |
| ArcFace | 2,048 | 0.36933035 | 69.64% | 96.43% | 100.00% |
| FaceNet | 2,048 | 0.68705863 | 92.86% | 100.00% | 100.00% |

SFace and FaceNet tie on held-out TAR and Rank-1. Recorded tie-breaker is
smaller float32 feature vector, so **SFace is selected** (512 B versus 2,048
B). ArcFace ranks third because held-out TAR is 96.43%.

## Boundaries and reproducibility

- DL-trio comparison only. Do not merge it into separate classical
  LBPH/Eigenfaces/Fisherfaces selection ranking.
- Historical DL feature files are audit-only. They cover current training
  identifiers but zero held-out test identifiers and lack per-image pixel
  hashes. `archived_candidate_inventory.json` and
  `archive_similarity_*.json` preserve boundary.
- `run_provenance.json` records package versions, YuNet/SFace hashes,
  ArcFace/FaceNet pretrained-weight hashes, split pixel hashes, and command.
- Second full raw run reproduced 21 text artifacts and six NPZ array payloads
  exactly. It stays raw confirmation under `classical-cv/outputs/provenance_reruns/`.

## Supporting artifacts

`embeddings_*`, `gallery_templates_*`, `calibration_scores_*`,
`test_scores_*`, and `test_decisions_*` contain every vector, enrolment,
score, threshold input, and held-out decision needed to recompute table.
`artifact_hashes.json` verifies promoted raw artifacts.
