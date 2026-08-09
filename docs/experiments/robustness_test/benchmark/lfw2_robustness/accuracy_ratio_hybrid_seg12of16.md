# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 99.44% | 99.72% | 99.44% |
| **Overall AR** | **87.13%** | **98.15%** | **94.56%** | **98.18%** |
| Pooled AR [95% CI] | 85.54% [84.97-86.10] | 97.91% [97.66-98.13] | 93.83% [93.43-94.20] | 97.95% [97.71-98.16] |
| Mean latency | 93.41 ms | 19.80 ms | 3.63 ms | 7.11 ms |
| Latency median / p95 | 91.86 / 109.80 ms | 19.46 / 24.58 ms | 0.54 / 8.85 ms | 7.06 / 9.42 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 96.5% | 99.4% | 99.5% | 99.4% | dl_stronger | 53% |
| brightness_down | 74.2% | 99.7% | 97.4% | 99.9% | dl_stronger | 49% |
| contrast_up | 79.2% | 99.8% | 94.2% | 99.8% | dl_stronger | 30% |
| contrast_down | 100.0% | 99.4% | 99.6% | 99.4% | tie | 65% |
| gamma_up | 100.0% | 99.4% | 99.5% | 99.4% | tie | 35% |
| gamma_down | 97.8% | 99.8% | 99.9% | 99.8% | dl_stronger | 44% |
| gaussian_noise | 30.1% | 83.1% | 64.9% | 83.2% | dl_stronger | 61% |
| gaussian_blur | 100.0% | 99.4% | 99.6% | 99.4% | tie | 63% |
| motion_blur | 97.9% | 99.4% | 99.2% | 99.4% | tie | 55% |
| rotation | 70.1% | 99.2% | 81.3% | 99.2% | dl_stronger | 46% |
| zoom | 99.7% | 99.4% | 99.8% | 99.6% | tie | 36% |
| occlusion | 100.0% | 99.5% | 99.7% | 99.5% | tie | 27% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.62 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12557/69/1894/240
- **Recovery rate** = 88.8% [87.3-90.0] (1894/2134)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=69 vs y=1894): p_exact = 0.0e+00, chi2_cc = 1694.8
- Clean probes (360): w/x/y/z = 358/2/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 50 | 50 | 100% | 0.0% | 1.6e-08 | 1.00 |
| brightness_down | 372 | 372 | 100% | 0.0% | 1.1e-104 | 0.99 |
| contrast_up | 225 | 225 | 100% | 0.0% | 2.4e-64 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| gamma_down | 24 | 24 | 100% | 0.0% | 1.0e-05 | 1.00 |
| gaussian_noise | 1006 | 769 | 76% | 16.5% | 1.7e-217 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| motion_blur | 23 | 23 | 100% | 0.0% | 0.0052 | 1.00 |
| rotation | 430 | 427 | 99% | 0.2% | 6.8e-115 | 1.00 |
| zoom | 4 | 4 | 100% | 0.0% | 0.39 | 0.74 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.062 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.995**; margin signal: 0.991
- Deployed gate vs 'LBPH wrong': escalates 6972 probes; TPR (wrong probes escalated) = 0.689, FPR (right probes escalated) = 0.436, precision = 0.211
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=748, low_margin=713, ambiguous_band=9
- Including clean probes: AUC(d1) = 0.995, gate TPR = 0.689, FPR = 0.430
