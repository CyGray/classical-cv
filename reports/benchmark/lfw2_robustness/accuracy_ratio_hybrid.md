# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset` (5749 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---| ---: | ---: | ---: |
| Clean acceptance | 100.00% | 99.77% | 99.79% |
| **Overall AR** | **98.12%** | **97.21%** | **97.21%** |
| Pooled AR [95% CI] | 97.82% [97.76-97.88] | 96.77% [96.70-96.84] | 96.77% [96.70-96.84] |
| Mean latency | 123.23 ms | 27.36 ms | 0.57 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---| ---: | ---: | ---: |---|---:|
| brightness_up | 99.9% | 99.7% | 99.8% | tie | 99% |
| brightness_down | 97.1% | 99.6% | 99.6% | dl_stronger | 98% |
| contrast_up | 99.0% | 99.8% | 99.7% | tie | 88% |
| contrast_down | 100.0% | 99.7% | 99.7% | tie | 100% |
| gamma_up | 100.0% | 99.8% | 99.8% | tie | 99% |
| gamma_down | 100.0% | 99.8% | 99.8% | tie | 97% |
| gaussian_noise | 81.4% | 69.4% | 69.4% | cv_stronger | 80% |
| gaussian_blur | 100.0% | 99.8% | 99.8% | tie | 100% |
| motion_blur | 100.0% | 99.8% | 99.8% | tie | 99% |
| rotation | 100.0% | 99.6% | 99.6% | tie | 100% |
| zoom | 100.0% | 99.7% | 99.7% | tie | 99% |
| occlusion | 100.0% | 99.8% | 99.8% | tie | 98% |
