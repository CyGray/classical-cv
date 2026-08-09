# LFW all-families verification (Dr. Oh protocol, partial run)

Clean anchor vs modified probe, every pair scored. Identities: **575** (seed 42). Per modification: 575 genuine + 330,050 impostor pairs.

**Thresholds (LFW1-derived vs LS-DB1-frozen):**

| | tau_accept (LBPH) | l2_genuine (SFace) | tau_reject | cosine_genuine |
|---|---:|---:|---:|---:|
| **LFW1-derived (used here)** | 81.0383 (@0.01% FAR) | 1.355317 | 76.85 | 0.363 |
| LS-DB1-frozen (deployed) | 70.6089 | 1.106796 | 76.85 | 0.363 |

> **Transfer finding.** At LFW's **1% FAR** the LBPH accept edge is **88.4044** — *above* the carried reject edge 76.85, which would collapse the escalation band (Hybrid→LBPH). So tau_accept is placed at 100 ppm here to keep accept<reject. The LS-DB1-frozen 70.6089 is much stricter than either LFW point: the frozen thresholds do not transfer to LFW.

Accuracy = (TP+TN)/all (the figure's formula). Balanced = ½(TPR+TNR), the prevalence-robust companion — raw accuracy is TN-dominated at 574:1 impostor:genuine (STATE-07-21 Finding 3).

## Accuracy (%) — raw (TP+TN)/all

| Modification | LBPH | SFace | Hybrid |
|---|---:|---:|---:|
| clean | 99.99 | 99.919 | 99.99 |
| brightness_up | 99.988 | 99.918 | 99.988 |
| brightness_down | 99.943 | 99.946 | 99.943 |
| contrast_up | 99.955 | 99.935 | 99.955 |
| contrast_down | 99.993 | 99.924 | 99.993 |
| gamma_up | 99.991 | 99.92 | 99.991 |
| gamma_down | 99.989 | 99.925 | 99.989 |
| gaussian_noise | 99.892 | 99.889 | 99.892 |
| gaussian_blur | 99.994 | 99.921 | 99.994 |
| motion_blur | 99.997 | 99.916 | 99.997 |
| rotation | 99.983 | 99.921 | 99.983 |
| zoom | 99.994 | 99.92 | 99.994 |
| occlusion | 99.993 | 99.922 | 99.993 |
| **overall (mods)** | **99.974** | **99.921** | **99.974** |

## Balanced accuracy (%) — ½(TPR+TNR)

| Modification | LBPH | SFace | Hybrid |
|---|---:|---:|---:|
| clean | 99.995 | 99.959 | 99.995 |
| brightness_up | 98.236 | 99.959 | 98.236 |
| brightness_down | 87.32 | 99.886 | 87.32 |
| contrast_up | 89.85 | 99.968 | 89.85 |
| contrast_down | 99.997 | 99.904 | 99.997 |
| gamma_up | 99.996 | 99.96 | 99.996 |
| gamma_down | 99.213 | 99.934 | 99.213 |
| gaussian_noise | 69.022 | 92.392 | 69.022 |
| gaussian_blur | 99.997 | 99.874 | 99.997 |
| motion_blur | 99.998 | 99.871 | 99.998 |
| rotation | 95.89 | 99.939 | 95.89 |
| zoom | 99.997 | 99.851 | 99.997 |
| occlusion | 99.996 | 99.961 | 99.996 |
| **overall (mods)** | **94.366** | **99.183** | **94.366** |
