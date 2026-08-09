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
6. Select the deep candidate from the external team's LSDB SFace, ArcFace, and
   FaceNet artifacts under an explicitly documented footprint/deployment rule.
   Do not call it a same-harness accuracy comparison until the external team
   supplies reproducible run metadata.
7. Only after selection, report LFW-derived LBPH/SFace thresholds as frozen
   deployment calibration. They are not inputs to steps 1--6.

Every rerun must record source commit, dataset hashes, split membership,
commands, software versions, metrics, and artifact hashes before promotion to
`docs/results/algo_test/`.
