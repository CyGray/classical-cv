# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.17% | 100.00% |
| **Overall AR** | **86.93%** | **97.74%** | **94.72%** |
| Pooled AR [95% CI] | 85.29% [84.71-85.85] | 97.49% [97.23-97.73] | 94.01% [93.62-94.38] |
| Mean latency | 187.83 ms | 45.81 ms | 7.26 ms |
| Latency median / p95 | 171.14 / 262.52 ms | 44.13 / 62.85 ms | 0.71 / 17.34 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 96.6% | 99.4% | 99.7% | dl_stronger | 52% |
| brightness_down | 73.2% | 98.5% | 96.9% | dl_stronger | 48% |
| contrast_up | 79.0% | 99.1% | 94.4% | dl_stronger | 32% |
| contrast_down | 100.0% | 99.3% | 99.5% | tie | 66% |
| gamma_up | 100.0% | 99.2% | 99.8% | tie | 34% |
| gamma_down | 98.1% | 99.2% | 99.7% | tie | 42% |
| gaussian_noise | 29.1% | 82.1% | 65.7% | dl_stronger | 65% |
| gaussian_blur | 100.0% | 99.3% | 99.4% | tie | 64% |
| motion_blur | 98.5% | 99.2% | 99.4% | tie | 55% |
| rotation | 68.9% | 99.3% | 82.5% | dl_stronger | 51% |
| zoom | 99.8% | 99.3% | 99.6% | tie | 44% |
| occlusion | 100.0% | 99.2% | 100.0% | tie | 26% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gaussian_noise, rotation
- Ties: 7 modifications
- Cascade within 2 pts of the better engine on 9 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12478/111/1912/259
- **Recovery rate** = 88.1% [86.6-89.4] (1912/2171)
- **Both-fail ceiling** = 1.8% [1.6-2.0]
- **McNemar** (x=111 vs y=1912): p_exact = 0.0e+00, chi2_cc = 1601.6
- Clean probes (360): w/x/y/z = 357/3/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 49 | 49 | 100% | 0.0% | 9.0e-08 | 1.00 |
| brightness_down | 386 | 379 | 98% | 0.5% | 2.0e-93 | 0.99 |
| contrast_up | 227 | 226 | 100% | 0.1% | 1.9e-55 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.0078 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |
| gamma_down | 21 | 21 | 100% | 0.0% | 0.043 | 1.00 |
| gaussian_noise | 1021 | 775 | 76% | 17.1% | 2.7e-211 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.0078 | n/a |
| motion_blur | 16 | 16 | 100% | 0.0% | 0.23 | 1.00 |
| rotation | 448 | 443 | 99% | 0.3% | 4.1e-124 | 1.00 |
| zoom | 3 | 3 | 100% | 0.0% | 0.092 | 0.95 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.992**; margin signal: 0.989
- Deployed gate vs 'LBPH wrong': escalates 7187 probes; TPR (wrong probes escalated) = 0.714, FPR (right probes escalated) = 0.448, precision = 0.216
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=843, low_margin=693, ambiguous_band=14
- Including clean probes: AUC(d1) = 0.993, gate TPR = 0.714, FPR = 0.442
