# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (26 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cascade |
|---|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 92.31% |
| Clean held-out baseline - TPIR @ threshold | 88.46% |
| **Overall AR (41 mods, TPIR @ threshold)** | **73.26%** |
| Pooled AR [95% CI] | 73.26% [70.53-75.83] |
| Overall Rank-1 (41 mods, threshold-free) | 81.61% |
| Pooled Rank-1 [95% CI] | 81.61% [79.18-83.82] |
| Mean latency | 119.97 ms |
| Latency median / p95 | 117.73 / 160.09 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| brightness_p25 | 88.5% | 1.00 | 100% |
| brightness_p20 | 88.5% | 1.00 | 100% |
| brightness_p10 | 88.5% | 1.00 | 100% |
| monochrome | 84.6% | 0.96 | 100% |
| jpeg_q30 | 84.6% | 0.96 | 100% |
| jpeg_q60 | 88.5% | 1.00 | 100% |
| jpeg_q80 | 92.3% | 1.04 | 100% |
| color_8bit | 38.5% | 0.43 | 100% |
| rgb565 | 84.6% | 0.96 | 100% |
| gaussnoise_12 | 76.9% | 0.87 | 100% |
| gaussnoise_8 | 88.5% | 1.00 | 100% |
| gaussnoise_4 | 84.6% | 0.96 | 100% |
| histeq | 84.6% | 0.96 | 96% |
| autolevel | 88.5% | 1.00 | 100% |
| blur_7 | 84.6% | 0.96 | 100% |
| blur_5 | 84.6% | 0.96 | 100% |
| blur_3 | 84.6% | 0.96 | 100% |
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 100% |
| rot_45 | 7.7% | 0.09 | 100% |
| rot_25 | 42.3% | 0.48 | 100% |
| rot_10 | 80.8% | 0.91 | 100% |
| scale_50 | 73.1% | 0.83 | 100% |
| scale_70 | 76.9% | 0.87 | 100% |
| scale_90 | 80.8% | 0.91 | 100% |
| trans_30 | 73.1% | 0.83 | 100% |
| trans_20 | 80.8% | 0.91 | 100% |
| trans_10 | 76.9% | 0.87 | 100% |
| flip_lr | 88.5% | 1.00 | 100% |
| aspect_6_3 | 88.5% | 1.00 | 100% |
| aspect_16_9 | 84.6% | 0.96 | 100% |
| crop_60 | 80.8% | 0.91 | 100% |
| crop_70 | 80.8% | 0.91 | 100% |
| crop_90 | 84.6% | 0.96 | 100% |
| skew_10 | 84.6% | 0.96 | 100% |
| skew_6 | 80.8% | 0.91 | 100% |
| skew_4 | 88.5% | 1.00 | 100% |
| persp_10 | 76.9% | 0.87 | 100% |
| persp_6 | 76.9% | 0.87 | 100% |
| persp_4 | 80.8% | 0.91 | 100% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cascade |
|---|---:|
| brightness_p25 | 92.3% |
| brightness_p20 | 92.3% |
| brightness_p10 | 92.3% |
| monochrome | 88.5% |
| jpeg_q30 | 92.3% |
| jpeg_q60 | 92.3% |
| jpeg_q80 | 92.3% |
| color_8bit | 73.1% |
| rgb565 | 92.3% |
| gaussnoise_12 | 92.3% |
| gaussnoise_8 | 92.3% |
| gaussnoise_4 | 92.3% |
| histeq | 88.5% |
| autolevel | 92.3% |
| blur_7 | 92.3% |
| blur_5 | 92.3% |
| blur_3 | 92.3% |
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| rot_45 | 19.2% |
| rot_25 | 61.5% |
| rot_10 | 92.3% |
| scale_50 | 84.6% |
| scale_70 | 88.5% |
| scale_90 | 88.5% |
| trans_30 | 88.5% |
| trans_20 | 88.5% |
| trans_10 | 88.5% |
| flip_lr | 92.3% |
| aspect_6_3 | 96.2% |
| aspect_16_9 | 92.3% |
| crop_60 | 92.3% |
| crop_70 | 92.3% |
| crop_90 | 92.3% |
| skew_10 | 92.3% |
| skew_6 | 88.5% |
| skew_4 | 92.3% |
| persp_10 | 88.5% |
| persp_6 | 92.3% |
| persp_4 | 92.3% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cascade |
|---|---:|
| Detector-canonical AR (TPIR @ threshold) | **22.12%** |
| Detector-canonical Rank-1 (threshold-free) | **23.08%** |

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| rot_270 | 0.0% | 0.00 | 100% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 100% |
| flip_lr | 88.5% | 1.00 | 100% |

| Modification | cascade |
|---|---:|
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| flip_lr | 92.3% |
