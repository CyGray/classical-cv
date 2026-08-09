# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (26 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only |
|---|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 15.38% | 100.00% |
| Clean held-out baseline - TPIR @ threshold | 3.85% | 100.00% |
| **Overall AR (41 mods, TPIR @ threshold)** | **3.85%** | **86.96%** |
| Pooled AR [95% CI] | 3.85% [2.85-5.18] | 86.96% [84.81-88.85] |
| Overall Rank-1 (41 mods, threshold-free) | 15.01% | 89.31% |
| Pooled Rank-1 [95% CI] | 15.01% [12.99-17.28] | 89.31% [87.31-91.02] |
| Mean latency | 107.40 ms | 64.12 ms |
| Latency median / p95 | 106.60 / 143.77 ms | 63.30 / 89.18 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| brightness_p25 | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |
| brightness_p20 | 11.5% | 100.0% | 3.00 / 1.00 | dl_stronger |
| brightness_p10 | 7.7% | 100.0% | 2.00 / 1.00 | dl_stronger |
| monochrome | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |
| jpeg_q30 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| jpeg_q60 | 7.7% | 100.0% | 2.00 / 1.00 | dl_stronger |
| jpeg_q80 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| color_8bit | 0.0% | 50.0% | 0.00 / 0.50 | dl_stronger |
| rgb565 | 7.7% | 100.0% | 2.00 / 1.00 | dl_stronger |
| gaussnoise_12 | 0.0% | 92.3% | 0.00 / 0.92 | dl_stronger |
| gaussnoise_8 | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |
| gaussnoise_4 | 7.7% | 100.0% | 2.00 / 1.00 | dl_stronger |
| histeq | 0.0% | 92.3% | 0.00 / 0.92 | dl_stronger |
| autolevel | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| blur_7 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| blur_5 | 7.7% | 100.0% | 2.00 / 1.00 | dl_stronger |
| blur_3 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| rot_270 | 0.0% | 0.0% | 0.00 / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | 0.00 / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | 0.00 / 0.00 | tie |
| rot_45 | 0.0% | 11.5% | 0.00 / 0.12 | dl_stronger |
| rot_25 | 0.0% | 65.4% | 0.00 / 0.65 | dl_stronger |
| rot_10 | 3.8% | 92.3% | 1.00 / 0.92 | dl_stronger |
| scale_50 | 0.0% | 88.5% | 0.00 / 0.88 | dl_stronger |
| scale_70 | 3.8% | 92.3% | 1.00 / 0.92 | dl_stronger |
| scale_90 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| trans_30 | 3.8% | 88.5% | 1.00 / 0.88 | dl_stronger |
| trans_20 | 7.7% | 100.0% | 2.00 / 1.00 | dl_stronger |
| trans_10 | 11.5% | 100.0% | 3.00 / 1.00 | dl_stronger |
| flip_lr | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |
| aspect_6_3 | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |
| aspect_16_9 | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |
| crop_60 | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |
| crop_70 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| crop_90 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| skew_10 | 11.5% | 100.0% | 3.00 / 1.00 | dl_stronger |
| skew_6 | 11.5% | 100.0% | 3.00 / 1.00 | dl_stronger |
| skew_4 | 3.8% | 100.0% | 1.00 / 1.00 | dl_stronger |
| persp_10 | 7.7% | 96.2% | 2.00 / 0.96 | dl_stronger |
| persp_6 | 3.8% | 96.2% | 1.00 / 0.96 | dl_stronger |
| persp_4 | 7.7% | 100.0% | 2.00 / 1.00 | dl_stronger |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---|---:|---:|
| brightness_p25 | 15.4% | 100.0% |
| brightness_p20 | 19.2% | 100.0% |
| brightness_p10 | 19.2% | 100.0% |
| monochrome | 15.4% | 100.0% |
| jpeg_q30 | 23.1% | 100.0% |
| jpeg_q60 | 23.1% | 100.0% |
| jpeg_q80 | 19.2% | 100.0% |
| color_8bit | 3.8% | 84.6% |
| rgb565 | 15.4% | 100.0% |
| gaussnoise_12 | 7.7% | 100.0% |
| gaussnoise_8 | 15.4% | 100.0% |
| gaussnoise_4 | 19.2% | 100.0% |
| histeq | 15.4% | 100.0% |
| autolevel | 15.4% | 100.0% |
| blur_7 | 15.4% | 100.0% |
| blur_5 | 19.2% | 100.0% |
| blur_3 | 19.2% | 100.0% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 19.2% |
| rot_25 | 3.8% | 80.8% |
| rot_10 | 15.4% | 100.0% |
| scale_50 | 11.5% | 88.5% |
| scale_70 | 19.2% | 92.3% |
| scale_90 | 15.4% | 100.0% |
| trans_30 | 15.4% | 96.2% |
| trans_20 | 26.9% | 100.0% |
| trans_10 | 19.2% | 100.0% |
| flip_lr | 7.7% | 100.0% |
| aspect_6_3 | 15.4% | 100.0% |
| aspect_16_9 | 15.4% | 100.0% |
| crop_60 | 19.2% | 100.0% |
| crop_70 | 15.4% | 100.0% |
| crop_90 | 15.4% | 100.0% |
| skew_10 | 19.2% | 100.0% |
| skew_6 | 23.1% | 100.0% |
| skew_4 | 15.4% | 100.0% |
| persp_10 | 19.2% | 100.0% |
| persp_6 | 19.2% | 100.0% |
| persp_4 | 23.1% | 100.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only |
|---|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **25.00%** |
| Detector-canonical Rank-1 (threshold-free) | **1.92%** | **25.00%** |

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| rot_270 | 0.0% | 0.0% | 0.00 / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | 0.00 / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | 0.00 / 0.00 | tie |
| flip_lr | 0.0% | 100.0% | 0.00 / 1.00 | dl_stronger |

| Modification | cv_only | dl_only |
|---|---:|---:|
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 7.7% | 100.0% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_45, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 3 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 1066 | w/x/y/z = 41/0/886/139
- **Recovery rate** = 86.4% [84.2-88.4] (886/1025)
- **Both-fail ceiling** = 13.0% [11.1-15.2]
- **McNemar** (x=0 vs y=886): p_exact = 3.9e-267, chi2_cc = 884.0
- Clean probes (26): w/x/y/z = 1/0/25/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 26 | 26 | 100% | 0.0% | 3.0e-08 | n/a |
| brightness_p20 | 23 | 23 | 100% | 0.0% | 2.4e-07 | 1.00 |
| brightness_p10 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
| monochrome | 26 | 26 | 100% | 0.0% | 3.0e-08 | n/a |
| jpeg_q30 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| jpeg_q60 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
| jpeg_q80 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| color_8bit | 26 | 13 | 50% | 50.0% | 0.00024 | n/a |
| rgb565 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
| gaussnoise_12 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| gaussnoise_8 | 26 | 26 | 100% | 0.0% | 3.0e-08 | n/a |
| gaussnoise_4 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
| histeq | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| autolevel | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| blur_7 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| blur_5 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
| blur_3 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| rot_270 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 26 | 3 | 12% | 88.5% | 0.25 | n/a |
| rot_25 | 26 | 17 | 65% | 34.6% | 1.5e-05 | n/a |
| rot_10 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| scale_50 | 26 | 23 | 88% | 11.5% | 2.4e-07 | n/a |
| scale_70 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| scale_90 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| trans_30 | 25 | 22 | 88% | 11.5% | 4.8e-07 | 1.00 |
| trans_20 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
| trans_10 | 23 | 23 | 100% | 0.0% | 2.4e-07 | 1.00 |
| flip_lr | 26 | 26 | 100% | 0.0% | 3.0e-08 | n/a |
| aspect_6_3 | 26 | 26 | 100% | 0.0% | 3.0e-08 | n/a |
| aspect_16_9 | 26 | 26 | 100% | 0.0% | 3.0e-08 | n/a |
| crop_60 | 26 | 26 | 100% | 0.0% | 3.0e-08 | n/a |
| crop_70 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| crop_90 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| skew_10 | 23 | 23 | 100% | 0.0% | 2.4e-07 | 1.00 |
| skew_6 | 23 | 23 | 100% | 0.0% | 2.4e-07 | 1.00 |
| skew_4 | 25 | 25 | 100% | 0.0% | 6.0e-08 | 1.00 |
| persp_10 | 24 | 23 | 96% | 3.8% | 2.4e-07 | 1.00 |
| persp_6 | 25 | 24 | 96% | 3.8% | 1.2e-07 | 1.00 |
| persp_4 | 24 | 24 | 100% | 0.0% | 1.2e-07 | 1.00 |
