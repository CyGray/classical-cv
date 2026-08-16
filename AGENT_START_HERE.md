# Agent Start Here

Shared workspace orientation for Codex, Agy/Gemini, Cmdc, and human
contributors. Read this first, then open only the map that matches the task.

## 30-second map

| Location | Use it for | Important boundary |
|---|---|---|
| `classical-cv/` | Live, runnable face-recognition code | Read `classical-cv/AGENTS.md` for project rules. |
| `classical-cv/src/` | LBPH, Eigenfaces, Fisherfaces, SFace, hybrid, and benchmark code | Use CodeGraph before searching or reading code. |
| `classical-cv/scripts/` | Experiment orchestration, reporting, and figure generation | Check the repo map before choosing a similarly named script. |
| `classical-cv/data/` | Local datasets and split manifests | Dataset contents are machine-specific and may be absent or empty. |
| `docs/results/` | Canonical, reviewable evidence | Read the category README, manifest, and provenance audit before citing anything. |
| `classical-cv/reports/`, `classical-cv/outputs/` | Raw and working outputs | Do not treat these as citation sources. |
| `docs/` | Workspace-level manuscript/evidence and experiment material | This is different from `classical-cv/docs/`. |
| `deep-learning/` | Source/reference material for the separate DL track | Plan-only on this machine; do not launch it without fixing its hard-coded dataset paths. |

The workspace root is one Git repository. Run Git commands here, not from a
subdirectory. `face-detection-g3/` is currently empty; verify before relying
on any older document that describes it as an active project.

## Fast startup

From the workspace root:

```powershell
git rev-parse --show-toplevel
git status --short
Get-ChildItem -Force classical-cv, docs | Select-Object Name, FullName
```

Preserve existing dirty-worktree changes. Do not reset, checkout, clean, or
delete files unless the user explicitly asks for that exact operation.

For code questions, resolve the absolute checkout path first, then pass that
path to the CodeGraph MCP as `projectPath`:

```powershell
git rev-parse --show-toplevel
```

Start with `codegraph_status`/`codegraph_explore` (or the host's equivalent).
Use `rg` for literal text and documentation searches after structural context
is known. If CodeGraph reports that the project is not indexed, do not create
an index automatically; report that the user can run `codegraph init -i`.

## Task router

| Task | Read first | Then use |
|---|---|---|
| General source change in `classical-cv/` | `classical-cv/AGENTS.md` and `classical-cv/.claude/skills/cv-repo-map/SKILL.md` | CodeGraph context/explore for the symbols and callers. |
| Workspace layout or cross-project question | `.claude/skills/cv-workspace-map/SKILL.md` | Verify paths and current state; do not trust old prose. |
| LFW2/41-mod robustness result or script | `.claude/skills/robustness-protocol-map/SKILL.md`, then `classical-cv/.claude/skills/cv-repo-map/SKILL.md` | Confirm identification vs pairwise verification vs transform-sensitivity and the operating point. |
| Independence test or threshold work | workspace map, repo map, and `classical-cv/docs/READ THIS/` | Read `classical-cv/src/hybrid/thresholds.json` immediately before relying on a deployed value. |
| Create or regenerate a chart, graph, figure, or diagram | `scripts/visualization/README.md`, then the applicable result/map guide | Use Matplotlib for data-driven charts, Graphviz for structural diagrams, and SVG for manuscript assets; regenerate from recorded data rather than converting a historical raster. |
| Result citation or manuscript table | Relevant `docs/results/*/README.md`, `docs/results/RESULTS_MANIFEST.json`, and `docs/results/metadata/PROVENANCE_AUDIT.md` | Use only reviewed canonical artifacts. |
| Candidate improvements, latency/throughput speedups, or major experiments | `docs/experiments/major/README.md` | Consult `architecture/` (Quality-First Early Bypass) and `lbph_config/` (`r3_n8_g6x6` multi-scale descriptor). |
| One known table, caption, or inline-object change in a named Springer DOCM | `.claude/skills/springer-docm-targeted-edit/SKILL.md` | Write the scope contract first; preserve VBA; compare only the named-object delta; inspect the changed and adjacent reflow pages. |
| Springer/LNCS DOCX/DOCM work | `.claude/skills/springer-docm-production/SKILL.md` and `classical-cv/docs/READ THIS/INSTRUCTIONS.md` | Start from the named version, preserve macros, validate macro caption types/effective formatting, then render/inspect the actual changed and reflow pages. |
| UI/dashboard or local run console | `classical-cv/ui/README.md` | Follow the app-specific README before installing or building. |
| Deep-learning track | workspace map | Inspect or write a plan; do not assume it is runnable here. |

## Non-negotiable source-of-truth rules

- The deployed hybrid threshold is loaded from
  `classical-cv/src/hybrid/thresholds.json`; prose values are historical or
  explanatory until verified against that file.
- LBPH hand-rolled chi-square distances and native OpenCV
  `predict_collect()` distances are different scales. Never mix their raw
  magnitudes.
- `docs/results/` is the only canonical result store. A filename in a report
  or output directory does not establish provenance.
- LSDB algorithm selection and LFW deployment-threshold calibration answer
  different questions. Do not transfer one operating point into the other.
- Robustness numbers must be labelled with their protocol and operating point;
  identification, pairwise verification, and legacy transform-sensitivity are
  not interchangeable.

## Authority by domain

- Runtime behavior: the code and configuration actually loaded at runtime.
- Result provenance: the relevant `docs/results/` manifest and audit.
- Protocol interpretation: the applicable workspace/repo task map.
- Engineering policy: the nearest applicable `AGENTS.md`.
- Navigation only: this file and the host-specific adapters.

## Before an expensive run

Check the actual dataset and disk state first. In particular, do not launch a
full LFW, independence, or robustness run merely because a historical command
exists. Confirm the intended dataset path, crop/preprocessing contract,
threshold family, output directory, and provenance requirements. Put raw
rerun output under `classical-cv/outputs/provenance_reruns/<run-name>/` and
promote only reviewed artifacts to `docs/results/` with manifest metadata.

## Agent host adapters

Each host may auto-load a native adapter before reaching this file. When that
happens, use the adapter to route here immediately; this file is the shared
navigation layer.

- Codex: native adapter `AGENTS.md`; use the CodeGraph MCP when available.
- Agy/Gemini: native adapter `GEMINI.md`.
- Cmdc/CommandCode: native adapter `AGENTS.md` plus
  `.commandcode/taste/taste.md` when present.

If an adapter file conflicts with the runtime configuration or the canonical
result manifest, the runtime/configuration and provenance rules win. Keep this
file short and update it when the workspace layout or agent entry points
change; do not copy live threshold values into it.
