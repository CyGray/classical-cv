# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (415 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all). AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py; the 4 detector-canonical ones (rot_90/180/270, flip_lr) are included AND broken out separately below. Retention = AR_mod / AR_clean (threshold-gated).

| Metric | cv_only | dl_only |
|---| ---: | ---: |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 91.81% |
| **Overall AR (41 mods, TPIR @ threshold)** | **0.00%** | **80.30%** |
| Pooled AR [95% CI] | 0.00% [0.00-0.02] | 80.30% [79.70-80.89] |
| Clean held-out baseline - Rank-1 (threshold-free) | 4.34% | 96.87% |
| Overall Rank-1 (41 mods, threshold-free) | 2.38% | 86.95% |
| Pooled Rank-1 [95% CI] | 2.38% [2.16-2.62] | 86.95% [86.44-87.45] |
| Mean latency | 103.03 ms | 54.75 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner | escalation |
|---| ---: | ---: |---:|---|---:|
| brightness_p25 | 0.0% | 90.8% | n/a / 0.99 | dl_stronger | - |
| brightness_p20 | 0.0% | 90.6% | n/a / 0.99 | dl_stronger | - |
| brightness_p10 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger | - |
| monochrome | 0.0% | 88.4% | n/a / 0.96 | dl_stronger | - |
| jpeg_q30 | 0.0% | 90.6% | n/a / 0.99 | dl_stronger | - |
| jpeg_q60 | 0.0% | 91.6% | n/a / 1.00 | dl_stronger | - |
| jpeg_q80 | 0.0% | 92.3% | n/a / 1.01 | dl_stronger | - |
| color_8bit | 0.0% | 44.6% | n/a / 0.49 | dl_stronger | - |
| rgb565 | 0.0% | 91.3% | n/a / 0.99 | dl_stronger | - |
| gaussnoise_12 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger | - |
| gaussnoise_8 | 0.0% | 89.9% | n/a / 0.98 | dl_stronger | - |
| gaussnoise_4 | 0.0% | 91.6% | n/a / 1.00 | dl_stronger | - |
| histeq | 0.0% | 89.4% | n/a / 0.97 | dl_stronger | - |
| autolevel | 0.0% | 91.3% | n/a / 0.99 | dl_stronger | - |
| blur_7 | 0.0% | 90.8% | n/a / 0.99 | dl_stronger | - |
| blur_5 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger | - |
| blur_3 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger | - |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_45 | 0.0% | 10.8% | n/a / 0.12 | dl_stronger | - |
| rot_25 | 0.0% | 63.1% | n/a / 0.69 | dl_stronger | - |
| rot_10 | 0.0% | 89.4% | n/a / 0.97 | dl_stronger | - |
| scale_50 | 0.0% | 85.3% | n/a / 0.93 | dl_stronger | - |
| scale_70 | 0.0% | 89.4% | n/a / 0.97 | dl_stronger | - |
| scale_90 | 0.0% | 92.3% | n/a / 1.01 | dl_stronger | - |
| trans_30 | 0.0% | 84.3% | n/a / 0.92 | dl_stronger | - |
| trans_20 | 0.0% | 91.1% | n/a / 0.99 | dl_stronger | - |
| trans_10 | 0.0% | 91.8% | n/a / 1.00 | dl_stronger | - |
| flip_lr | 0.0% | 92.8% | n/a / 1.01 | dl_stronger | - |
| aspect_6_3 | 0.0% | 91.6% | n/a / 1.00 | dl_stronger | - |
| aspect_16_9 | 0.0% | 91.3% | n/a / 0.99 | dl_stronger | - |
| crop_60 | 0.0% | 92.8% | n/a / 1.01 | dl_stronger | - |
| crop_70 | 0.0% | 93.0% | n/a / 1.01 | dl_stronger | - |
| crop_90 | 0.0% | 92.5% | n/a / 1.01 | dl_stronger | - |
| skew_10 | 0.0% | 90.8% | n/a / 0.99 | dl_stronger | - |
| skew_6 | 0.0% | 90.4% | n/a / 0.98 | dl_stronger | - |
| skew_4 | 0.0% | 91.6% | n/a / 1.00 | dl_stronger | - |
| persp_10 | 0.0% | 88.7% | n/a / 0.97 | dl_stronger | - |
| persp_6 | 0.0% | 89.9% | n/a / 0.98 | dl_stronger | - |
| persp_4 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger | - |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---| ---: | ---: |
| brightness_p25 | 3.1% | 97.3% |
| brightness_p20 | 4.1% | 97.1% |
| brightness_p10 | 4.1% | 97.1% |
| monochrome | 4.3% | 97.1% |
| jpeg_q30 | 2.7% | 96.9% |
| jpeg_q60 | 4.1% | 97.3% |
| jpeg_q80 | 3.4% | 97.3% |
| color_8bit | 1.7% | 80.2% |
| rgb565 | 2.7% | 97.1% |
| gaussnoise_12 | 1.0% | 96.1% |
| gaussnoise_8 | 1.2% | 97.1% |
| gaussnoise_4 | 3.6% | 96.6% |
| histeq | 3.9% | 97.1% |
| autolevel | 4.1% | 96.9% |
| blur_7 | 2.7% | 97.1% |
| blur_5 | 3.6% | 97.3% |
| blur_3 | 3.6% | 97.1% |
| rot_270 | 0.2% | 0.0% |
| rot_180 | 0.2% | 0.7% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.2% | 23.1% |
| rot_25 | 0.7% | 82.2% |
| rot_10 | 2.7% | 95.7% |
| scale_50 | 0.2% | 90.4% |
| scale_70 | 0.5% | 93.7% |
| scale_90 | 2.4% | 96.6% |
| trans_30 | 0.2% | 94.9% |
| trans_20 | 0.5% | 95.9% |
| trans_10 | 0.7% | 96.1% |
| flip_lr | 1.2% | 96.9% |
| aspect_6_3 | 2.9% | 97.3% |
| aspect_16_9 | 2.7% | 97.1% |
| crop_60 | 1.7% | 97.6% |
| crop_70 | 2.9% | 97.3% |
| crop_90 | 4.1% | 97.3% |
| skew_10 | 2.4% | 97.1% |
| skew_6 | 3.1% | 96.9% |
| skew_4 | 3.6% | 97.1% |
| persp_10 | 2.7% | 94.9% |
| persp_6 | 4.1% | 96.1% |
| persp_4 | 3.9% | 96.9% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed.

| Metric | cv_only | dl_only |
|---| ---: | ---: |
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **23.19%** |
| Detector-canonical Rank-1 (threshold-free) | **0.42%** | **24.40%** |

| Modification | cv_only | dl_only | retention | winner | escalation |
|---| ---: | ---: |---:|---|---:|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie | - |
| flip_lr | 0.0% | 92.8% | n/a / 1.01 | dl_stronger | - |

| Modification | cv_only | dl_only |
|---| ---: | ---: |
| rot_270 | 0.2% | 0.0% |
| rot_180 | 0.2% | 0.7% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 1.2% | 96.9% |
