# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% | 99.72% |
| **Overall AR** | **85.58%** | **98.23%** | **94.43%** | **98.30%** |
| Pooled AR [95% CI] | 83.90% [83.30-84.49] | 97.99% [97.75-98.20] | 93.73% [93.33-94.11] | 98.06% [97.83-98.27] |
| Mean latency | 95.02 ms | 19.73 ms | 3.51 ms | 7.11 ms |
| Latency median / p95 | 93.09 / 114.15 ms | 19.36 / 24.55 ms | 0.50 / 8.81 ms | 7.03 / 9.40 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 95.9% | 99.7% | 99.7% | 99.7% | dl_stronger | 49% |
| brightness_down | 69.7% | 99.2% | 96.0% | 99.3% | dl_stronger | 48% |
| contrast_up | 73.2% | 99.4% | 91.9% | 99.6% | dl_stronger | 33% |
| contrast_down | 100.0% | 99.6% | 99.6% | 99.6% | tie | 61% |
| gamma_up | 100.0% | 99.7% | 99.7% | 99.7% | tie | 32% |
| gamma_down | 96.0% | 99.6% | 99.5% | 99.7% | dl_stronger | 42% |
| gaussian_noise | 25.3% | 83.5% | 65.8% | 83.6% | dl_stronger | 64% |
| gaussian_blur | 100.0% | 99.6% | 99.7% | 99.7% | tie | 58% |
| motion_blur | 98.8% | 99.7% | 99.4% | 99.7% | tie | 50% |
| rotation | 68.5% | 99.5% | 82.4% | 99.6% | dl_stronger | 45% |
| zoom | 99.6% | 99.4% | 99.5% | 99.6% | tie | 33% |
| occlusion | 100.0% | 99.7% | 99.7% | 99.7% | tie | 24% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.87 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12324/60/2139/237
- **Recovery rate** = 90.0% [88.8-91.2] (2139/2376)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=60 vs y=2139): p_exact = 0.0e+00, chi2_cc = 1963.7
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 59 | 59 | 100% | 0.0% | 9.0e-13 | 1.00 |
| brightness_down | 437 | 435 | 100% | 0.1% | 7.7e-116 | 0.99 |
| contrast_up | 289 | 289 | 100% | 0.0% | 5.9e-76 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 43 | 43 | 100% | 0.0% | 2.8e-09 | 1.00 |
| gaussian_noise | 1076 | 842 | 78% | 16.2% | 9.1e-245 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| motion_blur | 13 | 13 | 100% | 0.0% | 0.021 | 1.00 |
| rotation | 453 | 452 | 100% | 0.1% | 3.4e-125 | 1.00 |
| zoom | 6 | 6 | 100% | 0.0% | 0.79 | 0.88 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.993**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 6697 probes; TPR (wrong probes escalated) = 0.717, FPR (right probes escalated) = 0.403, precision = 0.254
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=874, low_margin=818, ambiguous_band=11
- Including clean probes: AUC(d1) = 0.994, gate TPR = 0.717, FPR = 0.398
