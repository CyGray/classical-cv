# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **97.77%** | **97.40%** | **97.37%** |
| Pooled AR [95% CI] | 97.43% [97.16-97.68] | 96.96% [96.68-97.23] | 96.94% [96.65-97.20] |
| Mean latency | 140.08 ms | 34.07 ms | 0.67 ms |
| Latency median / p95 | 138.17 / 165.54 ms | 31.77 / 55.89 ms | 0.46 / 1.96 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 100.0% | 100.0% | tie | 99% |
| brightness_down | 96.7% | 99.7% | 99.7% | dl_stronger | 98% |
| contrast_up | 98.3% | 99.9% | 99.5% | tie | 91% |
| contrast_down | 100.0% | 100.0% | 100.0% | tie | 100% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 98% |
| gamma_down | 99.9% | 100.0% | 100.0% | tie | 98% |
| gaussian_noise | 78.4% | 69.9% | 69.9% | cv_stronger | 81% |
| gaussian_blur | 100.0% | 99.9% | 99.9% | tie | 100% |
| motion_blur | 100.0% | 99.9% | 99.9% | tie | 100% |
| rotation | 100.0% | 99.6% | 99.6% | tie | 100% |
| zoom | 100.0% | 100.0% | 100.0% | tie | 100% |
| occlusion | 100.0% | 99.9% | 99.9% | tie | 99% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14166/215/146/233
- **Recovery rate** = 38.5% [33.8-43.5] (146/379)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=215 vs y=146): p_exact = 0.00033, chi2_cc = 12.8
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 1 | 1.00 |
| brightness_down | 48 | 46 | 96% | 0.1% | 8.4e-12 | 1.00 |
| contrast_up | 18 | 18 | 100% | 0.0% | 7.6e-05 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 1 | 1 | 100% | 0.0% | 1 | 1.00 |
| gaussian_noise | 311 | 80 | 26% | 16.0% | 1.7e-13 | 0.97 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 1 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 1 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | n/a | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 1 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.998**; margin signal: 0.985
- Deployed gate vs 'LBPH wrong': escalates 14290 probes; TPR (wrong probes escalated) = 0.989, FPR (right probes escalated) = 0.968, precision = 0.026
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=375
- Including clean probes: AUC(d1) = 0.998, gate TPR = 0.989, FPR = 0.968
