# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (25 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cascade |
|---|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 96.00% |
| Clean held-out baseline - TPIR @ threshold | 92.00% |
| **Overall AR (41 mods, TPIR @ threshold)** | **79.61%** |
| Pooled AR [95% CI] | 79.61% [77.03-81.96] |
| Overall Rank-1 (41 mods, threshold-free) | 85.66% |
| Pooled Rank-1 [95% CI] | 85.66% [83.38-87.67] |
| Mean latency | 119.90 ms |
| Latency median / p95 | 118.06 / 158.83 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| brightness_p25 | 88.0% | 0.96 | 96% |
| brightness_p20 | 84.0% | 0.91 | 96% |
| brightness_p10 | 88.0% | 0.96 | 96% |
| monochrome | 92.0% | 1.00 | 100% |
| jpeg_q30 | 88.0% | 0.96 | 96% |
| jpeg_q60 | 92.0% | 1.00 | 100% |
| jpeg_q80 | 92.0% | 1.00 | 100% |
| color_8bit | 56.0% | 0.61 | 100% |
| rgb565 | 92.0% | 1.00 | 100% |
| gaussnoise_12 | 84.0% | 0.91 | 100% |
| gaussnoise_8 | 84.0% | 0.91 | 100% |
| gaussnoise_4 | 88.0% | 0.96 | 100% |
| histeq | 88.0% | 0.96 | 96% |
| autolevel | 88.0% | 0.96 | 100% |
| blur_7 | 92.0% | 1.00 | 100% |
| blur_5 | 92.0% | 1.00 | 100% |
| blur_3 | 92.0% | 1.00 | 100% |
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 100% |
| rot_45 | 24.0% | 0.26 | 100% |
| rot_25 | 64.0% | 0.70 | 100% |
| rot_10 | 84.0% | 0.91 | 100% |
| scale_50 | 88.0% | 0.96 | 100% |
| scale_70 | 88.0% | 0.96 | 100% |
| scale_90 | 88.0% | 0.96 | 100% |
| trans_30 | 92.0% | 1.00 | 100% |
| trans_20 | 92.0% | 1.00 | 100% |
| trans_10 | 84.0% | 0.91 | 100% |
| flip_lr | 88.0% | 0.96 | 100% |
| aspect_6_3 | 92.0% | 1.00 | 100% |
| aspect_16_9 | 92.0% | 1.00 | 100% |
| crop_60 | 92.0% | 1.00 | 100% |
| crop_70 | 96.0% | 1.04 | 100% |
| crop_90 | 92.0% | 1.00 | 100% |
| skew_10 | 88.0% | 0.96 | 100% |
| skew_6 | 88.0% | 0.96 | 100% |
| skew_4 | 88.0% | 0.96 | 100% |
| persp_10 | 88.0% | 0.96 | 100% |
| persp_6 | 88.0% | 0.96 | 100% |
| persp_4 | 88.0% | 0.96 | 100% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cascade |
|---|---:|
| brightness_p25 | 96.0% |
| brightness_p20 | 92.0% |
| brightness_p10 | 92.0% |
| monochrome | 100.0% |
| jpeg_q30 | 88.0% |
| jpeg_q60 | 100.0% |
| jpeg_q80 | 100.0% |
| color_8bit | 76.0% |
| rgb565 | 96.0% |
| gaussnoise_12 | 92.0% |
| gaussnoise_8 | 92.0% |
| gaussnoise_4 | 96.0% |
| histeq | 96.0% |
| autolevel | 92.0% |
| blur_7 | 96.0% |
| blur_5 | 96.0% |
| blur_3 | 96.0% |
| rot_270 | 0.0% |
| rot_180 | 4.0% |
| rot_90 | 0.0% |
| rot_45 | 28.0% |
| rot_25 | 88.0% |
| rot_10 | 88.0% |
| scale_50 | 88.0% |
| scale_70 | 92.0% |
| scale_90 | 92.0% |
| trans_30 | 96.0% |
| trans_20 | 96.0% |
| trans_10 | 92.0% |
| flip_lr | 92.0% |
| aspect_6_3 | 100.0% |
| aspect_16_9 | 100.0% |
| crop_60 | 100.0% |
| crop_70 | 100.0% |
| crop_90 | 96.0% |
| skew_10 | 96.0% |
| skew_6 | 96.0% |
| skew_4 | 96.0% |
| persp_10 | 92.0% |
| persp_6 | 92.0% |
| persp_4 | 92.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cascade |
|---|---:|
| Detector-canonical AR (TPIR @ threshold) | **22.00%** |
| Detector-canonical Rank-1 (threshold-free) | **24.00%** |

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 100% |
| flip_lr | 88.0% | 0.96 | 100% |

| Modification | cascade |
|---|---:|
| rot_270 | 0.0% |
| rot_180 | 4.0% |
| rot_90 | 0.0% |
| flip_lr | 92.0% |
