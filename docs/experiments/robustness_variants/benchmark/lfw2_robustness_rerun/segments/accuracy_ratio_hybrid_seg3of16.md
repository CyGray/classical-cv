# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 98.89% | 100.00% |
| **Overall AR** | **86.27%** | **97.62%** | **94.78%** |
| Pooled AR [95% CI] | 84.61% [84.02-85.18] | 97.37% [97.10-97.62] | 94.11% [93.71-94.47] |
| Mean latency | 187.87 ms | 45.74 ms | 7.65 ms |
| Latency median / p95 | 171.50 / 263.05 ms | 44.27 / 62.66 ms | 10.69 / 17.45 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 95.6% | 99.0% | 99.5% | dl_stronger | 55% |
| brightness_down | 72.9% | 99.1% | 97.5% | dl_stronger | 50% |
| contrast_up | 76.9% | 98.9% | 93.3% | dl_stronger | 35% |
| contrast_down | 100.0% | 99.4% | 99.5% | tie | 66% |
| gamma_up | 100.0% | 99.0% | 99.9% | tie | 39% |
| gamma_down | 96.4% | 99.0% | 99.4% | dl_stronger | 44% |
| gaussian_noise | 25.3% | 81.9% | 65.6% | dl_stronger | 68% |
| gaussian_blur | 100.0% | 99.2% | 99.5% | tie | 64% |
| motion_blur | 98.7% | 99.2% | 99.6% | tie | 57% |
| rotation | 70.1% | 98.8% | 83.9% | dl_stronger | 55% |
| zoom | 99.4% | 99.0% | 99.7% | tie | 47% |
| occlusion | 100.0% | 99.0% | 99.9% | tie | 33% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 9 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12369/119/2003/269
- **Recovery rate** = 88.2% [86.8-89.4] (2003/2272)
- **Both-fail ceiling** = 1.8% [1.6-2.1]
- **McNemar** (x=119 vs y=2003): p_exact = 0.0e+00, chi2_cc = 1670.9
- Clean probes (360): w/x/y/z = 356/4/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 64 | 64 | 100% | 0.0% | 8.6e-09 | 1.00 |
| brightness_down | 390 | 383 | 98% | 0.5% | 7.5e-105 | 0.98 |
| contrast_up | 250 | 247 | 99% | 0.3% | 2.0e-61 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.016 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.00098 | n/a |
| gamma_down | 39 | 36 | 92% | 0.3% | 2.5e-05 | 1.00 |
| gaussian_noise | 1076 | 825 | 77% | 17.4% | 9.1e-231 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |
| motion_blur | 14 | 14 | 100% | 0.0% | 0.4 | 1.00 |
| rotation | 430 | 425 | 99% | 0.3% | 5.0e-109 | 1.00 |
| zoom | 9 | 9 | 100% | 0.0% | 0.4 | 0.88 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.00098 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.990**; margin signal: 0.987
- Deployed gate vs 'LBPH wrong': escalates 7600 probes; TPR (wrong probes escalated) = 0.734, FPR (right probes escalated) = 0.475, precision = 0.219
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=921, low_margin=740, ambiguous_band=6
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.734, FPR = 0.470
