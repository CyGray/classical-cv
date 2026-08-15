---
name: springer-docm-targeted-edit
description: Make one known, scope-bounded change inside a named Springer/LNCS DOCM while preserving VBA and all non-target content. Use this as the default whenever a user asks to add, remove, reorder, or replace a column, row, cell value, table rule, single caption, or another named inline object in a specific DOCM version and does not request prose, global formatting, figure, citation, or manuscript-wide work. Escalate to springer-docm-production when the edit is not provably localized.
---

# Springer DOCM Targeted Edit

Use this skill to make a small manuscript change quickly without broadening its
scope. The speed comes from proving what may change, not from skipping DOCM,
VBA, source-of-truth, or visual checks.

## Route here only when the scope is known

Use this workflow when all of these are true:

- The user names an exact DOCM baseline and intended derivative, or the legal
  derivative name can be determined from `docs/manuscript/versions/README.md`.
- One object is the target: a table, its single caption, or one inline object.
- The expected starting state and exact intended content are known.
- The user does not ask to revise prose, citations, figures, global styles,
  headers/footers, or several manuscript objects.

Route to `springer-docm-production` instead when a change affects multiple
sections or objects, alters a research argument, needs new evidence or a
figure, changes a global style, has an uncertain target, or reflows beyond the
changed and adjacent pages.

For a new or replacement figure/diagram, the full-production route must first
read `scripts/visualization/README.md`: it selects Matplotlib for data-driven
charts, Graphviz for diagrams, and SVG as the manuscript source format.

## Write the scope contract before editing

Put this compact contract in the first progress update and treat it as the
acceptance test:

```text
Baseline: <exact input .docm>
Output: <exact derivative .docm>
Target: <e.g., Table 4, identified by caption/header>
Expected baseline state: <rows, columns, header/caption or other identity>
Operation: <e.g., insert a column before Role>
Exact target content: <header and values, including comparison signs/precision>
Authoritative source: <path, or "layout only; no claim changed">
No-change boundary: <everything else, including captions unless named>
Visual scope: <changed page and adjacent reflow page(s)>
```

If a material field is unknown, ask one precise question before writing. Do
not substitute a footnote, a caption rewrite, or a prose change for a request
to display information in a table. For example, "add the actual values as a
column in Table 4" means write a column in the cell matrix, not a table note.

## Prove the source only as far as the edit needs

Read `AGENTS.md`, `AGENT_START_HERE.md`, and
`docs/manuscript/versions/README.md`. Inspect the target object in the named
baseline before designing the edit.

- For a pure border, width, or placement repair, do not front-load unrelated
  result manifests or manuscript-wide audits.
- For a numeric value, threshold, metric, or claim, check the current
  authoritative configuration and the relevant canonical artifact immediately
  before writing. Follow the applicable result README, manifest, provenance
  audit, and protocol map. Never copy a value from narrative prose.
- For this workspace's deployed thresholds, read
  `classical-cv/src/hybrid/thresholds.json` and the matching independence
  artifact. Keep native scale, inequality direction, and published precision.

## Edit only a staged copy

1. Start from exactly the named version. Do not overwrite the baseline or
   `docs/manuscript/lsface.docm`.
2. Stage the copy outside the archive, then write only the requested final
   derivative under `docs/manuscript/versions/`.
3. Keep reusable PowerShell helpers under `scripts/document-production/`.
   Make the helper assert the expected target before it mutates anything:
   object identity, starting row/column count, headers, and, where relevant,
   the original cell matrix.
4. Open the staged copy with Word `AutomationSecurity = ForceDisable`, alerts
   disabled, and link updates disabled. Macro execution must be prevented even
   though the macro project is retained.
5. Change the target only. Preserve non-target cell text, captions, section
   properties, styles, headers/footers, and figure anchors. Do not repair
   unrelated problems found during inspection.
6. For a rewritten table, clear inherited list formatting from every edited
   cell and explicitly restore text, alignment, widths, padding, and header
   emphasis. Use native Word tables.

### Table-specific guardrails

Preserve the Springer three-rule table design unless the user requests a
different design:

1. 1.5 pt black rule at the table top.
2. One 0.75 pt black rule below the header row.
3. 1.5 pt black rule at the table bottom.

Do not introduce vertical rules, body-row rules, shading, tiny text, or
character-by-character wrapping. Allocate columns deliberately and prefer a
concise header to shrinking body text.

## Restore and verify VBA

Saving through Word can rewrite `word/vbaProject.bin`. After saving, replace
the output part with the exact named baseline's macro part and compare their
SHA-256 hashes. A mismatch is a hard stop; do not hand off a macro-preserving
derivative with an unverified macro project.

## Validate the delta, then inspect only relevant pages

Validate in this order:

1. The target matches the scope contract exactly: table dimensions, headers,
   cell matrix, text precision, and inequality signs.
2. The baseline/output delta proves that all non-target prose, captions,
   tables, and objects are unchanged. If a caption is not the target, it must
   be unchanged in content, effective formatting, and position relative to
   its object.
3. The VBA hash matches the named baseline.
4. Run `scripts/document-production/inspect-word-layout.ps1` with the named
   baseline and the changed page plus every adjacent reflow page. Check table
   width, wrapping, three-rule borders, caption placement, and the active
   output document.
5. Give PDF export a short, bounded attempt. If it is unreliable, use the
   active-document-verified Word PrintWindow capture fallback. A fallback is
   valid only after asserting `ActiveDocument` for the output, never the
   reference specimen.

If the baseline already has an unrelated audit failure, record it as
pre-existing and compare the output against the baseline. Do not fix it in a
targeted derivative. Any new failure inside the target or a non-target delta
expands scope and must be stopped or escalated.

## Handoff

Report only the information the user needs to trust a small change:

- output path and named baseline;
- exact target change;
- authoritative values/source, if content changed;
- VBA hash result;
- delta result and inspected pages;
- any reason the task escalated to full production.

## Routing examples

| Request | Route |
|---|---|
| “From 010, create 010b and add a Current threshold column to Table 4.” | This skill. |
| “Correct one existing Table 2 border without changing its data.” | This skill. |
| “Update the Results discussion, Table 4, captions, and Figure 2.” | `springer-docm-production`. |
| “Make all captions match the template.” | `springer-docm-production`. |
