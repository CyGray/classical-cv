# Transform Sensitivity - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `transform_sensitivity` (same-image path - enrollment and probing share the same seeded image; see docs/audits/STATE-08-01.md. This is NOT recognition accuracy.)

Originals: `..\data\lsdb\split\test` (56 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `strict`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 100.00% | 100.00% | 100.00% |
| Clean held-out baseline - TPIR @ threshold | 62.50% | 100.00% | 100.00% |
| **Overall AR (41 mods, TPIR @ threshold)** | **30.79%** | **87.24%** | **87.24%** |
| Pooled AR [95% CI] | 30.79% [28.94-32.71] | 87.24% [85.81-88.54] | 87.24% [85.81-88.54] |
| Overall Rank-1 (41 mods, threshold-free) | 70.38% | 88.20% | 88.20% |
| Pooled Rank-1 [95% CI] | 70.38% [68.48-72.22] | 88.20% [86.81-89.45] | 88.20% [86.81-89.45] |
| Mean latency | 4.49 ms | 12.71 ms | 11.10 ms |
| Latency median / p95 | 4.70 / 6.22 ms | 13.51 / 17.05 ms | 13.25 / 16.47 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | cascade | retention | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_p25 | 60.7% | 100.0% | 100.0% | 0.97 / 1.00 / 1.00 | dl_stronger | 50% |
| brightness_p20 | 62.5% | 100.0% | 100.0% | 1.00 / 1.00 / 1.00 | dl_stronger | 43% |
| brightness_p10 | 60.7% | 100.0% | 100.0% | 0.97 / 1.00 / 1.00 | dl_stronger | 41% |
| monochrome | 62.5% | 100.0% | 100.0% | 1.00 / 1.00 / 1.00 | dl_stronger | 46% |
| jpeg_q30 | 28.6% | 100.0% | 100.0% | 0.46 / 1.00 / 1.00 | dl_stronger | 88% |
| jpeg_q60 | 48.2% | 100.0% | 100.0% | 0.77 / 1.00 / 1.00 | dl_stronger | 64% |
| jpeg_q80 | 55.4% | 100.0% | 100.0% | 0.89 / 1.00 / 1.00 | dl_stronger | 54% |
| color_8bit | 62.5% | 100.0% | 100.0% | 1.00 / 1.00 / 1.00 | dl_stronger | 46% |
| rgb565 | 62.5% | 100.0% | 100.0% | 1.00 / 1.00 / 1.00 | dl_stronger | 46% |
| gaussnoise_12 | 0.0% | 75.0% | 75.0% | 0.00 / 0.75 / 0.75 | dl_stronger | 80% |
| gaussnoise_8 | 14.3% | 98.2% | 98.2% | 0.23 / 0.98 / 0.98 | dl_stronger | 98% |
| gaussnoise_4 | 50.0% | 100.0% | 100.0% | 0.80 / 1.00 / 1.00 | dl_stronger | 62% |
| histeq | 53.6% | 100.0% | 100.0% | 0.86 / 1.00 / 1.00 | dl_stronger | 89% |
| autolevel | 60.7% | 100.0% | 100.0% | 0.97 / 1.00 / 1.00 | dl_stronger | 62% |
| blur_7 | 8.9% | 100.0% | 100.0% | 0.14 / 1.00 / 1.00 | dl_stronger | 100% |
| blur_5 | 42.9% | 100.0% | 100.0% | 0.69 / 1.00 / 1.00 | dl_stronger | 100% |
| blur_3 | 55.4% | 100.0% | 100.0% | 0.89 / 1.00 / 1.00 | dl_stronger | 100% |
| rot_270 | 0.0% | 0.0% | 0.0% | 0.00 / 0.00 / 0.00 | tie | 0% |
| rot_180 | 0.0% | 0.0% | 0.0% | 0.00 / 0.00 / 0.00 | tie | 36% |
| rot_90 | 0.0% | 0.0% | 0.0% | 0.00 / 0.00 / 0.00 | tie | 0% |
| rot_45 | 0.0% | 0.0% | 0.0% | 0.00 / 0.00 / 0.00 | tie | 34% |
| rot_25 | 0.0% | 83.9% | 83.9% | 0.00 / 0.84 / 0.84 | dl_stronger | 100% |
| rot_10 | 1.8% | 100.0% | 100.0% | 0.03 / 1.00 / 1.00 | dl_stronger | 100% |
| scale_50 | 0.0% | 41.1% | 41.1% | 0.00 / 0.41 / 0.41 | dl_stronger | 41% |
| scale_70 | 0.0% | 100.0% | 100.0% | 0.00 / 1.00 / 1.00 | dl_stronger | 100% |
| scale_90 | 57.1% | 100.0% | 100.0% | 0.91 / 1.00 / 1.00 | dl_stronger | 75% |
| trans_30 | 0.0% | 78.6% | 78.6% | 0.00 / 0.79 / 0.79 | dl_stronger | 89% |
| trans_20 | 0.0% | 100.0% | 100.0% | 0.00 / 1.00 / 1.00 | dl_stronger | 100% |
| trans_10 | 0.0% | 100.0% | 100.0% | 0.00 / 1.00 / 1.00 | dl_stronger | 100% |
| flip_lr | 10.7% | 100.0% | 100.0% | 0.17 / 1.00 / 1.00 | dl_stronger | 91% |
| aspect_6_3 | 44.6% | 100.0% | 100.0% | 0.71 / 1.00 / 1.00 | dl_stronger | 91% |
| aspect_16_9 | 51.8% | 100.0% | 100.0% | 0.83 / 1.00 / 1.00 | dl_stronger | 88% |
| crop_60 | 0.0% | 100.0% | 100.0% | 0.00 / 1.00 / 1.00 | dl_stronger | 100% |
| crop_70 | 3.6% | 100.0% | 100.0% | 0.06 / 1.00 / 1.00 | dl_stronger | 100% |
| crop_90 | 39.3% | 100.0% | 100.0% | 0.63 / 1.00 / 1.00 | dl_stronger | 86% |
| skew_10 | 37.5% | 100.0% | 100.0% | 0.60 / 1.00 / 1.00 | dl_stronger | 73% |
| skew_6 | 50.0% | 100.0% | 100.0% | 0.80 / 1.00 / 1.00 | dl_stronger | 64% |
| skew_4 | 55.4% | 100.0% | 100.0% | 0.89 / 1.00 / 1.00 | dl_stronger | 59% |
| persp_10 | 8.9% | 100.0% | 100.0% | 0.14 / 1.00 / 1.00 | dl_stronger | 96% |
| persp_6 | 48.2% | 100.0% | 100.0% | 0.77 / 1.00 / 1.00 | dl_stronger | 75% |
| persp_4 | 64.3% | 100.0% | 100.0% | 1.03 / 1.00 / 1.00 | dl_stronger | 62% |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| brightness_p25 | 98.2% | 100.0% | 100.0% |
| brightness_p20 | 100.0% | 100.0% | 100.0% |
| brightness_p10 | 98.2% | 100.0% | 100.0% |
| monochrome | 100.0% | 100.0% | 100.0% |
| jpeg_q30 | 98.2% | 100.0% | 100.0% |
| jpeg_q60 | 96.4% | 100.0% | 100.0% |
| jpeg_q80 | 100.0% | 100.0% | 100.0% |
| color_8bit | 100.0% | 100.0% | 100.0% |
| rgb565 | 100.0% | 100.0% | 100.0% |
| gaussnoise_12 | 37.5% | 80.4% | 80.4% |
| gaussnoise_8 | 71.4% | 98.2% | 98.2% |
| gaussnoise_4 | 94.6% | 100.0% | 100.0% |
| histeq | 96.4% | 100.0% | 100.0% |
| autolevel | 98.2% | 100.0% | 100.0% |
| blur_7 | 98.2% | 100.0% | 100.0% |
| blur_5 | 98.2% | 100.0% | 100.0% |
| blur_3 | 98.2% | 100.0% | 100.0% |
| rot_270 | 0.0% | 0.0% | 0.0% |
| rot_180 | 3.6% | 1.8% | 1.8% |
| rot_90 | 0.0% | 0.0% | 0.0% |
| rot_45 | 0.0% | 10.7% | 10.7% |
| rot_25 | 16.1% | 96.4% | 96.4% |
| rot_10 | 80.4% | 100.0% | 100.0% |
| scale_50 | 0.0% | 41.1% | 41.1% |
| scale_70 | 57.1% | 100.0% | 100.0% |
| scale_90 | 100.0% | 100.0% | 100.0% |
| trans_30 | 5.4% | 87.5% | 87.5% |
| trans_20 | 0.0% | 100.0% | 100.0% |
| trans_10 | 7.1% | 100.0% | 100.0% |
| flip_lr | 57.1% | 100.0% | 100.0% |
| aspect_6_3 | 98.2% | 100.0% | 100.0% |
| aspect_16_9 | 100.0% | 100.0% | 100.0% |
| crop_60 | 35.7% | 100.0% | 100.0% |
| crop_70 | 57.1% | 100.0% | 100.0% |
| crop_90 | 89.3% | 100.0% | 100.0% |
| skew_10 | 98.2% | 100.0% | 100.0% |
| skew_6 | 100.0% | 100.0% | 100.0% |
| skew_4 | 100.0% | 100.0% | 100.0% |
| persp_10 | 96.4% | 100.0% | 100.0% |
| persp_6 | 100.0% | 100.0% | 100.0% |
| persp_4 | 100.0% | 100.0% | 100.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **2.68%** | **25.00%** | **25.00%** |
| Detector-canonical Rank-1 (threshold-free) | **15.18%** | **25.45%** | **25.45%** |

| Modification | cv_only | dl_only | cascade | retention | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| rot_270 | 0.0% | 0.0% | 0.0% | 0.00 / 0.00 / 0.00 | tie | 0% |
| rot_180 | 0.0% | 0.0% | 0.0% | 0.00 / 0.00 / 0.00 | tie | 36% |
| rot_90 | 0.0% | 0.0% | 0.0% | 0.00 / 0.00 / 0.00 | tie | 0% |
| flip_lr | 10.7% | 100.0% | 100.0% | 0.17 / 1.00 / 1.00 | dl_stronger | 91% |

| Modification | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| rot_270 | 0.0% | 0.0% | 0.0% |
| rot_180 | 3.6% | 1.8% | 1.8% |
| rot_90 | 0.0% | 0.0% | 0.0% |
| flip_lr | 57.1% | 100.0% | 100.0% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 4 modifications
- Cascade within 2 pts of the better engine on 41 / 41 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 2296 | w/x/y/z = 707/0/1296/293
- **Recovery rate** = 81.6% [79.6-83.4] (1296/1589)
- **Both-fail ceiling** = 12.8% [11.5-14.2]
- **McNemar** (x=0 vs y=1296): p_exact = 0.0e+00, chi2_cc = 1294.0
- Clean probes (56): w/x/y/z = 35/0/21/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 22 | 22 | 100% | 0.0% | 4.8e-07 | 1.00 |
| brightness_p20 | 21 | 21 | 100% | 0.0% | 9.5e-07 | 1.00 |
| brightness_p10 | 22 | 22 | 100% | 0.0% | 4.8e-07 | 1.00 |
| monochrome | 21 | 21 | 100% | 0.0% | 9.5e-07 | 1.00 |
| jpeg_q30 | 40 | 40 | 100% | 0.0% | 1.8e-12 | 1.00 |
| jpeg_q60 | 29 | 29 | 100% | 0.0% | 3.7e-09 | 1.00 |
| jpeg_q80 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| color_8bit | 21 | 21 | 100% | 0.0% | 9.5e-07 | 1.00 |
| rgb565 | 21 | 21 | 100% | 0.0% | 9.5e-07 | 1.00 |
| gaussnoise_12 | 56 | 42 | 75% | 25.0% | 4.5e-13 | n/a |
| gaussnoise_8 | 48 | 47 | 98% | 1.8% | 1.4e-14 | 1.00 |
| gaussnoise_4 | 28 | 28 | 100% | 0.0% | 7.5e-09 | 1.00 |
| histeq | 26 | 26 | 100% | 0.0% | 3.0e-08 | 1.00 |
| autolevel | 22 | 22 | 100% | 0.0% | 4.8e-07 | 1.00 |
| blur_7 | 51 | 51 | 100% | 0.0% | 8.9e-16 | 1.00 |
| blur_5 | 32 | 32 | 100% | 0.0% | 4.7e-10 | 1.00 |
| blur_3 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| rot_270 | 56 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 56 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 56 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 56 | 0 | 0% | 100.0% | n/a | n/a |
| rot_25 | 56 | 47 | 84% | 16.1% | 1.4e-14 | n/a |
| rot_10 | 55 | 55 | 100% | 0.0% | 5.6e-17 | 1.00 |
| scale_50 | 56 | 23 | 41% | 58.9% | 2.4e-07 | n/a |
| scale_70 | 56 | 56 | 100% | 0.0% | 2.8e-17 | n/a |
| scale_90 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
| trans_30 | 56 | 44 | 79% | 21.4% | 1.1e-13 | n/a |
| trans_20 | 56 | 56 | 100% | 0.0% | 2.8e-17 | n/a |
| trans_10 | 56 | 56 | 100% | 0.0% | 2.8e-17 | n/a |
| flip_lr | 50 | 50 | 100% | 0.0% | 1.8e-15 | 1.00 |
| aspect_6_3 | 31 | 31 | 100% | 0.0% | 9.3e-10 | 1.00 |
| aspect_16_9 | 27 | 27 | 100% | 0.0% | 1.5e-08 | 1.00 |
| crop_60 | 56 | 56 | 100% | 0.0% | 2.8e-17 | n/a |
| crop_70 | 54 | 54 | 100% | 0.0% | 1.1e-16 | 1.00 |
| crop_90 | 34 | 34 | 100% | 0.0% | 1.2e-10 | 1.00 |
| skew_10 | 35 | 35 | 100% | 0.0% | 5.8e-11 | 1.00 |
| skew_6 | 28 | 28 | 100% | 0.0% | 7.5e-09 | 1.00 |
| skew_4 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| persp_10 | 51 | 51 | 100% | 0.0% | 8.9e-16 | 1.00 |
| persp_6 | 29 | 29 | 100% | 0.0% | 3.7e-09 | 1.00 |
| persp_4 | 20 | 20 | 100% | 0.0% | 1.9e-06 | 1.00 |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **1.000**; margin signal: 0.946
- Deployed gate vs 'LBPH wrong': escalates 1642 probes; TPR (wrong probes escalated) = 1.000, FPR (right probes escalated) = 0.409, precision = 0.824
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=688, ambiguous_band=664, low_margin=1
- Including clean probes: AUC(d1) = 1.000, gate TPR = 1.000, FPR = 0.396
- Probes excluded (no gate signal, strict no-face): 236
