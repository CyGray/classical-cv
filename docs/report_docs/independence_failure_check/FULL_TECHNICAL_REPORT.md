# Full Technical Report: LaSalle DB1 Independence Failure Analysis

## 1. Stage-by-Stage Distance Decay (Normalized 0-100)
| Algorithm | Identity Pair | Raw Pixels | Equalized | Feature Space | Status |
|-----------|---------------|------------|-----------|---------------|--------|
| Eigenfaces | Saltat vs Ramos | 66.6 | 100.0 | 100.0 | PRESERVED |
| Fisherfaces | Ramos vs Ong | 69.8 | 100.0 | 0.0 | COLLAPSED |
| LBPH | Maghari vs Belen | 70.5 | 100.0 | 0.3 | COLLAPSED |

### Visual Decay Curves
![Eigenfaces Decay](independence_failure_check/reports/collapse_analysis/eigenfaces_decay_plot.png)
![Fisherfaces Decay](independence_failure_check/reports/collapse_analysis/fisherfaces_decay_plot.png)
![LBPH Decay](independence_failure_check/reports/collapse_analysis/lbph_decay_plot.png)

## 2. Multi-Sample Separation Trend (Fisherfaces)
| Samples/ID | Raw Distance | Normalized (0-100) |
|------------|--------------|--------------------|
| 1 Image(s) | 0.0000 | 0.0 |
| 3 Image(s) | 4883.3433 | 100.0 |
| 5 Image(s) | 2598.6897 | 53.2 |
| 7 Image(s) | 2317.3919 | 47.5 |
| 10 Image(s) | 2079.6227 | 42.6 |

### Visual Training Trend
![Fisherfaces Trend](independence_failure_check/reports/multi_image_analysis/fisherfaces_multi_image_plot.png)
