---
name: cv-workspace-map
description: >
  Navigation map for the "Computer Vision" workspace root (USLS CV Group 3,
  LS-Face / Smart Gate). Covers what this directory actually is (a folder
  holding two independent git repos, not a repo itself), which sibling repo is
  runnable on this machine and which is not, where the ONE runtime source of
  truth for hybrid thresholds lives versus the five prose documents that
  currently disagree with it, and the cross-repo traps that have already
  produced wrong numbers: two non-comparable LBPH distance scales, cropped vs
  full-frame LBPH tiles, and same-filename/different-pixel LFW copies. Use this
  BEFORE reading root AGENTS.md as fact, before quoting or writing any
  threshold value, before running anything under deep-learning/, before
  comparing an independence-test number against another one, and whenever a
  path, report, or doc exists at both the workspace root and inside
  classical-cv/ under a similar name. For classical-cv internals (which
  independence script to run, data/ folder contents) defer to the cv-repo-map
  skill inside that repo.
---

# Workspace map: Computer Vision root

This is the **workspace root**, not a project. It holds two unrelated git repos
plus some inert directories. `classical-cv/` has its own, deeper navigation
skill (`cv-repo-map`) — this file covers only what spans repos or what the root
gets wrong. Read this first, then hand off.

*Facts below verified 2026-08-01. Anything marked **verify** changes over time —
check it, don't quote it.*

## 0. The two mistakes this workspace causes most

1. **Trusting a threshold number found in prose.** Six different files state
   hybrid threshold values and they do not agree (§2). Only one is loaded at
   runtime. Copying a number out of a doc into config, or into a paper, without
   checking the runtime file has already happened.
2. **Comparing two independence-test numbers that measure different things.**
   The same nominal quantity (`tau_accept`) is produced by pipelines that differ
   in distance scale, in whether the face is cropped, and in which copy of LFW
   they read (§3). Two such numbers being far apart is usually a pipeline
   difference, not a finding.

## 1. What is actually here

The root itself is **not a git repository** — `git rev-parse` fails here. Run
git commands inside a subdirectory, never at root.

| Path | What it is | Runnable here? |
|---|---|---|
| `classical-cv/` | **Git repo.** The live project: LBPH / Eigenfaces / Fisherfaces and the hybrid LBPH+SFace cascade (`src/hybrid/`). Has its own `AGENTS.md` + `.claude/skills/cv-repo-map`. | **Yes** — this is where work happens. |
| `deep-learning/` | **Git repo** (has commits; `archive/` is untracked). SFace / ArcFace / FaceNet feature extraction and threshold scripts. | **No.** `loader.py:10-12` hardcodes `D:/FILES/PROGRAMMING/...` dataset roots and there is no `D:` drive on this machine. Treat DL work as plan-only; write plans into `classical-cv/docs/`. |
| `face-detection-g3/` | **Empty.** Contains only `.codegraph/` — no source, no data. Root `AGENTS.md` describes it as "auxiliary face detection and evaluation modules"; that is false as of 2026-08-01. | No — nothing to run. |
| `docs/`, `reports/`, `scripts/`, `archive/` | Small root-level output/aggregation dirs. Not the project's main docs or reports — those live inside `classical-cv/` (§4). | — |
| `.codegraph/` | Codegraph index for the workspace. The `codegraph_*` MCP tools are not always connected in a given session; if they aren't, fall back to `rg`/`fd`. | — |

Root `AGENTS.md` also lists a `preprocess/` directory at root. **It does not
exist.** Do not build paths from that file's structure section.

## 2. Thresholds: one runtime file, five disagreeing narrators

**The only value that is deployed is what `classical-cv/src/hybrid/thresholds.json`
contains.** That is the file `load_thresholds()` reads. Everything else is
narrative and may be stale, aspirational, or describing a different run.

Known state as of 2026-08-01 — **an unresolved conflict, not a resolved one**:

| Source | What it says about `tau_accept` | Status |
|---|---|---|
| `classical-cv/src/hybrid/thresholds.json` | 77.7693 | **Loaded at runtime.** |
| root `AGENTS.md` | 77.7693, labelled "Frozen Deployed" | Matches runtime. |
| `classical-cv/docs/READ THIS/FROZEN_THRESHOLDS.md` | 67.0084 | Contradicts runtime. |
| `classical-cv/docs/READ THIS/FROZEN_THRESHOLDS_HYBRID.md` | 77.769348, explicitly *"candidate, not adopted — thresholds.json was NOT changed by this run"* | Self-contradicting: the value it says was not adopted **is** what runtime now loads. |
| root `reports/independence/independence_report.md` | a mixed table (70.6089 / 67.0084 / 76.85) | Stale; also mislabels the scale (§3.1). |
| `classical-cv/.claude/skills/cv-repo-map` | 67.0084 | Stale. |

Rules that follow from this:

- **Read `thresholds.json` to learn the deployed value. Always.** Never quote a
  threshold from a doc, this skill included — which is why no "current value"
  table appears here.
- **A doc saying "frozen" does not mean the config matches it.** Verify both.
- Before changing any threshold, `FROZEN_THRESHOLDS.md`'s "Where these values
  live (keep in sync)" section lists four locations that must move together
  (`thresholds.json`, `src/hybrid/gate.py` fallback, `src/hybrid/calibrate.py`,
  `src/sface/recognizer.py`). **verify** that list is still accurate.
- There is an open question, as of 2026-08-01, about whether the deployed
  77.7693 is correct at all — it was derived from full-frame (uncropped) LBPH
  tiles (§3.2). Do not "fix" the docs to match the config, or the config to
  match the docs, without resolving that first.

## 3. Why two independence numbers disagree — three independent causes

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

## 4. Same name, different thing: root vs classical-cv

Two parallel trees use similar names for unrelated content. Always state which
one you mean, and prefer the `classical-cv/` one for anything current.

| Root | classical-cv | Note |
|---|---|---|
| `reports/independence/` — a small hand-assembled summary + PNGs | `reports/independence/` — the actual per-run artifact tree (`lbph_lfw1/`, `hybrid/`, ...) | Different content, same relative path. |
| `AGENTS.md` — 32 lines, workspace-level, contains stale claims (§1, §2) | `AGENTS.md` — the real engineering standards | When they conflict, classical-cv wins on project matters. |
| `docs/`, `scripts/` | `docs/`, `scripts/` | Root versions are aggregation/reporting only. |

## 5. Environment

- **Python:** global Python 3.11 on Windows. No `.venv` in `classical-cv`. The
  "Termux/Android" setup described in `classical-cv/AGENTS.md` is another
  contributor's machine — ignore it here.
- **Shell:** PowerShell primary; a Bash tool is also available. `rg` and `fd`
  are installed.
- **Disk is the binding constraint** — **verify** free space before any full-LFW
  hybrid run. `src/hybrid/independence_test.py` writes two per-pair
  `comparisons.csv` files at ~11.5 GB each (33M rows) at full LFW1 scale. Use
  `scripts/archive/run_hybrid_independence_no_pair_csv.py`, which suppresses
  both and still writes `records.npz` + `summary.json` (all the rank extractor
  needs).
- **No `D:` drive**, which is what makes `deep-learning/` unrunnable (§1).

## 6. Where to go next

- **classical-cv internals** — which independence script for which dataset, what
  each `data/` folder holds, ordered vs unidirectional pair counts, plotting
  conventions: `classical-cv/.claude/skills/cv-repo-map`. Start there for any
  actual run.
- **Engineering standards, project structure:** `classical-cv/AGENTS.md`.
- **Threshold history and change records:** `classical-cv/docs/audits/STATE-*.md`
  (dated; read the newest first and check its date against the config).
