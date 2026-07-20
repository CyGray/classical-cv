# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.44% | 99.72% |
| **Overall AR** | **98.23%** | **96.94%** | **96.97%** |
| Pooled AR [95% CI] | 97.95% [97.71-98.17] | 96.48% [96.17-96.77] | 96.52% [96.21-96.80] |
| Mean latency | 139.74 ms | 34.14 ms | 0.67 ms |
| Latency median / p95 | 137.83 / 164.67 ms | 31.90 / 55.37 ms | 0.46 / 1.92 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 99.2% | 99.3% | tie | 99% |
| brightness_down | 97.2% | 99.7% | 99.7% | dl_stronger | 97% |
| contrast_up | 98.9% | 99.4% | 99.4% | tie | 88% |
| contrast_down | 100.0% | 99.6% | 99.6% | tie | 99% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 98% |
| gamma_down | 99.9% | 99.4% | 99.4% | tie | 96% |
| gaussian_noise | 82.8% | 68.2% | 68.3% | cv_stronger | 82% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 100% |
| motion_blur | 100.0% | 99.6% | 99.7% | tie | 98% |
| rotation | 100.0% | 99.5% | 99.5% | tie | 100% |
| zoom | 100.0% | 99.4% | 99.4% | tie | 99% |
| occlusion | 100.0% | 99.7% | 99.7% | tie | 96% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14136/322/105/197
- **Recovery rate** = 34.8% [29.6-40.3] (105/302)
- **Both-fail ceiling** = 1.3% [1.2-1.5]
- **McNemar** (x=322 vs y=105): p_exact = 1.0e-26, chi2_cc = 109.3
- Clean probes (360): w/x/y/z = 358/2/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 0.0063 | 1.00 |
| brightness_down | 41 | 41 | 100% | 0.0% | 4.4e-08 | 1.00 |
| contrast_up | 12 | 12 | 100% | 0.0% | 0.24 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 1 | 1 | 100% | 0.0% | 0.07 | 1.00 |
| gaussian_noise | 247 | 50 | 20% | 13.7% | 1.3e-35 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.016 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | 0.0078 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.985
- Deployed gate vs 'LBPH wrong': escalates 14165 probes; TPR (wrong probes escalated) = 0.990, FPR (right probes escalated) = 0.959, precision = 0.021
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=299
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.990, FPR = 0.959
