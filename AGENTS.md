# Workspace Agent Guidelines & Memory (Computer Vision Root)

## Fast entrypoint for all agents

Read [`AGENT_START_HERE.md`](AGENT_START_HERE.md) first. It is the short
workspace router for Codex, Agy/Gemini, Cmdc, and human contributors; this
file retains the detailed safety, provenance, and collaboration rules.

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
4. Not using Claude Code (no Skill tool available)? Read `GEMINI.md` and
   `AGENT_START_HERE.md`; they are the cross-agent routing adapters for the
   detailed maps above.

Also check `classical-cv/docs/READ THIS/` before editing files that touch
threshold provenance.

## Canonical result governance

`docs/results/` is the only canonical, version-controlled result store.
Its four subdirectories separate algorithm selection, complementarity,
independence, and robustness evidence. Read the applicable subdirectory
`README.md`, then `docs/results/RESULTS_MANIFEST.json` and
`docs/results/metadata/PROVENANCE_AUDIT.md` before citing or inserting a
result. Every artifact needs manifest metadata; do not infer provenance from a
filename.

`classical-cv/reports/` and `classical-cv/outputs/` are working/raw output
locations, not citation sources. Robustness tables belong only under
`docs/results/robustness_test/`; never place them in, or use them as evidence
for, `complementarity_test/`. Files marked `illustrative_stand_in`,
`needs_provenance_review`, `historical_rerun_required`, or `rerun_required`
have the citation restrictions defined in the audit.

### Selection results are not deployment calibration

For the initial algorithm-selection Results subsection, use the reviewed LSDB
selection campaign in `docs/results/algo_test/lsdb_selection_2026-08-10/`.
It evaluates the classical candidates on the deterministic La Salle DB1 split:
224 fit images, 56 calibration images, and 56 held-out test images. This
selection evidence determines the best classical candidate (LBPH) and the
deployment-compatible learned candidate (external-team SFace artifact).

Do not use its LSDB operating point to alter, justify, or silently replace the
frozen LFW thresholds. LFW independence evidence calibrates the later deployed
verification/cascade operating point; LSDB selection answers a different
question. State that separation whenever both appear in the manuscript.

## Collaboration memory: this workspace owner

- Prefer decisive execution. When the user says "go", "do it", or "stop
  asking", make safe, scope-preserving assumptions, run the work end-to-end,
  and ask only for a genuinely material missing choice or authority.
- Use short, concrete progress updates while work runs; report completed
  artifacts, numbers, and checks rather than speculative status. Do not claim
  a job is running unless a process or tool invocation is actually active.
- For a requested manuscript version, start from exactly the named baseline
  and include only the explicitly finalized sections. Do not silently merge
  material from a fuller current draft.
- Treat Word layout as an output to verify, not an implementation detail:
  render the edited DOCM to PDF and visually inspect every page containing a
  new or changed table/figure before handoff. Keep captions with their object,
  clear inherited list numbering from table cells, and check wrapping, rules,
  column widths, and figure scale.
- A caption is a layout-bearing semantic object, not merely text with the
  right style name. Table titles must be separate above-table `tablecaption`
  paragraphs; figure names must be separate below-figure `figurecaption`
  paragraphs. Match the macro reference's style definition and clear any
  direct font/paragraph overrides before applying it. Enumerate every caption,
  its effective formatting, and its relative object position before handoff.
- A render is evidence only when it depicts the requested output. When Word
  opens a reference document as well as the target, reactivate the target and
  assert `ActiveDocument` before every capture. If PDF export is unreliable,
  use the verified Word PrintWindow capture fallback; visually inspect the
  changed pages and adjacent reflow pages, not a stale or reference window.
- If an independent advisor is requested, use a different model tier from the
  executor. A Terra-led task consults Sol only when the decision warrants it;
  never dispatch Terra as its own advisor.

## Springer manuscript production

For a one-object DOCM micro-edit with an exact named baseline and derivative,
an explicit target, exact replacement content, and a no-change boundary, read
`.claude/skills/springer-docm-targeted-edit/SKILL.md` first. It is the fast,
macro-safe route for a single table, caption, or inline object. Use
`.claude/skills/springer-docm-production/SKILL.md` for all other Springer/LNCS
paper, DOCX, or DOCM work. It covers the official template, `header.png`, current claim
provenance, Word automation, and macro preservation. If macros must survive,
create a new `.docm` copy and verify its `word/vbaProject.bin` hash matches
the named DOCM baseline (or `docs/manuscript/sample/sample.docm` when starting
from the macro specimen); never overwrite or convert the original template.
For every edit to `docs/manuscript/lsface.docm`, archive both the before copy
and final after copy in `docs/manuscript/versions/` using the exact sequential
format `[index]_lsface_[version_name].docm`; read that directory's README and
never substitute timestamped or suffix-index names. If the user explicitly
names a derivative (for example, `009b` from `009`), start from that exact
archive and create exactly that requested derivative—do not advance to a new
number or write the personal-access `docs/manuscript/copy/` source.
Keep generators and helper scripts under `scripts/document-production/`; keep
`docs/` limited to manuscript sources, final office files, templates, visual
references, and evidence documents.

For every new or regenerated manuscript visual, first read
`scripts/visualization/README.md`: use Matplotlib for data-driven charts and
graphs, Graphviz for structural diagrams, and SVG as the primary export. Use
native Word tables for tabular results. Do not auto-trace a PNG into a fake
vector figure. Regenerate a verified SVG from recorded data only after its
manifest status is clear; validate the rendered manuscript output.

---

## Workspace Structure

- `classical-cv/` — Classical computer vision track (LBPH, Eigenfaces, Fisherfaces) and the Hybrid Recognizer cascade (`src/hybrid/`).
- `deep-learning/` — Deep learning track features, embeddings, and reference evaluations (SFace, ArcFace, FaceNet).
- `cascade-porting/` — Raspberry Pi / embedded deployment porting and test suites.
- `porting-sets/` — Porting models, alignment routines, and lightweight feature assets.
- `docs/` — Manuscript sources, LNCS templates, visual references, and evidence documents.
- `scripts/` — Project orchestration, plotting, and report generation scripts.

---

## Metric Contracts & Deployed Thresholds

**Prose values below may be stale — see "Check Project Maps First" above.
`thresholds.json` is the only runtime source of truth.**

- **Native Predict Distance Scales**:
  - **LBPH**: Raw Chi-Square distance (via OpenCV `predict_collect`).
  - **SFace**: Raw L2 distance (`FR_NORM_L2`, Euclidean distance $\sqrt{2 - 2 \cdot \text{cosine}}$).

- **Canonical LBPH `tau_accept` — UNIFIED 2026-08-02 (standalone and hybrid cascade now share one value)**:
  - **`tau_accept` (both `cv_only` and `gate.tau_accept`)**: **`67.03325520645528`**
    - Provenance: LFW1 rank-165 unidirectional unique-pair impostor distance (9.986 ppm FAR, native `predict_collect` scale), **box-cropped** YuNet standalone sweep — `docs/results/independence_test/independence/lbph_lfw1/native_predict_scale_yunet.json`.
    - **Why unified:** `cv_only`'s accept rule and the cascade's outright-accept rule are the same test (`distance <= tau_accept`, SFace never runs before this gate either way) — a single-engine LBPH question, not something the joint pipeline should be recalibrating. The previous split (67.0084 standalone / 77.7693 hybrid) was traced to a **box-crop-vs-full-frame harness bug** in `src/hybrid/independence_test.py`, not a real detector- or pipeline-driven difference — confirmed by re-running the standalone script with the joint test's own YuNet detector: box-cropped YuNet lands at 67.033, next to the old Haar-standalone 67.0084, nowhere near 77.7693. Full trail: `docs/independence/MASTER_FILE.md`, `classical-cv/docs/audits/STATE-08-02.md`.
    - **Rule:** Do not diverge `cv_only` and `gate.tau_accept` again without re-establishing a principled reason (e.g. a real whole-system FAR-budget constraint — checked and ruled out 2026-08-02, see `docs/PAPER.md`'s cascade-undercuts-either-engine-alone finding).
    - **Domain Shift Note:** On unconstrained, in-the-wild LFW2 images, clean AR at this threshold is **`~1.74%`** (median clean distance $\sim 72.82$). This low AR is expected and serves as empirical proof of why classical LBPH requires the hybrid cascade (`SFace`) on wild images.
  - **Hybrid Cascade Gate Reject Edge (`gate.tau_reject`)**: **`140.13`** — **CANONIZED 2026-08-02, advisor sign-off**, replacing the box-crop-tainted 88.4927. NOT an impostor-FAR-derived value: an FRR-vs-escalation trade-off curve (`docs/independence/TAU_REJECT_METHOD.md`) found no `tau_reject` candidate in [70, 170] separates genuine from impostor escalation on wild LFW (they track ~1:1 throughout), so 140.13 (heavy-tier p99 genuine LBPH distance) was adopted as a deliberate permissive choice — makes the confident-reject branch near-inert on LFW, favoring SFace escalation. Does not generalize to La Salle DB1. See `docs/independence/MASTER_FILE.md` row 6.
  - **SFace Genuine Threshold (`sface.l2_genuine`)**: **`1.0313`** (YuNet joint hybrid run $\sim 10\text{ ppm}$ FAR) — **resolved 2026-08-02** vs. the SFace **standalone** value (`1.0306278467178345`, `docs/independence/MASTER_FILE.md` row 2/5): gap (0.0007) judged immaterial, no config change, since ~97-99% of wild-LFW probes land in LBPH's escalation band regardless of `tau_reject` candidate, making the two derivations' populations near-identical. Scoped to LFW — see `docs/experiments/hybrid_sface_threshold/ANALYSIS.md`.
  - **LFW Impostor 1.0% FAR Sensitivity Point**: **`76.7922`** (from `tar_at_far.json`; used only for diagnostic sensitivity studies such as `docs/experiments/standalone_lbph_robustness/THRESHOLD_CHANGE.md`).

---

## Codebase Navigation & API Efficiency Rules

- **LBPHAdapter API:** In `src/hybrid/recognizer.py`, `LBPHAdapter` exposes `.score(sample) -> LBPHMatch` (which returns `.name` and `.distance`), NOT `.predict()` or `.predict_collect()`.
- **Face Detector API:** In `src/classical_faces/detection.py`, `create_face_detector(backend="yunet")` requires the backend string argument (e.g., `"yunet"`).
- **Benchmark Smoke-Testing:** For rapid LFW2 robustness smoke tests, pass `--limit-identities 575` (`10%` subset, `172` clean probes) to `run_lfw2_robustness.py` to iterate quickly before launching full runs.
