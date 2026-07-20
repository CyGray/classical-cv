# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **98.15%** | **97.20%** | **97.19%** |
| Pooled AR [95% CI] | 97.87% [97.63-98.09] | 96.78% [96.48-97.05] | 96.77% [96.47-97.04] |
| Mean latency | 139.63 ms | 34.08 ms | 0.67 ms |
| Latency median / p95 | 137.65 / 164.73 ms | 31.73 / 56.00 ms | 0.46 / 1.93 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 99.7% | 99.7% | tie | 100% |
| brightness_down | 96.9% | 99.7% | 99.7% | dl_stronger | 99% |
| contrast_up | 98.6% | 99.7% | 99.6% | tie | 92% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 99% |
| gamma_up | 100.0% | 99.6% | 99.6% | tie | 99% |
| gamma_down | 100.0% | 99.6% | 99.6% | tie | 98% |
| gaussian_noise | 82.4% | 70.1% | 70.1% | cv_stronger | 81% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 100% |
| motion_blur | 100.0% | 99.6% | 99.6% | tie | 99% |
| rotation | 100.0% | 99.6% | 99.6% | tie | 100% |
| zoom | 100.0% | 99.7% | 99.7% | tie | 100% |
| occlusion | 100.0% | 99.5% | 99.5% | tie | 99% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14160/286/124/190
- **Recovery rate** = 39.5% [34.2-45.0] (124/314)
- **Both-fail ceiling** = 1.3% [1.1-1.5]
- **McNemar** (x=286 vs y=124): p_exact = 7.8e-16, chi2_cc = 63.2
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 0.22 | 1.00 |
| brightness_down | 44 | 44 | 100% | 0.0% | 1.5e-09 | 1.00 |
| contrast_up | 15 | 15 | 100% | 0.0% | 0.0075 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| gaussian_noise | 254 | 64 | 25% | 13.2% | 2.6e-25 | 0.97 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.062 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.998**; margin signal: 0.984
- Deployed gate vs 'LBPH wrong': escalates 14307 probes; TPR (wrong probes escalated) = 0.997, FPR (right probes escalated) = 0.969, precision = 0.022
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=313
- Including clean probes: AUC(d1) = 0.998, gate TPR = 0.997, FPR = 0.969
