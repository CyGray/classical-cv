# LS-Face / Smart Gate — Agent Guide

> **Fast path:** from this subproject, read [`../AGENT_START_HERE.md`](../AGENT_START_HERE.md)
> first, then use the repo-specific map at
> `.claude/skills/cv-repo-map/SKILL.md`. The root guide handles cross-project
> paths and canonical result provenance; this file handles project internals.

Face recognition research project (USLS Computer Vision, Group 3). Classical CV
recognizers (LBPH, Eigenfaces, Fisherfaces) plus a hybrid LBPH→SFace cascade,
selected via independence testing. Deliverable: the IW-FCV 2026 paper at
`docs/PAPER.md` (edit instructions in `docs/READ THIS/INSTRUCTIONS.md`).

## Project Structure

- `main.py` — interactive launcher; the entry point for every train / evaluate /
  live-detect / independence-test / benchmark action.
- `src/`
  - `lbph/`, `eigenfaces/`, `fisherfaces/` — classical pipelines (the only
    recognizer families in this repo, besides SFace below).
  - `classical_faces/` — shared classical pipeline core (datasets, detection,
    preprocessing, variants).
  - `sface/` — SFace embedding recognizer; the DL half of the hybrid. Not a
    standalone track.
  - `hybrid/` — LBPH fast path + SFace escalation cascade (enroll, evaluate,
    calibrate, gate, joint independence test). Modes: `cascade` (deployed),
    `cv_only`, `dl_only` — the `parallel` (run-both) mode was removed.
  - `benchmark/` — cross-model comparison, TAR@FAR, 41-mod accuracy ratio,
    evidence matrix, aggregation.
  - `independence_common.py`, `stats_utils.py`, `dataset_layout.py`,
    `reporting/` — shared utilities.
- `scripts/` — orchestration and figure scripts, dataset augmentation
  (`augment_split_light_medium.py`), and `independence_failure_check/`
  (post-hoc failure-analysis scripts).
- `models/` — trained artifacts. `models/yunet/` holds the shared YuNet
  detector ONNX used by the classical YuNet option, SFace, and the hybrid.
- `reports/` — all generated results: `independence/`, `figures/`,
  `independence_failure_check/` (raw CSV runs + aggregated JSON + plots),
  plus untracked `evaluation/` and `benchmark/` outputs.
- `data/` — datasets (managed externally, gitignored).
- `docs/` — `PAPER.md`, `READ THIS/` (briefing, audit, paper instructions,
  CFP), `reports/` (finished write-ups), `figures/`, `changelogs/`,
  `archive/` (superseded plans and prior report drafts).

For every new or regenerated manuscript visual, first read
`../scripts/visualization/README.md`: use Matplotlib for data-driven charts,
Graphviz for structural diagrams, and SVG as the primary export. Do not rename
or convert historical result rasters in place; regenerate an SVG from recorded
data only after the applicable provenance checks pass.

## Candidate Improvements & Major Experiments

When asked for performance optimizations, latency reductions, or candidate model enhancements, check [`../docs/experiments/major/`](../docs/experiments/major/README.md):
1. **[`../docs/experiments/major/architecture/`](../docs/experiments/major/architecture/README.md)**: **Quality-First Early-Bypass Routing** (evaluates quality before LBPH; eliminates 43.29% of LBPH calls, cuts dual inference from 77.61% to 34.32%, reduces cascade latency by 18.27% from 11.96 ms to 9.77 ms with 100% bit-for-bit decision equivalence across all 2,296 DL41 conditions).
2. **[`../docs/experiments/major/lbph_config/`](../docs/experiments/major/lbph_config/README.md)**: **Multi-Scale `r3_n8_g6x6` Descriptor** (radius=3, grid=6x6; improves Rank-1 accuracy by +11.07 pp on LSDB, cuts template memory by 43.75% from 64 KB to 36 KB, and reduces Chi-Square prediction latency by ~42%).

## Engineering Standards

- **Minimal edits:** surgical updates only; do not refactor unrelated code.
- **Conventions:** follow existing naming and structure; `argparse` for CLI
  tools; `pathlib` for paths; no hardcoded absolute paths.
- **Validation:** new features or fixes must be validated with tests or by
  running the relevant script.
- **Frozen thresholds — read `src/hybrid/thresholds.json`, never a prose file
  (including this one).** `load_thresholds()` reads that JSON and nothing else;
  the values quoted in prose here and in `docs/READ THIS/FROZEN_THRESHOLDS.md`
  have gone stale before and are stale again as you read this.
  **Superseded 2026-08-01:** the `tau_accept` 67.0084 / `l2_genuine` 1.018 pair
  described below was replaced by YuNet joint-hybrid-derived values — see the
  table's last column. Two threshold *families* now exist: **joint-hybrid**
  (deployed; what the cascade uses) and **standalone single-engine** (what the
  `cv_only` / `dl_only` benchmark modes must use). They are not
  interchangeable, and mixing them silently scores the two standalone engines
  at different FARs. Full detail: the `cv-repo-map` skill §3. See
  `docs/READ THIS/FROZEN_THRESHOLDS.md` before changing any of them.
  **Protocol change (2026-07-28):** `tau_accept` is now derived directly on
  **LFW1** (previously the rule below held: derive once on La Salle DB1, treat
  other datasets as never-re-tuned transfer legs). This was a deliberate,
  explicit instruction, not an oversight — see
  [`docs/audits/STATE-07-28.md`](docs/audits/STATE-07-28.md) for the full
  record and what it changes about cascade behavior. `l2_genuine` was supplied
  directly by the SFace sub-team and not re-derived here.
- **Deployed vs. superseded thresholds — history, not a live choice.** The
  table below is provenance, not alternatives to pick between; the current
  deployed values are the last row.

  | Threshold | LS-DB1 (2026-07-20, superseded) | LFW1 partial-diagnostic (2026-07-21, superseded, `scripts/pipeline/lfw_all_families_verify.py`, 575 ids) | LFW1 full, Haar, LBPH-only (2026-07-28, superseded) | LFW1 YuNet joint-hybrid (2026-08-01, historical run record — **superseded, NOT deployed**, see below) |
  |---|---:|---:|---:|---:|
  | LBPH `tau_accept` | 70.6089 | 81.04 (100 ppm FAR) / 88.40 (1% FAR) | 67.0084 (rank-165 unidirectional unique pair, ~10 ppm FAR, 5,703 ids) | 77.7693 (rank-165 unidirectional unique pair, ~10 ppm FAR, YuNet, 5,749 ids) — **rejected 2026-08-02, box-crop harness bug** |
  | SFace `l2_genuine` | 1.106796 | 1.3553 (impostor-L2 mean) | 1.018 (supplied by SFace sub-team) | 1.0313 (rank-165 unidirectional unique pair, ~10 ppm FAR) — **still deployed, resolved 2026-08-02 as immaterial vs. standalone** |
  | LBPH `tau_reject` | 76.85 (LFW-carried, `tar_at_far.md`) | 76.85 (unchanged) | 76.85 (unchanged) | 88.4927 (rank-165,226 unidirectional unique pair, ~1% FAR) — **superseded 2026-08-02, canonized to 140.13 via a different method** |
  | SFace `cosine_genuine` | 0.363 | 0.363 (unchanged) | 0.363 (unchanged) | 0.363 (unchanged) |

  **Currently deployed (`src/hybrid/thresholds.json`, 2026-08-02 — read that
  file, not this table, for the live value):** `gate.tau_accept =
  `cv_only`; not the 77.7693 shown above), `gate.tau_reject = 140.13`
  (canonized via `docs/independence/TAU_REJECT_METHOD.md`, not shown above —
  no historical row for it, it's a genuine-percentile/permissive-choice pick,
  not an impostor-FAR one), `sface.l2_genuine = 1.0313` (unchanged, this
  table's own 2026-08-01 column value). Full trail:
  `docs/independence/MASTER_FILE.md`, `docs/audits/STATE-08-02.md`.

  > **CRITICAL STANDALONE LBPH RULE (`cv_only`)**: For standalone LBPH (`cv_only`) robustness and benchmark evaluations, the canonical threshold is **`tau_accept = 67.03325520645528`** (LFW1 rank-165 unidirectional unique-pair impostor distance, native `predict_collect()` scale, **box-cropped** — supersedes the 67.0084 Haar-standalone figure this callout stated before 2026-08-02; the two are the same derivation method on a different detector and land within 0.03 of each other). As of 2026-08-02 this is now ALSO `gate.tau_accept` (unified, see `docs/independence/MASTER_FILE.md` row 4) — do not overwrite it with 77.7693 (rejected joint-hybrid candidate, box-crop harness bug) or 76.7922 (LFW 1% FAR diagnostic point). Note: on unconstrained wild LFW2 images, clean AR at this threshold is **`1.74%`** (clean median distance $\sim 72.82$)—this is expected and serves as empirical proof of why classical LBPH requires the hybrid cascade (`SFace`) on wild images.

---

## Codebase Navigation & API Efficiency Rules

- **Check Project Maps First:** Always check `.claude/skills/cv-repo-map/SKILL.md` (or `.gemini/skills/`) and `docs/READ_THIS.md` before editing files to understand architecture and threshold provenance.
- **LBPHAdapter API:** In `src/hybrid/recognizer.py`, `LBPHAdapter` exposes `.score(sample) -> LBPHMatch` (which returns `.name` and `.distance`), NOT `.predict()` or `.predict_collect()`.
- **Face Detector API:** In `src/classical_faces/detection.py`, `create_face_detector(backend="yunet")` requires the backend string argument (e.g., `"yunet"`).
- **Benchmark Smoke-Testing:** For rapid LFW2 robustness smoke tests, pass `--limit-identities 575` (`10%` subset, `172` clean probes) to `run_lfw2_robustness.py` to iterate quickly before launching full runs.

  The 2026-08-01 column is the **joint** family — derived by scoring LBPH,
  SFace and the gate together in one pass. The **standalone** LBPH counterpart
  is 67.03325520645528
  (`reports/independence/lbph_lfw1/native_predict_scale_yunet.json`, LBPH-alone,
  YuNet, 9.986 ppm FAR); SFace has no standalone sweep in this repo at all.
  Part of the joint-vs-standalone gap is that the joint test feeds LBPH the
  whole frame while deployment and the standalone path feed it the cropped face
  box — so whether the deployed joint value is the right operating point is an
  open question, not a settled one.

  **On the escalation band.** The 2026-07-21 audit found the LFW1-diagnostic
  accept edge (81.04) sat *above* `tau_reject` (76.85), so the band was empty
  and the cascade collapsed to LBPH-only on LFW. As of 2026-08-02 the
  deployed band is **[67.03325520645528, 140.13]** — wide by deliberate
  design (see `docs/independence/TAU_REJECT_METHOD.md`): an FRR-vs-escalation
  sweep found no LBPH-separable region between genuine and impostor on wild
  LFW in the 70-170 range, so `tau_reject` was set permissively rather than
  at an (nonexistent) separation point. Consequence: ~97-99% of ALL wild-LFW
  probes, genuine and impostor alike, fall inside this band regardless of the
  exact `tau_reject` value — LBPH's cheap fast path resolves almost nothing
  on wild LFW; nearly everything escalates to SFace (contrast with
  `docs/PAPER.md`'s ~75%-kept-cheap figure, which is La Salle DB1-calibrated,
  a dataset where LBPH separates genuine/impostor much better). Re-verify
  [`docs/audits/STATE-07-21.md`](docs/audits/STATE-07-21.md) §7 and
  [`STATE-07-28.md`](docs/audits/STATE-07-28.md) against
  `thresholds.json` before citing either — both describe earlier
  configurations.
- **Independence tests** (LBPH, Eigenfaces, Fisherfaces): La Salle DB1 uses exactly one fixed, deterministic `light_front` image per identity (no per-run variation). Large datasets like LFW use 10-fold repetition with different seeds; raw results in `_raw_runs/run_X/`; aggregate by mean; keep the 0–100 normalized distance scaling.

## 🟠 Open Findings — benchmark validity (as of 2026-07-21)

**Status: OPEN — awaiting Dr. Oh's confirmation (2026-07-22). Do not action, cite,
or write into `docs/PAPER.md` until then.** Full evidence:
[`docs/audits/STATE-07-21.md`](docs/audits/STATE-07-21.md).

1. **`robustness_lfw2` branch reports are invalid — do not merge or cite.** That
   branch's only commit changes report files, not code; the run was pointed at a
   *pre-aligned* dataset (`*__processed.jpg`, D: machine) instead of raw
   `data/lfw-dataset`. Aligned crops absorb the modifications, so `cv_only` overall
   AR reads 98.12% vs master's 86.66% (rotation 100% vs 68.9%). A local rerun on raw
   LFW with the current frozen thresholds reproduces master (85.58%), confirming the
   dataset — not the thresholds — caused the inflation. The source dataset is not
   present on this machine, so that run cannot be reproduced here.

2. **The `dl_only` AR column is saturated by benchmark design — on every run,
   master included.** In `src/benchmark/accuracy_ratio_hybrid.py`, probes are
   *distorted copies of the enrolled image* (enrollment and probing share
   `select_originals(..., seed=42)`; every `clean` row has `lbph_distance = 0.0`),
   YuNet re-detects and `alignCrop` undoes geometric distortion before SFace embeds,
   the genuine rule (`cosine >= 0.363 AND l2 <= 1.106796`) has huge headroom for
   same-image pairs, and **no impostors are scored at all**. Result: every non-noise
   modification pins to 99.4–99.7%, with only `gaussian_noise` (83.19%) moving.
   **AR is genuine-retention-under-distortion of the enrolled image, measured after
   re-alignment — an upper bound, not recognition accuracy.** Use the impostor sweep
   in `src/hybrid/independence_test.py` (TAR@FAR) for any accuracy claim.

3. **The threshold sweep measures identification accuracy, not the verification
   accuracy the professor's 2026-07-21 figure prescribes.**
   `scripts/pipeline/sweep_gate_curve.py` reports `overall_ar_percent` = closed-set rank-1
   identification on genuine probes only (`matched = ... r["lbph_name"] ==
   r["person"]`, line 189); there are no cross-family (impostor) comparisons, so
   FP/TN are structurally absent — the script itself flags *"FAR/ROC excepted -
   needs impostors"* (line 310). The figure's `(TP+TN)/(TP+TN+FP+FN)` needs
   impostors: "Recognition (family)" = genuine pairs, "Recognition (all)" = impostor
   pairs from all other families. Even with a train/test split the impostor:genuine
   ratio stays `(N_test − 1):1`, so raw accuracy is TN-dominated and near-100%
   regardless of threshold. **Do not present the current sweep as "Recognition (all)"
   accuracy.** Remediation: balanced matched/mismatched pairs (LFW View-2), or report
   TAR@FAR / ROC / EER. Full evidence + math: `docs/audits/STATE-07-21.md` §3.

Rerun artifacts (JSON + MD + probes CSV per segment, harness filename convention,
mergeable via `scripts/utils/merge_robustness_segments.py`) live in
`reports/benchmark/lfw2_robustness_rerun/`.

## Key Resources

- `src/independence_common.py` — `train_and_extract_features`,
  `compute_pairwise_distances`, `aggregate_pairwise_results`.
- `src/stats_utils.py` — Wilson CIs, Fisher's exact test, classifier-diversity
  measures (pure stdlib).
- `docs/READ THIS/BRIEFING.md` — project spec and milestones.
- `docs/archive/` — historical context (superseded plans, prior report drafts,
  the original CODEX task prompt).

## Execution Environment (Termux PRoot Ubuntu)

This project runs inside a **Termux PRoot Ubuntu (aarch64)** container.
- **Python Virtual Environment**: Set up at `.venv/` (Python 3.12.3). Run all scripts using `.venv/bin/python` or activate the virtualenv.
- **System Dependencies**: All required packages in `requirements.txt` are installed, including system-level graphics/helper libraries for OpenCV (`libgl1` and `libglib2.0-0`).
- **Activation Shortcuts**: Shell aliases `cv-activate` and `act-cv` are defined in `/root/.bashrc` to jump to `/root/School/classical-cv` and activate the environment.
- **Git LFS for Datasets**: Large dataset files (images in `data/`) are managed using Git LFS. If images are not readable and appear as ~120-130B text pointers, ensure `git-lfs` is installed and run `git lfs pull` to retrieve the actual binary objects.
- **Viewing Output Plots**: As the environment is headless, you cannot use interactive visual GUI windows (`cv.imshow`). Use the shell utility function `export-cv-figs` (defined in `/root/.bashrc`) to copy generated plots (from `reports/figures/` or specified as arguments) to `/data/data/com.termux/files/home/storage/shared/Pictures/CV_Reports` to view them in the Android Gallery app.
- **Hardware Details**: Deployed on a MediaTek Dimensity 8500 Ultra with 8 GB RAM. The octa-core ARM64 CPU is highly capable for both classical CV (LBPH, Eigenfaces, Fisherfaces) and deep learning (YuNet detector and SFace recognizer via ONNX runtime).

## Benchmark Execution Benchmarks (Agent Memory)

- **LFW2 41-Modification Benchmark (`scripts/pipeline/run_lfw2_robustness.py`)**:
  - **Workload**: 235,709 probes (5,749 identities $\times$ 41 modifications).
  - **Empirical Execution Time**: **1 hour 52 minutes 52 seconds** (112.8 minutes total wall-clock time) when run on 16 CPU cores / 15.9 GB RAM with `--num-workers 10`.
  - **Per-Probe Latency**: $\sim 28\text{ ms}$ per probe (YuNet detection + SFace ONNX + LBPH distance + gate evaluation across 3 modes under 10-worker CPU core contention). (Measured before the `parallel` mode was dropped; 3 modes now run instead of 4.)
