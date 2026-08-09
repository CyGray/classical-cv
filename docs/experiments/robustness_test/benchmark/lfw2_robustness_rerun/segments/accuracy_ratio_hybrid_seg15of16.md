# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **86.47%** | **98.22%** | **94.65%** |
| Pooled AR [95% CI] | 84.82% [84.23-85.39] | 97.97% [97.73-98.19] | 93.94% [93.55-94.32] |
| Mean latency | 108.77 ms | 21.30 ms | 4.03 ms |
| Latency median / p95 | 107.72 / 131.47 ms | 20.95 / 26.55 ms | 0.60 / 9.44 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 95.6% | 99.9% | 99.9% | dl_stronger | 52% |
| brightness_down | 73.1% | 98.9% | 96.3% | dl_stronger | 49% |
| contrast_up | 77.5% | 99.6% | 92.7% | dl_stronger | 30% |
| contrast_down | 100.0% | 99.5% | 99.6% | tie | 62% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 32% |
| gamma_down | 97.0% | 99.5% | 99.8% | dl_stronger | 43% |
| gaussian_noise | 27.0% | 83.3% | 65.6% | dl_stronger | 66% |
| gaussian_blur | 100.0% | 99.6% | 99.9% | tie | 61% |
| motion_blur | 98.6% | 99.7% | 99.7% | tie | 55% |
| rotation | 69.4% | 99.3% | 82.8% | dl_stronger | 52% |
| zoom | 99.4% | 99.5% | 99.5% | tie | 43% |
| occlusion | 100.0% | 99.7% | 99.9% | tie | 28% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12461/58/2000/241
- **Recovery rate** = 89.2% [87.9-90.5] (2000/2241)
- **Both-fail ceiling** = 1.6% [1.4-1.9]
- **McNemar** (x=58 vs y=2000): p_exact = 0.0e+00, chi2_cc = 1830.7
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 63 | 63 | 100% | 0.0% | 1.2e-16 | 1.00 |
| brightness_down | 387 | 381 | 98% | 0.4% | 8.3e-99 | 0.99 |
| contrast_up | 243 | 243 | 100% | 0.0% | 1.4e-66 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 32 | 32 | 100% | 0.0% | 7.4e-06 | 1.00 |
| gaussian_noise | 1051 | 819 | 78% | 16.1% | 1.2e-230 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| motion_blur | 15 | 15 | 100% | 0.0% | 0.0075 | 1.00 |
| rotation | 441 | 438 | 99% | 0.2% | 1.5e-119 | 1.00 |
| zoom | 9 | 9 | 100% | 0.0% | 0.8 | 0.93 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.993**; margin signal: 0.987
- Deployed gate vs 'LBPH wrong': escalates 7145 probes; TPR (wrong probes escalated) = 0.705, FPR (right probes escalated) = 0.445, precision = 0.221
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=857, low_margin=719, ambiguous_band=4
- Including clean probes: AUC(d1) = 0.993, gate TPR = 0.705, FPR = 0.439
