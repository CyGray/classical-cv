# GEMINI.md - Computer Vision workspace

This is the Gemini/Agy adapter for the shared workspace. Start with
[`AGENT_START_HERE.md`](AGENT_START_HERE.md), then read only the map needed for
the task. Do not copy live threshold values from this file or from any other
prose document.

## Current workspace

- The workspace root is one Git repository. Run Git commands from the root.
- `classical-cv/` is the active, runnable face-recognition project. Its
  `AGENTS.md` contains project-specific engineering rules.
- `deep-learning/` is not runnable on this machine because its dataset paths
  are hard-coded for a missing `D:` drive. Treat work there as inspection or
  planning unless the environment is repaired first.
- `docs/results/` is the canonical evidence store. The reports and outputs
  under `classical-cv/` are working/raw locations.
- Root `docs/` and `classical-cv/docs/` are different trees. Check the path
  before opening or citing a document.

## Fast routing

| Task | First reads |
|---|---|
| Source change or architecture question | `classical-cv/AGENTS.md`, then `classical-cv/.claude/skills/cv-repo-map/SKILL.md` and CodeGraph. |
| Workspace layout or cross-project question | `.claude/skills/cv-workspace-map/SKILL.md`. |
| LFW2/41-mod robustness work | `.claude/skills/robustness-protocol-map/SKILL.md`, then `classical-cv/.claude/skills/cv-repo-map/SKILL.md`. |
| Independence or threshold work | Workspace map, repo map, `classical-cv/docs/READ THIS/`, then `classical-cv/src/hybrid/thresholds.json`. |
| Result citation | Relevant `docs/results/*/README.md`, `docs/results/RESULTS_MANIFEST.json`, and `docs/results/metadata/PROVENANCE_AUDIT.md`. |
| Candidate improvements or major experiments | `docs/experiments/major/README.md` (`architecture/` and `lbph_config/`). |
| One known table, caption, or inline-object change in a named Springer DOCM | `.claude/skills/springer-docm-targeted-edit/SKILL.md`. |
| Other Springer DOCX/DOCM work | `.claude/skills/springer-docm-production/SKILL.md` and `classical-cv/docs/READ THIS/INSTRUCTIONS.md`. |
| UI work | `classical-cv/ui/README.md`. |

## Research safety rules

- Use CodeGraph before grep or raw code reads. Pass the absolute workspace path
  as `projectPath`. If the project is not indexed, report that the user can
  run `codegraph init -i`; do not initialize it automatically.
- Read `classical-cv/src/hybrid/thresholds.json` at the moment a deployed
  threshold is needed. Prose values are dated history, not runtime truth.
- Native OpenCV `predict_collect()` LBPH distances and the hand-rolled
  chi-square distances are different scales. Never mix their raw magnitudes.
- LSDB algorithm selection is separate from LFW deployment calibration.
- Label robustness results as identification, pairwise verification, or legacy
  transform-sensitivity, and state the operating point.
- Use only reviewed artifacts from `docs/results/` as evidence. Check the
  manifest and provenance audit; do not infer provenance from filenames.
- Preserve dirty worktree changes. Do not reset, checkout, clean, or delete
  files unless the user explicitly requests it.

## Authority by domain

- Runtime behavior: the code and configuration actually loaded at runtime.
- Result provenance: the relevant `docs/results/` manifest and audit.
- Protocol interpretation: the applicable workspace/repo task map.
- Engineering policy: the nearest applicable `AGENTS.md`.
- Navigation only: this file and the host-specific adapters.

## Manuscript and document work

For a named single-object Springer DOCM edit, use the targeted-edit skill:
write the scope contract, preserve VBA, compare the target-object delta, and
inspect only the changed and adjacent reflow pages. For broader Springer/LNCS
DOCX or DOCM work, preserve the template and macro rules, archive manuscript
versions using the existing sequential convention, render the edited document
to PDF, and visually inspect every page containing a changed table or figure
before handoff. Keep document-production scripts under
`scripts/document-production/`.

## Environment check

```powershell
git rev-parse --show-toplevel
git status --short
Get-ChildItem -Force classical-cv, docs | Select-Object Name, FullName
```

PowerShell is the primary shell on this machine; global Python 3.11 is used.
Check dataset availability and free disk space before any expensive run.
