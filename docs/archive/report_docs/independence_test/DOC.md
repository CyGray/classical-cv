# Independence Test Report: Classical Face Recognition Algorithms

## ABSTRACT
This study evaluates the identity independence of three classical face recognition algorithms—Local Binary Patterns Histograms (LBPH), Eigenfaces (PCA), and Fisherfaces (LDA)—to establish their baseline reliability against false positives. Using a single frontal image for 28 distinct individuals from the processed LaSalle DB1 dataset, we performed exhaustive inter-identity comparisons. Because every comparison involved different people, any high similarity score directly highlighted the algorithm's vulnerability to false positives. Distances were normalized to a 0-100 scale, using the 5th percentile (p05) distance as a benchmark for a 5% False Positive Rate. The results demonstrate that LBPH significantly outperforms holistic methods, maintaining a strong separability margin with a minimum inter-identity distance of 73.74 and a p05 threshold of 79.82. In contrast, Eigenfaces and Fisherfaces exhibited significant feature overlap, with minimum distances dropping to 44.35 and 51.72, respectively. Consequently, LBPH is concluded to be the most robust and reliable classical algorithm for distinguishing distinct identities under controlled lighting, while Eigenfaces and Fisherfaces are highly susceptible to false positives unless extremely aggressive thresholds are applied.

## INTRODUCTION
A critical metric for any face recognition system is its False Positive Rate (FPR)—the frequency at which it incorrectly identifies two different people as the same person. To establish a baseline for algorithmic reliability, we conducted an "independence test" where every identity in a dataset is compared against every other identity. Because all comparisons are strictly inter-identity (different people), any similarity score surpassing a given threshold is a guaranteed false positive. This allows us to empirically determine optimal thresholds and compare the separability power of different algorithms.

## METHODS
- **Dataset:** LaSalle DB1 (Processed).
- **Identities:** 28 distinct individuals.
- **Images:** 1 `light_front.jpg` image per identity.
- **Comparisons:** A full N*(N-1) cross-comparison resulting in pairs of distinct identities.
- **Normalization:** Raw distance metrics for each algorithm were normalized to a 0-100 scale based on the maximum observed distance to allow for direct comparison.
- **Metric:** The 5th Percentile (p05) distance was used as a baseline threshold to simulate a 5% False Positive Rate. Lower distances indicate higher similarity.

## RESULTS & DISCUSSION

### LBPH Performance
- **Minimum Distance:** 73.74
- **Mean Distance:** 87.16
- **p05 Threshold:** 79.82
LBPH demonstrated the strongest separability. Even the two most similar looking different identities only achieved a distance score of 73.74, placing the vast majority of imposter comparisons safely at the high end of the distance spectrum.
*Figures: [lbph_distance_histogram.png], [lbph_distance_curve_plot.png]*

### Eigenfaces Performance
- **Minimum Distance:** 44.35
- **Mean Distance:** 75.25
- **p05 Threshold:** 54.49
Eigenfaces struggled the most with identity separation. The minimum distance dropped to 44.35, indicating that the algorithm found significant mathematical similarity between distinct individuals, likely due to PCA's sensitivity to holistic lighting and background structures rather than distinct facial features.
*Figures: [eigenfaces_distance_histogram.png], [eigenfaces_distance_curve_plot.png]*

### Fisherfaces Performance
- **Minimum Distance:** 51.72
- **Mean Distance:** 73.53
- **p05 Threshold:** 58.70
Fisherfaces performed moderately better than Eigenfaces, successfully pushing the absolute minimum imposter distance slightly higher to 51.72. However, its mean distance remained low, indicating a broad overlap in the feature space.
*Figures: [fisherfaces_distance_histogram.png], [fisherfaces_distance_curve_plot.png]*

## CONCLUSION
Among the classical algorithms tested, **LBPH** is definitively the most reliable for distinguishing between distinct identities under controlled lighting. Its local texture-based approach creates a much wider gap between inter-identity comparisons than the holistic projection methods (Eigenfaces and Fisherfaces). If a strict access-control threshold is required, LBPH offers the safest margin for error, whereas Eigenfaces and Fisherfaces are highly prone to false positives unless the threshold is set extremely aggressively (e.g., < 40).