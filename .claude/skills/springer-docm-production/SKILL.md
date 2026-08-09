---
name: springer-docm-production
description: Create, update, review, or migrate a Springer LNCS/LN-series manuscript in this workspace. Use whenever a task mentions DOCX/DOCM, a Springer template, Word formatting, table design or borders, figures, citations, headers, exports, or macro preservation. Treat even small table or layout changes as template-fidelity work because visual conventions, VBA preservation, and claim provenance are coupled.
compatibility: Requires Windows Microsoft Word for final DOCM production; PowerShell; the workspace document assets in docs/.
---

# Springer DOCM Production

Use this workflow to produce a submission-ready Springer manuscript without corrupting the official template or copying stale research claims.

## Workspace assets and companion skills

- Windows table/template reference: `docs/manuscript/sample.docm`
- Mac reference: `docs/manuscript/sample_mac.docm` (do not use as a Windows macro source)
- Table design screenshot: `docs/manuscript/sample_table_format.png`
- Current manuscript: `docs/manuscript/lsface.docm`
- Manuscript version archive: `docs/manuscript/versions/README.md`
- Current manuscript source: `classical-cv/docs/PAPER.md`
- Claim register: `docs/manuscript/claim-evidence-register.md`
- Canonical-result manifest: `docs/results/RESULTS_MANIFEST.json`
- Result status / rerun audit: `docs/results/metadata/PROVENANCE_AUDIT.md`
- Reusable macro-preserving builder: `scripts/document-production/build-springer-paper.ps1`

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

## Safe Word workflow

1. Inspect the template contents and styles before writing. The relevant Springer styles include `papertitle`, `author`, `address`, `abstract`, `keywords`, `heading1`, `heading2`, `tablecaption`, `figurecaption`, `referenceitem`, and `acknowlegments`.
2. Treat `header.png` as a visual reference, not a raster title block. Recreate title, authors, affiliations, and markers as editable text. If the image contains a duplicate or blurred line, use the complete block and flag any ambiguous spelling for human confirmation.
3. When automating Word, open the output copy with `AutomationSecurity = ForceDisable`; this prevents macro execution while retaining the macro project. Keep alerts and link updates disabled.
4. Before editing `docs/manuscript/lsface.docm`, archive the before copy and final after copy in `docs/manuscript/versions/`. Name every archive exactly `[index]_lsface_[version_name].docm` (for example, `001_lsface_model-selection.docm`): use the next zero-padded sequential index, never a timestamp or a suffix-before-index name. Then set `AutomationSecurity = ForceDisable` and save the output as `.docm`.
5. Word can rewrite `word/vbaProject.bin` even when macro execution is disabled. After saving, replace that part with the original copy's `word/vbaProject.bin`, then verify identical SHA-256 hashes. If the hash differs, restore the backup and stop.
6. For a table-border-only repair, leave content, caption text, fonts, widths, cell padding, and alignments untouched unless the request expands scope.
7. For a `.docx`, save to a different path and explicitly verify the output does not include `word/vbaProject.bin`.
8. Preserve custom styles, section properties, headers/footers, page geometry, and figure/table conventions. Do not paste the paper as unstyled plain text.

### Automated-table failure guard

Word can inherit numbered-list formatting from the insertion paragraph into
every new table cell. Before saving a generated or rewritten table, explicitly
remove list formatting from each cell and reset the intended text, font,
alignment, widths, and header emphasis. Never accept a table solely because
the COM call succeeded: a table can render with stray numbers, collapsed
columns, or a separated caption while its data remains technically present.

When a table is newly inserted or materially rebuilt, render the DOCM to PDF
and inspect the affected pages visually. Verify that the caption is above and
on the same page as the table, there is no inherited numbering, headers and
values do not wrap character-by-character, and the three-rule LNCS design is
visible at the intended widths. Apply the same render-and-inspect check to
new vector figures and their below-figure captions.

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
- Render to PDF and inspect first page, page breaks, equations, table rules/wrapping, figure scaling, Unicode symbols, and headers/footers.
- For a macro-preserving document, verify `vbaProject.bin` matches the original template hash.
- The `docs/manuscript/versions/` before/after archives exist and use consecutive `[index]_lsface_[version_name].docm` names.

## Handoff

Report the output path, the output format, whether VBA was preserved or stripped, any placeholders intentionally left for collaborators, and any evidence that needs a rerun before camera-ready submission.
