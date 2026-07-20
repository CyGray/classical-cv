# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **98.15%** | **97.43%** | **97.41%** |
| Pooled AR [95% CI] | 97.89% [97.64-98.11] | 96.99% [96.70-97.26] | 96.98% [96.69-97.24] |
| Mean latency | 139.70 ms | 34.45 ms | 0.67 ms |
| Latency median / p95 | 137.88 / 163.92 ms | 32.19 / 56.31 ms | 0.46 / 1.92 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 100.0% | 99.9% | 99.9% | tie | 99% |
| brightness_down | 96.7% | 99.9% | 99.9% | dl_stronger | 98% |
| contrast_up | 98.2% | 100.0% | 99.6% | tie | 87% |
| contrast_down | 100.0% | 99.8% | 99.8% | tie | 99% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 99% |
| gamma_down | 99.7% | 100.0% | 100.0% | tie | 97% |
| gaussian_noise | 83.3% | 70.3% | 70.3% | cv_stronger | 79% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | tie | 100% |
| motion_blur | 100.0% | 100.0% | 100.0% | tie | 100% |
| rotation | 99.9% | 99.4% | 99.5% | tie | 99% |
| zoom | 100.0% | 99.9% | 99.9% | tie | 100% |
| occlusion | 100.0% | 100.0% | 100.0% | tie | 98% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14192/256/124/188
- **Recovery rate** = 39.7% [34.5-45.3] (124/312)
- **Both-fail ceiling** = 1.3% [1.1-1.5]
- **McNemar** (x=256 vs y=124): p_exact = 1.1e-11, chi2_cc = 45.2
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| brightness_down | 48 | 47 | 98% | 0.1% | 3.5e-13 | 1.00 |
| contrast_up | 19 | 19 | 100% | 0.0% | 3.8e-06 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 3 | 3 | 100% | 0.0% | 0.25 | 1.00 |
| gaussian_noise | 240 | 54 | 22% | 12.9% | 1.4e-29 | 0.97 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| rotation | 2 | 1 | 50% | 0.1% | 0.07 | 0.61 |
| zoom | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.981
- Deployed gate vs 'LBPH wrong': escalates 14196 probes; TPR (wrong probes escalated) = 0.987, FPR (right probes escalated) = 0.961, precision = 0.022
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=308
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.987, FPR = 0.962
