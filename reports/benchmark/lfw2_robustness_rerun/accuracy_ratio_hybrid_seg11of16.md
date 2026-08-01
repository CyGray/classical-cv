# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **86.82%** | **98.45%** | **94.79%** |
| Pooled AR [95% CI] | 85.15% [84.57-85.71] | 98.19% [97.96-98.39] | 94.06% [93.67-94.43] |
| Mean latency | 186.98 ms | 45.88 ms | 7.42 ms |
| Latency median / p95 | 169.79 / 261.92 ms | 44.21 / 62.95 ms | 3.01 / 17.34 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 96.2% | 100.0% | 100.0% | dl_stronger | 55% |
| brightness_down | 75.5% | 99.9% | 97.6% | dl_stronger | 48% |
| contrast_up | 79.7% | 100.0% | 93.9% | dl_stronger | 34% |
| contrast_down | 100.0% | 100.0% | 100.0% | tie | 64% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 39% |
| gamma_down | 98.0% | 100.0% | 99.9% | dl_stronger | 43% |
| gaussian_noise | 26.9% | 81.7% | 64.3% | dl_stronger | 66% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | tie | 63% |
| motion_blur | 98.4% | 99.8% | 99.6% | tie | 56% |
| rotation | 67.6% | 100.0% | 82.4% | dl_stronger | 51% |
| zoom | 99.5% | 99.9% | 99.7% | tie | 45% |
| occlusion | 100.0% | 100.0% | 100.0% | tie | 30% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12558/10/1935/257
- **Recovery rate** = 88.3% [86.9-89.6] (1935/2192)
- **Both-fail ceiling** = 1.7% [1.5-2.0]
- **McNemar** (x=10 vs y=1935): p_exact = 0.0e+00, chi2_cc = 1903.2
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 54 | 54 | 100% | 0.0% | 1.1e-16 | 1.00 |
| brightness_down | 353 | 353 | 100% | 0.0% | 1.9e-104 | 0.98 |
| contrast_up | 219 | 219 | 100% | 0.0% | 2.4e-66 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 22 | 22 | 100% | 0.0% | 4.8e-07 | 1.00 |
| gaussian_noise | 1053 | 796 | 76% | 17.8% | 2.7e-227 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 17 | 17 | 100% | 0.0% | 0.00073 | 1.00 |
| rotation | 467 | 467 | 100% | 0.0% | 5.2e-141 | 1.00 |
| zoom | 7 | 7 | 100% | 0.0% | 0.07 | 0.90 |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.991**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 7368 probes; TPR (wrong probes escalated) = 0.707, FPR (right probes escalated) = 0.463, precision = 0.210
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=827, low_margin=715, ambiguous_band=8
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.707, FPR = 0.458
