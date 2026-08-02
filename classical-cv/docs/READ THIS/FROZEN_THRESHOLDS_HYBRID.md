# Hybrid-model independence-test thresholds — candidate values, mostly NOT deployed

**UPDATE 2026-08-02:** the LBPH `tau_accept` candidate below (77.769348) was
evaluated and **rejected** — see "What's surprising" below, corrected in
place. It was a box-crop-vs-full-frame harness bug in
`src/hybrid/independence_test.py`, not a legitimate detector-driven
recalibration. The deployed `gate.tau_accept` moved instead to
**67.03325520645528**, the box-cropped YuNet **standalone** LBPH sweep
(`FROZEN_THRESHOLDS.md`), unified with `cv_only`'s threshold. Full trail:
`docs/independence/MASTER_FILE.md`, `docs/audits/STATE-08-02.md`. The
`tau_reject`/SFace rows below are unaffected by that specific correction but
remain open for other reasons — `tau_reject` in particular is now suspect for
the *same* box-crop bug, since it comes from the identical full-frame run
(see `docs/NOTES.md` item 3).

*Generated 2026-07-28. This doc is intentionally separate from
[`FROZEN_THRESHOLDS.md`](FROZEN_THRESHOLDS.md), which covers the deployed
`thresholds.json` values derived in isolation (LBPH-only, and the SFace
`l2_genuine` supplied by the SFace sub-team). This doc covers thresholds
re-derived by running LBPH + SFace + the cascade gate together, on the same
pass, via `src/hybrid/independence_test.py`. Do not merge the two tables —
they answer different questions (see "Why a separate doc" below).*

## Status: candidate, not adopted

**`src/hybrid/thresholds.json` was NOT changed by this run.** The numbers
below are what the *joint hybrid pipeline* measures on LFW1; whether to
adopt any of them into the deployed config is an open decision, not made
here. See "What's surprising" before deciding.

## The numbers

All measured unidirectional (upper-triangle unique pairs only, i<j, no
mirrored A→B/B→A double-count), LFW1 (`data/lfw-dataset`), N=5,749
identities, 16,522,626 unique cross-identity pairs, seed=42, same
per-identity probe picks as the frozen LBPH-only `tau_accept` run (see
"Reproduction" for the manifest that pins this).

| Threshold | Deployed (isolated-derivation) | **Hybrid-derived (this run)** | Rank / FAR target |
|---|---:|---:|---|
| LBPH `tau_accept` | 67.0084 (LBPH-only, Haar detector, `reports/independence/lbph_lfw1/`) | **77.769348** | rank-165 unidirectional unique pair, 9.99 ppm FAR |
| LBPH `tau_reject` | 76.85 (carried from `tar_at_far.md`, ~1% FAR, different pipeline/era) | **88.492676** | rank-165,226 unidirectional unique pair, 1.000% FAR |
| SFace `l2_genuine` | 1.018 (supplied by SFace sub-team, not derived) | **1.031255** | rank-165 unidirectional unique pair, 9.99 ppm FAR |
| SFace `l2` @ 1% FAR | — (no prior 1%-FAR SFace measurement in this repo) | **1.192200** | rank-165,226 unidirectional unique pair, 1.000% FAR |
| SFace `cosine_genuine` | 0.363 (unchanged, not re-targeted here) | 0.468256 (rank-165) / 0.289329 (1% FAR) | for reference only — `cosine_genuine` is a fixed policy gate, not FAR-fit |

Boundary pairs (for anyone re-verifying): LBPH rank-165 = `Joao_Rocha` vs
`Thabo_Mbeki`; LBPH rank-165226 = `Deepa_Mehta` vs `Jim_Talent`; SFace
rank-165 = `Ray_Allen` vs `Stacey_Jones`; SFace rank-165226 = `Donna_Ralston`
vs `Sadie_Frost`.

## What's surprising: the LBPH numbers moved a lot — CORRECTED 2026-08-02, it's the crop, not the detector

77.77 vs 67.01 (tau_accept-equivalent) and 88.49 vs 76.85 (tau_reject-equivalent)
are large gaps for the *same dataset, same seed, same per-identity image picks*.

**Original explanation below (detector mismatch) is WRONG — falsified by a
like-for-like test.** Keeping the original text for the record, then the
correction:

- The frozen `tau_accept` (67.0084 at the time) was derived by
  `scripts/archive/run_lfw_lbph_native_predict_independence.py`, which detects faces
  with a **Haar cascade** and skipped 46 of 5,749 identities (no face found,
  `--min-face-size 40`) — final N=5,703 (`docs/audits/STATE-07-28.md` §1.2).
- This hybrid run detects faces with **YuNet** (`create_face_detector("yunet")`,
  the same detector the deployed hybrid pipeline actually uses end-to-end) and
  kept **all 5,749** identities — zero skips.
- ~~Different detector -> different face boxes -> different Tan-Triggs-normalized
  LBPH tiles -> different chi-square distances, even off the identical source
  photos. The two `tau_accept` numbers are not measuring the same face-crop
  pipeline.~~ **This diagnosis was never isolated as a controlled variable —
  detector and crop-mode both changed at once between the two runs compared.**

**Correction (2026-08-02):** ran the same box-cropped standalone script with
the **YuNet** detector instead of Haar — isolating detector as the only
variable — and got **67.03325520645528**
(`reports/independence/lbph_lfw1/native_predict_scale_yunet.json`), landing
right next to the old Haar-standalone 67.0084 and nowhere near this run's
77.769348. Swapping the detector alone does not reproduce the gap. What *does*
differ between the two `tau_accept`-producing runs is crop: this hybrid run's
`independence_test.py` feeds LBPH the **whole frame**
(`normalize_face(gray, ...)`), while both the standalone scripts and actual
deployment (`LBPHAdapter._normalize`, `src/hybrid/recognizer.py:190`) feed it
the **detected face box**. A direct crop-mode A/B on the same detector
(`cv-workspace-map` §3.2) measured cropped 67.03 vs full-frame 74.64 — most of
this run's 77.77 gap, with the small remainder plausibly sampling/rank noise.
**Conclusion: 77.769348 is a box-crop harness artifact from `independence_test.py`,
not a legitimate YuNet-vs-Haar recalibration. Not adopted; `gate.tau_accept`
instead unified with the standalone value (67.03325520645528) — see
`FROZEN_THRESHOLDS.md` and `docs/audits/STATE-08-02.md`.**

Practically: the previously-deployed `tau_accept`=67.0084 was measured on a
detector (Haar) that isn't the one running in production (YuNet). That's
still true and still worth fixing — which is exactly what the 2026-08-02
YuNet-standalone re-derivation (67.03325520645528) did, **without** also
picking up this run's full-frame crop bug. This run's own tau_accept number
is not "the more representative one for what's deployed" as originally
speculated here; it's representative of a crop mode deployment doesn't use.

The SFace `l2` gap (1.031 vs 1.018) is much smaller (~1.3%) and in the
direction you'd expect from a supplied-not-derived value landing close to,
but not exactly on, an independence-test boundary — no detector-mismatch
story needed there (SFace's own embedding pipeline already used YuNet+SFace
in whatever produced the 1.018 supply, presumably).

## Why a separate doc (not merged into FROZEN_THRESHOLDS.md)

`FROZEN_THRESHOLDS.md`'s LBPH number comes from an LBPH-only sweep (no SFace,
no gate) and its SFace number was supplied externally, never independence-tested
in this repo at all. This doc's numbers come from one run that scores LBPH,
SFace, and the cascade gate together on the same probes — a different
methodology answering "what does the deployed joint pipeline see," not "what
does LBPH alone see." Conflating the two tables would make it look like one
protocol produced both, which isn't true.

## Reproduction

- Selection manifest (pins the exact per-identity image used, sha256-verified
  by the test before running):
  `docs/features/BATCH_WORK/selection_manifest_lfw1_hybrid.json`
  (sha256 `061d17d8ce3502400bc4df76c068a16e2589de5aba1baf235a76d381335e1e81`).
  Built to replicate `scripts/pipeline/run_lfw_independence.py::select_probes`'s exact
  picks (same seed=42, same sorted-identity iteration order) since
  `scripts/utils/make_selection_manifest.py` can't be used for raw LFW — it imports
  `select_one_image_per_person`, which hardcodes `light_front.jpg`
  (La Salle DB1 convention) and raises on LFW's arbitrary filenames.
- Run: `python -m src.hybrid.independence_test --dataset-dir data/lfw-dataset
  --output-dir reports/independence/hybrid/lfw1_2026-07-28 --thresholds-json
  src/hybrid/thresholds.json --iterations 1 --selection-manifest
  docs/features/BATCH_WORK/selection_manifest_lfw1_hybrid.json --random-seed 42
  --no-plots`
- Exact-rank extraction (bypasses a real bug in the test's own rank report —
  see next section): `python scripts/archive/extract_hybrid_unidirectional_ranks.py
  --npz reports/independence/hybrid/lfw1_2026-07-28/_raw_runs/run_1/records.npz
  --rank 165 --rank 165226`
- Raw artifacts: `reports/independence/hybrid/lfw1_2026-07-28/summary.json`
  (aggregate) and `_raw_runs/run_1/{summary.json,records.npz,comparisons.csv}`
  (per-iteration; `comparisons.csv` is ~11.5 GB, not committed).

## Three things fixed in `src/hybrid/independence_test.py` to get here

Kept as permanent fixes (not reverted after this run) since they're correctness/
performance bugs independent of this specific threshold question:

1. **Rank report wasn't unidirectional.** The script scores every *ordered*
   (i, j) pair (both directions) because the cascade-gate simulation needs
   each probe's full nearest-neighbor row against all other identities — that
   part can't be halved. But the rank-based FAR/threshold report (what
   `tau_accept`/`l2_genuine` come from) only needs the marginal distance
   distribution, which is mirror-symmetric. It was built from the full
   ordered array (double-counting every pair), inflating apparent sample size
   2x. Fixed: `main()` now filters to `query_idx < candidate_idx` before the
   rank report, with an assertion that exactly half the ordered pairs survive
   (catches a non-symmetric distance metric silently corrupting the mapping).
2. **Rank report's FAR%% math was capped at a 500,000-pair pool.** On small
   datasets (La Salle DB1, 756 pairs) this was invisible. On full LFW1
   (16.5M unique pairs) `error_pair_report`'s `n = len(records)` was
   `min(unique_pairs, 500_000)`, not the true unique-pair count — so
   `realized_far_ppm` was inflated ~33x for anything computed from the
   default `--target-far-ppm` auto-rank-selection. Ranks *up to* 500,000 still
   report the correct raw threshold value at that rank; only the printed
   FAR%% for those, and the default spec's auto-picked rank, were wrong. The
   test now prints a `[WARN]` when this cap is active; `scripts/extract_hybrid_
   unidirectional_ranks.py` computes FAR correctly regardless.
3. **`--no-plots` was silently ignored.** `_write_hybrid_plots()` was called
   unconditionally, running KDE curves over all 33M raw distances twice per
   engine (histogram + curve plot) plus a FAR curve — this was the actual
   bottleneck stalling the aggregation stage for 20+ minutes on the first
   attempt. Now gated on `args.plots`.
4. **LBPH sweep is now multiprocessed.** `predict_collect()` (one native call
   per query row, O(N) each inside OpenCV's C++) is independent per row with
   no shared mutable state, so it's now spread across a `ProcessPoolExecutor`
   (each worker trains its own recognizer once via the pool initializer, then
   serves per-row predict requests). Falls back to the original serial loop
   when only 1 worker is available. Verified bit-identical FP counts/boundary
   pairs against the pre-parallel serial run at N=300 before trusting it at
   full scale.
