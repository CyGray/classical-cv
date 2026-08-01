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
- **Frozen thresholds:** the hybrid gate's LBPH `tau_accept` (**67.0084**, as of
  2026-07-28) and the SFace genuine L2 distance (**1.018**, as of 2026-07-28)
  are frozen (SHA-256 recorded by the evidence matrix) — see
  `docs/READ THIS/FROZEN_THRESHOLDS.md` before changing either.
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

  | Threshold | LS-DB1 (2026-07-20, superseded) | LFW1 partial-diagnostic (2026-07-21, superseded, `scripts/pipeline/lfw_all_families_verify.py`, 575 ids) | **LFW1 full (2026-07-28, deployed)** |
  |---|---:|---:|---:|
  | LBPH `tau_accept` | 70.6089 | 81.04 (100 ppm FAR) / 88.40 (1% FAR) | **67.0084** (rank-165 unidirectional unique pair, ~10 ppm FAR, 5,703 ids) |
  | SFace `l2_genuine` | 1.106796 | 1.3553 (impostor-L2 mean) | **1.018** (supplied by SFace sub-team) |
  | LBPH `tau_reject` | 76.85 (LFW-carried, `tar_at_far.md`) | 76.85 (unchanged) | 76.85 (unchanged) |
  | SFace `cosine_genuine` | 0.363 | 0.363 (unchanged) | 0.363 (unchanged) |

  **This flips the 2026-07-21 escalation-band finding.** That audit found the
  LFW1-diagnostic accept edge (81.04) sat *above* `tau_reject` (76.85), so the
  escalation band was empty and the cascade collapsed to LBPH-only on LFW. The
  now-deployed `tau_accept` (67.0084) sits well *below* `tau_reject`, reopening
  a normal [67.0084, 76.85] escalation band — re-verify
  [`docs/audits/STATE-07-21.md`](docs/audits/STATE-07-21.md) §7's conclusion
  before citing it; it describes the pre-2026-07-28 configuration.
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