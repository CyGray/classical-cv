# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (349 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.71% | 99.71% |
| **Overall AR** | **98.26%** | **97.16%** | **97.15%** |
| Pooled AR [95% CI] | 97.97% [97.73-98.19] | 96.72% [96.42-97.00] | 96.71% [96.40-96.99] |
| Mean latency | 95.65 ms | 16.12 ms | 0.40 ms |
| Latency median / p95 | 95.24 / 113.71 ms | 15.14 / 22.64 ms | 0.36 / 0.64 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 99.7% | 99.7% | tie | 100% |
| brightness_down | 97.8% | 99.2% | 99.2% | tie | 99% |
| contrast_up | 99.4% | 100.0% | 99.8% | tie | 89% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 100% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 99% |
| gamma_down | 100.0% | 99.7% | 99.7% | tie | 98% |
| gaussian_noise | 82.0% | 69.5% | 69.5% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 100% |
| motion_blur | 100.0% | 99.6% | 99.6% | tie | 99% |
| rotation | 99.9% | 99.6% | 99.6% | tie | 99% |
| zoom | 100.0% | 99.7% | 99.7% | tie | 99% |
| occlusion | 100.0% | 99.7% | 99.7% | tie | 98% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): none
- Ties: 11 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14309 | w/x/y/z = 13731/288/109/181
- **Recovery rate** = 37.6% [32.2-43.3] (109/290)
- **Both-fail ceiling** = 1.3% [1.1-1.5]
- **McNemar** (x=288 vs y=109): p_exact = 9.6e-20, chi2_cc = 79.8
- Clean probes (349): w/x/y/z = 348/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 0.38 | 1.00 |
| brightness_down | 31 | 28 | 90% | 0.2% | 0.0012 | 1.00 |
| contrast_up | 6 | 6 | 100% | 0.0% | 0.031 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gaussian_noise | 251 | 74 | 29% | 12.7% | 2.7e-23 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| rotation | 1 | 0 | 0% | 0.1% | 0.12 | 0.50 |
| zoom | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.996**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 13809 probes; TPR (wrong probes escalated) = 0.993, FPR (right probes escalated) = 0.964, precision = 0.021
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=288
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.993, FPR = 0.965
