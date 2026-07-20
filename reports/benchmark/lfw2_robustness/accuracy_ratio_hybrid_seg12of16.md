# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **98.28%** | **97.40%** | **97.40%** |
| Pooled AR [95% CI] | 98.00% [97.76-98.21] | 97.01% [96.72-97.27] | 97.01% [96.72-97.27] |
| Mean latency | 95.38 ms | 16.02 ms | 0.40 ms |
| Latency median / p95 | 94.89 / 114.01 ms | 15.05 / 22.48 ms | 0.36 / 0.64 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 99.7% | 99.7% | tie | 99% |
| brightness_down | 97.6% | 99.7% | 99.7% | dl_stronger | 98% |
| contrast_up | 99.3% | 99.7% | 99.6% | tie | 87% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 99% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 99% |
| gamma_down | 100.0% | 99.7% | 99.7% | tie | 97% |
| gaussian_noise | 82.6% | 71.9% | 72.0% | cv_stronger | 79% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 100% |
| motion_blur | 100.0% | 99.7% | 99.7% | tie | 99% |
| rotation | 100.0% | 99.7% | 99.7% | tie | 100% |
| zoom | 100.0% | 99.7% | 99.7% | tie | 99% |
| occlusion | 100.0% | 99.7% | 99.7% | tie | 98% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14216/249/102/193
- **Recovery rate** = 34.6% [29.4-40.2] (102/295)
- **Both-fail ceiling** = 1.3% [1.1-1.5]
- **McNemar** (x=249 vs y=102): p_exact = 2.6e-15, chi2_cc = 60.7
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 0.22 | 1.00 |
| brightness_down | 35 | 35 | 100% | 0.0% | 3.4e-07 | 1.00 |
| contrast_up | 8 | 8 | 100% | 0.0% | 0.23 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gaussian_noise | 251 | 58 | 23% | 13.4% | 1.4e-21 | 0.97 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.998**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 14189 probes; TPR (wrong probes escalated) = 0.997, FPR (right probes escalated) = 0.961, precision = 0.021
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=294
- Including clean probes: AUC(d1) = 0.998, gate TPR = 0.997, FPR = 0.961
