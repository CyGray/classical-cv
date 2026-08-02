# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (26 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only |
|---|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 3.85% | 100.00% |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 92.31% |
| **Overall AR (41 mods, TPIR @ threshold)** | **0.00%** | **81.61%** |
| Pooled AR [95% CI] | 0.00% [0.00-0.36] | 81.61% [79.18-83.82] |
| Overall Rank-1 (41 mods, threshold-free) | 2.25% | 88.93% |
| Pooled Rank-1 [95% CI] | 2.25% [1.52-3.33] | 88.93% [86.91-90.68] |
| Mean latency | 112.88 ms | 67.01 ms |
| Latency median / p95 | 111.58 / 151.36 ms | 62.06 / 110.00 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| brightness_p25 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| brightness_p20 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| brightness_p10 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| monochrome | 0.0% | 88.5% | n/a / 0.96 | dl_stronger |
| jpeg_q30 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| jpeg_q60 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| jpeg_q80 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| color_8bit | 0.0% | 46.2% | n/a / 0.50 | dl_stronger |
| rgb565 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| gaussnoise_12 | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |
| gaussnoise_8 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| gaussnoise_4 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| histeq | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |
| autolevel | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| blur_7 | 0.0% | 88.5% | n/a / 0.96 | dl_stronger |
| blur_5 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| blur_3 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_45 | 0.0% | 7.7% | n/a / 0.08 | dl_stronger |
| rot_25 | 0.0% | 61.5% | n/a / 0.67 | dl_stronger |
| rot_10 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| scale_50 | 0.0% | 84.6% | n/a / 0.92 | dl_stronger |
| scale_70 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| scale_90 | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |
| trans_30 | 0.0% | 80.8% | n/a / 0.88 | dl_stronger |
| trans_20 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| trans_10 | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |
| flip_lr | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |
| aspect_6_3 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| aspect_16_9 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| crop_60 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| crop_70 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| crop_90 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| skew_10 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| skew_6 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| skew_4 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| persp_10 | 0.0% | 92.3% | n/a / 1.00 | dl_stronger |
| persp_6 | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |
| persp_4 | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---|---:|---:|
| brightness_p25 | 3.8% | 100.0% |
| brightness_p20 | 3.8% | 100.0% |
| brightness_p10 | 3.8% | 96.2% |
| monochrome | 3.8% | 100.0% |
| jpeg_q30 | 0.0% | 96.2% |
| jpeg_q60 | 3.8% | 96.2% |
| jpeg_q80 | 3.8% | 100.0% |
| color_8bit | 0.0% | 84.6% |
| rgb565 | 0.0% | 100.0% |
| gaussnoise_12 | 0.0% | 100.0% |
| gaussnoise_8 | 0.0% | 100.0% |
| gaussnoise_4 | 3.8% | 100.0% |
| histeq | 3.8% | 100.0% |
| autolevel | 3.8% | 100.0% |
| blur_7 | 3.8% | 100.0% |
| blur_5 | 3.8% | 100.0% |
| blur_3 | 3.8% | 100.0% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 23.1% |
| rot_25 | 0.0% | 80.8% |
| rot_10 | 3.8% | 100.0% |
| scale_50 | 0.0% | 88.5% |
| scale_70 | 0.0% | 96.2% |
| scale_90 | 0.0% | 100.0% |
| trans_30 | 0.0% | 96.2% |
| trans_20 | 0.0% | 92.3% |
| trans_10 | 0.0% | 100.0% |
| flip_lr | 0.0% | 100.0% |
| aspect_6_3 | 3.8% | 100.0% |
| aspect_16_9 | 3.8% | 100.0% |
| crop_60 | 3.8% | 100.0% |
| crop_70 | 3.8% | 100.0% |
| crop_90 | 3.8% | 100.0% |
| skew_10 | 3.8% | 100.0% |
| skew_6 | 3.8% | 100.0% |
| skew_4 | 3.8% | 100.0% |
| persp_10 | 3.8% | 96.2% |
| persp_6 | 3.8% | 100.0% |
| persp_4 | 3.8% | 100.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only |
|---|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **24.04%** |
| Detector-canonical Rank-1 (threshold-free) | **0.00%** | **25.00%** |

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| flip_lr | 0.0% | 96.2% | n/a / 1.04 | dl_stronger |

| Modification | cv_only | dl_only |
|---|---:|---:|
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 0.0% | 100.0% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_45, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 3 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 1066 | w/x/y/z = 0/0/870/196
- **Recovery rate** = 81.6% [79.2-83.8] (870/1066)
- **Both-fail ceiling** = 18.4% [16.2-20.8]
- **McNemar** (x=0 vs y=870): p_exact = 2.5e-262, chi2_cc = 868.0
- Clean probes (26): w/x/y/z = 0/0/24/2

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| brightness_p20 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| brightness_p10 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| monochrome | 26 | 23 | 88% | 11.5% | 2.4e-07 | n/a |
| jpeg_q30 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| jpeg_q60 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| jpeg_q80 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| color_8bit | 26 | 12 | 46% | 53.8% | 0.00049 | n/a |
| rgb565 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| gaussnoise_12 | 26 | 25 | 96% | 3.8% | 6.0e-08 | n/a |
| gaussnoise_8 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| gaussnoise_4 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| histeq | 26 | 25 | 96% | 3.8% | 6.0e-08 | n/a |
| autolevel | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| blur_7 | 26 | 23 | 88% | 11.5% | 2.4e-07 | n/a |
| blur_5 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| blur_3 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| rot_270 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 26 | 2 | 8% | 92.3% | 0.5 | n/a |
| rot_25 | 26 | 16 | 62% | 38.5% | 3.1e-05 | n/a |
| rot_10 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| scale_50 | 26 | 22 | 85% | 15.4% | 4.8e-07 | n/a |
| scale_70 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| scale_90 | 26 | 25 | 96% | 3.8% | 6.0e-08 | n/a |
| trans_30 | 26 | 21 | 81% | 19.2% | 9.5e-07 | n/a |
| trans_20 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| trans_10 | 26 | 25 | 96% | 3.8% | 6.0e-08 | n/a |
| flip_lr | 26 | 25 | 96% | 3.8% | 6.0e-08 | n/a |
| aspect_6_3 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| aspect_16_9 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| crop_60 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| crop_70 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| crop_90 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| skew_10 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| skew_6 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| skew_4 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| persp_10 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| persp_6 | 26 | 25 | 96% | 3.8% | 6.0e-08 | n/a |
| persp_4 | 26 | 25 | 96% | 3.8% | 6.0e-08 | n/a |
