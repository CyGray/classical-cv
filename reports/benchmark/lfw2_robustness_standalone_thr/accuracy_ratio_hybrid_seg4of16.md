# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (105 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `strict`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only |
|---|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 3.81% | 92.38% |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 90.48% |
| **Overall AR (41 mods, TPIR @ threshold)** | **0.00%** | **78.21%** |
| Pooled AR [95% CI] | 0.00% [0.00-0.09] | 78.21% [76.95-79.42] |
| Overall Rank-1 (41 mods, threshold-free) | 2.11% | 82.74% |
| Pooled Rank-1 [95% CI] | 2.11% [1.72-2.59] | 82.74% [81.58-83.84] |
| Mean latency | 317.75 ms | 54.62 ms |
| Latency median / p95 | 318.66 / 419.65 ms | 52.79 / 82.32 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| brightness_p25 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| brightness_p20 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| brightness_p10 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| monochrome | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| jpeg_q30 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| jpeg_q60 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| jpeg_q80 | 0.0% | 91.4% | n/a / 1.01 | dl_stronger |
| color_8bit | 0.0% | 41.9% | n/a / 0.46 | dl_stronger |
| rgb565 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| gaussnoise_12 | 0.0% | 85.7% | n/a / 0.95 | dl_stronger |
| gaussnoise_8 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| gaussnoise_4 | 0.0% | 88.6% | n/a / 0.98 | dl_stronger |
| histeq | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| autolevel | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| blur_7 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| blur_5 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| blur_3 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_45 | 0.0% | 15.2% | n/a / 0.17 | dl_stronger |
| rot_25 | 0.0% | 61.0% | n/a / 0.67 | dl_stronger |
| rot_10 | 0.0% | 83.8% | n/a / 0.93 | dl_stronger |
| scale_50 | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| scale_70 | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| scale_90 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| trans_30 | 0.0% | 83.8% | n/a / 0.93 | dl_stronger |
| trans_20 | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| trans_10 | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| flip_lr | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| aspect_6_3 | 0.0% | 90.5% | n/a / 1.00 | dl_stronger |
| aspect_16_9 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| crop_60 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| crop_70 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| crop_90 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| skew_10 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |
| skew_6 | 0.0% | 86.7% | n/a / 0.96 | dl_stronger |
| skew_4 | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |
| persp_10 | 0.0% | 81.9% | n/a / 0.91 | dl_stronger |
| persp_6 | 0.0% | 85.7% | n/a / 0.95 | dl_stronger |
| persp_4 | 0.0% | 87.6% | n/a / 0.97 | dl_stronger |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---|---:|---:|
| brightness_p25 | 3.8% | 93.3% |
| brightness_p20 | 5.7% | 91.4% |
| brightness_p10 | 4.8% | 92.4% |
| monochrome | 3.8% | 94.3% |
| jpeg_q30 | 2.9% | 91.4% |
| jpeg_q60 | 2.9% | 93.3% |
| jpeg_q80 | 1.9% | 93.3% |
| color_8bit | 1.9% | 66.7% |
| rgb565 | 1.9% | 92.4% |
| gaussnoise_12 | 1.0% | 93.3% |
| gaussnoise_8 | 1.9% | 92.4% |
| gaussnoise_4 | 2.9% | 92.4% |
| histeq | 2.9% | 93.3% |
| autolevel | 3.8% | 91.4% |
| blur_7 | 1.0% | 93.3% |
| blur_5 | 2.9% | 93.3% |
| blur_3 | 2.9% | 92.4% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 22.9% |
| rot_25 | 0.0% | 68.6% |
| rot_10 | 2.9% | 89.5% |
| scale_50 | 0.0% | 88.6% |
| scale_70 | 0.0% | 91.4% |
| scale_90 | 1.0% | 92.4% |
| trans_30 | 0.0% | 91.4% |
| trans_20 | 1.0% | 92.4% |
| trans_10 | 1.0% | 90.5% |
| flip_lr | 1.0% | 93.3% |
| aspect_6_3 | 1.9% | 93.3% |
| aspect_16_9 | 1.9% | 92.4% |
| crop_60 | 1.0% | 95.2% |
| crop_70 | 3.8% | 94.3% |
| crop_90 | 3.8% | 94.3% |
| skew_10 | 3.8% | 92.4% |
| skew_6 | 2.9% | 93.3% |
| skew_4 | 3.8% | 92.4% |
| persp_10 | 2.9% | 89.5% |
| persp_6 | 2.9% | 92.4% |
| persp_4 | 2.9% | 91.4% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only |
|---|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **22.38%** |
| Detector-canonical Rank-1 (threshold-free) | **0.24%** | **23.33%** |

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| flip_lr | 0.0% | 89.5% | n/a / 0.99 | dl_stronger |

| Modification | cv_only | dl_only |
|---|---:|---:|
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 1.0% | 93.3% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_45, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 3 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 4305 | w/x/y/z = 0/0/3367/938
- **Recovery rate** = 78.2% [77.0-79.4] (3367/4305)
- **Both-fail ceiling** = 21.8% [20.6-23.0]
- **McNemar** (x=0 vs y=3367): p_exact = 0.0e+00, chi2_cc = 3365.0
- Clean probes (105): w/x/y/z = 0/0/95/10

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| brightness_p20 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| brightness_p10 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| monochrome | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| jpeg_q30 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| jpeg_q60 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| jpeg_q80 | 105 | 96 | 91% | 8.6% | 2.5e-29 | n/a |
| color_8bit | 105 | 44 | 42% | 58.1% | 1.1e-13 | n/a |
| rgb565 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| gaussnoise_12 | 105 | 90 | 86% | 14.3% | 1.6e-27 | n/a |
| gaussnoise_8 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| gaussnoise_4 | 105 | 93 | 89% | 11.4% | 2.0e-28 | n/a |
| histeq | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| autolevel | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| blur_7 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| blur_5 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| blur_3 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| rot_270 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 105 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 105 | 16 | 15% | 84.8% | 3.1e-05 | n/a |
| rot_25 | 105 | 64 | 61% | 39.0% | 1.1e-19 | n/a |
| rot_10 | 105 | 88 | 84% | 16.2% | 6.5e-27 | n/a |
| scale_50 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| scale_70 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| scale_90 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| trans_30 | 105 | 88 | 84% | 16.2% | 6.5e-27 | n/a |
| trans_20 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| trans_10 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| flip_lr | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| aspect_6_3 | 105 | 95 | 90% | 9.5% | 5.0e-29 | n/a |
| aspect_16_9 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| crop_60 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| crop_70 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| crop_90 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| skew_10 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
| skew_6 | 105 | 91 | 87% | 13.3% | 8.1e-28 | n/a |
| skew_4 | 105 | 94 | 90% | 10.5% | 1.0e-28 | n/a |
| persp_10 | 105 | 86 | 82% | 18.1% | 2.6e-26 | n/a |
| persp_6 | 105 | 90 | 86% | 14.3% | 1.6e-27 | n/a |
| persp_4 | 105 | 92 | 88% | 12.4% | 4.0e-28 | n/a |
