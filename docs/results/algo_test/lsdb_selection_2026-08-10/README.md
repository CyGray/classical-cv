# LSDB algorithm selection — 2026-08-10

Offline selection is intentionally separate from LFW deployment calibration.
Classical models fit on 224 LSDB training images (28 identities × 8), set native
thresholds from 56 disjoint LSDB calibration images (1,512 cross-identity
scores), then ran once on 56 untouched LSDB test images. The calibration rank
15 gave realized FAR 15/1,512 = 0.992%. LFW thresholds are not inputs here.

LBPH was selected as the classical fast path: it reached 96.43% thresholded
test TAR and 100.00% Rank-1; Eigenfaces and Fisherfaces reached 41.07%/75.00%
and 51.79%/58.93%, respectively. LBPH's 64 KB representation exceeds the
nominal 1 KB target and is recorded as an engineering exception.

`dl_external_lsdb_selection.json` records historical external-team LSDB
results for SFace, ArcFace, and FaceNet. It is not a same-harness accuracy
claim. The fresh DL-only comparison now lives in
`../lsdb_selection_dl_trio_2026-08-11/`; do not mix its result table into the
classical selection ranking above.
