# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **98.16%** | **97.33%** | **97.34%** |
| Pooled AR [95% CI] | 97.87% [97.63-98.09] | 96.91% [96.62-97.18] | 96.92% [96.63-97.18] |
| Mean latency | 140.02 ms | 34.09 ms | 0.67 ms |
| Latency median / p95 | 138.20 / 165.08 ms | 31.79 / 56.02 ms | 0.45 / 1.98 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 100.0% | 99.7% | 99.7% | tie | 100% |
| brightness_down | 97.0% | 99.4% | 99.4% | dl_stronger | 99% |
| contrast_up | 99.1% | 99.6% | 99.6% | tie | 89% |
| contrast_down | 100.0% | 99.9% | 99.9% | tie | 100% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 99% |
| gamma_down | 100.0% | 99.7% | 99.7% | tie | 98% |
| gaussian_noise | 81.9% | 70.3% | 70.4% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 100% |
| motion_blur | 100.0% | 99.7% | 99.7% | tie | 100% |
| rotation | 100.0% | 99.9% | 99.9% | tie | 100% |
| zoom | 100.0% | 100.0% | 100.0% | tie | 100% |
| occlusion | 100.0% | 99.9% | 99.9% | tie | 99% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14193/253/111/203
- **Recovery rate** = 35.4% [30.3-40.8] (111/314)
- **Both-fail ceiling** = 1.4% [1.2-1.6]
- **McNemar** (x=253 vs y=111): p_exact = 7.1e-14, chi2_cc = 54.6
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| brightness_down | 43 | 39 | 91% | 0.3% | 1.4e-07 | 1.00 |
| contrast_up | 10 | 9 | 90% | 0.1% | 0.15 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gaussian_noise | 261 | 63 | 24% | 13.8% | 2.6e-23 | 0.97 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 1 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | n/a | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 1 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.986
- Deployed gate vs 'LBPH wrong': escalates 14277 probes; TPR (wrong probes escalated) = 1.000, FPR (right probes escalated) = 0.967, precision = 0.022
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=314
- Including clean probes: AUC(d1) = 0.997, gate TPR = 1.000, FPR = 0.967
