Canonical, version-controlled results for the four manuscript evidence groups.
Every artifact is recorded in `RESULTS_MANIFEST.json` with source path/script,
commit, timestamp, checksum, status, and rerun flag.

- `algo_test/` — classical/SFace model-selection outputs, preprocessing evidence, and comparison figures.
- `complementarity_test/` — LBPH/SFace complementarity and gate evidence only; no robustness tables.
- `independence_test/` — threshold derivations, FAR sweeps, and independence artifacts.
- `robustness_test/` — 41-modification, identification, verification, and robustness reports/tables.
- `metadata/` — cross-test metrics and raw-output history.

`classical-cv/reports/` and `classical-cv/outputs/` remain working locations for newly generated and ignored raw artifacts. Only reviewed, canonical snapshots belong here.

Read every relevant subdirectory `README.md` first. Then read
`metadata/PROVENANCE_AUDIT.md` before citing a raster figure or any artifact
marked `historical_rerun_required`, `needs_provenance_review`,
`illustrative_stand_in`, or `rerun_required`. Tables belong in the manuscript
as native Word tables; publication figures must be regenerated from verified
data as SVG/PDF (or EMF on Windows), never auto-traced from a PNG.
