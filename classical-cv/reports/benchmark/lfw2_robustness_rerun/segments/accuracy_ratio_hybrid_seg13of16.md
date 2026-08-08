# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 100.00% |
| **Overall AR** | **86.79%** | **98.05%** | **94.36%** |
| Pooled AR [95% CI] | 85.14% [84.55-85.70] | 97.79% [97.54-98.02] | 93.62% [93.22-94.01] |
| Mean latency | 109.10 ms | 21.26 ms | 3.79 ms |
| Latency median / p95 | 107.86 / 131.37 ms | 20.83 / 26.59 ms | 0.54 / 9.32 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 97.6% | 99.6% | 99.8% | dl_stronger | 51% |
| brightness_down | 72.2% | 99.0% | 96.7% | dl_stronger | 46% |
| contrast_up | 78.9% | 99.3% | 91.9% | dl_stronger | 28% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 61% |
| gamma_up | 100.0% | 99.7% | 99.9% | tie | 31% |
| gamma_down | 97.5% | 99.4% | 100.0% | tie | 40% |
| gaussian_noise | 28.9% | 81.9% | 64.1% | dl_stronger | 63% |
| gaussian_blur | 100.0% | 99.6% | 99.7% | tie | 58% |
| motion_blur | 98.9% | 99.4% | 99.2% | tie | 50% |
| rotation | 67.8% | 99.7% | 81.6% | dl_stronger | 49% |
| zoom | 99.7% | 99.5% | 99.7% | tie | 40% |
| occlusion | 100.0% | 99.6% | 100.0% | tie | 24% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gaussian_noise, rotation
- Ties: 7 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12507/59/1927/267
- **Recovery rate** = 87.8% [86.4-89.1] (1927/2194)
- **Both-fail ceiling** = 1.8% [1.6-2.0]
- **McNemar** (x=59 vs y=1927): p_exact = 0.0e+00, chi2_cc = 1755.1
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 35 | 35 | 100% | 0.0% | 4.9e-06 | 1.00 |
| brightness_down | 400 | 394 | 98% | 0.4% | 3.1e-105 | 0.99 |
| contrast_up | 228 | 225 | 99% | 0.3% | 6.1e-60 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 27 | 27 | 100% | 0.0% | 0.00032 | 1.00 |
| gaussian_noise | 1024 | 766 | 75% | 17.9% | 4.9e-224 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| motion_blur | 12 | 12 | 100% | 0.0% | 0.24 | 1.00 |
| rotation | 463 | 463 | 100% | 0.0% | 1.0e-131 | 1.00 |
| zoom | 5 | 5 | 100% | 0.0% | 0.77 | 0.97 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.12 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.995**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 6721 probes; TPR (wrong probes escalated) = 0.683, FPR (right probes escalated) = 0.416, precision = 0.223
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=746, low_margin=744, ambiguous_band=9
- Including clean probes: AUC(d1) = 0.995, gate TPR = 0.683, FPR = 0.409
