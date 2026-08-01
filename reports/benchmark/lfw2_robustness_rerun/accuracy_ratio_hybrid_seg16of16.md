# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (349 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **87.20%** | **98.48%** | **94.83%** |
| Pooled AR [95% CI] | 85.55% [84.97-86.12] | 98.23% [98.00-98.44] | 94.08% [93.68-94.46] |
| Mean latency | 109.48 ms | 21.32 ms | 3.99 ms |
| Latency median / p95 | 108.25 / 131.67 ms | 20.92 / 26.52 ms | 0.59 / 9.41 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 97.3% | 100.0% | 100.0% | dl_stronger | 53% |
| brightness_down | 74.9% | 99.5% | 97.1% | dl_stronger | 48% |
| contrast_up | 81.8% | 100.0% | 94.7% | dl_stronger | 30% |
| contrast_down | 100.0% | 99.9% | 100.0% | tie | 64% |
| gamma_up | 100.0% | 99.8% | 100.0% | tie | 36% |
| gamma_down | 97.8% | 100.0% | 100.0% | dl_stronger | 42% |
| gaussian_noise | 27.7% | 83.1% | 65.7% | dl_stronger | 66% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | tie | 61% |
| motion_blur | 98.5% | 99.9% | 99.6% | tie | 55% |
| rotation | 68.6% | 99.9% | 80.9% | dl_stronger | 48% |
| zoom | 99.9% | 99.8% | 99.9% | tie | 41% |
| occlusion | 100.0% | 99.8% | 100.0% | tie | 25% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14309 | w/x/y/z = 12226/16/1830/237
- **Recovery rate** = 88.5% [87.1-89.8] (1830/2067)
- **Both-fail ceiling** = 1.7% [1.5-1.9]
- **McNemar** (x=16 vs y=1830): p_exact = 0.0e+00, chi2_cc = 1780.6
- Clean probes (349): w/x/y/z = 349/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 37 | 37 | 100% | 0.0% | 1.5e-11 | 1.00 |
| brightness_down | 350 | 345 | 99% | 0.4% | 4.2e-100 | 0.99 |
| contrast_up | 191 | 191 | 100% | 0.0% | 6.4e-58 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| gamma_down | 23 | 23 | 100% | 0.0% | 2.4e-07 | 1.00 |
| gaussian_noise | 1010 | 779 | 77% | 16.5% | 4.8e-224 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 16 | 16 | 100% | 0.0% | 0.00027 | 1.00 |
| rotation | 439 | 438 | 100% | 0.1% | 2.8e-132 | 1.00 |
| zoom | 1 | 1 | 100% | 0.0% | 0.62 | 1.00 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.5 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.995**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 6850 probes; TPR (wrong probes escalated) = 0.693, FPR (right probes escalated) = 0.442, precision = 0.209
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: low_margin=720, quality=706, ambiguous_band=7
- Including clean probes: AUC(d1) = 0.995, gate TPR = 0.693, FPR = 0.436
