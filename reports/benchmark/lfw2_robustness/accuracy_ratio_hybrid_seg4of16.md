# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **98.13%** | **97.40%** | **97.40%** |
| Pooled AR [95% CI] | 97.85% [97.61-98.07] | 96.97% [96.68-97.24] | 96.97% [96.68-97.24] |
| Mean latency | 139.83 ms | 34.26 ms | 0.67 ms |
| Latency median / p95 | 138.09 / 164.42 ms | 31.96 / 55.84 ms | 0.46 / 1.94 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 100.0% | 100.0% | tie | 99% |
| brightness_down | 97.0% | 99.7% | 99.7% | dl_stronger | 98% |
| contrast_up | 98.5% | 99.9% | 99.8% | tie | 85% |
| contrast_down | 100.0% | 100.0% | 100.0% | tie | 100% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 98% |
| gamma_down | 100.0% | 99.9% | 99.9% | tie | 97% |
| gaussian_noise | 82.2% | 69.8% | 69.8% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 99.9% | 99.9% | tie | 100% |
| motion_blur | 100.0% | 99.9% | 100.0% | tie | 99% |
| rotation | 100.0% | 99.9% | 99.9% | tie | 100% |
| zoom | 100.0% | 100.0% | 100.0% | tie | 99% |
| occlusion | 100.0% | 99.9% | 99.9% | tie | 97% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14203/240/110/207
- **Recovery rate** = 34.7% [29.7-40.1] (110/317)
- **Both-fail ceiling** = 1.4% [1.2-1.6]
- **McNemar** (x=240 vs y=110): p_exact = 3.0e-12, chi2_cc = 47.5
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 2 | 2 | 100% | 0.0% | 0.5 | 1.00 |
| brightness_down | 43 | 40 | 93% | 0.2% | 4.1e-10 | 1.00 |
| contrast_up | 16 | 16 | 100% | 0.0% | 0.00027 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gaussian_noise | 256 | 52 | 20% | 14.2% | 4.3e-28 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 1 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 1 | n/a |
| rotation | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| zoom | 0 | 0 | nan% | 0.0% | n/a | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 1 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.986
- Deployed gate vs 'LBPH wrong': escalates 14149 probes; TPR (wrong probes escalated) = 0.997, FPR (right probes escalated) = 0.958, precision = 0.022
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=316
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.997, FPR = 0.958
