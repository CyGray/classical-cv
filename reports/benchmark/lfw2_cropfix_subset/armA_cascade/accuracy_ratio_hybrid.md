# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (415 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all). AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py; the 4 detector-canonical ones (rot_90/180/270, flip_lr) are included AND broken out separately below. Retention = AR_mod / AR_clean (threshold-gated).

| Metric | cascade |
|---| ---: |
| Clean held-out baseline - TPIR @ threshold | 90.84% |
| **Overall AR (41 mods, TPIR @ threshold)** | **79.83%** |
| Pooled AR [95% CI] | 79.83% [79.22-80.43] |
| Clean held-out baseline - Rank-1 (threshold-free) | 95.90% |
| Overall Rank-1 (41 mods, threshold-free) | 86.37% |
| Pooled Rank-1 [95% CI] | 86.37% [85.85-86.88] |
| Mean latency | 154.93 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cascade | retention | winner | escalation |
|---| ---: |---:|---|---:|
| brightness_p25 | 89.9% | 0.99 | - | 99% |
| brightness_p20 | 89.4% | 0.98 | - | 98% |
| brightness_p10 | 90.8% | 1.00 | - | 98% |
| monochrome | 87.5% | 0.96 | - | 99% |
| jpeg_q30 | 89.4% | 0.98 | - | 99% |
| jpeg_q60 | 90.4% | 0.99 | - | 99% |
| jpeg_q80 | 91.3% | 1.01 | - | 99% |
| color_8bit | 43.4% | 0.48 | - | 97% |
| rgb565 | 91.3% | 1.01 | - | 100% |
| gaussnoise_12 | 88.0% | 0.97 | - | 100% |
| gaussnoise_8 | 90.1% | 0.99 | - | 100% |
| gaussnoise_4 | 91.8% | 1.01 | - | 100% |
| histeq | 88.0% | 0.97 | - | 98% |
| autolevel | 90.1% | 0.99 | - | 98% |
| blur_7 | 90.8% | 1.00 | - | 100% |
| blur_5 | 91.8% | 1.01 | - | 100% |
| blur_3 | 91.6% | 1.01 | - | 100% |
| rot_270 | 0.0% | 0.00 | - | 100% |
| rot_180 | 0.0% | 0.00 | - | 100% |
| rot_90 | 0.0% | 0.00 | - | 100% |
| rot_45 | 11.1% | 0.12 | - | 100% |
| rot_25 | 62.7% | 0.69 | - | 100% |
| rot_10 | 89.2% | 0.98 | - | 100% |
| scale_50 | 85.3% | 0.94 | - | 100% |
| scale_70 | 89.2% | 0.98 | - | 100% |
| scale_90 | 91.6% | 1.01 | - | 99% |
| trans_30 | 84.3% | 0.93 | - | 100% |
| trans_20 | 90.8% | 1.00 | - | 100% |
| trans_10 | 91.3% | 1.01 | - | 100% |
| flip_lr | 91.6% | 1.01 | - | 99% |
| aspect_6_3 | 91.1% | 1.00 | - | 100% |
| aspect_16_9 | 90.8% | 1.00 | - | 100% |
| crop_60 | 92.8% | 1.02 | - | 100% |
| crop_70 | 93.0% | 1.02 | - | 100% |
| crop_90 | 92.3% | 1.02 | - | 100% |
| skew_10 | 90.1% | 0.99 | - | 99% |
| skew_6 | 89.2% | 0.98 | - | 99% |
| skew_4 | 91.3% | 1.01 | - | 100% |
| persp_10 | 88.4% | 0.97 | - | 100% |
| persp_6 | 89.6% | 0.99 | - | 100% |
| persp_4 | 91.8% | 1.01 | - | 100% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cascade |
|---| ---: |
| brightness_p25 | 96.4% |
| brightness_p20 | 95.9% |
| brightness_p10 | 95.7% |
| monochrome | 96.1% |
| jpeg_q30 | 95.4% |
| jpeg_q60 | 96.1% |
| jpeg_q80 | 96.4% |
| color_8bit | 77.6% |
| rgb565 | 96.9% |
| gaussnoise_12 | 96.1% |
| gaussnoise_8 | 97.1% |
| gaussnoise_4 | 96.6% |
| histeq | 95.4% |
| autolevel | 95.7% |
| blur_7 | 97.1% |
| blur_5 | 96.9% |
| blur_3 | 96.6% |
| rot_270 | 0.0% |
| rot_180 | 0.7% |
| rot_90 | 0.0% |
| rot_45 | 22.9% |
| rot_25 | 81.7% |
| rot_10 | 95.4% |
| scale_50 | 90.4% |
| scale_70 | 93.5% |
| scale_90 | 95.7% |
| trans_30 | 94.9% |
| trans_20 | 95.7% |
| trans_10 | 95.7% |
| flip_lr | 95.7% |
| aspect_6_3 | 96.9% |
| aspect_16_9 | 96.6% |
| crop_60 | 97.3% |
| crop_70 | 97.3% |
| crop_90 | 97.1% |
| skew_10 | 96.4% |
| skew_6 | 95.7% |
| skew_4 | 96.6% |
| persp_10 | 94.5% |
| persp_6 | 95.9% |
| persp_4 | 96.6% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed.

| Metric | cascade |
|---| ---: |
| Detector-canonical AR (TPIR @ threshold) | **22.89%** |
| Detector-canonical Rank-1 (threshold-free) | **24.10%** |

| Modification | cascade | retention | winner | escalation |
|---| ---: |---:|---|---:|
| rot_270 | 0.0% | 0.00 | - | 100% |
| rot_180 | 0.0% | 0.00 | - | 100% |
| rot_90 | 0.0% | 0.00 | - | 100% |
| flip_lr | 91.6% | 1.01 | - | 99% |

| Modification | cascade |
|---| ---: |
| rot_270 | 0.0% |
| rot_180 | 0.7% |
| rot_90 | 0.0% |
| flip_lr | 95.7% |
