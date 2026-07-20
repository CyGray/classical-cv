# LS-Face / Smart Gate — Agent Guide

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

## Engineering Standards

- **Minimal edits:** surgical updates only; do not refactor unrelated code.
- **Conventions:** follow existing naming and structure; `argparse` for CLI
  tools; `pathlib` for paths; no hardcoded absolute paths.
- **Validation:** new features or fixes must be validated with tests or by
  running the relevant script.
- **Frozen thresholds:** all thresholds are derived once on La Salle DB1 and
  frozen (SHA-256 recorded by the evidence matrix). Other datasets (LS-DB2,
  LFW) are transfer legs — never re-tune on them. The hybrid gate's LBPH
  `tau_accept` (70.6089) and the SFace genuine L2 distance (1.106796) are
  frozen as of 2026-07-20 — see `docs/READ THIS/FROZEN_THRESHOLDS.md` before
  changing either.
- **Independence tests** (LBPH, Eigenfaces, Fisherfaces): La Salle DB1 uses exactly one fixed, deterministic `light_front` image per identity (no per-run variation). Large datasets like LFW use 10-fold repetition with different seeds; raw results in `_raw_runs/run_X/`; aggregate by mean; keep the 0–100 normalized distance scaling.

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

- **LFW2 41-Modification Benchmark (`scripts/run_lfw2_robustness.py`)**:
  - **Workload**: 235,709 probes (5,749 identities $\times$ 41 modifications).
  - **Empirical Execution Time**: **1 hour 52 minutes 52 seconds** (112.8 minutes total wall-clock time) when run on 16 CPU cores / 15.9 GB RAM with `--num-workers 10`.
  - **Per-Probe Latency**: $\sim 28\text{ ms}$ per probe (YuNet detection + SFace ONNX + LBPH distance + gate evaluation across 3 modes under 10-worker CPU core contention). (Measured before the `parallel` mode was dropped; 3 modes now run instead of 4.)