---
name: springer-docm-production
description: >
  Create, update, review, or migrate a Springer LNCS/LN-series manuscript in
  this workspace. Use for full-manuscript DOCX/DOCM work involving prose or
  claim revisions, multiple objects, figures, captions, global styles,
  citations, exports, or template migration. For one named table, caption, or
  inline-object edit with an explicit no-change boundary, use
  springer-docm-targeted-edit instead.
---

# Springer DOCM Production

Use this workflow to produce a submission-ready Springer manuscript without corrupting the official template or copying stale research claims.

## Route scoped object edits first

Use `springer-docm-targeted-edit` rather than this full-production workflow
when the user names an exact DOCM baseline and derivative, the change is
confined to one known table, caption, or inline object, and the intended
content can be written as an exact scope contract. It retains VBA, provenance,
and visual safeguards without turning a one-object change into a manuscript
rebuild.

Stay in this workflow when the edit changes prose, claims across sections,
multiple objects, figure assets, citations, global styles, headers/footers, or
an uncertain layout boundary.

## Workspace assets and companion skills

- Windows table/template reference: `docs/manuscript/sample/sample.docm`
- Mac reference: `docs/manuscript/sample/sample_mac.docm` (do not use as a Windows macro source)
- Table design screenshot: `docs/manuscript/sample/sample_table_format.png`
- Current manuscript: `docs/manuscript/lsface.docm`
- Manuscript version archive: `docs/manuscript/versions/README.md`
- Current manuscript source: `classical-cv/docs/PAPER.md`
- Claim register: `docs/manuscript/claim-evidence-register.md`
- Canonical-result manifest: `docs/results/RESULTS_MANIFEST.json`
- Result status / rerun audit: `docs/results/metadata/PROVENANCE_AUDIT.md`
- Reusable macro-preserving builder: `scripts/document-production/build-springer-paper.ps1`
- SVG visual-export policy: `scripts/visualization/README.md`

Read `AGENTS.md`, the CV workspace maps, the relevant `docs/results/*/README.md`,
and the manifest/audit before quoting metrics. Treat
`classical-cv/src/hybrid/thresholds.json` and verified canonical artifacts as
sources of truth; old narrative papers and working reports can describe
historical configurations.

Companion skills:

- [DOCX CLI](../docx-cli/SKILL.md): read, diff, inspect, render, or edit `.docx` packages. Read-only inspection can help compare table structure. It does **not** claim DOCM/VBA support; never use its mutators on a `.docm`.
- [Research paper writing](../research-paper-writing/SKILL.md): use before changing research prose, claims, figures, tables, or reviewer-facing structure. Keep its claim-evidence checks alongside this skill's source-of-truth rules.

The old `docs/splnproc2510.docm` path is absent in the current workspace. Do not run the builder until its input-template path has been restored or made configurable. Do not substitute the Mac sample for a Windows macro-enabled output.

## Decide the output format first

Ask or infer this before touching the template:

| Need | Output | Rule |
|---|---|---|
| Preserve template macros | `.docm` | Copy the source template, edit only the copy, and save it as `.docm`. |
| No macros required | `.docx` | Start from a copied template and save a new macro-free file. |
| Review only | no generated office file | Return a claim/layout review and leave source assets unchanged. |

Never convert a macro-preserving request to `.docx`. Do not overwrite `splnproc2510.docm` or `splnproc2510_mac.docm`.

## Table design contract

Use `sample.docm` and `sample_table_format.png` as the visual source of truth. This is a three-rule LNCS table design, not a full grid:

1. Thick 1.5 pt black horizontal rule at table top.
2. Thin 0.75 pt black horizontal rule immediately below header row.
3. Thick 1.5 pt black horizontal rule at table bottom.
4. No vertical rules, body-row rules, shading, or additional horizontal rules.

In Word/OOXML, the separator can serialize as both the header-bottom border and the next-row top border. That is one visible 0.75 pt rule, not two. Do not copy the sample's three-column widths into wider results tables; reproduce border design only unless layout change is requested.

## Figure and diagram export contract

Before creating or regenerating a manuscript chart, graph, figure, or diagram,
read `scripts/visualization/README.md`. Use Matplotlib for data-driven charts
and graphs, Graphviz for structural diagrams, and SVG as the primary
manuscript export. First establish that the source data and result provenance
permit the visual; regenerate from recorded data rather than converting or
overwriting a historical raster artifact.

Keep the SVG source with its generator/run record. Make a non-SVG derivative
only when a documented Word compatibility constraint requires it, never as a
replacement for the canonical SVG source.

## Caption and style contract

Caption styles carry the official LNCS spacing and page-break behavior. A
caption whose `Range.Style` has the expected name can still be wrong if direct
paragraph formatting overrides the macro style.

- Table titles must be separate `tablecaption` paragraphs above their table.
- Figure names must be separate `figurecaption` paragraphs below the matching
  inline figure; do not leave caption text on the image's anchor paragraph.
- Copy the `tablecaption` and `figurecaption` definitions from
  `docs/manuscript/sample/sample.docm` before applying them. Clear direct font
  and paragraph formatting on each caption, then apply the named style. Never
  tighten caption spacing merely to recover a page.
- Use `scripts/document-production/inspect-word-layout.ps1` before handoff.
  Its default check compares the target's caption style definitions and every
  caption's *effective* formatting against the macro specimen, and confirms
  table/figure caption placement. Treat a failure as a failed document build.

## Safe Word workflow

1. Inspect the template contents and styles before writing. The relevant Springer styles include `papertitle`, `author`, `address`, `abstract`, `keywords`, `heading1`, `heading2`, `tablecaption`, `figurecaption`, `referenceitem`, and `acknowlegments`.
2. Treat `header.png` as a visual reference, not a raster title block. Recreate title, authors, affiliations, and markers as editable text. If the image contains a duplicate or blurred line, use the complete block and flag any ambiguous spelling for human confirmation.
3. When automating Word, open the output copy with `AutomationSecurity = ForceDisable`; this prevents macro execution while retaining the macro project. Keep alerts and link updates disabled.
4. Before any manuscript edit, read `docs/manuscript/versions/README.md`. Start from exactly the version the user named; stage a copy, then put the final DOCM only in `docs/manuscript/versions/`. Use the next zero-padded index unless the user explicitly names a derivative such as `009b`; never redirect the output to `docs/manuscript/copy/`.
5. Word can rewrite `word/vbaProject.bin` even when macro execution is disabled. After saving, replace that part with the original named baseline's `word/vbaProject.bin`, then verify identical SHA-256 hashes. If the named baseline is open/locked, use a separately verified identical macro baseline and report that fallback. If the hash differs, restore the backup and stop.
6. For a table-border-only repair, leave content, caption text, fonts, widths, cell padding, and alignments untouched unless the request expands scope.
7. For a `.docx`, save to a different path and explicitly verify the output does not include `word/vbaProject.bin`.
8. Preserve custom styles, section properties, headers/footers, page geometry, and figure/table conventions. Do not paste the paper as unstyled plain text.

### Automated object and render guard

Word can inherit numbered-list formatting from an insertion paragraph into
every new table cell. Before saving a generated or rewritten table, explicitly
remove list formatting from each cell and reset the intended text, font,
alignment, widths, and header emphasis. Never accept a table solely because
the COM call succeeded: it can render with stray numbers, collapsed columns,
or a separated caption while its data remains technically present.

Run `scripts/document-production/inspect-word-layout.ps1` on the final DOCM
with the named macro baseline and the changed-page numbers. It fails on page
budget overflow, a table outside the text block, a changed VBA project, or a
caption-style/placement mismatch. The script opens the macro specimen too, so
it must reactivate and assert the target `ActiveDocument` before each
PrintWindow capture. If Word-to-PDF export fails, those verified captures are
the permitted fallback—not an unverified screen grab. Inspect every changed
object page and adjacent page affected by reflow, including object closeups
when full-page captures make text too small to judge.

## Manuscript writing and evidence rules

1. Build a claim-evidence register before migrating a paper. Every numerical claim needs its dataset, protocol, operating point, metric definition, and artifact path.
2. Do not copy threshold values from prose. For this project, inspect `thresholds.json` and the matching independence artifact immediately before writing.
3. Keep Rank-1, TPIR/AR, GAR, FAR, and EER distinct. Each number must state the protocol and operating point.
4. If an existing result used a superseded threshold, label it as historical/archived or omit it until rerun. Never silently relabel it as the current deployed result.
5. Keep Abstract, Keywords, and Introduction as styled placeholders when a collaborator owns them. Do not backfill them with old text.
6. Use native Word tables and Word equations. Put table captions above tables and figure captions below figures. Keep robustness tables in the robustness evidence set; do not present them as complementarity evidence.
7. For a manuscript figure, first check its manifest status and the provenance audit. `illustrative_stand_in`, `needs_provenance_review`, `historical_rerun_required`, and `rerun_required` artifacts cannot be silently promoted to current evidence.
8. Prefer a regenerated SVG/PDF figure (or EMF on Windows) only when its data, script, configuration, and run are recorded. Never auto-trace a raster PNG: that creates a vector wrapper, not reproducible vector evidence.
9. Use Springer numbered references, not an IEEE bibliography pasted verbatim. Add `Acknowledgments` and `Disclosure of Interests` before the references.

## Validation checklist

- Output opens in Word without repair warnings.
- Source template timestamp/hash is unchanged.
- Title, author, and affiliation block visually match the approved header reference.
- Required collaborator-owned sections remain placeholders.
- All figures/tables are cited in order, styled consistently, and have the correct caption position.
- Every citation resolves to one reference and every reference is cited.
- Every result has a claim-register entry; stale or historical values are visibly labeled.
- Every cited result has a manifest entry; its status permits the citation, and its provenance is recorded.
- No stand-in is cited as a measurement; any raster figure is either an approved exception or replaced by a regenerated vector source.
- For every table, inspect rule positions: top 1.5 pt, below-header 0.75 pt, bottom 1.5 pt; no vertical/body rules.
- Table text may not be made smaller than the sample's normal 9 pt solely to meet the page budget. Reflow, rewrite headers, alter justified column allocation, or move a float first; retain comfortable page margins.
- Confirm every table title uses the effective macro `tablecaption` style and every figure name uses `figurecaption`, with no direct spacing/font override; keep tables above and figures below their matching object.
- Render to PDF and inspect first page, page breaks, equations, table rules/wrapping, figure scaling, Unicode symbols, and headers/footers. If PDF export is unavailable, use the active-document-verified Word capture fallback and inspect the actual output, never the macro specimen.
- For a macro-preserving document, verify `vbaProject.bin` matches the original template hash.
- The `docs/manuscript/versions/` before/after archives exist and use consecutive `[index]_lsface_[version_name].docm` names.

## Handoff

Report the output path, the output format, whether VBA was preserved or stripped, any placeholders intentionally left for collaborators, and any evidence that needs a rerun before camera-ready submission.
