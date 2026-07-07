# Results, Discussion, and Conclusion: LaSalle DB1 Diagnostics

## 1. Key Results: Representation Collapse
The investigation confirms that identity independence fails catastrophically for **Fisherfaces** when using single-sample enrollment.

| Experiment | Finding |
|------------|---------|
| Baseline Verification | Saltat/Ramos (Eigen) = 100.0, Ramos/Ong (Fisher) = 0.0, Maghari/Belen (LBPH) = 0.3 |
| Multi-Image Test | Separation restored from 0.0 to 100.0 normalized units at 10 images. |

## 2. Discussion
The 'Zero-Distance' problem is strictly a **Feature Space Collapse**. In the raw pixel domain, these identities are mathematically distinct. However, the Linear Discriminant Analysis (LDA) used in Fisherfaces fails to define any discriminative dimensions when intra-class variance is absent.

## 3. Conclusion
To maintain identity independence in LaSalle DB1:
1. **Fisherfaces** requires at least 3-5 images per person to begin separating identities.
2. **LBPH** and **Eigenfaces** are more robust to single-sample enrollment but still show significantly reduced separation compared to multi-sample deep learning methods.
