# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **98.23%** | **97.17%** | **97.16%** |
| Pooled AR [95% CI] | 97.94% [97.70-98.16] | 96.70% [96.40-96.98] | 96.70% [96.40-96.98] |
| Mean latency | 95.26 ms | 16.02 ms | 0.40 ms |
| Latency median / p95 | 94.84 / 113.69 ms | 15.04 / 22.43 ms | 0.36 / 0.63 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.8% | 99.9% | 99.9% | tie | 98% |
| brightness_down | 97.4% | 99.6% | 99.6% | dl_stronger | 97% |
| contrast_up | 99.3% | 100.0% | 99.9% | tie | 86% |
| contrast_down | 100.0% | 99.6% | 99.6% | tie | 99% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 97% |
| gamma_down | 100.0% | 100.0% | 100.0% | tie | 96% |
| gaussian_noise | 82.2% | 68.1% | 68.1% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 99.8% | 99.8% | tie | 100% |
| motion_blur | 100.0% | 100.0% | 100.0% | tie | 99% |
| rotation | 100.0% | 99.4% | 99.4% | tie | 99% |
| zoom | 100.0% | 99.8% | 99.8% | tie | 99% |
| occlusion | 100.0% | 99.8% | 99.8% | tie | 96% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14173/283/100/204
- **Recovery rate** = 32.9% [27.9-38.4] (100/304)
- **Both-fail ceiling** = 1.4% [1.2-1.6]
- **McNemar** (x=283 vs y=100): p_exact = 2.3e-21, chi2_cc = 86.5
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 3 | 3 | 100% | 0.0% | 1 | 1.00 |
| brightness_down | 37 | 33 | 89% | 0.3% | 3.7e-08 | 1.00 |
| contrast_up | 8 | 8 | 100% | 0.0% | 0.0078 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gaussian_noise | 256 | 56 | 22% | 13.9% | 1.4e-32 | 0.97 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.0078 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.5 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.985
- Deployed gate vs 'LBPH wrong': escalates 14099 probes; TPR (wrong probes escalated) = 0.997, FPR (right probes escalated) = 0.954, precision = 0.021
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=303
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.997, FPR = 0.955
