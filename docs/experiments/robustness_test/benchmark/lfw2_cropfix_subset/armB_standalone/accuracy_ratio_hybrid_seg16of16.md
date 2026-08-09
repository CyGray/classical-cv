# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (25 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only |
|---|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 12.00% | 96.00% |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 92.00% |
| **Overall AR (41 mods, TPIR @ threshold)** | **0.10%** | **80.00%** |
| Pooled AR [95% CI] | 0.10% [0.02-0.55] | 80.00% [77.44-82.33] |
| Overall Rank-1 (41 mods, threshold-free) | 5.46% | 86.15% |
| Pooled Rank-1 [95% CI] | 5.46% [4.23-7.03] | 86.15% [83.90-88.13] |
| Mean latency | 90.23 ms | 32.69 ms |
| Latency median / p95 | 88.04 / 122.52 ms | 32.12 / 41.24 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| brightness_p25 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| brightness_p20 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| brightness_p10 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| monochrome | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| jpeg_q30 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| jpeg_q60 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| jpeg_q80 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| color_8bit | 0.0% | 56.0% | n/a / 0.61 | dl_stronger |
| rgb565 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| gaussnoise_12 | 0.0% | 84.0% | n/a / 0.91 | dl_stronger |
| gaussnoise_8 | 0.0% | 84.0% | n/a / 0.91 | dl_stronger |
| gaussnoise_4 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| histeq | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| autolevel | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| blur_7 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| blur_5 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| blur_3 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_45 | 0.0% | 24.0% | n/a / 0.26 | dl_stronger |
| rot_25 | 0.0% | 64.0% | n/a / 0.70 | dl_stronger |
| rot_10 | 0.0% | 84.0% | n/a / 0.91 | dl_stronger |
| scale_50 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| scale_70 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| scale_90 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| trans_30 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| trans_20 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| trans_10 | 0.0% | 84.0% | n/a / 0.91 | dl_stronger |
| flip_lr | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| aspect_6_3 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| aspect_16_9 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| crop_60 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| crop_70 | 0.0% | 96.0% | n/a / 1.04 | dl_stronger |
| crop_90 | 0.0% | 92.0% | n/a / 1.00 | dl_stronger |
| skew_10 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| skew_6 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| skew_4 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| persp_10 | 4.0% | 88.0% | n/a / 0.96 | dl_stronger |
| persp_6 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |
| persp_4 | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---|---:|---:|
| brightness_p25 | 12.0% | 100.0% |
| brightness_p20 | 4.0% | 96.0% |
| brightness_p10 | 8.0% | 96.0% |
| monochrome | 12.0% | 100.0% |
| jpeg_q30 | 8.0% | 92.0% |
| jpeg_q60 | 8.0% | 100.0% |
| jpeg_q80 | 8.0% | 100.0% |
| color_8bit | 4.0% | 76.0% |
| rgb565 | 8.0% | 96.0% |
| gaussnoise_12 | 0.0% | 92.0% |
| gaussnoise_8 | 0.0% | 92.0% |
| gaussnoise_4 | 8.0% | 96.0% |
| histeq | 4.0% | 100.0% |
| autolevel | 12.0% | 92.0% |
| blur_7 | 8.0% | 96.0% |
| blur_5 | 8.0% | 96.0% |
| blur_3 | 8.0% | 96.0% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 4.0% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 28.0% |
| rot_25 | 0.0% | 88.0% |
| rot_10 | 0.0% | 88.0% |
| scale_50 | 0.0% | 88.0% |
| scale_70 | 0.0% | 92.0% |
| scale_90 | 8.0% | 92.0% |
| trans_30 | 0.0% | 96.0% |
| trans_20 | 8.0% | 96.0% |
| trans_10 | 4.0% | 92.0% |
| flip_lr | 0.0% | 92.0% |
| aspect_6_3 | 16.0% | 100.0% |
| aspect_16_9 | 12.0% | 100.0% |
| crop_60 | 4.0% | 100.0% |
| crop_70 | 4.0% | 100.0% |
| crop_90 | 8.0% | 96.0% |
| skew_10 | 4.0% | 96.0% |
| skew_6 | 4.0% | 96.0% |
| skew_4 | 4.0% | 96.0% |
| persp_10 | 8.0% | 92.0% |
| persp_6 | 8.0% | 92.0% |
| persp_4 | 12.0% | 92.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only |
|---|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **22.00%** |
| Detector-canonical Rank-1 (threshold-free) | **0.00%** | **24.00%** |

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| flip_lr | 0.0% | 88.0% | n/a / 0.96 | dl_stronger |

| Modification | cv_only | dl_only |
|---|---:|---:|
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 4.0% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 0.0% | 92.0% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_45, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 3 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 1025 | w/x/y/z = 1/0/819/205
- **Recovery rate** = 80.0% [77.4-82.3] (819/1024)
- **Both-fail ceiling** = 20.0% [17.7-22.6]
- **McNemar** (x=0 vs y=819): p_exact = 5.7e-247, chi2_cc = 817.0
- Clean probes (25): w/x/y/z = 0/0/23/2

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| brightness_p20 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| brightness_p10 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| monochrome | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| jpeg_q30 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| jpeg_q60 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| jpeg_q80 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| color_8bit | 25 | 14 | 56% | 44.0% | 0.00012 | n/a |
| rgb565 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| gaussnoise_12 | 25 | 21 | 84% | 16.0% | 9.5e-07 | n/a |
| gaussnoise_8 | 25 | 21 | 84% | 16.0% | 9.5e-07 | n/a |
| gaussnoise_4 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| histeq | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| autolevel | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| blur_7 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| blur_5 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| blur_3 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| rot_270 | 25 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 25 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 25 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 25 | 6 | 24% | 76.0% | 0.031 | n/a |
| rot_25 | 25 | 16 | 64% | 36.0% | 3.1e-05 | n/a |
| rot_10 | 25 | 21 | 84% | 16.0% | 9.5e-07 | n/a |
| scale_50 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| scale_70 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| scale_90 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| trans_30 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| trans_20 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| trans_10 | 25 | 21 | 84% | 16.0% | 9.5e-07 | n/a |
| flip_lr | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| aspect_6_3 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| aspect_16_9 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| crop_60 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| crop_70 | 25 | 24 | 96% | 4.0% | 1.2e-07 | n/a |
| crop_90 | 25 | 23 | 92% | 8.0% | 2.4e-07 | n/a |
| skew_10 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| skew_6 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| skew_4 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| persp_10 | 24 | 21 | 88% | 12.0% | 9.5e-07 | 1.00 |
| persp_6 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
| persp_4 | 25 | 22 | 88% | 12.0% | 4.8e-07 | n/a |
