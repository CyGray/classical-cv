# Gate accept-protection descriptive replay (2026-08-13)

Status: **canonical descriptive-only**. This result may be cited only as a
post-hoc, same-data routing ablation with the limitations below. It is not
independent validation and it does not authorize a runtime gate change.

This replay uses the stored LSDB-DL41 per-probe scores. It does not rescore
images, change `gate.py`, retune `tau_accept`, or measure unknown-query FPIR.

## Main result

| Policy | AR (%) | Escalation (%) | Mean stored-stage latency (ms) | Strict-correct LBPH accepts escalated |
|---|---:|---:|---:|---:|
| Deployed | 87.2387 | 71.5157 | 11.9585 | 289 |
| Quality cannot override strict accept; margin 0.05 retained | 87.2387 | 59.2334 | 10.8125 | 7 |
| Exploratory margin 0.025 sensitivity | 87.2387 | 58.9286 | 10.7859 | 0 |
| Direct SFace anchor | 87.2387 | N/A | 8.3253 | N/A |

The conservative candidate prevents quality flags from overriding
`d <= tau_accept`, retains the deployed `margin_min=0.05` veto, and leaves
all behavior above `tau_accept` unchanged. On the 2,296 modified rows it saved
**282 SFace calls** (plus
4 clean calls), changed AR by
**+0.0000**
points, cut escalation by **12.2822**
points, and cut the arithmetic mean by
**1.1460 ms**.

It still remained **2.4872 ms
(29.9%) slower** than the
direct SFace anchor. This improves the current cascade but does not establish
an efficiency win over SFace.

## Margin sensitivity

The deployed gate escalated 289 modified probes that LBPH would correctly
accept at the frozen threshold. Removing every accept-side override also lost
one SFace rescue: a low-distance LBPH misidentification with margin 0.022716.
The already-used smoke-grid value 0.025 retained that rescue while avoiding
all 289 strict-correct escalations on this dataset. It saved
289 modified SFace calls
and reached 10.7859 ms with unchanged AR.
That apparent one-row separator is post-hoc overfitting, so 0.025 is a
sensitivity result only - not a selected policy.

## Two meanings of "LBPH could get it right"

- **Actionable deployed definition:** Rank-1 identity correct and
  `d <= tau_accept`. The conservative candidate reduces escalations from
  289 to
  7 of
  707 such modified probes.
- **Raw oracle definition:** LBPH Rank-1 identity correct regardless of its
  threshold. The candidate still escalates
  916 of
  1616 such probes, and
  6
  end as thresholded SFace failures. Fixing those requires a newly calibrated
  accept/risk model under open-set FPIR, not just gate reordering.

## Files

- `results.json`: complete machine-readable results and caveats.
- `policy_summary.csv`: primary policy comparison.
- `accept_margin_sweep.csv`: accept-side margin smoke grid.
- `quality_flag_ablation.csv`: per-quality-flag leave-one-out and only-flag checks.
- `primary_candidate_changed_rows.csv`: auditable route changes.
- `run_provenance.json`: hashes, environment, source location, and bounded
  canonical status.
- `PROMOTION_AUDIT.md`: the original validation-gap audit plus the project
  owner's bounded promotion decision.
- Replay implementation (hash-pinned by provenance):
  `docs/experiments/complementarity_test/gate_accept_protection_smoke_2026-08-13/smoke_gate_policies.py`.

## Mandatory limitations

1. The policies were motivated and evaluated on the same 56 source images / 28 identities.
2. The 2,296 rows are correlated synthetic transforms, not independent trials.
3. There are no unknown probes, so removing a quality override could worsen FPIR unseen here.
4. Stored timings are recognition-stage arithmetic, not end-to-end or
   target-device measurements. Target-device testing is outside this campaign.
5. The candidate is slower than the stored direct-SFace anchor, so this result
   supports a routing-efficiency observation, not a speed win over SFace.
6. The runtime gate and frozen thresholds remain unchanged. A stronger policy
   claim would require independent, open-set validation beyond this result's
   descriptive scope.
