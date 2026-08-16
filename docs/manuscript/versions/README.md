# Manuscript Versions & Lineage

Archive every edited main-manuscript DOCM here. Start from the exact named
baseline, and put the final editable output here—not in
`docs/manuscript/copy/`, which is personal-access source material. Name a
normal successor `[i+1]_lsface_[version_name].docm`.

If the user explicitly asks for a derivative from a named version (for example
`009b` from `009`, or `020b` from `020p`), create that exact derivative name from
the named baseline; do not advance to a new number or silently substitute a fuller draft.

## Current Approved Baseline

The current approved main-line baseline is:
- **`020b_lsface_canonical-selfmatch-promoted.docm`** (with accompanying `020b_lsface_canonical-selfmatch-promoted.pdf` and `_page_renders_020b/`)
- Parent canonical baseline: **`020p_lsface_canonical-selfmatch-promoted.docm`** (with accompanying `020p_lsface_canonical-selfmatch-promoted.pdf` and `_page_renders_020p/`)

These versions incorporate canonical self-match robustness results (77.02% LBPH, 88.90% SFace, 88.91% cascade retention, 92.45% pooled escalation, 6.40% strict detector failure handling), complete terminology reconciliation (within-image transformation retention vs image-disjoint evaluation), precise mathematical typography ($m_{\text{min}}$, $\tau_{\text{reject}}$, $\tau_{\text{accept}}$, $p_5$), calibrated figure dimensions, verified 16-page budget, and bit-for-bit VBA macro preservation.

## Directory Structure

- `archive/` — Historical early main-line versions (`001` through `010`).
- `pairwise/` — Archived experimental fork (`012p` through `019p`) that developed and refined the canonical self-match robustness integration before the promotion of `020p`/`020b`.
- `_table_capture/` — Visual inspection renders of manuscript tables.
- `_page_renders_020p/` & `_page_renders_020b/` — Visual inspection page renders for promoted versions.
