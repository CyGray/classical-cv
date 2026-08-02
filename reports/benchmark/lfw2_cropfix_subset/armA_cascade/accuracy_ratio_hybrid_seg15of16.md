# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (26 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cascade |
|---|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 92.31% |
| Clean held-out baseline - TPIR @ threshold | 88.46% |
| **Overall AR (41 mods, TPIR @ threshold)** | **79.27%** |
| Pooled AR [95% CI] | 79.27% [76.73-81.59] |
| Overall Rank-1 (41 mods, threshold-free) | 85.65% |
| Pooled Rank-1 [95% CI] | 85.65% [83.41-87.62] |
| Mean latency | 117.07 ms |
| Latency median / p95 | 114.37 / 158.35 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| brightness_p25 | 92.3% | 1.04 | 100% |
| brightness_p20 | 96.2% | 1.09 | 100% |
| brightness_p10 | 92.3% | 1.04 | 96% |
| monochrome | 84.6% | 0.96 | 96% |
| jpeg_q30 | 92.3% | 1.04 | 100% |
| jpeg_q60 | 88.5% | 1.00 | 96% |
| jpeg_q80 | 88.5% | 1.00 | 96% |
| color_8bit | 26.9% | 0.30 | 92% |
| rgb565 | 92.3% | 1.04 | 100% |
| gaussnoise_12 | 88.5% | 1.00 | 100% |
| gaussnoise_8 | 88.5% | 1.00 | 100% |
| gaussnoise_4 | 96.2% | 1.09 | 100% |
| histeq | 88.5% | 1.00 | 96% |
| autolevel | 92.3% | 1.04 | 96% |
| blur_7 | 92.3% | 1.04 | 100% |
| blur_5 | 92.3% | 1.04 | 100% |
| blur_3 | 96.2% | 1.09 | 100% |
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 96% |
| rot_90 | 0.0% | 0.00 | 100% |
| rot_45 | 15.4% | 0.17 | 100% |
| rot_25 | 73.1% | 0.83 | 100% |
| rot_10 | 92.3% | 1.04 | 100% |
| scale_50 | 88.5% | 1.00 | 100% |
| scale_70 | 84.6% | 0.96 | 96% |
| scale_90 | 84.6% | 0.96 | 96% |
| trans_30 | 73.1% | 0.83 | 100% |
| trans_20 | 84.6% | 0.96 | 100% |
| trans_10 | 92.3% | 1.04 | 100% |
| flip_lr | 88.5% | 1.00 | 96% |
| aspect_6_3 | 88.5% | 1.00 | 96% |
| aspect_16_9 | 88.5% | 1.00 | 96% |
| crop_60 | 92.3% | 1.04 | 100% |
| crop_70 | 88.5% | 1.00 | 100% |
| crop_90 | 92.3% | 1.04 | 100% |
| skew_10 | 88.5% | 1.00 | 96% |
| skew_6 | 84.6% | 0.96 | 96% |
| skew_4 | 92.3% | 1.04 | 96% |
| persp_10 | 76.9% | 0.87 | 96% |
| persp_6 | 92.3% | 1.04 | 100% |
| persp_4 | 100.0% | 1.13 | 100% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cascade |
|---|---:|
| brightness_p25 | 96.2% |
| brightness_p20 | 96.2% |
| brightness_p10 | 92.3% |
| monochrome | 92.3% |
| jpeg_q30 | 100.0% |
| jpeg_q60 | 96.2% |
| jpeg_q80 | 92.3% |
| color_8bit | 61.5% |
| rgb565 | 96.2% |
| gaussnoise_12 | 100.0% |
| gaussnoise_8 | 96.2% |
| gaussnoise_4 | 96.2% |
| histeq | 92.3% |
| autolevel | 96.2% |
| blur_7 | 100.0% |
| blur_5 | 100.0% |
| blur_3 | 96.2% |
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| rot_45 | 23.1% |
| rot_25 | 84.6% |
| rot_10 | 96.2% |
| scale_50 | 92.3% |
| scale_70 | 88.5% |
| scale_90 | 92.3% |
| trans_30 | 92.3% |
| trans_20 | 96.2% |
| trans_10 | 96.2% |
| flip_lr | 96.2% |
| aspect_6_3 | 92.3% |
| aspect_16_9 | 92.3% |
| crop_60 | 100.0% |
| crop_70 | 100.0% |
| crop_90 | 100.0% |
| skew_10 | 92.3% |
| skew_6 | 96.2% |
| skew_4 | 92.3% |
| persp_10 | 88.5% |
| persp_6 | 100.0% |
| persp_4 | 100.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cascade |
|---|---:|
| Detector-canonical AR (TPIR @ threshold) | **22.12%** |
| Detector-canonical Rank-1 (threshold-free) | **24.04%** |

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 96% |
| rot_90 | 0.0% | 0.00 | 100% |
| flip_lr | 88.5% | 1.00 | 96% |

| Modification | cascade |
|---|---:|
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| flip_lr | 96.2% |
