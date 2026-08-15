---
name: cv-workspace-map
description: >
  Navigation map for the Computer Vision workspace (LS-Face / Smart Gate).
  Use before cross-project work, root-vs-classical-cv path/result confusion,
  threshold or deep-learning work, independence-result comparisons, or
  creating/regenerating manuscript figures and diagrams. Route classical-CV
  internals to cv-repo-map and LFW2 protocol questions to
  robustness-protocol-map; use the shared SVG visual-export guide for assets.
---

# Workspace map: Computer Vision root

This is the **workspace root**. As of 2026-08-02 it is itself a single git
repo (see §1's correction) holding two functionally-unrelated subprojects
plus some inert directories. `classical-cv/` has its own, deeper navigation
skill (`cv-repo-map`) — this file covers only what spans repos or what the root
gets wrong. Read this first, then hand off.

*Facts below verified 2026-08-01, with a correction to §2 verified 2026-08-02
(see that section). Anything marked **verify** changes over time — check it,
don't quote it.*

## 0. The two mistakes this workspace causes most

1. **Trusting a threshold number found in prose.** Six different files state
   hybrid threshold values and they do not agree (§2). Only one is loaded at
   runtime. Copying a number out of a doc into config, or into a paper, without
   checking the runtime file has already happened.
2. **Comparing two independence-test numbers that measure different things.**
   The same nominal quantity (`tau_accept`, `l2_genuine`) is produced by
   pipelines that differ in distance scale, in whether the face is cropped,
   and in which copy of LFW they read (§3). Two such numbers being far apart
   is usually a pipeline difference, not a finding — LBPH `tau_accept`'s old
   ~10-unit "joint vs standalone" gap turned out to be exactly this (a
   box-crop-vs-full-frame bug), resolved 2026-08-02 by unifying the two
   families into one value. §3.4.

## Result evidence governance (2026-08-09)

`docs/results/` is canonical, version-controlled evidence. Current manifest:
**62 `canonical_snapshot` artifacts and one `reference_specification`**.
Before citing or comparing, read its category README,
`docs/results/RESULTS_MANIFEST.json`, and
`docs/results/metadata/PROVENANCE_AUDIT.md`. `classical-cv/reports/` and
`classical-cv/outputs/` are raw/working locations, not citation sources.

### Retention: merged results, not worker noise

Keep merged reports and merged supporting data in `docs/results/`. Archive
per-worker/per-segment artifacts under the identical relative path in
`docs/experiments/`; never move a mixed directory wholesale. As of 2026-08-09,
all 64 canonical `*_segNof16` robustness artifacts are archived. The retained
robustness set is three merged reports, the standalone merged probes CSV, the
evidence note, README/reference files, and `TODO.md`.

`docs/experiments/RESULTS_MANIFEST_PRE_PROVENANCE_SORT.json` preserves the
pre-cleanup registry. `RESULTS_MANIFEST_PRE_SEGMENT_ARCHIVE.json` preserves
the pre-segment-archive registry. Artifacts there are not canonical merely
because their filenames match a result.

Artifacts flagged `illustrative_stand_in`, `needs_provenance_review`,
`historical_rerun_required`, or `rerun_required` stay quarantined in
`docs/experiments/`. Do not auto-trace PNGs for Springer: regenerate from
recorded data to SVG/PDF (or EMF on Windows) after provenance clears.

### Canonical rerun contract

Write raw rerun output to
`classical-cv/outputs/provenance_reruns/<run-name>/`. Promote reviewed
summary/CSV/plot snapshots only to
`docs/results/independence_test/reruns/<campaign>/<run-name>/` with sibling
`run_provenance.json`. Record real entrypoint, argv, source-script SHA-256,
Git commit/dirty state, dataset tree hash, crop/preprocessing contract,
seed/iterations, runtime versions, resolved thresholds-file hash/values when
applicable, and comparison-count validation. Run
`scripts/reporting/generate_results_manifest.py` after promotion; documented
reruns (including nested plots) become canonical. A rerun without that record
is `needs_provenance_review`.

`lasalle_processed_2026-08-09` is first verified rerun campaign: LBPH,
Eigenfaces, Fisherfaces, and hybrid clean sweeps, each 28 identities and
756/756 ordered impostor comparisons. It uses pre-cropped La Salle tiles;
it is not an LFW threshold recalibration.

### Algorithm selection is a separate decision from threshold calibration

For the paper's initial algorithm-selection result, the reviewed evidence is
`docs/results/algo_test/lsdb_selection_2026-08-10/`, not the older partial
LFW all-families snapshot. Its deterministic LSDB split uses 224 fit images,
56 calibration images, and 56 held-out test images. The resulting classical
comparison selects LBPH; the external DL artifact retains SFace on
deployment-compatible footprint, without presenting its model-specific
external metrics as a same-harness accuracy ranking.

This campaign is deliberately **LSDB-only**: it selects candidates for the
La Salle deployment domain. Its calibration threshold is local experimental
scaffolding and must not update the frozen LFW verification/cascade thresholds
in `classical-cv/src/hybrid/thresholds.json`. In prose, name the two questions
separately: LSDB selects algorithms; LFW establishes the deployed operating
point.

## Manuscript visual-export route

Before creating or regenerating any figure, chart, graph, or diagram, read
`scripts/visualization/README.md` at the workspace root. It is the shared
export policy: use Matplotlib for data-driven charts/graphs, Graphviz for
structural diagrams, and SVG as the manuscript output. For result figures,
first check the applicable `docs/results/` README, manifest, and provenance
audit; regenerate from recorded data rather than converting or overwriting an
existing PNG run artifact.

## 1. What is actually here

**Correction, 2026-08-02:** the root *is now* a git repository — a single repo
was initialized here (`0169818 feat: initialize root workspace repository
structure`, same day) that absorbed both `classical-cv/` (history preserved
via a `fa80995 Snapshot of classical-cv master state...` commit + merges) and
`deep-learning/` (added fresh, no prior history carried over — its
pre-restructuring commit history, if any existed, is not reachable from
current refs and no separate remote for it is configured; only
`origin` → `classical-cv.git` exists). Run git commands from the workspace
root now; there is no longer a need to `cd` into a subdirectory first. This
supersedes the "not a git repository" claim below and in any doc dated
2026-08-01 or earlier — verify against `git rev-parse --show-toplevel` if in
doubt, don't trust a date-stamped claim in prose.

| Path | What it is | Runnable here? |
|---|---|---|
| `classical-cv/` | Subdirectory of the single root repo (§1 correction) — no longer its own `.git`. Its pre-2026-08-02 history is preserved (`fa80995` snapshot + merges). The live project: LBPH / Eigenfaces / Fisherfaces and the hybrid LBPH+SFace cascade (`src/hybrid/`). Has its own `AGENTS.md` + `.claude/skills/cv-repo-map`. | **Yes** — this is where work happens. |
| `deep-learning/` | Subdirectory of the single root repo (§1 correction) — no longer its own `.git`; `archive/` is untracked. Its pre-2026-08-02 history is not reachable from current refs (added fresh, no separate remote found). SFace / ArcFace / FaceNet feature extraction and threshold scripts. | **No.** `loader.py:10-12` hardcodes `D:/FILES/PROGRAMMING/...` dataset roots and there is no `D:` drive on this machine. Treat DL work as plan-only; write plans into `classical-cv/docs/`. |
| `face-detection-g3/` | **Empty.** Contains only `.codegraph/` — no source, no data. Root `AGENTS.md` describes it as "auxiliary face detection and evaluation modules"; that is false as of 2026-08-01. | No — nothing to run. |
| `docs/` | Workspace-level manuscript, experiment, and canonical evidence material; `docs/results/` is the canonical result store. | — |
| `reports/`, `scripts/`, `archive/` | Root-level working/aggregation and historical material; the active source/report tree remains under `classical-cv/`. | — |
| `.codegraph/` | Codegraph index for the workspace. The `codegraph_*` MCP tools are not always connected in a given session; if they aren't, fall back to `rg`/`fd`. | — |

Root `AGENTS.md` also lists a `preprocess/` directory at root. **It does not
exist.** Do not build paths from that file's structure section.

## 2. Thresholds: one runtime file, five disagreeing narrators

**The only value that is deployed is what `classical-cv/src/hybrid/thresholds.json`
contains.** That is the file `load_thresholds()` reads. Everything else is
narrative and may be stale, aspirational, or describing a different run.

**History, most recent first — 67.0084 was wrong-not-stale on 2026-08-01
(`git log -p` showed a single commit, always 67.0084, never the 77.7693 an
earlier version of this skill claimed was live); then on 2026-08-02 the value
itself genuinely moved, deliberately, to 67.03325520645528** — LBPH
`tau_accept` was **unified** with the standalone single-engine threshold by
design decision (`docs/independence/MASTER_FILE.md`,
`classical-cv/docs/audits/STATE-08-02.md`). The old joint-hybrid candidate
(77.769348) was investigated and **rejected** — it measured a box-crop
harness bug in `independence_test.py`, not a real detector- or
pipeline-driven recalibration (§3.4).

| Source | What it says about `tau_accept` | Status |
|---|---|---|
| `classical-cv/src/hybrid/thresholds.json` | **67.03325520645528** | **Loaded at runtime**, current as of 2026-08-02. Its `provenance` note now correctly describes this as the standalone box-cropped YuNet sweep, superseding the earlier mislabeled "LFW1 YuNet joint hybrid run" description. |
| root `AGENTS.md` | Updated 2026-08-02: **one** unified value, 67.03325520645528, for both `cv_only` and `gate.tau_accept`. | **Matches runtime.** The previous two-value split (67.0084 standalone / 77.7693 "hybrid cascade gate") is gone — corrected in place, with history retained in the doc's own provenance table. |
| `classical-cv/docs/READ THIS/FROZEN_THRESHOLDS.md` | 67.03325520645528 | **Matches runtime.** Updated 2026-08-02 with the crop-bug finding in place of the old value. |
| `classical-cv/docs/READ THIS/FROZEN_THRESHOLDS_HYBRID.md` | 77.769348, marked **rejected 2026-08-02** (correction appended in place; original "candidate, not adopted" framing plus the now-falsified "it's the detector" explanation both kept for the record, struck through) | Consistent — the value was never adopted and is now explicitly ruled out, not just untried. |
| root `reports/independence/independence_report.md` | a mixed table (70.6089 / 67.0084 / 76.85) | Stale (predates even the 2026-08-01 state); also mislabels the scale (§3.1). Left alone — run record, not live config. |
| `classical-cv/.claude/skills/cv-repo-map` | states no fixed value in prose — defers to the runtime file, updated 2026-08-02 | Its §3.1 now documents the unification and why the old family split was a harness bug, not a real distinction, for LBPH specifically (still real for SFace). |

Rules that follow from this:

- **Read `thresholds.json` to learn the deployed value. Always — including
  from this skill.** This skill asserted a wrong value for a full day
  (2026-08-01) before being corrected, and the true value has since moved
  again (2026-08-02, deliberately); a memory or skill saying a threshold "is"
  some number is a claim about when it was last checked, not a fact.
- **A doc saying "frozen" does not mean the config matches it, and a config
  value does not mean its own description string is accurate** — was true of
  the pre-2026-08-02 `thresholds.json` (`provenance` note mislabeled 67.0084
  as a YuNet joint-run output); the current provenance string was corrected
  as part of the same change that moved the value, so check both stayed in
  sync going forward, don't assume they always will.
- Before changing any threshold, `FROZEN_THRESHOLDS.md`'s "Where these values
  live (keep in sync)" section lists four locations that must move together
  (`thresholds.json`, `src/hybrid/gate.py` fallback, `src/hybrid/calibrate.py`,
  `src/sface/recognizer.py`). **verify** that list is still accurate —
  `docs/audits/STATE-08-02.md` also lists the prose docs (both `AGENTS.md`
  files, `FROZEN_THRESHOLDS*.md`) that the JSON-focused list omits but that go
  stale just as fast.
- **LBPH `tau_accept` is no longer split into "standalone" and "hybrid
  cascade" values — it's one value now.** SFace `l2_genuine` is still split
  (joint 1.0313 deployed vs standalone 1.0306278467178345, unresolved,
  `docs/independence/MASTER_FILE.md` row 5) — don't assume the LBPH
  resolution generalizes to SFace without separately checking.

## 3. Why two independence numbers disagree — four independent causes

Before concluding that a threshold "moved," rule these out. They compound.

### 3.1 Two LBPH distance scales

`src/independence_common.py`'s hand-rolled chi-square and OpenCV's native
`predict_collect()` produce **different, non-comparable magnitudes** for the same
pair (roughly 4x apart). Deployed thresholds are on the **native
`predict_collect()`** scale. Root `AGENTS.md` calls the native scale "Raw
Chi-Square distance (via OpenCV `predict_collect`)", which invites exactly this
mix-up — the naming collides, the numbers do not.

Full detail, including which script emits which scale: **`cv-repo-map` §2.**

### 3.2 Cropped vs full-frame LBPH tiles

The two independence paths disagree about what image LBPH sees:

- `scripts/archive/run_lfw_lbph_native_predict_independence.py` calls
  `detect_sample(..., assume_cropped=False)` and normalizes **the detected face
  box**.
- `src/hybrid/independence_test.py` runs YuNet (`:286`) but uses it only for
  SFace alignment and quality probes; LBPH's tile is
  `normalize_face(gray, ...)` at `:302` — **the whole frame**.

This is deliberate and correct for the hybrid test's default dataset
(`data/lasalle_db1_processed`, 100x100 pre-cropped tiles — the tile *is* the
face, and `make_sample()` in `src/hybrid/recognizer.py:90-95` documents the
intent). It is wrong when that test is pointed at raw LFW (250x250 frames with
margin), because deployment crops: `LBPHAdapter._normalize`
(`src/hybrid/recognizer.py:190`) uses `sample.face_gray`.

Measured 2026-08-01, same LFW copy, same seed, same probe picks, same detector,
rank-165 unidirectional: cropped **67.03** vs full-frame **74.64** (+11.4%).
A hybrid-test LBPH number is therefore **not** comparable to a standalone one,
and is not the deployment operating point.

### 3.3 Same filenames, different pixels

Multiple LFW copies exist with **identical directory and file names but
different image content**. `docs/features/BATCH_WORK/selection_manifest_lfw1_hybrid.json`
is pinned to `face-detection-g3/data/lfw-dataset`, which **no longer exists**;
all of its SHA-256 entries mismatch `classical-cv/data/lfw-dataset`, so
`load_selection_manifest()` aborts on it. Regenerate against the copy you are
actually sweeping (`scripts/archive/make_lfw_selection_manifest.py`).

Diagnostic value: LBPH is sensitive to this, SFace barely notices (it aligns via
landmarks). A 4% LBPH shift alongside a 0.06% SFace shift means the image source
changed, not the algorithm.

### 3.4 Joint-hybrid vs standalone derivation — real for SFace, resolved for LBPH (2026-08-02)

The same nominal quantity (`tau_accept`, `l2_genuine`) used to be produced by
a **joint** sweep (LBPH + SFace + cascade gate scored together,
`src/hybrid/independence_test.py`) and by a **standalone** single-engine
sweep, both targeting ~10 ppm FAR. For LBPH they differed by ~10 distance
units — this overlapped §3.2 (the joint test is also the full-frame one).

**2026-08-02: for LBPH, this was never two legitimate families — it was §3.2's
crop bug wearing a "joint vs standalone" label.** Isolated by rerunning the
standalone box-cropped script with the joint test's own YuNet detector (same
detector, only crop mode differs from the joint run): landed at
67.03325520645528, next to the old Haar-standalone number, nowhere near the
joint run's 77.769348. Detector was never the driver (contradicting the
original explanation in `FROZEN_THRESHOLDS_HYBRID.md`, corrected in place);
crop mode was. `gate.tau_accept` is now unified with the standalone value —
one number, one derivation, for both `cv_only` and the cascade's
outright-accept. Full trail: `docs/independence/MASTER_FILE.md`,
`classical-cv/docs/audits/STATE-08-02.md`.

**SFace `l2_genuine` is split in value but the gap is RESOLVED as immaterial
(2026-08-02) — not unified into one number the way LBPH was, but not left
open either.** Joint-deployed 1.0313 vs standalone 1.0306278467178345 (added
2026-08-02) — `reports/independence/sface_lfw1/standalone_l2_yunet.json`
(`classical-cv/scripts/archive/run_lfw_sface_standalone_independence.py`),
rank-165, N=5,749, zero YuNet skips, reproducing the previously-unprovenanced
externally-supplied `1.030628` to 6 dp. **Do not assume the LBPH unification
mechanism generalizes here** — SFace's gap was never a crop-bug artifact like
LBPH's was. Instead it was closed via a different argument: a
band-conditioned diagnostic found that on wild LFW, ~97-99% of ALL probes
land in LBPH's escalation band regardless of `tau_reject` candidate (see
`tau_reject` paragraph below), so the band-conditioned SFace population is
not meaningfully different from the marginal one either derivation measures
— a third independent number (the band diagnostic's own zero-observed-FA
floor, 1.0417) lands within ~1% of both, corroborating "these are the same
number, noise aside." `L2_GENUINE_THRESHOLD` stays 1.0313. **Scoped to
LFW** — La Salle DB1's escalation band is a real, much smaller subset
(`docs/PAPER.md`'s ~75%-kept-cheap figure), so this argument doesn't
transfer there without re-checking. Full comparison:
`docs/independence/MASTER_FILE.md` row 5 (closed). Detail: `cv-repo-map`
§3.1, `docs/experiments/hybrid_sface_threshold/ANALYSIS.md`.

**`tau_reject` was suspect (88.4927, cascade-only, no standalone equivalent
by definition, same full-frame-harness-bug taint as the rejected `tau_accept`
candidate) — CANONIZED 2026-08-02 to 140.13, advisor sign-off.** The right
derivation was NOT a plain box-crop rerun at a different rank (unlike
`tau_accept`) and NOT a plain genuine percentile either — `tau_reject`'s real
cost is asymmetric (FRR on the escalation path vs. impostor escalation into
SFace's reach), so the canon method sweeps `tau_reject` and measures both at
once: `docs/independence/TAU_REJECT_METHOD.md`
(`classical-cv/scripts/pipeline/tau_reject_tradeoff_curve.py`, sweep
70-170). **Finding: no knee** — genuine-probe and impostor-probe escalation
rates track almost 1:1 across the entire range; LBPH does not separate
genuine from impostor distances anywhere in this band on wild LFW (same
conclusion as `robustness-protocol-map` §4's EER-crossover finding, now
confirmed across the whole plausible range, not one point). Given no
candidate trades favorably, 140.13 (heavy-tier p99 genuine LBPH distance,
`docs/experiments/tau_reject/THRESHOLD_ANALYSIS.md`) was adopted as a
deliberate **permissive** engineering choice, not a derived separation bound
— makes the confident-reject branch functionally near-inert on wild LFW
(~97-99% of ALL probes escalate regardless of the exact `tau_reject` value),
favoring SFace escalation since LBPH can't be trusted to reject correctly
here. **Does not generalize to La Salle DB1**, where LBPH separates
genuine/impostor much better. `docs/NOTES.md` item 3,
`classical-cv/docs/audits/STATE-08-02.md`,
`docs/independence/MASTER_FILE.md` row 6.

## 4. Same name, different thing: root vs classical-cv

Two parallel trees use similar names for unrelated content. Always state which
one you mean, and prefer the `classical-cv/` one for anything current.

| Root | classical-cv | Note |
|---|---|---|
| `reports/independence/` — a small hand-assembled summary + PNGs | `reports/independence/` — the actual per-run artifact tree (`lbph_lfw1/`, `hybrid/`, ...) | Different content, same relative path. |
| `AGENTS.md` — workspace-level rules plus the shared fast router | `AGENTS.md` — project-specific engineering standards | The nearest applicable guide governs; use the workspace map for cross-project facts. |
| `docs/` — workspace manuscript, experiment, and canonical-result material; `scripts/` — root orchestration | `docs/`, `scripts/` — project docs and source tooling | Similar names have different scopes; `docs/results/` is the canonical evidence store. |

## 5. Environment

- **Python:** global Python 3.11 on Windows. No `.venv` in `classical-cv`. The
  "Termux/Android" setup described in `classical-cv/AGENTS.md` is another
  contributor's machine — ignore it here.
- **Shell:** PowerShell primary; a Bash tool is also available. `rg` and `fd`
  are installed.
- **Disk is the binding constraint** — **verify** free space before any full-LFW
  run. Full joint LFW independence can emit roughly 23 GB of pair CSVs. The
  historical no-pair wrapper referenced by older notes is not present in the
  live tree. Do not recreate the invalid full-frame LFW harness merely to fill
  a provenance gap.
- **Dataset availability (checked 2026-08-09):**
  `data/lasalle_db1_processed` is present (28 identities / 336 images), but
  raw `data/lasalle_db1` is absent. `data/lfw-dataset` exists but is empty.
  Do not launch LFW1, pairwise-verification, or LFW2 robustness reruns until
  sanctioned raw gallery data is restored and hash-verified.
- **No `D:` drive**, which is what makes `deep-learning/` unrunnable (§1).

## 5b. DL-track robustness test is a different protocol entirely — not comparable to classical-cv AR

`deep-learning/ar-table.py` (verified 2026-08-02 by direct read — the repo
isn't runnable here per §1, but its source reads fine) is the DL team's own
robustness-test script, parallel to classical-cv's LFW2 41-mod benchmark. It
answers a different question and must never be tabled next to a classical-cv
AR number without saying so:

| Axis | classical-cv (`accuracy_ratio_verification.py`) | DL (`ar-table.py`) |
|---|---|---|
| Protocol | Genuine **and** impostor pair scored (Sec 0/1 of `robustness-protocol-map`) | **Genuine-only** — `is_match = dist <= threshold`, no impostor pair ever scored. Same trap `robustness-protocol-map` §1 warns about: an accept-rate wearing an "AR" label. |
| Genuine pair definition | Probe vs a *different* gallery photo of the same identity (gallery/probe-disjoint split) | Modified image vs **the exact same original photo it was damaged from**, matched by filename (`dark_right__rot_90.jpg` -> `dark_right_orig.jpg`) — same pose/lighting condition, not a different photo. Even more lenient than classical-cv's genuine pair. |
| Dataset | LFW (wild, uncontrolled) | **La Salle DB1/DB2** (`dark_right`, `dark_up`, ... pose-tagged filenames) — not LFW at all. |
| Distance formula | LBPH native `predict_collect()`; SFace cosine+L2 dual rule | Per-model, hardcoded in-script: ArcFace = `1 - cosine_sim`; SFace = L2-normalized-then-Euclidean; FaceNet/MobileNet = **raw, unnormalized** Euclidean (embedding magnitude affects distance). |
| Threshold | From an independence sweep, provenance-tracked (§2, `cv-repo-map` §3) | Fixed constants in the script: `{"mobilenet": 0.70, "facenet": 0.80, "arcface": 0.65, "sface": 1.128}` — no visible derivation in this file. `sface: 1.128` is a **sixth** SFace threshold value in this workspace, matching none of the ones `cv-repo-map`/memory track (1.018 / 1.0313 / 1.031255 / 1.192 / 1.030628). |
| Aggregation | Pooled genuine+impostor pairs per tier -> GAR/FAR/Accuracy@tau | Per-category-per-tier rate, then mean-of-tiers per category, then unweighted mean-of-category-means overall. |

**Rule:** a DL-track AR number and a classical-cv AR number share a label and
nothing else — different protocol, dataset, distance formula, threshold
family, and averaging method. Never place them in the same table or sentence
without stating all five differences; a reader (or a thesis committee) will
otherwise assume they measure the same thing.

## 6. Where to go next

- **New or regenerated visual asset**: read `scripts/visualization/README.md`
  first, then apply this map's canonical-result rules and the relevant
  repository/protocol map before using experimental data.

- **classical-cv internals** — which independence script for which dataset, what
  each `data/` folder holds, ordered vs unidirectional pair counts, plotting
  conventions: `classical-cv/.claude/skills/cv-repo-map`. Start there for any
  actual run.
- **Robustness-test protocol** (1-to-N identification vs 1:1 pairwise
  verification vs legacy transform-sensitivity, the two operating points
  `tau_accept` vs EER-swept, and why a protocol switch alone did NOT recover
  the literature 65-75% figure): `.claude/skills/robustness-protocol-map`
  (workspace root). Read before quoting or comparing any AR/GAR/TPIR/Rank-1/
  EER number from the 41-modification suite.
- **Engineering standards, project structure:** `classical-cv/AGENTS.md`.
- **Threshold history and change records:** `classical-cv/docs/audits/STATE-*.md`
  (dated; read the newest first and check its date against the config).
