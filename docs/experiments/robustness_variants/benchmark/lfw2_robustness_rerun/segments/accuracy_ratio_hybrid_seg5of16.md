# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **87.20%** | **98.44%** | **94.65%** |
| Pooled AR [95% CI] | 85.60% [85.03-86.16] | 98.21% [97.98-98.41] | 93.92% [93.53-94.30] |
| Mean latency | 187.36 ms | 46.20 ms | 7.03 ms |
| Latency median / p95 | 170.41 / 262.12 ms | 44.46 / 63.19 ms | 0.67 / 17.28 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 97.6% | 99.9% | 99.9% | dl_stronger | 53% |
| brightness_down | 74.0% | 99.5% | 96.8% | dl_stronger | 48% |
| contrast_up | 81.2% | 99.8% | 93.6% | dl_stronger | 27% |
| contrast_down | 100.0% | 99.9% | 99.9% | tie | 62% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 34% |
| gamma_down | 96.9% | 99.7% | 100.0% | dl_stronger | 41% |
| gaussian_noise | 29.4% | 84.0% | 65.2% | dl_stronger | 62% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 60% |
| motion_blur | 97.9% | 99.7% | 99.4% | tie | 53% |
| rotation | 69.8% | 99.9% | 81.9% | dl_stronger | 49% |
| zoom | 99.7% | 99.7% | 99.8% | tie | 41% |
| occlusion | 100.0% | 99.7% | 99.7% | tie | 25% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12600/35/1896/229
- **Recovery rate** = 89.2% [87.8-90.5] (1896/2125)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=35 vs y=1896): p_exact = 0.0e+00, chi2_cc = 1791.6
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 34 | 34 | 100% | 0.0% | 1.9e-08 | 1.00 |
| brightness_down | 375 | 373 | 99% | 0.1% | 2.1e-103 | 0.98 |
| contrast_up | 203 | 203 | 100% | 0.0% | 8.2e-58 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 33 | 33 | 100% | 0.0% | 2.3e-07 | 1.00 |
| gaussian_noise | 1017 | 792 | 78% | 15.6% | 4.3e-226 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 23 | 23 | 100% | 0.0% | 8.8e-05 | 1.00 |
| rotation | 435 | 433 | 100% | 0.1% | 9.0e-131 | 1.00 |
| zoom | 5 | 5 | 100% | 0.0% | 1 | 0.88 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.991**; margin signal: 0.985
- Deployed gate vs 'LBPH wrong': escalates 6900 probes; TPR (wrong probes escalated) = 0.680, FPR (right probes escalated) = 0.432, precision = 0.210
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=732, low_margin=708, ambiguous_band=6
- Including clean probes: AUC(d1) = 0.991, gate TPR = 0.680, FPR = 0.426
