# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **86.82%** | **98.53%** | **94.83%** | **98.53%** |
| Pooled AR [95% CI] | 85.15% [84.57-85.71] | 98.28% [98.06-98.48] | 94.11% [93.72-94.48] | 98.29% [98.06-98.48] |
| Mean latency | 93.58 ms | 19.63 ms | 3.71 ms | 7.10 ms |
| Latency median / p95 | 92.11 / 110.05 ms | 19.26 / 24.34 ms | 0.57 / 8.89 ms | 7.04 / 9.43 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 96.2% | 100.0% | 100.0% | 100.0% | dl_stronger | 55% |
| brightness_down | 75.5% | 99.9% | 97.6% | 99.9% | dl_stronger | 48% |
| contrast_up | 79.7% | 100.0% | 93.7% | 100.0% | dl_stronger | 33% |
| contrast_down | 100.0% | 100.0% | 100.0% | 100.0% | tie | 64% |
| gamma_up | 100.0% | 100.0% | 100.0% | 100.0% | tie | 39% |
| gamma_down | 98.0% | 100.0% | 99.8% | 100.0% | dl_stronger | 43% |
| gaussian_noise | 26.9% | 82.6% | 65.1% | 82.7% | dl_stronger | 63% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | 100.0% | tie | 63% |
| motion_blur | 98.4% | 99.8% | 99.6% | 99.8% | tie | 55% |
| rotation | 67.6% | 100.0% | 82.4% | 100.0% | dl_stronger | 47% |
| zoom | 99.5% | 99.9% | 99.7% | 99.9% | tie | 38% |
| occlusion | 100.0% | 100.0% | 100.0% | 100.0% | tie | 30% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.70 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12559/9/1947/245
- **Recovery rate** = 88.8% [87.4-90.1] (1947/2192)
- **Both-fail ceiling** = 1.7% [1.5-1.9]
- **McNemar** (x=9 vs y=1947): p_exact = 0.0e+00, chi2_cc = 1918.2
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 54 | 54 | 100% | 0.0% | 1.1e-16 | 1.00 |
| brightness_down | 353 | 353 | 100% | 0.0% | 1.9e-104 | 0.98 |
| contrast_up | 219 | 219 | 100% | 0.0% | 2.4e-66 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 22 | 22 | 100% | 0.0% | 4.8e-07 | 1.00 |
| gaussian_noise | 1053 | 808 | 77% | 17.0% | 1.1e-232 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 17 | 17 | 100% | 0.0% | 0.00073 | 1.00 |
| rotation | 467 | 467 | 100% | 0.0% | 5.2e-141 | 1.00 |
| zoom | 7 | 7 | 100% | 0.0% | 0.07 | 0.90 |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.991**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 7150 probes; TPR (wrong probes escalated) = 0.706, FPR (right probes escalated) = 0.446, precision = 0.216
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=827, low_margin=716, ambiguous_band=4
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.706, FPR = 0.441
