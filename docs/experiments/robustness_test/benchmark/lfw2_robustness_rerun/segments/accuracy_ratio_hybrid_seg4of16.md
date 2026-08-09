# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 100.00% |
| **Overall AR** | **87.30%** | **98.48%** | **94.86%** |
| Pooled AR [95% CI] | 85.70% [85.12-86.25] | 98.26% [98.03-98.46] | 94.15% [93.76-94.52] |
| Mean latency | 187.86 ms | 45.97 ms | 6.95 ms |
| Latency median / p95 | 171.26 / 262.71 ms | 44.29 / 62.97 ms | 0.63 / 17.22 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 96.8% | 99.7% | 99.9% | dl_stronger | 53% |
| brightness_down | 75.3% | 99.6% | 97.4% | dl_stronger | 46% |
| contrast_up | 80.6% | 99.7% | 94.3% | dl_stronger | 28% |
| contrast_down | 100.0% | 99.8% | 99.8% | tie | 62% |
| gamma_up | 100.0% | 99.7% | 100.0% | tie | 34% |
| gamma_down | 97.6% | 99.7% | 99.7% | dl_stronger | 40% |
| gaussian_noise | 28.7% | 84.7% | 66.0% | dl_stronger | 64% |
| gaussian_blur | 100.0% | 99.9% | 99.9% | tie | 60% |
| motion_blur | 98.6% | 99.7% | 99.4% | tie | 53% |
| rotation | 70.2% | 99.7% | 82.0% | dl_stronger | 48% |
| zoom | 99.8% | 99.8% | 99.9% | tie | 39% |
| occlusion | 100.0% | 99.6% | 100.0% | tie | 23% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12612/37/1891/220
- **Recovery rate** = 89.6% [88.2-90.8] (1891/2111)
- **Both-fail ceiling** = 1.5% [1.3-1.7]
- **McNemar** (x=37 vs y=1891): p_exact = 0.0e+00, chi2_cc = 1780.9
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 46 | 46 | 100% | 0.0% | 4.5e-10 | 1.00 |
| brightness_down | 355 | 354 | 100% | 0.1% | 8.3e-98 | 0.98 |
| contrast_up | 210 | 210 | 100% | 0.0% | 2.4e-58 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 26 | 26 | 100% | 0.0% | 1.5e-05 | 0.99 |
| gaussian_noise | 1027 | 808 | 79% | 15.2% | 9.6e-239 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 1 | n/a |
| motion_blur | 15 | 15 | 100% | 0.0% | 0.0075 | 1.00 |
| rotation | 429 | 429 | 100% | 0.0% | 1.3e-121 | 1.00 |
| zoom | 3 | 3 | 100% | 0.0% | 1 | 0.92 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.12 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.991**; margin signal: 0.987
- Deployed gate vs 'LBPH wrong': escalates 6810 probes; TPR (wrong probes escalated) = 0.690, FPR (right probes escalated) = 0.423, precision = 0.214
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: low_margin=727, quality=718, ambiguous_band=11
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.690, FPR = 0.417
