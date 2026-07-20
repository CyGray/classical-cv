# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **97.93%** | **97.40%** | **97.40%** |
| Pooled AR [95% CI] | 97.60% [97.34-97.84] | 96.96% [96.68-97.23] | 96.96% [96.68-97.23] |
| Mean latency | 139.81 ms | 33.97 ms | 0.67 ms |
| Latency median / p95 | 138.17 / 165.24 ms | 31.73 / 55.81 ms | 0.46 / 1.99 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 100.0% | 100.0% | tie | 100% |
| brightness_down | 96.2% | 99.9% | 99.9% | dl_stronger | 98% |
| contrast_up | 99.0% | 99.9% | 99.9% | tie | 91% |
| contrast_down | 100.0% | 100.0% | 100.0% | tie | 100% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 100% |
| gamma_down | 100.0% | 99.9% | 99.9% | tie | 98% |
| gaussian_noise | 80.1% | 69.2% | 69.2% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | tie | 100% |
| motion_blur | 100.0% | 100.0% | 100.0% | tie | 99% |
| rotation | 100.0% | 100.0% | 100.0% | tie | 100% |
| zoom | 100.0% | 100.0% | 100.0% | tie | 100% |
| occlusion | 100.0% | 100.0% | 100.0% | tie | 99% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14163/243/149/205
- **Recovery rate** = 42.1% [37.1-47.3] (149/354)
- **Both-fail ceiling** = 1.4% [1.2-1.6]
- **McNemar** (x=243 vs y=149): p_exact = 2.4e-06, chi2_cc = 22.1
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 1 | 1.00 |
| brightness_down | 55 | 54 | 98% | 0.1% | 3.1e-15 | 1.00 |
| contrast_up | 11 | 11 | 100% | 0.0% | 0.0063 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gaussian_noise | 287 | 83 | 29% | 14.2% | 7.8e-19 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| rotation | 0 | 0 | nan% | 0.0% | n/a | n/a |
| zoom | 0 | 0 | nan% | 0.0% | n/a | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.983
- Deployed gate vs 'LBPH wrong': escalates 14283 probes; TPR (wrong probes escalated) = 1.000, FPR (right probes escalated) = 0.967, precision = 0.025
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=354
- Including clean probes: AUC(d1) = 0.997, gate TPR = 1.000, FPR = 0.967
