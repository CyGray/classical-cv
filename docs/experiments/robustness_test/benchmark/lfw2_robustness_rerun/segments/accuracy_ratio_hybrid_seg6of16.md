# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 100.00% | 100.00% |
| **Overall AR** | **86.64%** | **98.30%** | **94.51%** |
| Pooled AR [95% CI] | 84.99% [84.41-85.56] | 98.03% [97.79-98.24] | 93.74% [93.34-94.12] |
| Mean latency | 186.87 ms | 45.88 ms | 7.05 ms |
| Latency median / p95 | 169.81 / 262.01 ms | 44.25 / 62.32 ms | 0.65 / 17.27 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 97.1% | 99.9% | 100.0% | dl_stronger | 52% |
| brightness_down | 73.8% | 99.9% | 97.2% | dl_stronger | 47% |
| contrast_up | 78.5% | 99.8% | 93.6% | dl_stronger | 31% |
| contrast_down | 100.0% | 99.8% | 100.0% | tie | 62% |
| gamma_up | 100.0% | 100.0% | 100.0% | tie | 33% |
| gamma_down | 96.9% | 99.9% | 100.0% | dl_stronger | 40% |
| gaussian_noise | 27.6% | 81.2% | 62.4% | dl_stronger | 66% |
| gaussian_blur | 100.0% | 100.0% | 100.0% | tie | 60% |
| motion_blur | 98.3% | 99.8% | 99.4% | tie | 52% |
| rotation | 67.8% | 99.6% | 81.7% | dl_stronger | 50% |
| zoom | 99.6% | 99.7% | 99.8% | tie | 43% |
| occlusion | 100.0% | 100.0% | 100.0% | tie | 25% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12526/19/1943/272
- **Recovery rate** = 87.7% [86.3-89.0] (1943/2215)
- **Both-fail ceiling** = 1.8% [1.6-2.1]
- **McNemar** (x=19 vs y=1943): p_exact = 0.0e+00, chi2_cc = 1884.8
- Clean probes (360): w/x/y/z = 360/0/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 42 | 42 | 100% | 0.0% | 1.0e-11 | 1.00 |
| brightness_down | 378 | 376 | 99% | 0.1% | 1.3e-113 | 0.98 |
| contrast_up | 232 | 232 | 100% | 0.0% | 2.0e-66 | 0.98 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.5 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | n/a | n/a |
| gamma_down | 33 | 33 | 100% | 0.0% | 4.1e-09 | 1.00 |
| gaussian_noise | 1043 | 776 | 74% | 18.5% | 4.8e-225 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | n/a | n/a |
| motion_blur | 18 | 18 | 100% | 0.0% | 0.0004 | 1.00 |
| rotation | 463 | 460 | 99% | 0.2% | 1.4e-132 | 1.00 |
| zoom | 6 | 6 | 100% | 0.0% | 0.75 | 0.90 |
| occlusion | 0 | 0 | nan% | 0.0% | n/a | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.992**; margin signal: 0.988
- Deployed gate vs 'LBPH wrong': escalates 6971 probes; TPR (wrong probes escalated) = 0.698, FPR (right probes escalated) = 0.432, precision = 0.222
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: low_margin=777, quality=757, ambiguous_band=13
- Including clean probes: AUC(d1) = 0.992, gate TPR = 0.698, FPR = 0.427
