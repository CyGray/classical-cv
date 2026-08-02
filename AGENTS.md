# Workspace Agent Guidelines & Memory (Computer Vision Root)

## Primary Directive: Code Intelligence & Exploration

- **ALWAYS use Codegraph first for codebase exploration**: Before performing any text search (`grep`) or raw file reads, ALWAYS use Codegraph (`codegraph_explore` / `codegraph_context` MCP tools, or the `codegraph` CLI) for symbol discovery, architecture exploration, call graph analysis, and evaluating change blast-radius.
- When calling `codegraph_explore`, pass the absolute path to the project as `projectPath`.
- On Windows PowerShell, if calling the CLI directly, bypass execution policy if needed: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process; codegraph ...`.

---

## Check Project Maps First — in this order

1. `.claude/skills/cv-workspace-map/SKILL.md` (workspace root) — what this
   directory is, which sibling repo is runnable, and why the threshold
   values quoted later in this file may be stale (read
   `classical-cv/src/hybrid/thresholds.json` for the deployed value, not the
   "Metric Contracts" section below — see that skill's Sec 2).
2. `.claude/skills/robustness-protocol-map/SKILL.md` (workspace root) —
   before running/editing `accuracy_ratio_hybrid.py`,
   `accuracy_ratio_verification.py`, or `run_lfw2_robustness.py`, or before
   quoting/comparing any AR, GAR, TPIR, Rank-1, or EER number from the
   41-modification robustness suite.
3. `classical-cv/.claude/skills/cv-repo-map/SKILL.md` — independence-test
   script selection, LBPH distance scales, `data/` folder contents.
4. Not using Claude Code (no Skill tool available)? Read `GEMINI.md`
   (workspace root) — a self-contained mirror of all three skills above.

Also check `classical-cv/docs/READ THIS/` before editing files that touch
threshold provenance.

---

## Workspace Structure

- `classical-cv/` — Classical computer vision track (LBPH, Eigenfaces, Fisherfaces) and the Hybrid Recognizer cascade (`src/hybrid/`).
- `deep-learning/` — Deep learning track features, embeddings, and reference evaluations (SFace, ArcFace, FaceNet).
- `face-detection-g3/` — Auxiliary face detection and evaluation modules.
- `preprocess/` — Face preprocessing and alignment pipeline.
- `reports/` — Root report outputs (`reports/independence/`, benchmark summaries, figure artifacts).
- `scripts/` — Project orchestration, plotting, and report generation scripts.

---

## Metric Contracts & Deployed Thresholds

**Prose values below may be stale — see "Check Project Maps First" above.
`thresholds.json` is the only runtime source of truth.**

- **Native Predict Distance Scales**:
  - **LBPH**: Raw Chi-Square distance (via OpenCV `predict_collect`).
  - **SFace**: Raw L2 distance (`FR_NORM_L2`, Euclidean distance $\sqrt{2 - 2 \cdot \text{cosine}}$).

- **Canonical Standalone vs. Hybrid Thresholds (CRITICAL — DO NOT CONFUSE)**:
  - **Standalone LBPH (`cv_only`) Canonical Threshold (`tau_accept`)**: **`67.0084`**
    - Provenance: LFW1 rank-165 unidirectional unique-pair impostor distance ($\sim 10\text{ ppm}$ FAR, native `predict_collect` scale), matching La Salle DB1 frontal-crop tolerances.
    - **Rule:** Never overwrite or revert `67.0084` to `77.7693` or `76.7922` for standalone LBPH tests.
    - **Domain Shift Note:** On unconstrained, in-the-wild LFW2 images, clean AR at `67.0084` is **`1.74%`** (median clean distance $\sim 72.82$). This low AR is expected and serves as empirical proof of why classical LBPH requires the hybrid cascade (`SFace`) on wild images.
  - **Hybrid Cascade Gate Accept Edge (`gate.tau_accept`)**: **`77.7693`** (YuNet joint hybrid run $\sim 10\text{ ppm}$ FAR accept edge).
  - **Hybrid Cascade Gate Reject Edge (`gate.tau_reject`)**: **`88.4927`** ($\sim 1.0\%$ FAR confident-reject edge).
  - **SFace Genuine Threshold (`sface.l2_genuine`)**: **`1.0313`** (YuNet joint hybrid run $\sim 10\text{ ppm}$ FAR).
  - **LFW Impostor 1.0% FAR Sensitivity Point**: **`76.7922`** (from `tar_at_far.json`; used only for diagnostic sensitivity studies such as `docs/experiments/standalone_lbph_robustness/THRESHOLD_CHANGE.md`).

---

## Codebase Navigation & API Efficiency Rules

- **LBPHAdapter API:** In `src/hybrid/recognizer.py`, `LBPHAdapter` exposes `.score(sample) -> LBPHMatch` (which returns `.name` and `.distance`), NOT `.predict()` or `.predict_collect()`.
- **Face Detector API:** In `src/classical_faces/detection.py`, `create_face_detector(backend="yunet")` requires the backend string argument (e.g., `"yunet"`).
- **Benchmark Smoke-Testing:** For rapid LFW2 robustness smoke tests, pass `--limit-identities 575` (`10%` subset, `172` clean probes) to `run_lfw2_robustness.py` to iterate quickly before launching full runs.
