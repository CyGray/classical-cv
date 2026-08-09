# Accuracy Ratio - dl41 modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade

Protocol: `identification_disjoint` | split manifest: `data/splits/lfw_ident_split_seed42.json` (triples sha256 `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`)

Originals: `data/splits/lfw_ident_split_seed42.json` (manifest probes) (26 tiles) | 41 variants/original (all 41 in the headline mean; 4 of them are detector-canonical and are ALSO broken out separately below) | seed=42 | no-face policy: `fallback`.

AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on the right identity at all, regardless of accept/reject). These answer different questions: a mode can rank the right person first and still reject them for sitting outside its accept band - see docs/audits/STATE-08-01.md. AR per modification = mean over its levels; overall = mean over ALL 41 modifications, matching the DL team's ar-table.py. The 4 detector-canonical ones (rot_90/180/270, flip_lr) are included here AND broken out separately below, since a recognizer failing on an upside-down face is expected behaviour and reads differently from a failure on blur or noise. Retention = AR_mod / AR_clean (threshold-gated, clean = the held-out baseline row, undegraded probes).

| Metric | cv_only | dl_only |
|---|---:|---:|
| Clean held-out baseline - Rank-1 (threshold-free) | 7.69% | 96.15% |
| Clean held-out baseline - TPIR @ threshold | 0.00% | 88.46% |
| **Overall AR (41 mods, TPIR @ threshold)** | **2.06%** | **81.14%** |
| Pooled AR [95% CI] | 2.06% [1.37-3.11] | 81.14% [78.69-83.38] |
| Overall Rank-1 (41 mods, threshold-free) | 7.88% | 89.02% |
| Pooled Rank-1 [95% CI] | 7.88% [6.41-9.65] | 89.02% [87.01-90.76] |
| Mean latency | 106.60 ms | 63.72 ms |
| Latency median / p95 | 106.24 / 142.28 ms | 62.76 / 92.44 ms |

## Per modification (41 mods) - AR (TPIR @ threshold)

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| brightness_p25 | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |
| brightness_p20 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| brightness_p10 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| monochrome | 3.8% | 88.5% | n/a / 1.00 | dl_stronger |
| jpeg_q30 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| jpeg_q60 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| jpeg_q80 | 3.8% | 88.5% | n/a / 1.00 | dl_stronger |
| color_8bit | 0.0% | 61.5% | n/a / 0.70 | dl_stronger |
| rgb565 | 0.0% | 88.5% | n/a / 1.00 | dl_stronger |
| gaussnoise_12 | 0.0% | 84.6% | n/a / 0.96 | dl_stronger |
| gaussnoise_8 | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |
| gaussnoise_4 | 3.8% | 88.5% | n/a / 1.00 | dl_stronger |
| histeq | 7.7% | 92.3% | n/a / 1.04 | dl_stronger |
| autolevel | 0.0% | 88.5% | n/a / 1.00 | dl_stronger |
| blur_7 | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |
| blur_5 | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |
| blur_3 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_45 | 0.0% | 19.2% | n/a / 0.22 | dl_stronger |
| rot_25 | 0.0% | 88.5% | n/a / 1.00 | dl_stronger |
| rot_10 | 3.8% | 88.5% | n/a / 1.00 | dl_stronger |
| scale_50 | 0.0% | 80.8% | n/a / 0.91 | dl_stronger |
| scale_70 | 0.0% | 84.6% | n/a / 0.96 | dl_stronger |
| scale_90 | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |
| trans_30 | 0.0% | 84.6% | n/a / 0.96 | dl_stronger |
| trans_20 | 3.8% | 88.5% | n/a / 1.00 | dl_stronger |
| trans_10 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| flip_lr | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |
| aspect_6_3 | 0.0% | 84.6% | n/a / 0.96 | dl_stronger |
| aspect_16_9 | 3.8% | 88.5% | n/a / 1.00 | dl_stronger |
| crop_60 | 7.7% | 92.3% | n/a / 1.04 | dl_stronger |
| crop_70 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| crop_90 | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |
| skew_10 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| skew_6 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| skew_4 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| persp_10 | 0.0% | 88.5% | n/a / 1.00 | dl_stronger |
| persp_6 | 3.8% | 92.3% | n/a / 1.04 | dl_stronger |
| persp_4 | 3.8% | 96.2% | n/a / 1.09 | dl_stronger |

## Per modification (41 mods) - Rank-1 identification (threshold-free)

| Modification | cv_only | dl_only |
|---|---:|---:|
| brightness_p25 | 3.8% | 100.0% |
| brightness_p20 | 11.5% | 100.0% |
| brightness_p10 | 11.5% | 100.0% |
| monochrome | 7.7% | 100.0% |
| jpeg_q30 | 11.5% | 100.0% |
| jpeg_q60 | 11.5% | 100.0% |
| jpeg_q80 | 11.5% | 96.2% |
| color_8bit | 7.7% | 84.6% |
| rgb565 | 15.4% | 96.2% |
| gaussnoise_12 | 11.5% | 96.2% |
| gaussnoise_8 | 11.5% | 100.0% |
| gaussnoise_4 | 11.5% | 96.2% |
| histeq | 7.7% | 100.0% |
| autolevel | 15.4% | 96.2% |
| blur_7 | 3.8% | 100.0% |
| blur_5 | 11.5% | 100.0% |
| blur_3 | 11.5% | 100.0% |
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| rot_45 | 0.0% | 42.3% |
| rot_25 | 3.8% | 92.3% |
| rot_10 | 11.5% | 96.2% |
| scale_50 | 0.0% | 88.5% |
| scale_70 | 0.0% | 92.3% |
| scale_90 | 3.8% | 100.0% |
| trans_30 | 0.0% | 92.3% |
| trans_20 | 3.8% | 96.2% |
| trans_10 | 7.7% | 100.0% |
| flip_lr | 3.8% | 100.0% |
| aspect_6_3 | 11.5% | 96.2% |
| aspect_16_9 | 11.5% | 96.2% |
| crop_60 | 11.5% | 100.0% |
| crop_70 | 11.5% | 100.0% |
| crop_90 | 7.7% | 100.0% |
| skew_10 | 7.7% | 100.0% |
| skew_6 | 7.7% | 100.0% |
| skew_4 | 7.7% | 100.0% |
| persp_10 | 11.5% | 92.3% |
| persp_6 | 11.5% | 100.0% |
| persp_4 | 11.5% | 100.0% |

## Detector-canonical (rot_90/180/270, flip_lr) - INCLUDED in the headline mean above, broken out here as well

A recognizer failing on an upside-down face is expected behaviour, and flip is near-free for a roughly-symmetric embedding, so these four read differently from the damage-style modifications. They are counted in the headline mean (--headline-scope all41, the default, matching the DL team's ar-table.py) and repeated here so the headline can be decomposed. Re-run with --headline-scope exclude-canonical for the headline without them.

| Metric | cv_only | dl_only |
|---|---:|---:|
| Detector-canonical AR (TPIR @ threshold) | **0.00%** | **23.08%** |
| Detector-canonical Rank-1 (threshold-free) | **0.96%** | **25.00%** |

| Modification | cv_only | dl_only | retention | winner |
|---|---:|---:|---:|---|
| rot_270 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_180 | 0.0% | 0.0% | n/a / 0.00 | tie |
| rot_90 | 0.0% | 0.0% | n/a / 0.00 | tie |
| flip_lr | 0.0% | 92.3% | n/a / 1.04 | dl_stronger |

| Modification | cv_only | dl_only |
|---|---:|---:|
| rot_270 | 0.0% | 0.0% |
| rot_180 | 0.0% | 0.0% |
| rot_90 | 0.0% | 0.0% |
| flip_lr | 3.8% | 100.0% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_p25, brightness_p20, brightness_p10, monochrome, jpeg_q30, jpeg_q60, jpeg_q80, color_8bit, rgb565, gaussnoise_12, gaussnoise_8, gaussnoise_4, histeq, autolevel, blur_7, blur_5, blur_3, rot_45, rot_25, rot_10, scale_50, scale_70, scale_90, trans_30, trans_20, trans_10, flip_lr, aspect_6_3, aspect_16_9, crop_60, crop_70, crop_90, skew_10, skew_6, skew_4, persp_10, persp_6, persp_4
- Ties: 3 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 1066 | w/x/y/z = 22/0/843/201
- **Recovery rate** = 80.7% [78.2-83.0] (843/1044)
- **Both-fail ceiling** = 18.9% [16.6-21.3]
- **McNemar** (x=0 vs y=843): p_exact = 3.4e-254, chi2_cc = 841.0
- Clean probes (26): w/x/y/z = 0/0/23/3

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_p25 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| brightness_p20 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| brightness_p10 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| monochrome | 25 | 22 | 88% | 11.5% | 4.8e-07 | 1.00 |
| jpeg_q30 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| jpeg_q60 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| jpeg_q80 | 25 | 22 | 88% | 11.5% | 4.8e-07 | 1.00 |
| color_8bit | 26 | 16 | 62% | 38.5% | 3.1e-05 | n/a |
| rgb565 | 26 | 23 | 88% | 11.5% | 2.4e-07 | n/a |
| gaussnoise_12 | 26 | 22 | 85% | 15.4% | 4.8e-07 | n/a |
| gaussnoise_8 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| gaussnoise_4 | 25 | 22 | 88% | 11.5% | 4.8e-07 | 1.00 |
| histeq | 24 | 22 | 92% | 7.7% | 4.8e-07 | 1.00 |
| autolevel | 26 | 23 | 88% | 11.5% | 2.4e-07 | n/a |
| blur_7 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| blur_5 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| blur_3 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| rot_270 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_180 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_90 | 26 | 0 | 0% | 100.0% | n/a | n/a |
| rot_45 | 26 | 5 | 19% | 80.8% | 0.062 | n/a |
| rot_25 | 26 | 23 | 88% | 11.5% | 2.4e-07 | n/a |
| rot_10 | 25 | 22 | 88% | 11.5% | 4.8e-07 | 1.00 |
| scale_50 | 26 | 21 | 81% | 19.2% | 9.5e-07 | n/a |
| scale_70 | 26 | 22 | 85% | 15.4% | 4.8e-07 | n/a |
| scale_90 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| trans_30 | 26 | 22 | 85% | 15.4% | 4.8e-07 | n/a |
| trans_20 | 25 | 22 | 88% | 11.5% | 4.8e-07 | 1.00 |
| trans_10 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| flip_lr | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| aspect_6_3 | 26 | 22 | 85% | 15.4% | 4.8e-07 | n/a |
| aspect_16_9 | 25 | 22 | 88% | 11.5% | 4.8e-07 | 1.00 |
| crop_60 | 24 | 22 | 92% | 7.7% | 4.8e-07 | 1.00 |
| crop_70 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| crop_90 | 26 | 24 | 92% | 7.7% | 1.2e-07 | n/a |
| skew_10 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| skew_6 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| skew_4 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| persp_10 | 26 | 23 | 88% | 11.5% | 2.4e-07 | n/a |
| persp_6 | 25 | 23 | 92% | 7.7% | 2.4e-07 | 1.00 |
| persp_4 | 25 | 24 | 96% | 3.8% | 1.2e-07 | 1.00 |
