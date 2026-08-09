# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.44% | 99.72% |
| **Overall AR** | **87.13%** | **98.10%** | **94.52%** |
| Pooled AR [95% CI] | 85.54% [84.97-86.10] | 97.86% [97.61-98.08] | 93.79% [93.39-94.17] |
| Mean latency | 109.32 ms | 21.28 ms | 4.06 ms |
| Latency median / p95 | 108.10 / 131.71 ms | 20.89 / 26.50 ms | 0.62 / 9.42 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 96.5% | 99.4% | 99.5% | dl_stronger | 53% |
| brightness_down | 74.2% | 99.7% | 97.3% | dl_stronger | 50% |
| contrast_up | 79.2% | 99.8% | 94.4% | dl_stronger | 32% |
| contrast_down | 100.0% | 99.4% | 99.5% | tie | 65% |
| gamma_up | 100.0% | 99.4% | 99.5% | tie | 35% |
| gamma_down | 97.8% | 99.8% | 99.9% | dl_stronger | 44% |
| gaussian_noise | 30.1% | 82.8% | 64.7% | dl_stronger | 64% |
| gaussian_blur | 100.0% | 99.4% | 99.6% | tie | 63% |
| motion_blur | 97.9% | 99.3% | 99.1% | tie | 57% |
| rotation | 70.1% | 99.2% | 81.3% | dl_stronger | 50% |
| zoom | 99.7% | 99.4% | 99.7% | tie | 43% |
| occlusion | 100.0% | 99.5% | 99.7% | tie | 27% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12554/72/1890/244
- **Recovery rate** = 88.6% [87.1-89.8] (1890/2134)
- **Both-fail ceiling** = 1.7% [1.5-1.9]
- **McNemar** (x=72 vs y=1890): p_exact = 0.0e+00, chi2_cc = 1682.7
- Clean probes (360): w/x/y/z = 358/2/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 50 | 50 | 100% | 0.0% | 1.6e-08 | 1.00 |
| brightness_down | 372 | 372 | 100% | 0.0% | 4.1e-103 | 0.99 |
| contrast_up | 225 | 225 | 100% | 0.0% | 2.4e-64 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.016 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| gamma_down | 24 | 24 | 100% | 0.0% | 1.0e-05 | 1.00 |
| gaussian_noise | 1006 | 765 | 76% | 16.7% | 2.6e-216 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| motion_blur | 23 | 23 | 100% | 0.0% | 0.011 | 1.00 |
| rotation | 430 | 427 | 99% | 0.2% | 6.8e-115 | 1.00 |
| zoom | 4 | 4 | 100% | 0.0% | 0.39 | 0.74 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.062 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.995**; margin signal: 0.991
- Deployed gate vs 'LBPH wrong': escalates 7224 probes; TPR (wrong probes escalated) = 0.690, FPR (right probes escalated) = 0.456, precision = 0.204
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=748, low_margin=711, ambiguous_band=13
- Including clean probes: AUC(d1) = 0.995, gate TPR = 0.690, FPR = 0.449
