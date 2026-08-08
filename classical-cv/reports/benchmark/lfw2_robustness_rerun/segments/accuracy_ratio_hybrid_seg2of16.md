# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `data/lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **85.58%** | **98.20%** | **94.43%** |
| Pooled AR [95% CI] | 83.90% [83.30-84.49] | 97.96% [97.72-98.18] | 93.73% [93.32-94.11] |
| Mean latency | 79.55 ms | 16.96 ms | 3.06 ms |
| Latency median / p95 | 74.24 / 109.10 ms | 16.19 / 21.05 ms | 0.46 / 7.86 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 95.9% | 99.7% | 99.7% | dl_stronger | 49% |
| brightness_down | 69.7% | 99.2% | 96.1% | dl_stronger | 49% |
| contrast_up | 73.2% | 99.4% | 92.0% | dl_stronger | 34% |
| contrast_down | 100.0% | 99.6% | 99.6% | tie | 61% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 32% |
| gamma_down | 96.0% | 99.6% | 99.5% | dl_stronger | 42% |
| gaussian_noise | 25.3% | 83.2% | 65.6% | dl_stronger | 67% |
| gaussian_blur | 100.0% | 99.6% | 99.7% | tie | 58% |
| motion_blur | 98.8% | 99.7% | 99.4% | tie | 51% |
| rotation | 68.5% | 99.5% | 82.4% | dl_stronger | 49% |
| zoom | 99.6% | 99.4% | 99.5% | tie | 41% |
| occlusion | 100.0% | 99.7% | 99.7% | tie | 24% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12323/61/2136/240
- **Recovery rate** = 89.9% [88.6-91.0] (2136/2376)
- **Both-fail ceiling** = 1.6% [1.4-1.8]
- **McNemar** (x=61 vs y=2136): p_exact = 0.0e+00, chi2_cc = 1957.9
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 59 | 59 | 100% | 0.0% | 9.0e-13 | 1.00 |
| brightness_down | 437 | 435 | 100% | 0.1% | 7.7e-116 | 0.99 |
| contrast_up | 289 | 289 | 100% | 0.0% | 5.9e-76 | 0.99 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 43 | 43 | 100% | 0.0% | 2.8e-09 | 1.00 |
| gaussian_noise | 1076 | 839 | 78% | 16.5% | 6.0e-242 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| motion_blur | 13 | 13 | 100% | 0.0% | 0.021 | 1.00 |
| rotation | 453 | 452 | 100% | 0.1% | 3.4e-125 | 1.00 |
| zoom | 6 | 6 | 100% | 0.0% | 0.79 | 0.88 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.993**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 6955 probes; TPR (wrong probes escalated) = 0.718, FPR (right probes escalated) = 0.424, precision = 0.245
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=874, low_margin=812, ambiguous_band=19
- Including clean probes: AUC(d1) = 0.994, gate TPR = 0.718, FPR = 0.418
