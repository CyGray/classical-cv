# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **98.06%** | **97.09%** | **97.09%** |
| Pooled AR [95% CI] | 97.76% [97.51-97.98] | 96.63% [96.32-96.91] | 96.63% [96.32-96.91] |
| Mean latency | 95.30 ms | 16.06 ms | 0.40 ms |
| Latency median / p95 | 94.78 / 113.83 ms | 15.07 / 22.44 ms | 0.36 / 0.65 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 100.0% | 99.9% | 99.9% | tie | 100% |
| brightness_down | 97.4% | 99.9% | 99.9% | dl_stronger | 99% |
| contrast_up | 98.9% | 100.0% | 99.9% | tie | 88% |
| contrast_down | 100.0% | 99.5% | 99.5% | tie | 99% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 99% |
| gamma_down | 100.0% | 100.0% | 100.0% | tie | 98% |
| gaussian_noise | 80.5% | 67.4% | 67.4% | cv_stronger | 81% |
| gaussian_blur | 100.0% | 99.5% | 99.5% | tie | 100% |
| motion_blur | 100.0% | 100.0% | 100.0% | tie | 99% |
| rotation | 100.0% | 99.7% | 99.7% | tie | 99% |
| zoom | 100.0% | 99.7% | 99.7% | tie | 99% |
| occlusion | 100.0% | 99.7% | 99.7% | tie | 98% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14149/280/113/218
- **Recovery rate** = 34.1% [29.2-39.4] (113/331)
- **Both-fail ceiling** = 1.5% [1.3-1.7]
- **McNemar** (x=280 vs y=113): p_exact = 1.8e-17, chi2_cc = 70.1
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| brightness_down | 38 | 38 | 100% | 0.0% | 1.5e-10 | 1.00 |
| contrast_up | 12 | 12 | 100% | 0.0% | 0.00049 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gaussian_noise | 281 | 63 | 22% | 15.1% | 6.4e-28 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.989
- Deployed gate vs 'LBPH wrong': escalates 14256 probes; TPR (wrong probes escalated) = 0.997, FPR (right probes escalated) = 0.965, precision = 0.023
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=330
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.997, FPR = 0.966
