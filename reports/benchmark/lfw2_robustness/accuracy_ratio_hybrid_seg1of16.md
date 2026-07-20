# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **98.00%** | **97.33%** | **97.33%** |
| Pooled AR [95% CI] | 97.68% [97.42-97.91] | 96.89% [96.60-97.16] | 96.89% [96.60-97.16] |
| Mean latency | 140.00 ms | 34.11 ms | 0.67 ms |
| Latency median / p95 | 138.28 / 165.21 ms | 31.98 / 55.89 ms | 0.46 / 1.92 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 100.0% | 99.9% | 99.9% | tie | 99% |
| brightness_down | 96.7% | 99.7% | 99.7% | dl_stronger | 99% |
| contrast_up | 99.6% | 100.0% | 99.9% | tie | 88% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 100% |
| gamma_up | 100.0% | 99.8% | 99.8% | tie | 99% |
| gamma_down | 100.0% | 100.0% | 100.0% | tie | 98% |
| gaussian_noise | 79.9% | 69.6% | 69.7% | cv_stronger | 79% |
| gaussian_blur | 99.9% | 100.0% | 100.0% | tie | 100% |
| motion_blur | 99.9% | 99.9% | 99.9% | tie | 100% |
| rotation | 100.0% | 99.7% | 99.7% | tie | 99% |
| zoom | 100.0% | 99.7% | 99.7% | tie | 99% |
| occlusion | 100.0% | 99.9% | 99.9% | tie | 99% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14187/230/114/229
- **Recovery rate** = 33.2% [28.5-38.4] (114/343)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=230 vs y=114): p_exact = 3.9e-10, chi2_cc = 38.4
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 0 | 0 | nan% | 0.0% | 1 | n/a |
| brightness_down | 47 | 46 | 98% | 0.1% | 7.0e-11 | 1.00 |
| contrast_up | 4 | 4 | 100% | 0.0% | 0.12 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gaussian_noise | 290 | 62 | 21% | 15.8% | 5.5e-20 | 0.96 |
| gaussian_blur | 1 | 1 | 100% | 0.0% | 1 | 0.84 |
| motion_blur | 1 | 1 | 100% | 0.0% | 1 | 0.89 |
| rotation | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 1 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.996**; margin signal: 0.986
- Deployed gate vs 'LBPH wrong': escalates 14227 probes; TPR (wrong probes escalated) = 0.997, FPR (right probes escalated) = 0.963, precision = 0.024
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=342
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.997, FPR = 0.964
