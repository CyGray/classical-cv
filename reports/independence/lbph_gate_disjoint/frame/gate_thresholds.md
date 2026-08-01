# LBPH gate thresholds from the disjoint identification protocol

- protocol: gallery/probe-disjoint 1:N, 1680 mated probes vs 5749 enrolled identities
- scale: native cv.face.LBPHFaceRecognizer.predict_collect() (radius=1, neighbors=8, grid=8x8)
- crop family: **frame** (assume_cropped=True) - do not mix families across the two thresholds
- detector: yunet, split sha256 ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a

## tau_accept (impostor-driven)

- **75.3266** at rank 96 of 9,656,640 impostor comparisons
- realized per-comparison FAR: 9.94 ppm (target 10.00 ppm)
- realized per-probe FPIR at that threshold: 1.488% (resolution floor 595 ppm - too coarse to set a 10 ppm threshold, reported only)

## tau_reject (genuine-side / escalation-budget driven)

- **86.0744**, binding constraint: `escalation_budget`
- pre-gate false-reject target: 1.00%

| routed | share of probes |
|---|---|
| confident accept (`d1 <= tau_accept`) | 1.73% (29) |
| escalate to SFace | 50.00% (840) |
| pre-gate reject (`d1 >= tau_reject`) | 48.27% (811) |

Band clause only. The margin and quality clauses escalate additional frames,
so escalation here is a lower bound and pre-gate loss an upper bound.

## Against what is deployed

- deployed tau_accept 77.7693 -> per-comparison FAR 26.51 ppm on this protocol
- deployed tau_reject 88.4927 -> 19.88% of mated probes rejected before SFace is asked, 75.60% escalated
- standalone LBPH tau_accept 67.0333 (reports/independence/lbph_lfw1/native_predict_scale_yunet.json) -> per-comparison FAR 1.86 ppm on this protocol (**box**-cropped family; comparable only when `--crop-mode box`)

## Identification sanity

- rank-1 accuracy (threshold-free): 2.92%
- genuine distance p50 / p95 / p99: 98.6332 / 116.6602 / 130.8767

Candidates only - nothing here was written to `src/hybrid/thresholds.json`.
