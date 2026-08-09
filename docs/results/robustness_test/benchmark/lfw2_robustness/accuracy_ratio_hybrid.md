# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (5749 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade | parallel |
|---| ---: | ---: | ---: | ---: |
| Clean acceptance | 100.00% | 99.67% | 99.93% | 99.70% |
| **Overall AR** | **86.66%** | **98.22%** | **94.69%** | **98.26%** |
| Pooled AR [95% CI] | 85.02% [84.87-85.16] | 97.98% [97.92-98.04] | 93.98% [93.88-94.08] | 98.02% [97.97-98.08] |
| Mean latency | 94.35 ms | 19.82 ms | 3.61 ms | 7.14 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | parallel | winner | escalation |
|---| ---: | ---: | ---: | ---: |---|---:|
| brightness_up | 96.3% | 99.6% | 99.8% | 99.7% | dl_stronger | 53% |
| brightness_down | 73.4% | 99.4% | 96.9% | 99.4% | dl_stronger | 47% |
| contrast_up | 78.1% | 99.6% | 93.4% | 99.7% | dl_stronger | 30% |
| contrast_down | 100.0% | 99.6% | 99.8% | 99.7% | tie | 64% |
| gamma_up | 100.0% | 99.7% | 99.9% | 99.7% | tie | 35% |
| gamma_down | 97.2% | 99.6% | 99.8% | 99.7% | dl_stronger | 42% |
| gaussian_noise | 27.7% | 83.1% | 65.6% | 83.1% | dl_stronger | 62% |
| gaussian_blur | 100.0% | 99.6% | 99.8% | 99.7% | tie | 62% |
| motion_blur | 98.6% | 99.6% | 99.5% | 99.6% | tie | 53% |
| rotation | 68.9% | 99.6% | 82.3% | 99.6% | dl_stronger | 46% |
| zoom | 99.7% | 99.6% | 99.7% | 99.6% | tie | 36% |
| occlusion | 100.0% | 99.6% | 99.9% | 99.7% | tie | 27% |
