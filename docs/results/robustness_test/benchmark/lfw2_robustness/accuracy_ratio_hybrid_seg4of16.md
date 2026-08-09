# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 100.00% | 99.72% |
| **Overall AR** | **87.30%** | **98.48%** | **94.87%** | **98.48%** |
| Pooled AR [95% CI] | 85.70% [85.12-86.25] | 98.27% [98.04-98.46] | 94.16% [93.77-94.53] | 98.27% [98.04-98.46] |
| Mean latency | 95.15 ms | 19.67 ms | 3.42 ms | 7.06 ms |
| Latency median / p95 | 93.31 / 113.76 ms | 19.28 / 24.42 ms | 0.47 / 8.77 ms | 6.97 / 9.43 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 96.8% | 99.7% | 99.9% | 99.7% | dl_stronger | 53% |
| brightness_down | 75.3% | 99.6% | 97.4% | 99.6% | dl_stronger | 45% |
| contrast_up | 80.6% | 99.7% | 94.3% | 99.7% | dl_stronger | 27% |
| contrast_down | 100.0% | 99.8% | 99.8% | 99.8% | tie | 62% |
| gamma_up | 100.0% | 99.7% | 100.0% | 99.7% | tie | 34% |
| gamma_down | 97.6% | 99.7% | 99.7% | 99.7% | dl_stronger | 40% |
| gaussian_noise | 28.7% | 84.7% | 66.1% | 84.7% | dl_stronger | 59% |
| gaussian_blur | 100.0% | 99.9% | 99.9% | 99.9% | tie | 60% |
| motion_blur | 98.6% | 99.7% | 99.4% | 99.7% | tie | 52% |
| rotation | 70.2% | 99.7% | 82.0% | 99.7% | dl_stronger | 44% |
| zoom | 99.8% | 99.8% | 99.9% | 99.8% | tie | 32% |
| occlusion | 100.0% | 99.6% | 100.0% | 99.6% | tie | 23% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.61 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12612/37/1892/219
- **Recovery rate** = 89.6% [88.3-90.9] (1892/2111)
- **Both-fail ceiling** = 1.5% [1.3-1.7]
- **McNemar** (x=37 vs y=1892): p_exact = 0.0e+00, chi2_cc = 1781.9
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 46 | 46 | 100% | 0.0% | 4.5e-10 | 1.00 |
| brightness_down | 355 | 354 | 100% | 0.1% | 8.3e-98 | 0.98 |
| contrast_up | 210 | 210 | 100% | 0.0% | 2.4e-58 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 26 | 26 | 100% | 0.0% | 1.5e-05 | 0.99 |
| gaussian_noise | 1027 | 809 | 79% | 15.1% | 4.8e-239 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 1 | n/a |
| motion_blur | 15 | 15 | 100% | 0.0% | 0.0075 | 1.00 |
| rotation | 429 | 429 | 100% | 0.0% | 1.3e-121 | 1.00 |
| zoom | 3 | 3 | 100% | 0.0% | 1 | 0.92 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.12 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.991**; margin signal: 0.987
- Deployed gate vs 'LBPH wrong': escalates 6558 probes; TPR (wrong probes escalated) = 0.690, FPR (right probes escalated) = 0.403, precision = 0.222
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: low_margin=727, quality=718, ambiguous_band=11
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.690, FPR = 0.398
