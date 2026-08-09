# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 100.00% |
| **Overall AR** | **86.38%** | **98.23%** | **94.86%** |
| Pooled AR [95% CI] | 84.74% [84.15-85.31] | 97.95% [97.71-98.16] | 94.14% [93.75-94.51] |
| Mean latency | 186.83 ms | 46.16 ms | 7.57 ms |
| Latency median / p95 | 170.12 / 261.75 ms | 44.56 / 63.20 ms | 10.10 / 17.46 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 94.7% | 100.0% | 99.9% | dl_stronger | 57% |
| brightness_down | 74.3% | 99.6% | 96.7% | dl_stronger | 47% |
| contrast_up | 76.2% | 99.7% | 93.9% | dl_stronger | 34% |
| contrast_down | 100.0% | 99.9% | 99.9% | tie | 65% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 38% |
| gamma_down | 96.8% | 99.9% | 99.9% | dl_stronger | 43% |
| gaussian_noise | 28.1% | 80.4% | 64.7% | dl_stronger | 68% |
| gaussian_blur | 100.0% | 99.7% | 99.9% | tie | 64% |
| motion_blur | 99.0% | 99.9% | 99.7% | tie | 56% |
| rotation | 67.8% | 99.8% | 84.0% | dl_stronger | 54% |
| zoom | 99.7% | 99.8% | 99.8% | tie | 46% |
| occlusion | 100.0% | 100.0% | 100.0% | tie | 32% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12481/26/1976/277
- **Recovery rate** = 87.7% [86.3-89.0] (1976/2253)
- **Both-fail ceiling** = 1.9% [1.7-2.1]
- **McNemar** (x=26 vs y=1976): p_exact = 0.0e+00, chi2_cc = 1897.4
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 76 | 76 | 100% | 0.0% | 2.6e-23 | 1.00 |
| brightness_down | 370 | 369 | 100% | 0.1% | 3.1e-102 | 0.98 |
| contrast_up | 257 | 257 | 100% | 0.0% | 3.2e-72 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 35 | 35 | 100% | 0.0% | 1.1e-09 | 1.00 |
| gaussian_noise | 1036 | 761 | 73% | 19.1% | 4.0e-215 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 11 | 11 | 100% | 0.0% | 0.0063 | 1.00 |
| rotation | 464 | 463 | 100% | 0.1% | 2.3e-135 | 1.00 |
| zoom | 4 | 4 | 100% | 0.0% | 1 | 0.96 |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.993**; margin signal: 0.989
- Deployed gate vs 'LBPH wrong': escalates 7482 probes; TPR (wrong probes escalated) = 0.728, FPR (right probes escalated) = 0.467, precision = 0.219
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=937, low_margin=699, ambiguous_band=5
- Including clean probes: AUC(d1) = 0.993, gate TPR = 0.728, FPR = 0.462
