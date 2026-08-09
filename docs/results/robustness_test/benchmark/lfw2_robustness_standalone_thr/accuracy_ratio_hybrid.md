# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (1680 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `strict`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all). AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py; the 4 detector-canonical ones (rot_90/180/270, flip_lr) are included AND broken out separately below. Retention = AR_mod / AR_clean (threshold-gated).

| Metric | cv_only | dl_only |
|---| ---: | ---: |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 91.96% |
| **Overall AR (41 mods, TPIR @ threshold)** | **0.01%** | **80.61%** |
| Pooled AR [95% CI] | 0.01% [0.00-0.01] | 80.61% [80.32-80.91] |
| Clean held-out baseline - Rank-1 (threshold-free) | 2.92% | 95.42% |
| Overall Rank-1 (41 mods, threshold-free) | 1.83% | 85.09% |
| Pooled Rank-1 [95% CI] | 1.83% [1.73-1.94] | 85.09% [84.82-85.36] |
| Mean latency | 309.75 ms | 45.01 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner | escalation |
|---| ---: | ---: |---:|---|---:|
| brightness_p25 | 0.0% | 91.2% | n/a / 0.99 | dl_stronger | - |
| brightness_p20 | 0.0% | 91.3% | n/a / 0.99 | dl_stronger | - |
| brightness_p10 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger | - |
| monochrome | 0.0% | 88.9% | n/a / 0.97 | dl_stronger | - |
| jpeg_q30 | 0.0% | 90.9% | n/a / 0.99 | dl_stronger | - |
| jpeg_q60 | 0.0% | 91.8% | n/a / 1.00 | dl_stronger | - |
| jpeg_q80 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger | - |
| color_8bit | 0.0% | 47.1% | n/a / 0.51 | dl_stronger | - |
| rgb565 | 0.0% | 91.9% | n/a / 1.00 | dl_stronger | - |
| gaussnoise_12 | 0.0% | 88.8% | n/a / 0.97 | dl_stronger | - |
| gaussnoise_8 | 0.0% | 90.8% | n/a / 0.99 | dl_stronger | - |
| gaussnoise_4 | 0.0% | 91.8% | n/a / 1.00 | dl_stronger | - |
| histeq | 0.0% | 89.5% | n/a / 0.97 | dl_stronger | - |
| autolevel | 0.0% | 91.8% | n/a / 1.00 | dl_stronger | - |
| blur_7 | 0.1% | 90.6% | n/a / 0.99 | dl_stronger | - |
| blur_5 | 0.1% | 91.5% | n/a / 1.00 | dl_stronger | - |
| blur_3 | 0.1% | 92.1% | n/a / 1.00 | dl_stronger | - |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_45 | 0.0% | 10.4% | n/a / 0.11 | dl_stronger | - |
| rot_25 | 0.0% | 62.8% | n/a / 0.68 | dl_stronger | - |
| rot_10 | 0.0% | 89.4% | n/a / 0.97 | dl_stronger | - |
| scale_50 | 0.0% | 85.3% | n/a / 0.93 | dl_stronger | - |
| scale_70 | 0.0% | 89.2% | n/a / 0.97 | dl_stronger | - |
| scale_90 | 0.0% | 91.9% | n/a / 1.00 | dl_stronger | - |
| trans_30 | 0.0% | 85.7% | n/a / 0.93 | dl_stronger | - |
| trans_20 | 0.0% | 91.8% | n/a / 1.00 | dl_stronger | - |
| trans_10 | 0.0% | 92.4% | n/a / 1.01 | dl_stronger | - |
| flip_lr | 0.0% | 92.6% | n/a / 1.01 | dl_stronger | - |
| aspect_6_3 | 0.0% | 91.7% | n/a / 1.00 | dl_stronger | - |
| aspect_16_9 | 0.1% | 91.8% | n/a / 1.00 | dl_stronger | - |
| crop_60 | 0.0% | 93.2% | n/a / 1.01 | dl_stronger | - |
| crop_70 | 0.0% | 93.2% | n/a / 1.01 | dl_stronger | - |
| crop_90 | 0.0% | 92.5% | n/a / 1.01 | dl_stronger | - |
| skew_10 | 0.0% | 91.2% | n/a / 0.99 | dl_stronger | - |
| skew_6 | 0.0% | 91.6% | n/a / 1.00 | dl_stronger | - |
| skew_4 | 0.0% | 91.9% | n/a / 1.00 | dl_stronger | - |
| persp_10 | 0.0% | 89.4% | n/a / 0.97 | dl_stronger | - |
| persp_6 | 0.0% | 91.0% | n/a / 0.99 | dl_stronger | - |
| persp_4 | 0.0% | 92.1% | n/a / 1.00 | dl_stronger | - |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---| ---: | ---: |
| brightness_p25 | 2.6% | 95.6% |
| brightness_p20 | 2.9% | 95.3% |
| brightness_p10 | 2.9% | 95.4% |
| monochrome | 2.9% | 94.5% |
| jpeg_q30 | 2.7% | 95.1% |
| jpeg_q60 | 2.9% | 95.6% |
| jpeg_q80 | 2.9% | 95.7% |
| color_8bit | 1.4% | 73.3% |
| rgb565 | 2.6% | 95.7% |
| gaussnoise_12 | 1.0% | 94.5% |
| gaussnoise_8 | 1.4% | 95.3% |
| gaussnoise_4 | 2.3% | 95.4% |
| histeq | 2.8% | 94.9% |
| autolevel | 3.1% | 95.4% |
| blur_7 | 2.2% | 94.8% |
| blur_5 | 2.7% | 95.6% |
| blur_3 | 2.7% | 95.8% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.1% | 0.1% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 17.1% |
| rot_25 | 0.2% | 73.8% |
| rot_10 | 2.1% | 94.6% |
| scale_50 | 0.0% | 88.5% |
| scale_70 | 0.3% | 92.2% |
| scale_90 | 2.1% | 95.0% |
| trans_30 | 0.1% | 92.9% |
| trans_20 | 0.1% | 95.2% |
| trans_10 | 0.4% | 95.4% |
| flip_lr | 0.7% | 95.8% |
| aspect_6_3 | 2.4% | 95.5% |
| aspect_16_9 | 2.6% | 95.6% |
| crop_60 | 1.2% | 96.4% |
| crop_70 | 2.0% | 96.1% |
| crop_90 | 2.8% | 96.0% |
| skew_10 | 2.6% | 95.4% |
| skew_6 | 2.8% | 95.6% |
| skew_4 | 2.8% | 95.7% |
| persp_10 | 2.4% | 93.9% |
| persp_6 | 2.6% | 95.1% |
| persp_4 | 2.9% | 95.4% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed.

| Metric | cv_only | dl_only |
|---| ---: | ---: |
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **23.14%** |
| Detector-canonical Rank-1 (threshold-free) | **0.19%** | **23.96%** |

| Modification | cv_only | dl_only | retention | winner | escalation |
|---| ---: | ---: |---:|---|---:|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| flip_lr | 0.0% | 92.6% | n/a / 1.01 | dl_stronger | - |

| Modification | cv_only | dl_only |
|---| ---: | ---: |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.1% | 0.1% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 0.7% | 95.8% |
