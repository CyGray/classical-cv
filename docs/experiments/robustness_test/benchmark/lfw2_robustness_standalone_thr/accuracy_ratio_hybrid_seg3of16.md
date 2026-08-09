# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (105 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `strict`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only |
|---|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 1.90% | 95.24% |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 88.57% |
| **Overall AR (41 mods, TPIR @ threshold)** | **0.00%** | **77.38%** |
| Pooled AR [95% CI] | 0.00% [0.00-0.09] | 77.38% [76.10-78.60] |
| Overall Rank-1 (41 mods, threshold-free) | 0.84% | 84.09% |
| Pooled Rank-1 [95% CI] | 0.84% [0.60-1.16] | 84.09% [82.97-85.15] |
| Mean latency | 315.88 ms | 55.03 ms |
| Latency median / p95 | 316.65 / 416.47 ms | 53.07 / 82.29 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| brightness_p25 | 0.0% | 86.7% | n/a / 0.98 | dl_stronger |
| brightness_p20 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| brightness_p10 | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |
| monochrome | 0.0% | 82.9% | n/a / 0.94 | dl_stronger |
| jpeg_q30 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| jpeg_q60 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| jpeg_q80 | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |
| color_8bit | 0.0% | 44.8% | n/a / 0.51 | dl_stronger |
| rgb565 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| gaussnoise_12 | 0.0% | 84.8% | n/a / 0.96 | dl_stronger |
| gaussnoise_8 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| gaussnoise_4 | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |
| histeq | 0.0% | 85.7% | n/a / 0.97 | dl_stronger |
| autolevel | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |
| blur_7 | 0.0% | 85.7% | n/a / 0.97 | dl_stronger |
| blur_5 | 0.0% | 89.5% | n/a / 1.01 | dl_stronger |
| blur_3 | 0.0% | 89.5% | n/a / 1.01 | dl_stronger |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_45 | 0.0% | 10.5% | n/a / 0.12 | dl_stronger |
| rot_25 | 0.0% | 64.8% | n/a / 0.73 | dl_stronger |
| rot_10 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| scale_50 | 0.0% | 75.2% | n/a / 0.85 | dl_stronger |
| scale_70 | 0.0% | 83.8% | n/a / 0.95 | dl_stronger |
| scale_90 | 0.0% | 89.5% | n/a / 1.01 | dl_stronger |
| trans_30 | 0.0% | 81.0% | n/a / 0.91 | dl_stronger |
| trans_20 | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |
| trans_10 | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |
| flip_lr | 0.0% | 90.5% | n/a / 1.02 | dl_stronger |
| aspect_6_3 | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |
| aspect_16_9 | 0.0% | 89.5% | n/a / 1.01 | dl_stronger |
| crop_60 | 0.0% | 90.5% | n/a / 1.02 | dl_stronger |
| crop_70 | 0.0% | 89.5% | n/a / 1.01 | dl_stronger |
| crop_90 | 0.0% | 90.5% | n/a / 1.02 | dl_stronger |
| skew_10 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| skew_6 | 0.0% | 87.6% | n/a / 0.99 | dl_stronger |
| skew_4 | 0.0% | 89.5% | n/a / 1.01 | dl_stronger |
| persp_10 | 0.0% | 84.8% | n/a / 0.96 | dl_stronger |
| persp_6 | 0.0% | 83.8% | n/a / 0.95 | dl_stronger |
| persp_4 | 0.0% | 88.6% | n/a / 1.00 | dl_stronger |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---|---:|---:|
| brightness_p25 | 1.0% | 96.2% |
| brightness_p20 | 1.9% | 96.2% |
| brightness_p10 | 1.9% | 96.2% |
| monochrome | 1.9% | 91.4% |
| jpeg_q30 | 1.0% | 91.4% |
| jpeg_q60 | 1.9% | 93.3% |
| jpeg_q80 | 1.0% | 93.3% |
| color_8bit | 1.0% | 71.4% |
| rgb565 | 1.9% | 95.2% |
| gaussnoise_12 | 0.0% | 93.3% |
| gaussnoise_8 | 0.0% | 94.3% |
| gaussnoise_4 | 0.0% | 94.3% |
| histeq | 1.9% | 93.3% |
| autolevel | 1.9% | 95.2% |
| blur_7 | 1.0% | 96.2% |
| blur_5 | 1.9% | 96.2% |
| blur_3 | 1.0% | 95.2% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 1.0% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 18.1% |
| rot_25 | 0.0% | 80.0% |
| rot_10 | 1.0% | 93.3% |
| scale_50 | 0.0% | 83.8% |
| scale_70 | 0.0% | 88.6% |
| scale_90 | 1.0% | 94.3% |
| trans_30 | 0.0% | 90.5% |
| trans_20 | 0.0% | 92.4% |
| trans_10 | 0.0% | 93.3% |
| flip_lr | 0.0% | 95.2% |
| aspect_6_3 | 1.0% | 95.2% |
| aspect_16_9 | 1.9% | 95.2% |
| crop_60 | 1.0% | 95.2% |
| crop_70 | 1.0% | 94.3% |
| crop_90 | 1.0% | 94.3% |
| skew_10 | 1.0% | 94.3% |
| skew_6 | 1.9% | 93.3% |
| skew_4 | 1.0% | 96.2% |
| persp_10 | 0.0% | 91.4% |
| persp_6 | 1.0% | 91.4% |
| persp_4 | 1.0% | 93.3% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only |
|---|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **22.62%** |
| Detector-canonical Rank-1 (threshold-free) | **0.00%** | **24.05%** |

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| flip_lr | 0.0% | 90.5% | n/a / 1.02 | dl_stronger |

| Modification | cv_only | dl_only |
|---|---:|---:|
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 1.0% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 0.0% | 95.2% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_45, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 3 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 4305 | w/x/y/z = 0/0/3331/974
- **Recovery rate** = 77.4% [76.1-78.6] (3331/4305)
- **Both-fail ceiling** = 22.6% [21.4-23.9]
- **McNemar** (x=0 vs y=3331): p_exact = 0.0e+00, chi2_cc = 3329.0
- Clean probes (105): w/x/y/z = 0/0/93/12

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| brightness_p20 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| brightness_p10 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| monochrome | 105 | 87 | 83% | 17.1% | 1.3e-26 | n/a |
| jpeg_q30 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| jpeg_q60 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| jpeg_q80 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| color_8bit | 105 | 47 | 45% | 55.2% | 1.4e-14 | n/a |
| rgb565 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| gaussnoise_12 | 105 | 89 | 85% | 15.2% | 3.2e-27 | n/a |
| gaussnoise_8 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| gaussnoise_4 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| histeq | 105 | 90 | 86% | 14.3% | 1.6e-27 | n/a |
| autolevel | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| blur_7 | 105 | 90 | 86% | 14.3% | 1.6e-27 | n/a |
| blur_5 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| blur_3 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| rot_270 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 105 | 11 | 10% | 89.5% | 0.00098 | n/a |
| rot_25 | 105 | 68 | 65% | 35.2% | 6.8e-21 | n/a |
| rot_10 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| scale_50 | 105 | 79 | 75% | 24.8% | 3.3e-24 | n/a |
| scale_70 | 105 | 88 | 84% | 16.2% | 6.5e-27 | n/a |
| scale_90 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| trans_30 | 105 | 85 | 81% | 19.0% | 5.2e-26 | n/a |
| trans_20 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| trans_10 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| flip_lr | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| aspect_6_3 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| aspect_16_9 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| crop_60 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| crop_70 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| crop_90 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| skew_10 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| skew_6 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| skew_4 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| persp_10 | 105 | 89 | 85% | 15.2% | 3.2e-27 | n/a |
| persp_6 | 105 | 88 | 84% | 16.2% | 6.5e-27 | n/a |
| persp_4 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
