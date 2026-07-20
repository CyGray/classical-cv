# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 99.72% |
| **Overall AR** | **98.03%** | **97.01%** | **97.01%** |
| Pooled AR [95% CI] | 97.71% [97.46-97.94] | 96.57% [96.27-96.85] | 96.58% [96.27-96.86] |
| Mean latency | 139.98 ms | 34.13 ms | 0.66 ms |
| Latency median / p95 | 138.12 / 164.79 ms | 31.79 / 56.64 ms | 0.46 / 1.93 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 99.9% | 99.7% | 99.7% | tie | 99% |
| brightness_down | 97.4% | 99.5% | 99.5% | dl_stronger | 98% |
| contrast_up | 99.4% | 99.5% | 99.4% | tie | 88% |
| contrast_down | 100.0% | 99.5% | 99.5% | tie | 100% |
| gamma_up | 100.0% | 99.7% | 99.7% | tie | 98% |
| gamma_down | 100.0% | 99.5% | 99.5% | tie | 98% |
| gaussian_noise | 79.9% | 69.1% | 69.2% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 99.6% | 99.6% | tie | 100% |
| motion_blur | 99.9% | 99.4% | 99.4% | tie | 99% |
| rotation | 99.9% | 99.4% | 99.4% | tie | 100% |
| zoom | 100.0% | 99.6% | 99.6% | tie | 99% |
| occlusion | 100.0% | 99.4% | 99.4% | tie | 97% |

## Complementarity summary

- CV stronger (> 2 pts): gaussian_noise
- DL stronger (> 2 pts): brightness_down
- Ties: 10 modifications
- Cascade within 2 pts of the better engine on 11 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 14140/282/114/224
- **Recovery rate** = 33.7% [28.9-38.9] (114/338)
- **Both-fail ceiling** = 1.5% [1.3-1.7]
- **McNemar** (x=282 vs y=114): p_exact = 1.6e-17, chi2_cc = 70.4
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 1 | 1 | 100% | 0.0% | 0.22 | 1.00 |
| brightness_down | 38 | 37 | 97% | 0.1% | 1.6e-06 | 1.00 |
| contrast_up | 6 | 6 | 100% | 0.0% | 1 | 1.00 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 0 | 0 | nan% | 0.0% | 0.062 | n/a |
| gaussian_noise | 290 | 67 | 23% | 15.5% | 1.5e-20 | 0.96 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.12 | n/a |
| motion_blur | 1 | 1 | 100% | 0.0% | 0.12 | 1.00 |
| rotation | 2 | 2 | 100% | 0.0% | 0.065 | 0.62 |
| zoom | 0 | 0 | nan% | 0.0% | 0.031 | n/a |
| occlusion | 0 | 0 | nan% | 0.0% | 0.031 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.996**; margin signal: 0.987
- Deployed gate vs 'LBPH wrong': escalates 14192 probes; TPR (wrong probes escalated) = 0.997, FPR (right probes escalated) = 0.961, precision = 0.024
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=337
- Including clean probes: AUC(d1) = 0.996, gate TPR = 0.997, FPR = 0.961
