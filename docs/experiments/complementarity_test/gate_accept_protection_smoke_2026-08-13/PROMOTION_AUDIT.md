# Canonical-promotion audit (2026-08-13)

## Decision

**Do not promote this smoke test to canonical validated evidence, do not cite
it in the manuscript, and do not change the runtime gate from it.** Keep the
package in `docs/experiments/` as a reproducible post-hoc hypothesis generator.

The numerical replay is internally consistent: its recorded output hashes
match, and it exactly reproduces the archived deployed baseline before
applying alternative routing policies. That establishes reproducibility of
the replay, not external validity of the candidate policy.

## Promotion-gate assessment

| Requirement | Status | Evidence |
|---|---|---|
| Candidate selected without final-set feedback | **Fail** | The policy was motivated and evaluated on the same 56 LSDB test images and 2,296 correlated transforms. |
| Locked identity/session-disjoint final known-probe test | **Missing** | `data/lsdb/split/test` contains the same 56 images used by this replay; no unused target-domain final session is present. |
| Deployment-matched unknown-query FPIR | **Missing** | The source CSV contains known genuine probes only. It cannot measure query-level false-positive identification. |
| Exact deployed multi-shot gallery rule | **Not evaluated by this replay** | The replay inherits stored scores and does not run a fresh open-set test against the production enrollment rule. |
| Complete A8 gate ablation | **Incomplete** | The replay covers useful rule ablations but not a development-only selection followed by a locked final comparison, matched-escalation random gate, and joint FPIR/non-inferiority analysis. |
| Dependence-aware analysis | **Partial** | Identity-cluster bootstrap summaries are present, but the same identities and base images were used to discover and evaluate the policy. |
| Transform protocol frozen and independently validated | **Missing** | The source remains the internal deterministic synthetic stress suite; transform-conformance work is still open. |
| End-to-end target-hardware efficiency evidence | **Missing** | Timing is stored recognition-stage arithmetic, excluding detector/I/O/warm-up/repeats and Raspberry Pi measurements. |
| Benefit versus direct SFace | **Fail on current timing anchor** | The candidate is 2.4872 ms (29.9%) slower than direct SFace despite improving the deployed cascade. |
| Semantic canonical status support | **Missing** | The current manifest generator defaults most non-PNG artifacts to `canonical_snapshot`; it does not implement the roadmap's validated/descriptive status distinction or protocol assertions. |

## Existing-data feasibility check

- `data/lsdb/split/train` contains 280 images and is model-fitting data.
- `data/lsdb/split/test` contains 56 images across 28 identities, exactly the
  held-out images replayed here. It is no longer untouched after policy
  selection.
- `classical-cv/data/lfw-dataset` is now locally populated (13,233 images,
  5,749 identities). It can support an external unknown-query diagnostic
  against the LSDB gallery, but it cannot supply the missing fresh enrolled
  LSDB session. Historical LFW threshold calibration also used all LFW
  identities, so it does not by itself create a leakage-free final gate test.
- No existing result artifact was found containing deployment-matched unknown
  queries with the per-query LBPH distance, margin, quality flags, SFace
  decision, and final gate outcome needed to validate this policy offline.

## Minimum evidence needed for promotion

1. Predeclare the policy and tune it only inside identity-grouped development
   folds.
2. Freeze a fresh identity/session-disjoint final manifest and transform
   implementation before scoring.
3. Evaluate fresh enrolled probes and external unknown people against the
   exact 28-person, multi-shot deployment gallery; report TPIR/FNIR, CMC/OSCR,
   and direct query-level cascade FPIR.
4. Complete the A8 current/band/margin/per-quality/no-reject/random/always-
   LBPH/always-SFace/oracle comparison with clustered paired intervals and a
   predeclared non-inferiority margin.
5. For an efficiency claim, run isolated, repeated end-to-end measurements on
   the Raspberry Pi and compare mean and tail latency/energy with direct
   SFace at the same FPIR.
6. Promote only after the result manifest supports explicit reviewed campaign
   statuses and automated protocol assertions.

## Scope of this decision

No files under `docs/results/`, no runtime source or thresholds, and no
manuscript DOCM were changed as part of this promotion audit. A later
`canonical_descriptive_only` archival status may be reasonable after the
semantic manifest system exists, but it must remain non-citable and must not
be confused with validated evidence.
