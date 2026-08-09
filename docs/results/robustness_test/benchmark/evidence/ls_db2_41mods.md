# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `data/split_lasalle/test` (56 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **85.43%** | **96.50%** | **96.11%** | **96.50%** |
| Pooled AR [95% CI] | 84.54% [83.00-85.96] | 95.91% [95.02-96.64] | 95.51% [94.59-96.29] | 95.91% [95.02-96.64] |
| Mean latency | 7.71 ms | 25.89 ms | 19.68 ms | 26.41 ms |
| Latency median / p95 | 5.74 / 16.13 ms | 23.66 / 39.48 ms | 20.25 / 37.63 ms | 24.58 / 39.87 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 97.8% | 100.0% | 100.0% | 100.0% | dl_stronger | 40% |
| brightness_down | 73.7% | 98.2% | 98.2% | 98.2% | dl_stronger | 74% |
| contrast_up | 85.1% | 100.0% | 98.2% | 100.0% | dl_stronger | 53% |
| contrast_down | 98.2% | 100.0% | 100.0% | 100.0% | tie | 46% |
| gamma_up | 98.2% | 100.0% | 100.0% | 100.0% | tie | 18% |
| gamma_down | 97.6% | 100.0% | 100.0% | 100.0% | dl_stronger | 73% |
| gaussian_noise | 47.8% | 59.8% | 59.8% | 59.8% | dl_stronger | 92% |
| gaussian_blur | 88.1% | 100.0% | 100.0% | 100.0% | dl_stronger | 100% |
| motion_blur | 68.5% | 100.0% | 98.8% | 100.0% | dl_stronger | 92% |
| rotation | 83.5% | 100.0% | 99.6% | 100.0% | dl_stronger | 74% |
| zoom | 87.9% | 100.0% | 98.7% | 100.0% | dl_stronger | 67% |
| occlusion | 98.8% | 100.0% | 100.0% | 100.0% | tie | 25% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, gaussian_blur, motion_blur, rotation, zoom
- Ties: 3 modifications
- Cascade within 2 pts of the better engine on 12 / 12 modifications
- Cascade vs parallel (run-both ceiling): -0.40 pts overall, within tolerance on 12 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 2296 | w/x/y/z = 1923/18/279/76
- **Recovery rate** = 78.6% [74.0-82.5] (279/355)
- **Both-fail ceiling** = 3.3% [2.7-4.1]
- **McNemar** (x=18 vs y=279): p_exact = 2.5e-61, chi2_cc = 227.6
- Clean probes (56): w/x/y/z = 56/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 5 | 5 | 100% | 0.0% | 0.062 | 0.89 |
| brightness_down | 59 | 55 | 93% | 1.8% | 5.6e-17 | 1.00 |
| contrast_up | 25 | 25 | 100% | 0.0% | 6.0e-08 | 0.98 |
| contrast_down | 3 | 3 | 100% | 0.0% | 0.25 | 0.81 |
| gamma_up | 3 | 3 | 100% | 0.0% | 0.25 | 0.91 |
| gamma_down | 4 | 4 | 100% | 0.0% | 0.12 | 0.98 |
| gaussian_noise | 117 | 45 | 38% | 32.1% | 0.0009 | 0.88 |
| gaussian_blur | 20 | 20 | 100% | 0.0% | 1.9e-06 | 0.97 |
| motion_blur | 53 | 53 | 100% | 0.0% | 2.2e-16 | 0.99 |
| rotation | 37 | 37 | 100% | 0.0% | 1.5e-11 | 0.89 |
| zoom | 27 | 27 | 100% | 0.0% | 1.5e-08 | 0.90 |
| occlusion | 2 | 2 | 100% | 0.0% | 0.5 | 0.87 |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.953**; margin signal: 0.898
- Deployed gate vs 'LBPH wrong': escalates 1459 probes; TPR (wrong probes escalated) = 0.975, FPR (right probes escalated) = 0.573, precision = 0.237
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=298, low_margin=37, ambiguous_band=11
- Including clean probes: AUC(d1) = 0.954, gate TPR = 0.975, FPR = 0.564
