# Occlusion Impact Report: eigenfaces (Aggregated 10x)
## Identities: Anthony_Charles_Saltat vs Daniel_Ramos

### High-Level Summary
This report measures how blocking specific facial regions affects the mathematical separation between identities. Data is aggregated over 10 runs.

### Technical Data (Mean Impact on Distance)
| Occlusion | Mean Distance | Drop from Baseline |
|-----------|---------------|-------------------|
| None (Baseline) | 5267.5036 | - |
| Eyes Blocked | 4859.4418 | 408.0617 |
| Nose Blocked | 5049.0886 | 218.4150 |
| Mouth Blocked | 5115.5702 | 151.9334 |

### Sample by Sample Results (All Iterations)
| Run | None | Eyes Blocked | Nose Blocked | Mouth Blocked |
|-----|------|--------------|--------------|---------------|
| 1 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 2 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 3 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 4 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 5 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 6 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 7 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 8 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 9 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |
| 10 | 5267.5036 | 4859.4418 | 5049.0886 | 5115.5702 |

### Results & Discussion
The baseline separation of **5267.5036** is most affected by **Eyes Blocked**. 

This confirms that the **eigenfaces** algorithm's feature vectors are highly dependent on the structures in the **Eyes** region.

### Conclusion
To ensure robust identity separation for **eigenfaces**, high-quality capture of the **Eyes** is critical.
