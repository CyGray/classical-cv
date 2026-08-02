# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (26 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cascade |
|---|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 96.15% |
| Clean held-out baseline - TPIR @ threshold | 84.62% |
| **Overall AR (41 mods, TPIR @ threshold)** | **75.98%** |
| Pooled AR [95% CI] | 75.98% [73.33-78.45] |
| Overall Rank-1 (41 mods, threshold-free) | 85.46% |
| Pooled Rank-1 [95% CI] | 85.46% [83.22-87.45] |
| Mean latency | 119.96 ms |
| Latency median / p95 | 118.23 / 152.77 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| brightness_p25 | 84.6% | 1.00 | 100% |
| brightness_p20 | 84.6% | 1.00 | 100% |
| brightness_p10 | 84.6% | 1.00 | 100% |
| monochrome | 80.8% | 0.95 | 100% |
| jpeg_q30 | 80.8% | 0.95 | 100% |
| jpeg_q60 | 84.6% | 1.00 | 100% |
| jpeg_q80 | 88.5% | 1.05 | 100% |
| color_8bit | 30.8% | 0.36 | 100% |
| rgb565 | 84.6% | 1.00 | 100% |
| gaussnoise_12 | 84.6% | 1.00 | 100% |
| gaussnoise_8 | 84.6% | 1.00 | 100% |
| gaussnoise_4 | 84.6% | 1.00 | 100% |
| histeq | 84.6% | 1.00 | 100% |
| autolevel | 84.6% | 1.00 | 100% |
| blur_7 | 84.6% | 1.00 | 100% |
| blur_5 | 88.5% | 1.05 | 100% |
| blur_3 | 88.5% | 1.05 | 100% |
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 100% |
| rot_45 | 3.8% | 0.05 | 100% |
| rot_25 | 61.5% | 0.73 | 100% |
| rot_10 | 88.5% | 1.05 | 100% |
| scale_50 | 84.6% | 1.00 | 100% |
| scale_70 | 92.3% | 1.09 | 100% |
| scale_90 | 88.5% | 1.05 | 100% |
| trans_30 | 80.8% | 0.95 | 100% |
| trans_20 | 88.5% | 1.05 | 100% |
| trans_10 | 88.5% | 1.05 | 100% |
| flip_lr | 92.3% | 1.09 | 100% |
| aspect_6_3 | 88.5% | 1.05 | 100% |
| aspect_16_9 | 88.5% | 1.05 | 100% |
| crop_60 | 92.3% | 1.09 | 100% |
| crop_70 | 88.5% | 1.05 | 100% |
| crop_90 | 84.6% | 1.00 | 100% |
| skew_10 | 88.5% | 1.05 | 100% |
| skew_6 | 88.5% | 1.05 | 100% |
| skew_4 | 88.5% | 1.05 | 100% |
| persp_10 | 84.6% | 1.00 | 100% |
| persp_6 | 80.8% | 0.95 | 100% |
| persp_4 | 84.6% | 1.00 | 100% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cascade |
|---|---:|
| brightness_p25 | 96.2% |
| brightness_p20 | 96.2% |
| brightness_p10 | 96.2% |
| monochrome | 96.2% |
| jpeg_q30 | 96.2% |
| jpeg_q60 | 96.2% |
| jpeg_q80 | 96.2% |
| color_8bit | 69.2% |
| rgb565 | 96.2% |
| gaussnoise_12 | 96.2% |
| gaussnoise_8 | 96.2% |
| gaussnoise_4 | 96.2% |
| histeq | 96.2% |
| autolevel | 96.2% |
| blur_7 | 96.2% |
| blur_5 | 96.2% |
| blur_3 | 96.2% |
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| rot_45 | 11.5% |
| rot_25 | 76.9% |
| rot_10 | 96.2% |
| scale_50 | 88.5% |
| scale_70 | 92.3% |
| scale_90 | 96.2% |
| trans_30 | 96.2% |
| trans_20 | 96.2% |
| trans_10 | 96.2% |
| flip_lr | 96.2% |
| aspect_6_3 | 96.2% |
| aspect_16_9 | 96.2% |
| crop_60 | 96.2% |
| crop_70 | 96.2% |
| crop_90 | 96.2% |
| skew_10 | 96.2% |
| skew_6 | 96.2% |
| skew_4 | 96.2% |
| persp_10 | 92.3% |
| persp_6 | 92.3% |
| persp_4 | 96.2% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cascade |
|---|---:|
| Detector-canonical AR (TPIR @ threshold) | **23.08%** |
| Detector-canonical Rank-1 (threshold-free) | **24.04%** |

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 100% |
| flip_lr | 92.3% | 1.09 | 100% |

| Modification | cascade |
|---|---:|
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| flip_lr | 96.2% |
