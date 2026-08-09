# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 100.00% |
| **Overall AR** | **86.84%** | **98.18%** | **94.86%** |
| Pooled AR [95% CI] | 85.21% [84.63-85.77] | 97.95% [97.71-98.16] | 94.16% [93.77-94.53] |
| Mean latency | 187.92 ms | 45.79 ms | 7.23 ms |
| Latency median / p95 | 171.32 / 262.20 ms | 44.20 / 62.76 ms | 0.73 / 17.28 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 95.2% | 99.4% | 99.7% | dl_stronger | 56% |
| brightness_down | 75.1% | 99.4% | 96.9% | dl_stronger | 45% |
| contrast_up | 78.6% | 99.7% | 94.2% | dl_stronger | 32% |
| contrast_down | 100.0% | 99.4% | 99.7% | tie | 64% |
| gamma_up | 100.0% | 99.7% | 100.0% | tie | 37% |
| gamma_down | 97.5% | 99.4% | 99.9% | tie | 39% |
| gaussian_noise | 27.9% | 83.5% | 66.5% | dl_stronger | 66% |
| gaussian_blur | 100.0% | 99.4% | 99.7% | tie | 62% |
| motion_blur | 98.7% | 99.4% | 99.4% | tie | 55% |
| rotation | 69.1% | 99.7% | 82.4% | dl_stronger | 51% |
| zoom | 99.9% | 99.5% | 99.9% | tie | 42% |
| occlusion | 100.0% | 99.5% | 100.0% | tie | 28% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gaussian_noise, rotation
- Ties: 7 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12506/71/1951/232
- **Recovery rate** = 89.4% [88.0-90.6] (1951/2183)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=71 vs y=1951): p_exact = 0.0e+00, chi2_cc = 1746.1
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 69 | 69 | 100% | 0.0% | 1.4e-12 | 1.00 |
| brightness_down | 358 | 357 | 100% | 0.1% | 8.6e-96 | 0.99 |
| contrast_up | 231 | 231 | 100% | 0.0% | 1.5e-64 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 27 | 27 | 100% | 0.0% | 0.00032 | 1.00 |
| gaussian_noise | 1038 | 807 | 78% | 16.0% | 8.5e-229 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.016 | n/a |
| motion_blur | 14 | 14 | 100% | 0.0% | 0.12 | 1.00 |
| rotation | 445 | 445 | 100% | 0.0% | 1.0e-124 | 1.00 |
| zoom | 1 | 1 | 100% | 0.0% | 0.07 | 0.98 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.062 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.994**; margin signal: 0.989
- Deployed gate vs 'LBPH wrong': escalates 7167 probes; TPR (wrong probes escalated) = 0.708, FPR (right probes escalated) = 0.447, precision = 0.216
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=858, low_margin=677, ambiguous_band=11
- Including clean probes: AUC(d1) = 0.994, gate TPR = 0.708, FPR = 0.441
