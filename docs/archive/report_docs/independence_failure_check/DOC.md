# Independence Failure Check: Diagnostic Report

## ABSTRACT
This report investigates anomalous "zero-distance" similarity scores observed during initial identity independence tests. A series of controlled experiments—Collapse Tracking, Multi-Image Analysis, Regional Analysis, and Occlusion Analysis—were designed to trace the mathematical pipeline. While these diagnostics successfully isolated the "Small Sample Size" (SSS) collapse in Fisherfaces, a rigorous review reveals severe methodological flaws in the diagnostic scripts themselves. Specifically, the tests perform "apples-to-oranges" magnitude comparisons across entirely different mathematical spaces without proper normalization. Consequently, while the conclusion regarding Fisherfaces' singular matrix failure holds true, the quantitative comparisons of distance magnitudes across stages, regions, and image counts are mathematically invalid.

## INTRODUCTION
During early testing, certain pairs of distinct identities exhibited distance scores of exactly 0.0. To diagnose this, a suite of scripts was executed to test the feature extraction pipeline. This report presents the aggregated data from those tests, accompanied by a critical mathematical review of why the derived values, outside of the 0.0 collapse, are analytically flawed.

## METHODS
1. **Collapse Tracker:** Measured pairwise distances at three stages: Raw Pixels, Histogram Equalization, and Feature Space.
2. **Multi-Image Analysis:** Iteratively increased training images per identity (1 to 10) in Fisherfaces.
3. **Regional Analysis:** Extracted specific regions (Eyes, Nose, Mouth), resized them to 100x100, and computed feature distances.
4. **Occlusion Analysis:** Applied black-box occlusions to test images and measured distance drops.

## RESULTS & DISCUSSION

### 1. Collapse Tracking Analysis
*Table 1: Mean Distance across Processing Stages (Aggregated 10 Iterations)*

| Algorithm | Pair Tested | Raw Pixels (L2) | Equalized Pixels (L2) | Feature Space |
|-----------|-------------|-----------------|-----------------------|---------------|
| **Eigenfaces** | Saltat vs Ramos | 3508.57 | 5267.50 | 5267.50 (L2) |
| **Fisherfaces**| Ramos vs Ong | 3696.41 | 5298.13 | **0.00** (L2) |
| **LBPH** | Maghari vs Belen| 4887.38 | 6932.63 | 20.89 (Chi-Sq) |

**Discussion:** The Fisherfaces 0.00 feature distance is a genuine mathematical collapse (Singular Matrix). Furthermore, Eigenfaces simply returns the exact pixel distance (5267.50) because a PCA trained on only 2 images creates a trivial 1D line that preserves the exact L2 distance of the original inputs.

> **CRITICAL WARNING: The "Apples-to-Oranges" Metric Flaw**
> The `collapse_tracker` directly compares absolute Euclidean distance in raw 10,000-dimensional pixel space against Chi-Squared distance in LBPH histogram space and PCA-projected feature space. These metrics operate on entirely different scales and bounds. A drop from 5000 (Euclidean pixels) to 20 (Chi-Squared features) does not signify "collapse"; it is merely a change in the unit of measurement.
>
> **CRITICAL WARNING: The True Algorithm Flaw (Singular Matrix)**
> Evaluating Fisherfaces (LDA) using a **single image per identity** guarantees a within-class variance of zero. This results in a singular, non-invertible scatter matrix. The algorithm mathematically collapses, outputting a distance of **0.0** between different identities. This is the only valid finding of the diagnostic suite.

### 2. Multi-Image Recovery (Fisherfaces)
*Table 2: Fisherfaces Mean Distance by Training Image Count (Ramos vs Ong)*

| Images per Identity | Mean Feature Distance |
|---------------------|-----------------------|
| 1 | **0.00** |
| 3 | 4883.34 |
| 5 | 2598.69 |
| 7 | 2317.39 |
| 10| 2079.62 |

**Discussion:** This test proves that $>1$ image per identity resolves the singular matrix (0.00) error, but the subsequent "decay" from 4883 to 2079 is highly misleading.

> **CRITICAL WARNING: Unnormalized Subspace Comparisons**
> The `multi_image_test` compares the absolute Euclidean distances of Fisherfaces models trained on different quantities of images. Because each training set produces a completely different projection matrix with distinct eigenvalues and scaling, absolute distances between these independent models cannot be directly compared without normalizing by the subspace variance.

### 3. Regional and Occlusion Analysis
*Table 3: Mean Feature Distance by Extracted Region*

| Algorithm | Full Face | Eyes | Nose | Mouth |
|-----------|-----------|------|------|-------|
| **Eigenfaces** | 5267.50 | 3892.47 | 4497.86 | 3196.82 |
| **Fisherfaces**| **0.00** | **0.00** | **0.00** | **0.00** |
| **LBPH** | 20.89 | 18.68 | 24.46 | 23.36 |

**Discussion:** Fisherfaces consistently collapses across all regions due to the 1-image constraint. For the other algorithms, the regional extraction process and occlusion testing introduce artificial artifacts.

> **CRITICAL WARNING: Artificial Variance Reduction & Aspect Distortion**
> The `regional_analysis` resizes non-square facial regions (e.g., 50x10 pixel eyes) into 100x100 squares, destroying spatial relationships. Furthermore, `occlusion_analysis` blacking out regions artificially reduces total image variance to zero in those areas, which organically shrinks global Euclidean distance regardless of algorithmic feature weighting.

## CONCLUSION
The diagnostic suite correctly identified the root cause of the 0.0 distances: **Fisherfaces (LDA) strictly requires multiple images per identity to compute within-class variance and cannot be used in a 1-image-per-class independence test.** 

However, the diagnostic methodology used to analyze the other algorithms is fundamentally flawed. Direct magnitude comparisons between raw pixel distances, PCA sub-spaces, and Chi-Squared histograms constitute an "apples-to-oranges" logical error. Future evaluations must strictly utilize normalized thresholds (e.g., False Positive Rates) rather than absolute distance magnitudes to draw valid conclusions across different mathematical domains.