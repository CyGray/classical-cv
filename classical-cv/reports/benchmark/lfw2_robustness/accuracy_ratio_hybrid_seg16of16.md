# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (349 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---|---:|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **87.20%** | **98.51%** | **94.84%** | **98.52%** |
| Pooled AR [95% CI] | 85.55% [84.97-86.12] | 98.27% [98.04-98.47] | 94.11% [93.71-94.48] | 98.28% [98.05-98.48] |
| Mean latency | 94.94 ms | 20.17 ms | 3.63 ms | 7.28 ms |
| Latency median / p95 | 93.47 / 112.35 ms | 19.80 / 25.38 ms | 0.51 / 9.19 ms | 7.16 / 9.84 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---|---:|---:|---:|---:|---|---:|
| brightness_up | 97.3% | 100.0% | 100.0% | 100.0% | dl_stronger | 53% |
| brightness_down | 74.9% | 99.5% | 97.1% | 99.5% | dl_stronger | 47% |
| contrast_up | 81.8% | 100.0% | 94.5% | 100.0% | dl_stronger | 28% |
| contrast_down | 100.0% | 99.9% | 100.0% | 99.9% | tie | 64% |
| gamma_up | 100.0% | 99.8% | 100.0% | 99.8% | tie | 36% |
| gamma_down | 97.8% | 100.0% | 100.0% | 100.0% | dl_stronger | 42% |
| gaussian_noise | 27.7% | 83.5% | 66.1% | 83.5% | dl_stronger | 63% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | 100.0% | tie | 61% |
| motion_blur | 98.5% | 99.9% | 99.6% | 99.9% | tie | 54% |
| rotation | 68.6% | 99.9% | 80.9% | 99.9% | dl_stronger | 44% |
| zoom | 99.9% | 99.8% | 99.9% | 99.9% | tie | 33% |
| occlusion | 100.0% | 99.8% | 100.0% | 99.8% | tie | 25% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications
- Cascade vs parallel (run-both ceiling): -3.68 pts overall, within tolerance on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14309 | w/x/y/z = 12226/16/1835/232
- **Recovery rate** = 88.8% [87.3-90.1] (1835/2067)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=16 vs y=1835): p_exact = 0.0e+00, chi2_cc = 1785.6
- Clean probes (349): w/x/y/z = 349/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 37 | 37 | 100% | 0.0% | 1.5e-11 | 1.00 |
| brightness_down | 350 | 345 | 99% | 0.4% | 4.2e-100 | 0.99 |
| contrast_up | 191 | 191 | 100% | 0.0% | 6.4e-58 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 1 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| gamma_down | 23 | 23 | 100% | 0.0% | 2.4e-07 | 1.00 |
| gaussian_noise | 1010 | 784 | 78% | 16.2% | 1.6e-225 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 16 | 16 | 100% | 0.0% | 0.00027 | 1.00 |
| rotation | 439 | 438 | 100% | 0.1% | 2.8e-132 | 1.00 |
| zoom | 1 | 1 | 100% | 0.0% | 0.62 | 1.00 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.5 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.995**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 6596 probes; TPR (wrong probes escalated) = 0.692, FPR (right probes escalated) = 0.422, precision = 0.217
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: low_margin=720, quality=706, ambiguous_band=4
- Including clean probes: AUC(d1) = 0.995, gate TPR = 0.692, FPR = 0.416
