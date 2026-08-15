# LSDB DL same-split extension — 2026-08-11

> **Status:** superseded for DL model selection by
> `../lsdb_selection_dl_trio_2026-08-11/`. This retained SFace-only campaign
> is auditable early characterization, not completed SFace/ArcFace/FaceNet
> comparison.

This campaign supplies a recoverable SFace characterization for the LSDB
algorithm-selection protocol. It is a companion to
`lsdb_selection_2026-08-10/`, not a recalibration of any frozen LFW threshold.

## Same-harness SFace result

The current deterministic LSDB cohort was used exactly as for the classical
campaign: 224 fit images (28 identities × 8), 56 disjoint calibration images,
and 56 untouched test images. SFace enrolment averages eight unit-normalized
embeddings per identity; the calibration-only rank-15 impostor score sets the
acceptance edge (15 / 1,512 = 0.9921% realized FAR).

| Candidate | Feature bytes | Calibration threshold | Test TAR | Test Rank-1 | Status |
|---|---:|---:|---:|---:|---|
| SFace | 512 | 1.03462029 | 100.00% | 100.00% | Fresh same-split campaign |

The extraction contract is YuNet largest-face detection at score >= 0.50,
`FaceRecognizerSF.alignCrop`, LAB-CLAHE (`clipLimit=2.0`, `8×8`), SFace
features, and unit-vector L2 scoring. The deprecated extractor's historical
0.60 detector edge missed one current fit image; the recorded 0.50 edge embeds
all 336 planned records with no silent skips. See `run_provenance.json` for
model/pixel hashes, versions, and the exact command.

## Archived candidates not scored

ArcFace and FaceNet retain 280 archived training vectors; MobileNet retains
275. None contains the 56 held-out `dark_name.jpg` / `light_name.jpg` vectors,
none has per-image pixel hashes, and their original extractor weights are not
present. They therefore have no same-harness held-out TAR or Rank-1 metric.
`archived_candidate_inventory.json` records this boundary. Their historical
feature sizes remain 2,048 B (ArcFace/FaceNet) and 5,120 B (MobileNet).

This provides an honest SFace characterization on the classical campaign's
split. It does not select a DL model; use successor trio campaign for that
claim.

## Supporting artifacts

- `summary.json` — headline protocol and metrics.
- `split_manifest.json`, `embedding_records.jsonl`, and `embeddings.npz` —
  cohort identity, pixel hashes, detector score, and normalized embeddings.
- `gallery_templates.npz` / `gallery_manifest.json` — enrolment output.
- `calibration_scores.csv`, `test_scores.csv`, and `test_decisions.csv` — all
  raw scoring needed to recompute threshold, FAR, TAR, and Rank-1.
- `run_provenance.json` and `artifact_hashes.json` — reproducibility record.
