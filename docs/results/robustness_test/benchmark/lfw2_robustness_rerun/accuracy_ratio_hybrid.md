# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade

Originals: `C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\face-detection-g3\data\lfw-dataset` (5749 tiles) | 41 variants/original | seed=42 | no-face policy: `fallback`.

AR per modification = mean over its levels; overall = mean over modifications.

| Metric | cv_only | dl_only | cascade |
|---| ---: | ---: | ---: |
| Clean acceptance | 100.00% | 99.67% | 99.93% |
| **Overall AR** | **86.66%** | **98.18%** | **94.67%** |
| Pooled AR [95% CI] | 85.02% [84.87-85.16] | 97.94% [97.88-97.99] | 93.95% [93.85-94.04] |
| Mean latency | 156.26 ms | 36.42 ms | 5.98 ms |

## Per modification

| Modification | cv_only | dl_only | cascade | winner | escalation |
|---| ---: | ---: | ---: |---|---:|
| brightness_up | 96.3% | 99.6% | 99.8% | dl_stronger | 53% |
| brightness_down | 73.4% | 99.4% | 96.9% | dl_stronger | 48% |
| contrast_up | 78.1% | 99.6% | 93.5% | dl_stronger | 32% |
| contrast_down | 100.0% | 99.6% | 99.8% | tie | 64% |
| gamma_up | 100.0% | 99.7% | 99.9% | tie | 35% |
| gamma_down | 97.2% | 99.6% | 99.8% | dl_stronger | 42% |
| gaussian_noise | 27.7% | 82.7% | 65.2% | dl_stronger | 66% |
| gaussian_blur | 100.0% | 99.6% | 99.8% | tie | 62% |
| motion_blur | 98.6% | 99.6% | 99.5% | tie | 54% |
| rotation | 68.9% | 99.6% | 82.3% | dl_stronger | 51% |
| zoom | 99.7% | 99.6% | 99.7% | tie | 43% |
| occlusion | 100.0% | 99.6% | 99.9% | tie | 27% |
