# LSDB model-selection protocol

Use this protocol only for offline candidate selection. It is separate from
the LFW-derived frozen deployment thresholds.

1. Partition `data/lsdb/split/train` deterministically into a fitting subset
   and a calibration subset, preserving identity disjointness at the image
   level.
2. Fit LBPH, Eigenfaces, and Fisherfaces on the fitting subset only.
3. For each classical family, derive its own LSDB calibration threshold from
   cross-identity calibration scores at the coarsest resolvable LSDB operating
   point (8 ordered errors / 756 ordered comparisons, about 1.06% FAR).
4. Apply that unchanged threshold to `data/lsdb/split/test` and the LSDB
   modification suite. Do not tune on either set.
5. Select the classical fast-path candidate using the recorded rule and state
   any engineering exception explicitly.
6. Select the deep candidate from a fresh, same-split SFace, ArcFace, and
   FaceNet campaign. Enrol, calibrate, and test every candidate on the same
   LSDB cohorts; retain archived external-team vectors only as provenance
   diagnostics, never as held-out metrics.
7. Only after selection, report LFW-derived LBPH/SFace thresholds as frozen
   deployment calibration. They are not inputs to steps 1--6.

Every rerun must record source commit, dataset hashes, split membership,
commands, software versions, metrics, and artifact hashes before promotion to
`docs/results/algo_test/`.
