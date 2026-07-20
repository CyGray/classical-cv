# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 100.00% | 99.72% |
| **Overall AR** | **86.38%** | **98.27%** | **94.89%** | **98.28%** |
| Pooled AR [95% CI] | 84.74% [84.15-85.31] | 97.99% [97.76-98.21] | 94.19% [93.80-94.55] | 98.00% [97.76-98.21] |
| Mean latency | 93.84 ms | 19.72 ms | 3.73 ms | 7.08 ms |
| Latency median / p95 | 92.35 / 110.82 ms | 19.41 / 24.46 ms | 0.60 / 8.83 ms | 7.01 / 9.37 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 94.7% | 100.0% | 99.9% | 100.0% | dl_stronger | 57% |
| brightness_down | 74.3% | 99.7% | 96.7% | 99.7% | dl_stronger | 46% |
| contrast_up | 76.2% | 99.7% | 93.8% | 99.7% | dl_stronger | 33% |
| contrast_down | 100.0% | 99.9% | 99.9% | 99.9% | tie | 65% |
| gamma_up | 100.0% | 100.0% | 100.0% | 100.0% | tie | 38% |
| gamma_down | 96.8% | 99.9% | 99.9% | 99.9% | dl_stronger | 43% |
| gaussian_noise | 28.1% | 80.8% | 65.1% | 80.8% | dl_stronger | 64% |
| gaussian_blur | 100.0% | 99.7% | 99.9% | 99.7% | tie | 64% |
| motion_blur | 99.0% | 99.9% | 99.7% | 99.9% | tie | 55% |
| rotation | 67.8% | 99.8% | 84.0% | 99.9% | dl_stronger | 50% |
| zoom | 99.7% | 99.8% | 99.9% | 99.8% | tie | 39% |
| occlusion | 100.0% | 100.0% | 100.0% | 100.0% | tie | 32% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.38 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12481/26/1983/270
- **Recovery rate** = 88.0% [86.6-89.3] (1983/2253)
- **Both-fail ceiling** = 1.8% [1.6-2.1]
- **McNemar** (x=26 vs y=1983): p_exact = 0.0e+00, chi2_cc = 1904.4
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 76 | 76 | 100% | 0.0% | 2.6e-23 | 1.00 |
| brightness_down | 370 | 370 | 100% | 0.0% | 1.6e-102 | 0.98 |
| contrast_up | 257 | 257 | 100% | 0.0% | 3.2e-72 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 35 | 35 | 100% | 0.0% | 1.1e-09 | 1.00 |
| gaussian_noise | 1036 | 767 | 74% | 18.7% | 6.5e-217 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 11 | 11 | 100% | 0.0% | 0.0063 | 1.00 |
| rotation | 464 | 463 | 100% | 0.1% | 2.3e-135 | 1.00 |
| zoom | 4 | 4 | 100% | 0.0% | 1 | 0.96 |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.993**; margin signal: 0.989
- Deployed gate vs 'LBPH wrong': escalates 7231 probes; TPR (wrong probes escalated) = 0.728, FPR (right probes escalated) = 0.447, precision = 0.227
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=937, low_margin=700, ambiguous_band=3
- Including clean probes: AUC(d1) = 0.993, gate TPR = 0.728, FPR = 0.443
