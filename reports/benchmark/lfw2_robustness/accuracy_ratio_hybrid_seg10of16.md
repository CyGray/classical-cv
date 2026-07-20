# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 99.17% | 100.00% | 99.17% |
| **Overall AR** | **86.93%** | **97.76%** | **94.73%** | **97.86%** |
| Pooled AR [95% CI] | 85.29% [84.71-85.85] | 97.51% [97.25-97.75] | 94.02% [93.63-94.40] | 97.62% [97.36-97.86] |
| Mean latency | 93.60 ms | 19.72 ms | 3.60 ms | 7.09 ms |
| Latency median / p95 | 92.09 / 110.24 ms | 19.40 / 24.53 ms | 0.51 / 8.85 ms | 7.03 / 9.43 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 96.6% | 99.4% | 99.7% | 99.4% | dl_stronger | 52% |
| brightness_down | 73.2% | 98.5% | 96.9% | 98.8% | dl_stronger | 47% |
| contrast_up | 79.0% | 99.1% | 94.2% | 99.3% | dl_stronger | 31% |
| contrast_down | 100.0% | 99.3% | 99.5% | 99.3% | tie | 66% |
| gamma_up | 100.0% | 99.2% | 99.8% | 99.2% | tie | 34% |
| gamma_down | 98.1% | 99.2% | 99.7% | 99.4% | tie | 42% |
| gaussian_noise | 29.1% | 82.3% | 65.9% | 82.4% | dl_stronger | 62% |
| gaussian_blur | 100.0% | 99.3% | 99.4% | 99.3% | tie | 64% |
| motion_blur | 98.5% | 99.2% | 99.4% | 99.3% | tie | 54% |
| rotation | 68.9% | 99.3% | 82.5% | 99.4% | dl_stronger | 47% |
| zoom | 99.8% | 99.3% | 99.7% | 99.4% | tie | 37% |
| occlusion | 100.0% | 99.2% | 100.0% | 99.3% | tie | 26% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gaussian_noise, rotation
- Ties: 7 modifications
- Cascade within 2 pts of the better engine on 9 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.13 pts overall, within tolerance on 9 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12478/111/1915/256
- **Recovery rate** = 88.2% [86.8-89.5] (1915/2171)
- **Both-fail ceiling** = 1.7% [1.5-2.0]
- **McNemar** (x=111 vs y=1915): p_exact = 0.0e+00, chi2_cc = 1604.5
- Clean probes (360): w/x/y/z = 357/3/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 49 | 49 | 100% | 0.0% | 9.0e-08 | 1.00 |
| brightness_down | 386 | 379 | 98% | 0.5% | 2.0e-93 | 0.99 |
| contrast_up | 227 | 226 | 100% | 0.1% | 1.9e-55 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.0078 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |
| gamma_down | 21 | 21 | 100% | 0.0% | 0.043 | 1.00 |
| gaussian_noise | 1021 | 778 | 76% | 16.9% | 3.5e-212 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.0078 | n/a |
| motion_blur | 16 | 16 | 100% | 0.0% | 0.23 | 1.00 |
| rotation | 448 | 443 | 99% | 0.3% | 4.1e-124 | 1.00 |
| zoom | 3 | 3 | 100% | 0.0% | 0.092 | 0.95 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.992**; margin signal: 0.989
- Deployed gate vs 'LBPH wrong': escalates 6939 probes; TPR (wrong probes escalated) = 0.713, FPR (right probes escalated) = 0.428, precision = 0.223
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=843, low_margin=693, ambiguous_band=11
- Including clean probes: AUC(d1) = 0.993, gate TPR = 0.713, FPR = 0.423
