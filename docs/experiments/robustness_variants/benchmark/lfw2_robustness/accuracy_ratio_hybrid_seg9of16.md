# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 99.17% | 99.72% | 99.17% |
| **Overall AR** | **86.40%** | **97.82%** | **94.47%** | **97.86%** |
| Pooled AR [95% CI] | 84.76% [84.17-85.33] | 97.60% [97.34-97.84] | 93.77% [93.37-94.15] | 97.64% [97.38-97.87] |
| Mean latency | 93.64 ms | 19.73 ms | 3.66 ms | 7.10 ms |
| Latency median / p95 | 91.99 / 110.43 ms | 19.37 / 24.64 ms | 0.54 / 8.87 ms | 7.04 / 9.37 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 96.4% | 98.8% | 99.3% | 98.8% | dl_stronger | 52% |
| brightness_down | 70.7% | 98.9% | 95.6% | 99.0% | dl_stronger | 49% |
| contrast_up | 76.7% | 99.4% | 93.0% | 99.4% | dl_stronger | 30% |
| contrast_down | 100.0% | 99.0% | 99.6% | 99.1% | tie | 65% |
| gamma_up | 100.0% | 99.1% | 99.7% | 99.1% | tie | 33% |
| gamma_down | 96.8% | 99.4% | 99.2% | 99.4% | dl_stronger | 45% |
| gaussian_noise | 27.2% | 84.1% | 66.7% | 84.2% | dl_stronger | 63% |
| gaussian_blur | 100.0% | 99.1% | 99.5% | 99.2% | tie | 63% |
| motion_blur | 98.7% | 99.1% | 99.4% | 99.2% | tie | 55% |
| rotation | 70.6% | 99.2% | 82.6% | 99.2% | dl_stronger | 48% |
| zoom | 99.7% | 99.1% | 99.3% | 99.1% | tie | 38% |
| occlusion | 100.0% | 98.9% | 99.6% | 99.0% | tie | 29% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.40 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12397/113/2009/241
- **Recovery rate** = 89.3% [87.9-90.5] (2009/2250)
- **Both-fail ceiling** = 1.6% [1.4-1.9]
- **McNemar** (x=113 vs y=2009): p_exact = 0.0e+00, chi2_cc = 1692.3
- Clean probes (360): w/x/y/z = 357/3/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 52 | 52 | 100% | 0.0% | 2.9e-05 | 1.00 |
| brightness_down | 422 | 412 | 98% | 0.7% | 2.1e-113 | 0.99 |
| contrast_up | 252 | 249 | 99% | 0.3% | 2.3e-68 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.00098 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.002 | n/a |
| gamma_down | 35 | 35 | 100% | 0.0% | 1.5e-05 | 0.99 |
| gaussian_noise | 1048 | 824 | 79% | 15.6% | 1.8e-237 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.002 | n/a |
| motion_blur | 14 | 14 | 100% | 0.0% | 0.54 | 1.00 |
| rotation | 423 | 419 | 99% | 0.3% | 1.5e-112 | 1.00 |
| zoom | 4 | 4 | 100% | 0.0% | 0.049 | 0.79 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.00049 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.991**; margin signal: 0.987
- Deployed gate vs 'LBPH wrong': escalates 7066 probes; TPR (wrong probes escalated) = 0.706, FPR (right probes escalated) = 0.438, precision = 0.225
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=832, low_margin=746, ambiguous_band=10
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.706, FPR = 0.433
