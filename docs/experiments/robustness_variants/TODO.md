# TODO — robustness_variants

- [ ] DL-track vs classical-CV AR comparison, deferred. DL's `ar-table.py` is
  genuine-only, La Salle DB, per-model raw distances — not comparable to
  classical-CV's AR/TAR numbers on 5 counts (see memory `dl-vs-cv-ar-not-comparable`).
  Not a blocker for the robustness-versions work; revisit once both tracks
  share protocol.
- [ ] Per-modification table legibility for non-repo readers (e.g. Dr. Oh).
  The full 41-row PNG (`pairwise-verification/lfw-results/AR/per_modification_verification_table.png`)
  is dense; consider a family-level rollup (17 rows instead of 41) as the
  default view, full table as backup detail.
- [ ] "Escalation %" needs a standing plain-language definition next to the
  hybrid/cascade tables themselves (README currently assumes the reader
  already knows the cascade mechanics) — `diagram_4_escalation_cascade.png`
  (this dir) has a draft explainer/diagram, promote the wording into
  `hybrid-identification/README.md`.
- [ ] `pairwise-verification/GUIDE.md` §1/§2.A has gone stale: it points at
  `docs/experiments/AR/*.png` and quotes `τ_accept = 67.0084`; real files now
  live under `pairwise-verification/lfw-results/{AR,TAR,SWEEP}/` and the
  canonical unified threshold is `67.03325520645528`
  (`classical-cv/src/hybrid/thresholds.json`). Fix paths/value or a future
  reader will link/cite the wrong thing.
