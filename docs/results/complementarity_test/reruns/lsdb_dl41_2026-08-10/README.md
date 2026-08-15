# Finalized LSDB complementarity battery

Scope: deterministic LSDB held-out test split (56 probe tiles), transformed by
the DL41 41-variant suite; 2,296 modified probes. This is LSDB-scoped
complementarity evidence, not an LFW result and not an operating-point
recalibration.

Frozen runtime gate: `tau_accept=67.03325520645528`, `tau_reject=140.13`,
`margin_min=0.05`; strict detector-failure policy.

Primary results, recomputed from `complementarity_probes.csv`:

- Recovery: 1,296 of 1,589 LBPH errors recovered by SFace: 81.56% (Wilson
  95% CI 79.58–83.39%).
- McNemar: LBPH-only-right `b=0`, SFace-only-right `c=1,296`; exact two-sided
  `p < 1e-300` (underflowed to zero in stored double-precision result).
- Gate competence against threshold-free LBPH Rank-1 error: distance AUC
  0.95019; negative-margin AUC 0.95319 (2,060 scored probes; 444 Rank-1
  errors). Separately, deployed routing recalled 100% of thresholded LBPH
  system failures, with 40.88% FPR on thresholded LBPH-correct scored probes
  and 82.40% escalation precision.
- Speed–accuracy curve: deployed cascade 87.24% thresholded identification
  rate at 11.96 ms/probe and 71.52% escalation. Same fresh-record anchors:
  LBPH-only 30.79% at 5.25 ms; SFace-only 87.24% at 8.33 ms.

Assets have no embedded titles, headers, or footers; manuscript captions carry
the interpretation. `mcnemar_table.svg` is a presentation asset only—use a
native Word table in the manuscript.

Do not claim selective speed gain from this LSDB run: it records recognition-
stage single-pass timing (not warmed/repeated end-to-end deployment timing),
and cascade matched SFace accuracy but was slower than SFace-only.
See `run_provenance.json` for exact commands, hashes, and checks.
