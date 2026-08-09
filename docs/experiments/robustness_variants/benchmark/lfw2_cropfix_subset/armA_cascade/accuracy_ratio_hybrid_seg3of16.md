# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (26 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cascade |
|---|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 100.00% |
| Clean held-out baseline - TPIR @ threshold | 100.00% |
| **Overall AR (41 mods, TPIR @ threshold)** | **86.30%** |
| Pooled AR [95% CI] | 86.30% [84.11-88.24] |
| Overall Rank-1 (41 mods, threshold-free) | 88.56% |
| Pooled Rank-1 [95% CI] | 88.56% [86.50-90.33] |
| Mean latency | 175.33 ms |
| Latency median / p95 | 174.73 / 220.44 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| brightness_p25 | 100.0% | 1.00 | 92% |
| brightness_p20 | 100.0% | 1.00 | 92% |
| brightness_p10 | 100.0% | 1.00 | 96% |
| monochrome | 100.0% | 1.00 | 100% |
| jpeg_q30 | 96.2% | 0.96 | 96% |
| jpeg_q60 | 100.0% | 1.00 | 100% |
| jpeg_q80 | 96.2% | 0.96 | 96% |
| color_8bit | 46.2% | 0.46 | 92% |
| rgb565 | 100.0% | 1.00 | 100% |
| gaussnoise_12 | 92.3% | 0.92 | 100% |
| gaussnoise_8 | 100.0% | 1.00 | 100% |
| gaussnoise_4 | 100.0% | 1.00 | 100% |
| histeq | 92.3% | 0.92 | 92% |
| autolevel | 100.0% | 1.00 | 92% |
| blur_7 | 100.0% | 1.00 | 100% |
| blur_5 | 100.0% | 1.00 | 100% |
| blur_3 | 96.2% | 0.96 | 96% |
| rot_270 | 0.0% | 0.00 | 96% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 92% |
| rot_45 | 11.5% | 0.12 | 100% |
| rot_25 | 61.5% | 0.62 | 96% |
| rot_10 | 92.3% | 0.92 | 100% |
| scale_50 | 88.5% | 0.88 | 100% |
| scale_70 | 92.3% | 0.92 | 100% |
| scale_90 | 100.0% | 1.00 | 100% |
| trans_30 | 88.5% | 0.88 | 100% |
| trans_20 | 100.0% | 1.00 | 100% |
| trans_10 | 100.0% | 1.00 | 100% |
| flip_lr | 100.0% | 1.00 | 100% |
| aspect_6_3 | 100.0% | 1.00 | 100% |
| aspect_16_9 | 100.0% | 1.00 | 100% |
| crop_60 | 100.0% | 1.00 | 96% |
| crop_70 | 100.0% | 1.00 | 96% |
| crop_90 | 100.0% | 1.00 | 96% |
| skew_10 | 96.2% | 0.96 | 96% |
| skew_6 | 96.2% | 0.96 | 96% |
| skew_4 | 100.0% | 1.00 | 100% |
| persp_10 | 96.2% | 0.96 | 100% |
| persp_6 | 96.2% | 0.96 | 100% |
| persp_4 | 100.0% | 1.00 | 100% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cascade |
|---|---:|
| brightness_p25 | 100.0% |
| brightness_p20 | 100.0% |
| brightness_p10 | 100.0% |
| monochrome | 100.0% |
| jpeg_q30 | 96.2% |
| jpeg_q60 | 100.0% |
| jpeg_q80 | 96.2% |
| color_8bit | 76.9% |
| rgb565 | 100.0% |
| gaussnoise_12 | 100.0% |
| gaussnoise_8 | 100.0% |
| gaussnoise_4 | 100.0% |
| histeq | 100.0% |
| autolevel | 100.0% |
| blur_7 | 100.0% |
| blur_5 | 100.0% |
| blur_3 | 96.2% |
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| rot_45 | 19.2% |
| rot_25 | 76.9% |
| rot_10 | 100.0% |
| scale_50 | 88.5% |
| scale_70 | 92.3% |
| scale_90 | 100.0% |
| trans_30 | 96.2% |
| trans_20 | 100.0% |
| trans_10 | 100.0% |
| flip_lr | 100.0% |
| aspect_6_3 | 100.0% |
| aspect_16_9 | 100.0% |
| crop_60 | 100.0% |
| crop_70 | 100.0% |
| crop_90 | 100.0% |
| skew_10 | 96.2% |
| skew_6 | 96.2% |
| skew_4 | 100.0% |
| persp_10 | 100.0% |
| persp_6 | 100.0% |
| persp_4 | 100.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cascade |
|---|---:|
| Detector-canonical AR (TPIR @ threshold) | **25.00%** |
| Detector-canonical Rank-1 (threshold-free) | **25.00%** |

| Modification | cascade | retention | escalation |
|---|---:|---:|---:|
| rot_270 | 0.0% | 0.00 | 96% |
| rot_180 | 0.0% | 0.00 | 100% |
| rot_90 | 0.0% | 0.00 | 92% |
| flip_lr | 100.0% | 1.00 | 100% |

| Modification | cascade |
|---|---:|
| rot_270 | 0.0% |
| rot_180 | 0.0% |
| rot_90 | 0.0% |
| flip_lr | 100.0% |
