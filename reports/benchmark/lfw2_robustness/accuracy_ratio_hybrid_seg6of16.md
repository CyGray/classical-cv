# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **98.38%** | **97.05%** | **97.05%** |
| Pooled AR [95% CI] | 98.12% [97.88-98.32] | 96.59% [96.29-96.87] | 96.60% [96.29-96.88] |
| Mean latency | 139.98 ms | 33.96 ms | 0.66 ms |
| Latency median / p95 | 138.04 / 164.72 ms | 31.76 / 55.63 ms | 0.46 / 1.91 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 100.0% | 99.7% | 99.7% | tie | 100% |
| brightness_down | 97.8% | 99.7% | 99.7% | tie | 98% |
| contrast_up | 99.5% | 99.7% | 99.7% | tie | 91% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 99% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 100% |
| gamma_down | 99.9% | 99.7% | 99.7% | tie | 97% |
| gaussian_noise | 83.3% | 67.8% | 67.8% | cv_stronger | 81% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 100% |
| motion_blur | 100.0% | 99.7% | 99.7% | tie | 99% |
| rotation | 100.0% | 99.7% | 99.7% | tie | 100% |
| zoom | 100.0% | 99.7% | 99.7% | tie | 100% |
| occlusion | 100.0% | 99.7% | 99.7% | tie | 98% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): none
- Ties: 11 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14181/301/76/202
- **Recovery rate** = 27.3% [22.4-32.9] (76/278)
- **Both-fail ceiling** = 1.4% [1.2-1.6]
- **McNemar** (x=301 vs y=76): p_exact = 8.7e-33, chi2_cc = 133.1
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| brightness_down | 31 | 30 | 97% | 0.1% | 6.2e-06 | 1.00 |
| contrast_up | 5 | 5 | 100% | 0.0% | 0.73 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 1 | 1 | 100% | 0.0% | 0.62 | 1.00 |
| gaussian_noise | 241 | 40 | 17% | 14.0% | 2.2e-41 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 14255 probes; TPR (wrong probes escalated) = 1.000, FPR (right probes escalated) = 0.965, precision = 0.020
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=278
- Including clean probes: AUC(d1) = 0.997, gate TPR = 1.000, FPR = 0.965
