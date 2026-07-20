# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **98.19%** | **97.46%** | **97.46%** |
| Pooled AR [95% CI] | 97.89% [97.64-98.11] | 97.03% [96.74-97.29] | 97.03% [96.74-97.29] |
| Mean latency | 95.28 ms | 16.00 ms | 0.40 ms |
| Latency median / p95 | 94.88 / 113.72 ms | 15.06 / 22.17 ms | 0.36 / 0.65 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 100.0% | 100.0% | tie | 99% |
| brightness_down | 97.4% | 99.9% | 99.9% | dl_stronger | 97% |
| contrast_up | 99.7% | 100.0% | 100.0% | tie | 85% |
| contrast_down | 100.0% | 100.0% | 100.0% | tie | 99% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 99% |
| gamma_down | 100.0% | 100.0% | 100.0% | tie | 96% |
| gaussian_noise | 81.2% | 69.7% | 69.7% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | tie | 100% |
| motion_blur | 100.0% | 99.9% | 99.9% | tie | 99% |
| rotation | 100.0% | 100.0% | 100.0% | tie | 99% |
| zoom | 100.0% | 100.0% | 100.0% | tie | 99% |
| occlusion | 100.0% | 100.0% | 100.0% | tie | 97% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14226/222/95/217
- **Recovery rate** = 30.4% [25.6-35.8] (95/312)
- **Both-fail ceiling** = 1.5% [1.3-1.7]
- **McNemar** (x=222 vs y=95): p_exact = 7.3e-13, chi2_cc = 50.1
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 1 | 1.00 |
| brightness_down | 38 | 38 | 100% | 0.0% | 1.5e-10 | 1.00 |
| contrast_up | 3 | 3 | 100% | 0.0% | 0.25 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gaussian_noise | 270 | 53 | 20% | 15.1% | 2.4e-25 | 0.97 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 1 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | n/a | n/a |
| zoom | 0 | 0 | nan% | 0.0% | n/a | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.987
- Deployed gate vs 'LBPH wrong': escalates 14108 probes; TPR (wrong probes escalated) = 1.000, FPR (right probes escalated) = 0.955, precision = 0.022
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=312
- Including clean probes: AUC(d1) = 0.997, gate TPR = 1.000, FPR = 0.955
