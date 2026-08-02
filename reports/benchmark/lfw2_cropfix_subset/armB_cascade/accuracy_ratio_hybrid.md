# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (415 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all). AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py; the 4 detector-canonical ones (rot_90/180/270, flip_lr) are included AND broken out separately below. Retention = AR_mod / AR_clean (threshold-gated).

| Metric | cascade |
|---| ---: |
| Clean held-out baseline - TPIR @ threshold | 91.81% |
| **Overall AR (41 mods, TPIR @ threshold)** | **80.35%** |
| Pooled AR [95% CI] | 80.35% [79.74-80.94] |
| Clean held-out baseline - Rank-1 (threshold-free) | 96.87% |
| Overall Rank-1 (41 mods, threshold-free) | 86.94% |
| Pooled Rank-1 [95% CI] | 86.94% [86.43-87.44] |
| Mean latency | 155.25 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cascade | retention | winner | escalation |
|---| ---: |---:|---|---:|
| brightness_p25 | 90.8% | 0.99 | - | 100% |
| brightness_p20 | 90.6% | 0.99 | - | 100% |
| brightness_p10 | 92.3% | 1.01 | - | 100% |
| monochrome | 88.4% | 0.96 | - | 100% |
| jpeg_q30 | 90.6% | 0.99 | - | 100% |
| jpeg_q60 | 91.6% | 1.00 | - | 100% |
| jpeg_q80 | 92.3% | 1.01 | - | 100% |
| color_8bit | 44.8% | 0.49 | - | 100% |
| rgb565 | 91.6% | 1.00 | - | 100% |
| gaussnoise_12 | 87.7% | 0.96 | - | 100% |
| gaussnoise_8 | 90.1% | 0.98 | - | 100% |
| gaussnoise_4 | 91.8% | 1.00 | - | 100% |
| histeq | 89.4% | 0.97 | - | 100% |
| autolevel | 91.3% | 0.99 | - | 100% |
| blur_7 | 90.8% | 0.99 | - | 100% |
| blur_5 | 92.3% | 1.01 | - | 100% |
| blur_3 | 92.0% | 1.00 | - | 100% |
| rot_270 | 0.0% | 0.00 | - | 97% |
| rot_180 | 0.0% | 0.00 | - | 100% |
| rot_90 | 0.0% | 0.00 | - | 99% |
| rot_45 | 11.1% | 0.12 | - | 100% |
| rot_25 | 63.1% | 0.69 | - | 100% |
| rot_10 | 89.4% | 0.97 | - | 100% |
| scale_50 | 85.3% | 0.93 | - | 100% |
| scale_70 | 89.4% | 0.97 | - | 100% |
| scale_90 | 92.5% | 1.01 | - | 100% |
| trans_30 | 84.1% | 0.92 | - | 100% |
| trans_20 | 91.1% | 0.99 | - | 100% |
| trans_10 | 91.8% | 1.00 | - | 100% |
| flip_lr | 92.8% | 1.01 | - | 100% |
| aspect_6_3 | 91.6% | 1.00 | - | 100% |
| aspect_16_9 | 91.3% | 0.99 | - | 100% |
| crop_60 | 92.8% | 1.01 | - | 100% |
| crop_70 | 93.0% | 1.01 | - | 100% |
| crop_90 | 92.5% | 1.01 | - | 100% |
| skew_10 | 90.8% | 0.99 | - | 100% |
| skew_6 | 90.4% | 0.98 | - | 100% |
| skew_4 | 91.8% | 1.00 | - | 100% |
| persp_10 | 88.9% | 0.97 | - | 100% |
| persp_6 | 89.9% | 0.98 | - | 100% |
| persp_4 | 92.0% | 1.00 | - | 100% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cascade |
|---| ---: |
| brightness_p25 | 97.3% |
| brightness_p20 | 97.1% |
| brightness_p10 | 97.1% |
| monochrome | 97.1% |
| jpeg_q30 | 96.9% |
| jpeg_q60 | 97.3% |
| jpeg_q80 | 97.3% |
| color_8bit | 80.2% |
| rgb565 | 97.1% |
| gaussnoise_12 | 95.9% |
| gaussnoise_8 | 97.1% |
| gaussnoise_4 | 96.6% |
| histeq | 97.1% |
| autolevel | 96.9% |
| blur_7 | 97.1% |
| blur_5 | 97.3% |
| blur_3 | 97.1% |
| rot_270 | 0.0% |
| rot_180 | 0.7% |
| rot_90 | 0.0% |
| rot_45 | 23.1% |
| rot_25 | 82.2% |
| rot_10 | 95.7% |
| scale_50 | 90.4% |
| scale_70 | 93.7% |
| scale_90 | 96.6% |
| trans_30 | 94.7% |
| trans_20 | 95.9% |
| trans_10 | 96.1% |
| flip_lr | 96.9% |
| aspect_6_3 | 97.3% |
| aspect_16_9 | 97.1% |
| crop_60 | 97.6% |
| crop_70 | 97.3% |
| crop_90 | 97.3% |
| skew_10 | 97.1% |
| skew_6 | 96.9% |
| skew_4 | 97.1% |
| persp_10 | 94.9% |
| persp_6 | 96.1% |
| persp_4 | 96.9% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed.

| Metric | cascade |
|---| ---: |
| Detector-canonical AR (TPIR @ threshold) | **23.19%** |
| Detector-canonical Rank-1 (threshold-free) | **24.40%** |

| Modification | cascade | retention | winner | escalation |
|---| ---: |---:|---|---:|
| rot_270 | 0.0% | 0.00 | - | 97% |
| rot_180 | 0.0% | 0.00 | - | 100% |
| rot_90 | 0.0% | 0.00 | - | 99% |
| flip_lr | 92.8% | 1.01 | - | 100% |

| Modification | cascade |
|---| ---: |
| rot_270 | 0.0% |
| rot_180 | 0.7% |
| rot_90 | 0.0% |
| flip_lr | 96.9% |
