# Canonical-promotion audit (2026-08-13)

## Project-owner scope decision

The project owner directed promotion using the evidence already present in
the repository and explicitly placed Raspberry Pi 5 and other target-device
testing outside scope. The package is therefore promoted as
**`canonical_descriptive_only`**: it is a reproducible record of the exact
post-hoc replay, and the manuscript may report it only with the same-data,
known-genuine, correlated-transform limitation. The promotion does not make
the result independently validated, does not support an open-set FPIR or
target-device claim, does not establish a speed win over direct SFace, and
does not change the runtime gate or thresholds.

## Original validated-evidence decision

**Do not promote this smoke test to canonical validated evidence, do not cite
it in the manuscript, and do not change the runtime gate from it.** Keep the
package in `docs/experiments/` as a reproducible post-hoc hypothesis generator.

The numerical replay is internally consistent: its recorded output hashes
match, and it exactly reproduces the archived deployed baseline before
applying alternative routing policies. That establishes reproducibility of
the replay, not external validity of the candidate policy.

## Validated-evidence gate assessment at the time of the smoke audit

This table records why the replay does not qualify as independently validated
evidence. Its semantic-status row was subsequently resolved for the narrower
descriptive promotion; the remaining validation gaps are unchanged.

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
| Semantic canonical status support | **Resolved for descriptive-only promotion** | The manifest now uses an explicit allowlisted `canonical_descriptive_only` status for this campaign. This separates archival/citation semantics but does not supply the missing validation evidence above. |

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

## Evidence needed for a stronger validated claim

The following work is not required for this bounded descriptive promotion.
It remains the gap between this artifact and an independently validated or
deployment-authorizing policy claim.

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
5. Target-device timing is explicitly outside the present project scope. Any
   future target-device efficiency claim would require isolated, repeated
   end-to-end measurements and a matched-FPIR comparison with direct SFace.
6. Promote only after the result manifest supports explicit reviewed campaign
   statuses and automated protocol assertions.

## Scope of this decision

The artifact is now stored under `docs/results/` with an explicit
`canonical_descriptive_only` manifest status. Its exact restricted claim may
be carried into the manuscript. Runtime source and thresholds remain
unchanged, and the result must not be confused with validated evidence.
