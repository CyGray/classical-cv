# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (105 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `strict`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only |
|---|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 2.86% | 94.29% |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 90.48% |
| **Overall AR (41 mods, TPIR @ threshold)** | **0.00%** | **79.37%** |
| Pooled AR [95% CI] | 0.00% [0.00-0.09] | 79.37% [78.14-80.56] |
| Overall Rank-1 (41 mods, threshold-free) | 2.14% | 84.44% |
| Pooled Rank-1 [95% CI] | 2.14% [1.75-2.61] | 84.44% [83.32-85.49] |
| Mean latency | 297.68 ms | 28.93 ms |
| Latency median / p95 | 300.60 / 395.36 ms | 28.30 / 38.93 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| brightness_p25 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| brightness_p20 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| brightness_p10 | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| monochrome | 0.0% | 84.8% | n/a / 0.94 | dl_stronger |
| jpeg_q30 | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| jpeg_q60 | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| jpeg_q80 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| color_8bit | 0.0% | 41.9% | n/a / 0.46 | dl_stronger |
| rgb565 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| gaussnoise_12 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| gaussnoise_8 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| gaussnoise_4 | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| histeq | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| autolevel | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| blur_7 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| blur_5 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| blur_3 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_45 | 0.0% | 9.5% | n/a / 0.11 | dl_stronger |
| rot_25 | 0.0% | 59.0% | n/a / 0.65 | dl_stronger |
| rot_10 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| scale_50 | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| scale_70 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| scale_90 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| trans_30 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| trans_20 | 0.0% | 92.4% | n/a / 1.02 | dl_stronger |
| trans_10 | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| flip_lr | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| aspect_6_3 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| aspect_16_9 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| crop_60 | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| crop_70 | 0.0% | 94.3% | n/a / 1.04 | dl_stronger |
| crop_90 | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| skew_10 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| skew_6 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| skew_4 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| persp_10 | 0.0% | 88.6% | n/a / 0.98 | dl_stronger |
| persp_6 | 0.0% | 92.4% | n/a / 1.02 | dl_stronger |
| persp_4 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---|---:|---:|
| brightness_p25 | 3.8% | 94.3% |
| brightness_p20 | 4.8% | 94.3% |
| brightness_p10 | 2.9% | 95.2% |
| monochrome | 2.9% | 92.4% |
| jpeg_q30 | 2.9% | 93.3% |
| jpeg_q60 | 2.9% | 96.2% |
| jpeg_q80 | 2.9% | 95.2% |
| color_8bit | 1.9% | 69.5% |
| rgb565 | 2.9% | 95.2% |
| gaussnoise_12 | 0.0% | 94.3% |
| gaussnoise_8 | 1.0% | 94.3% |
| gaussnoise_4 | 1.0% | 95.2% |
| histeq | 2.9% | 93.3% |
| autolevel | 3.8% | 93.3% |
| blur_7 | 1.9% | 93.3% |
| blur_5 | 2.9% | 94.3% |
| blur_3 | 2.9% | 94.3% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 1.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 14.3% |
| rot_25 | 0.0% | 70.5% |
| rot_10 | 2.9% | 96.2% |
| scale_50 | 0.0% | 88.6% |
| scale_70 | 1.9% | 93.3% |
| scale_90 | 2.9% | 94.3% |
| trans_30 | 0.0% | 95.2% |
| trans_20 | 0.0% | 95.2% |
| trans_10 | 1.0% | 95.2% |
| flip_lr | 1.0% | 95.2% |
| aspect_6_3 | 2.9% | 94.3% |
| aspect_16_9 | 2.9% | 94.3% |
| crop_60 | 1.9% | 96.2% |
| crop_70 | 1.0% | 96.2% |
| crop_90 | 2.9% | 95.2% |
| skew_10 | 2.9% | 94.3% |
| skew_6 | 3.8% | 95.2% |
| skew_4 | 2.9% | 94.3% |
| persp_10 | 3.8% | 94.3% |
| persp_6 | 3.8% | 96.2% |
| persp_4 | 4.8% | 95.2% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only |
|---|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **22.86%** |
| Detector-canonical Rank-1 (threshold-free) | **0.48%** | **23.81%** |

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| flip_lr | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |

| Modification | cv_only | dl_only |
|---|---:|---:|
| rot_270 | 0.0% | 0.0% |
| rot_180 | 1.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 1.0% | 95.2% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_45, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 3 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 4305 | w/x/y/z = 0/0/3417/888
- **Recovery rate** = 79.4% [78.1-80.6] (3417/4305)
- **Both-fail ceiling** = 20.6% [19.4-21.9]
- **McNemar** (x=0 vs y=3417): p_exact = 0.0e+00, chi2_cc = 3415.0
- Clean probes (105): w/x/y/z = 0/0/95/10

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| brightness_p20 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| brightness_p10 | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| monochrome | 105 | 89 | 85% | 15.2% | 3.2e-27 | n/a |
| jpeg_q30 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| jpeg_q60 | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| jpeg_q80 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| color_8bit | 105 | 44 | 42% | 58.1% | 1.1e-13 | n/a |
| rgb565 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| gaussnoise_12 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| gaussnoise_8 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| gaussnoise_4 | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| histeq | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| autolevel | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| blur_7 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| blur_5 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| blur_3 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| rot_270 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 105 | 10 | 10% | 90.5% | 0.002 | n/a |
| rot_25 | 105 | 62 | 59% | 41.0% | 4.3e-19 | n/a |
| rot_10 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| scale_50 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| scale_70 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| scale_90 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| trans_30 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| trans_20 | 105 | 97 | 92% | 7.6% | 1.3e-29 | n/a |
| trans_10 | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| flip_lr | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| aspect_6_3 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| aspect_16_9 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| crop_60 | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| crop_70 | 105 | 99 | 94% | 5.7% | 3.2e-30 | n/a |
| crop_90 | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| skew_10 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| skew_6 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| skew_4 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| persp_10 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| persp_6 | 105 | 97 | 92% | 7.6% | 1.3e-29 | n/a |
| persp_4 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
