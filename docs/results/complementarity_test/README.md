Canonical evidence that SFace and LBPH are complementary:

- Recovery Rate
- McNemar's paired test
- Gate Accuracy
- Speed-Accuracy Curve

Robustness tables belong in `../robustness_test/`, never here.

Check `../RESULTS_MANIFEST.json` and `../metadata/PROVENANCE_AUDIT.md` before
citation.

## Reviewed campaigns

- `reruns/lsdb_dl41_2026-08-10/` is the canonical LSDB-DL41 rerun supporting
  within-suite recovery, gate-competence, and recognition-stage cost claims.
- `reruns/gate_accept_protection_descriptive_2026-08-13/` is
  `canonical_descriptive_only`. It may be cited only as a post-hoc replay on
  the same 56 known-genuine source images and 2,296 correlated transforms.
  It does not establish independent generalization, open-set FPIR, a runtime
  gate change, target-device behavior, or a speed win over direct SFace.

Neither campaign is a substitute for a robustness result.
