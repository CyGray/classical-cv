# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (360 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

Same probes as `accuracy_ratio.py` (identical per-image seeds). AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean acceptance | 100.00% | 99.72% | 100.00% |
| **Overall AR** | **85.80%** | **98.20%** | **94.63%** |
| Pooled AR [95% CI] | 84.15% [83.55-84.73] | 97.94% [97.70-98.16] | 93.94% [93.54-94.31] |
| Mean latency | 109.16 ms | 21.06 ms | 4.09 ms |
| Latency median / p95 | 108.07 / 131.52 ms | 20.66 / 26.34 ms | 0.78 / 9.34 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---|---:|---:|---:|---|---:|
| brightness_up | 96.6% | 99.7% | 99.9% | dl_stronger | 54% |
| brightness_down | 70.8% | 99.6% | 97.1% | dl_stronger | 48% |
| contrast_up | 73.7% | 99.7% | 92.7% | dl_stronger | 36% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 64% |
| gamma_up | 100.0% | 99.7% | 100.0% | tie | 38% |
| gamma_down | 95.6% | 99.7% | 99.6% | dl_stronger | 42% |
| gaussian_noise | 27.0% | 81.7% | 65.3% | dl_stronger | 67% |
| gaussian_blur | 100.0% | 99.7% | 99.7% | tie | 64% |
| motion_blur | 98.9% | 99.7% | 99.4% | tie | 56% |
| rotation | 67.4% | 99.7% | 82.6% | dl_stronger | 52% |
| zoom | 99.5% | 99.7% | 99.7% | tie | 45% |
| occlusion | 100.0% | 99.7% | 99.8% | tie | 29% |

## Complementarity summary

- CV stronger (> 2 pts): none
- DL stronger (> 2 pts): brightness_up, brightness_down, contrast_up, gamma_down, gaussian_noise, rotation
- Ties: 6 modifications
- Cascade within 2 pts of the better engine on 8 / 12 modifications

## Complementarity battery (identification axis)

Per-probe pairing of cv_only vs dl_only correctness on the SAME probes (w = both right, x = only LBPH right, y = only SFace right, z = both wrong). recovery = y/(y+z) - the share of LBPH's misses SFace rescues; both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.

- Modified probes: 14760 | w/x/y/z = 12381/39/2075/265
- **Recovery rate** = 88.7% [87.3-89.9] (2075/2340)
- **Both-fail ceiling** = 1.8% [1.6-2.0]
- **McNemar** (x=39 vs y=2075): p_exact = 0.0e+00, chi2_cc = 1959.0
- Clean probes (360): w/x/y/z = 359/1/0/0

| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |
|---|---:|---:|---:|---:|---:|---:|
| brightness_up | 49 | 49 | 100% | 0.0% | 7.1e-11 | 1.00 |
| brightness_down | 420 | 415 | 99% | 0.3% | 4.9e-123 | 0.97 |
| contrast_up | 284 | 282 | 99% | 0.2% | 3.7e-83 | 0.97 |
| contrast_down | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_up | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| gamma_down | 47 | 47 | 100% | 0.0% | 3.7e-11 | 0.99 |
| gaussian_noise | 1051 | 793 | 75% | 17.9% | 2.1e-226 | 1.00 |
| gaussian_blur | 0 | 0 | nan% | 0.0% | 0.25 | n/a |
| motion_blur | 12 | 12 | 100% | 0.0% | 0.035 | 1.00 |
| rotation | 470 | 470 | 100% | 0.0% | 4.1e-132 | 1.00 |
| zoom | 7 | 7 | 100% | 0.0% | 0.55 | 0.87 |
| occlusion | 0 | 0 | nan% | 0.0% | 0.25 | n/a |

### Gate competence (does LBPH know when it's wrong?)

- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): **0.986**; margin signal: 0.986
- Deployed gate vs 'LBPH wrong': escalates 7369 probes; TPR (wrong probes escalated) = 0.726, FPR (right probes escalated) = 0.457, precision = 0.230
- Escalation reasons on rescued-eligible (LBPH-wrong) probes: quality=962, low_margin=723, ambiguous_band=13
- Including clean probes: AUC(d1) = 0.986, gate TPR = 0.726, FPR = 0.451
