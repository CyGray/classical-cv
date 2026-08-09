# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% | 99.72% |
| **Overall AR** | **87.20%** | **98.48%** | **94.68%** | **98.49%** |
| Pooled AR [95% CI] | 85.60% [85.03-86.16] | 98.26% [98.03-98.46] | 93.96% [93.57-94.34] | 98.27% [98.05-98.47] |
| Mean latency | 93.92 ms | 19.77 ms | 3.48 ms | 7.11 ms |
| Latency median / p95 | 92.28 / 110.99 ms | 19.48 / 24.50 ms | 0.48 / 8.84 ms | 7.05 / 9.45 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 97.6% | 99.9% | 99.9% | 99.9% | dl_stronger | 53% |
| brightness_down | 74.0% | 99.5% | 96.8% | 99.5% | dl_stronger | 47% |
| contrast_up | 81.2% | 99.8% | 93.6% | 99.8% | dl_stronger | 26% |
| contrast_down | 100.0% | 99.9% | 99.9% | 99.9% | tie | 62% |
| gamma_up | 100.0% | 99.7% | 99.7% | 99.7% | tie | 34% |
| gamma_down | 96.9% | 99.7% | 100.0% | 99.7% | dl_stronger | 41% |
| gaussian_noise | 29.4% | 84.4% | 65.6% | 84.5% | dl_stronger | 59% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | 99.7% | tie | 60% |
| motion_blur | 97.9% | 99.7% | 99.4% | 99.7% | tie | 52% |
| rotation | 69.8% | 99.9% | 81.9% | 99.9% | dl_stronger | 44% |
| zoom | 99.7% | 99.7% | 99.8% | 99.8% | tie | 33% |
| occlusion | 100.0% | 99.7% | 99.7% | 99.7% | tie | 25% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.81 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12600/35/1903/222
- **Recovery rate** = 89.6% [88.2-90.8] (1903/2125)
- **Both-fail ceiling** = 1.5% [1.3-1.7]
- **McNemar** (x=35 vs y=1903): p_exact = 0.0e+00, chi2_cc = 1798.6
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 34 | 34 | 100% | 0.0% | 1.9e-08 | 1.00 |
| brightness_down | 375 | 373 | 99% | 0.1% | 2.1e-103 | 0.98 |
| contrast_up | 203 | 203 | 100% | 0.0% | 8.2e-58 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 33 | 33 | 100% | 0.0% | 2.3e-07 | 1.00 |
| gaussian_noise | 1017 | 799 | 79% | 15.1% | 3.5e-228 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 23 | 23 | 100% | 0.0% | 8.8e-05 | 1.00 |
| rotation | 435 | 433 | 100% | 0.1% | 9.0e-131 | 1.00 |
| zoom | 5 | 5 | 100% | 0.0% | 1 | 0.88 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.991**; margin signal: 0.985
- Deployed gate vs 'LBPH wrong': escalates 6652 probes; TPR (wrong probes escalated) = 0.680, FPR (right probes escalated) = 0.412, precision = 0.217
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=732, low_margin=713, ambiguous_band=1
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.680, FPR = 0.407
