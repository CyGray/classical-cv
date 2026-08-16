# LBPH descriptor ablation findings

Status: non-canonical provenance rerun. No deployed model, threshold, or
canonical result was changed.

The 12 candidates held neighbors at 8 and varied radius `{1,2,3}` against
square grids `{4,6,8,10}`. All used 100x100 Tan-Triggs preprocessing and
native OpenCV `predict_collect` distances. Every candidate received a fresh
calibrated threshold.

## Outcome

Both development rankings selected `r3_n8_g6x6` over the deployed descriptor
baseline `r1_n8_g8x8`.

| Cohort | Metric | Baseline 1/8x8 | Challenger 3/6x6 |
|---|---:|---:|---:|
| LSDB development (paired-view CV) | mean Rank-1 | 25.00% | 36.07% |
| LSDB development (paired-view CV) | mean TPIR | 9.29% | 17.50% |
| LSDB historical name-view test | Rank-1 | 100.00% (56/56) | 100.00% (56/56) |
| LSDB historical name-view test | TPIR | 96.43% (54/56) | 100.00% (56/56) |
| LFW development identities | Rank-1 | 6.79% (57/840) | 8.81% (74/840) |
| LFW development identities | TPIR | 3.10% (26/840) | 4.05% (34/840) |
| LFW locked identities | Rank-1 | 5.95% (50/840) | 10.00% (84/840) |
| LFW locked identities | TPIR | 1.43% (12/840) | 3.81% (32/840) |
| LFW locked identities | observed impostor FAR | 9.93 ppm | 11.87 ppm |
| Resource | descriptor/template | 64 KiB | 36 KiB |
| Resource | locked LFW mean score time | 36.32 ms | 21.09 ms |

The LFW development thresholds were 67.0132 for the baseline and 52.3724 for
the challenger. The baseline value is within 0.020 of the deployed 67.0333
threshold, providing a protocol sanity check. The challenger must never reuse
the baseline threshold.

On the same 840 locked LFW probes, the challenger gained 35 Rank-1 successes
while losing one (exact paired McNemar p = 1.08e-9). For thresholded TPIR, it
gained 21 and lost one (p = 1.10e-5). See `paired_locked_analysis.json`.

## Interpretation

`r3_n8_g6x6` is a credible replacement candidate: it improves both datasets,
cuts descriptor memory by 43.75%, and reduces observed scoring time by about
42%. The locked LFW FAR is close to, but above, the 10 ppm target (49 accepts
among 4,128,501 pairs); a final full-data calibration is therefore mandatory.

Do not deploy from this ablation alone. Before changing runtime configuration,
run the 41-modification robustness suite on baseline versus challenger, retrain
the production gallery with the selected descriptor, derive new full-data
`tau_accept`/FAR anchors, and revalidate the hybrid gate. The 56-image LSDB
name-view test has appeared in earlier workspace studies, so its two-probe gain
is supportive rather than pristine final-test evidence.
