# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **86.78%** | **98.48%** | **94.77%** |
| Pooled AR [95% CI] | 85.16% [84.57-85.72] | 98.24% [98.01-98.44] | 94.04% [93.65-94.42] |
| Mean latency | 188.14 ms | 45.81 ms | 7.02 ms |
| Latency median / p95 | 171.92 / 263.05 ms | 44.17 / 62.62 ms | 0.64 / 17.26 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 95.3% | 99.9% | 99.9% | dl_stronger | 54% |
| brightness_down | 75.1% | 99.7% | 97.4% | dl_stronger | 45% |
| contrast_up | 78.0% | 100.0% | 93.5% | dl_stronger | 30% |
| contrast_down | 100.0% | 99.9% | 99.9% | tie | 64% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 32% |
| gamma_down | 97.8% | 99.8% | 99.8% | dl_stronger | 40% |
| gaussian_noise | 27.8% | 83.6% | 65.3% | dl_stronger | 65% |
| gaussian_blur | 99.9% | 99.8% | 99.8% | tie | 61% |
| motion_blur | 98.5% | 100.0% | 99.9% | tie | 54% |
| rotation | 69.1% | 99.7% | 81.8% | dl_stronger | 49% |
| zoom | 99.8% | 99.5% | 99.7% | tie | 40% |
| occlusion | 100.0% | 99.9% | 100.0% | tie | 25% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12542/27/1958/233
- **Recovery rate** = 89.4% [88.0-90.6] (1958/2191)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=27 vs y=1958): p_exact = 0.0e+00, chi2_cc = 1876.5
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 67 | 67 | 100% | 0.0% | 4.7e-19 | 1.00 |
| brightness_down | 358 | 357 | 100% | 0.1% | 3.0e-100 | 0.98 |
| contrast_up | 238 | 238 | 100% | 0.0% | 4.5e-72 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 24 | 24 | 100% | 0.0% | 1.0e-05 | 0.99 |
| gaussian_noise | 1039 | 811 | 78% | 15.8% | 2.8e-228 | 1.00 |
| gaussian_blur | 1 | 0 | 0% | 0.1% | 1 | 0.73 |
| motion_blur | 16 | 16 | 100% | 0.0% | 3.1e-05 | 0.99 |
| rotation | 445 | 442 | 99% | 0.2% | 4.3e-129 | 1.00 |
| zoom | 3 | 3 | 100% | 0.0% | 0.34 | 0.80 |
| occlusion | 0 | 0 | nan% | 0.0% | 1 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.992**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 6940 probes; TPR (wrong probes escalated) = 0.698, FPR (right probes escalated) = 0.430, precision = 0.220
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=794, low_margin=731, ambiguous_band=5
- Including clean probes: AUC(d1) = 0.992, gate TPR = 0.698, FPR = 0.424
