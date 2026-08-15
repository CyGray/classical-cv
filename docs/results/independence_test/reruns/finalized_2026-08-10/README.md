# Finalized independence rerun — 2026-08-10

This campaign re-runs the selected LBPH fast path and the deployed
LBPH-to-SFace cascade on clean, pre-cropped La Salle DB1 tiles (28 identities;
756 ordered cross-identity comparisons). It evaluates the frozen LFW-derived
configuration locally; it is **not** a La Salle threshold calibration.

## Recorded result

| System | Deployed rule | False accepts / 756 | FAR (95% Wilson CI) |
|---|---|---:|---:|
| LBPH | `d <= 67.03325520645528` | 0 | 0.000% [0.000, 0.506] |
| SFace | cosine >= 0.363 and L2 <= 1.0313 | 2 | 0.265% [0.073, 0.959] |
| Cascade | frozen LBPH gate then SFace | 2 | 0.265% [0.073, 0.959] |

All 28 LSDB probes entered the cascade escalation path (23 ambiguous-band,
5 quality-flag). No joint LBPH/SFace false accept was observed. With a zero
LBPH false-accept cell, Q, phi, and Fisher inference are degenerate; do not
claim statistical error independence from this small local sweep.

`independence_frozen_thresholds.svg` is regenerated from the recorded CSV and
the canonical LFW threshold JSONs. It plots the frozen LFW boundaries on LSDB
impostor distances; it does not turn the observed LSDB distribution into a new
deployment threshold.

`tau_reject_tradeoff.svg` is regenerated from the canonical LFW trade-off
curve. Its impostor series is a documented 1:1 proxy, so it supports the
permissive-gate rationale but not a 1-to-N cascade FAR claim.

See `run_provenance.json` for command, hashes, runtime, dataset fingerprint,
and validation counts. The LFW threshold derivations remain under
`../../independence/`.
