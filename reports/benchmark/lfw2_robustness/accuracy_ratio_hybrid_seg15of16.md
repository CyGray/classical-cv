# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.17% | 99.17% |
| **Overall AR** | **97.95%** | **96.63%** | **96.62%** |
| Pooled AR [95% CI] | 97.64% [97.38-97.87] | 96.19% [95.87-96.49] | 96.19% [95.86-96.48] |
| Mean latency | 95.18 ms | 15.99 ms | 0.39 ms |
| Latency median / p95 | 94.66 / 113.58 ms | 15.00 / 22.37 ms | 0.35 / 0.64 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 100.0% | 99.1% | 99.1% | tie | 99% |
| brightness_down | 96.9% | 99.0% | 99.0% | dl_stronger | 99% |
| contrast_up | 98.4% | 99.2% | 99.1% | tie | 88% |
| contrast_down | 100.0% | 99.1% | 99.1% | tie | 100% |
| gamma_up | 100.0% | 99.2% | 99.2% | tie | 99% |
| gamma_down | 100.0% | 99.2% | 99.2% | tie | 98% |
| gaussian_noise | 80.2% | 69.0% | 69.2% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 99.2% | 99.2% | tie | 100% |
| motion_blur | 100.0% | 99.1% | 99.1% | tie | 99% |
| rotation | 99.9% | 99.2% | 99.2% | tie | 100% |
| zoom | 100.0% | 99.0% | 99.0% | tie | 99% |
| occlusion | 100.0% | 99.4% | 99.4% | tie | 98% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14061/351/137/211
- **Recovery rate** = 39.4% [34.4-44.6] (137/348)
- **Both-fail ceiling** = 1.4% [1.3-1.6]
- **McNemar** (x=351 vs y=137): p_exact = 1.1e-22, chi2_cc = 93.0
- Clean probes (360): w/x/y/z = 357/3/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 0 | 0 | nan% | 0.0% | 0.00024 | n/a |
| brightness_down | 45 | 43 | 96% | 0.1% | 3.3e-05 | 1.00 |
| contrast_up | 17 | 17 | 100% | 0.0% | 0.17 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.002 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |
| gaussian_noise | 285 | 76 | 27% | 14.5% | 2.1e-20 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.0039 | n/a |
| motion_blur | 0 | 0 | nan% | 0.0% | 0.002 | n/a |
| rotation | 1 | 1 | 100% | 0.0% | 0.0063 | 1.00 |
| zoom | 0 | 0 | nan% | 0.0% | 6.1e-05 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.016 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.997**; margin signal: 0.986
- Deployed gate vs 'LBPH wrong': escalates 14226 probes; TPR (wrong probes escalated) = 0.991, FPR (right probes escalated) = 0.963, precision = 0.024
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=345
- Including clean probes: AUC(d1) = 0.997, gate TPR = 0.991, FPR = 0.964
