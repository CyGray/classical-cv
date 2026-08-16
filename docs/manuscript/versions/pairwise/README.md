# Pairwise Experimental Fork Lineage (Archived)

This directory houses the experimental development fork that branched from
`docs/manuscript/versions/012_lsface_gate-accept-protection-descriptive.docm` to
integrate canonical self-match robustness evaluation results, formalize mathematical
notation, and refine manuscript terminology and visual balance across iterations `012p`
through `019p`.

**Promotion Notice**: The lineage culminated in `020p` and its figure-calibrated derivative
`020b`, which have now been **promoted to the main manuscript lineage** and moved to the
parent directory (`docs/manuscript/versions/`).

## Lineage History

- **Root Baseline**: `docs/manuscript/versions/012_lsface_gate-accept-protection-descriptive.docm`
- **012p**: `012p_lsface_legacy-selfmatch-robustness.docm` — Initial self-match robustness fork.
- **013p**: `013p_lsface_legacy-selfmatch-robustness-finalized - Copy.docm` — Intermediate formatting revisions.
- **014p**: `014p_finalizations.docm` — Initial candidate baseline for advisor review.
- **015p**: `015p_selfmatch .docm` — Exploratory self-match revisions.
- **016p**: `016p_new.docm` — Restructured text draft.
- **017p**: `017p_lsface_focused-cleanup.docm` (with `017p_lsface_focused-cleanup.pdf`) — Focused cleanup of Section 4.3 terminology and Table 6 formatting.
- **018p**: `018p_polish_run.docm` — Visual balance pass and table layout adjustments.
- **019p**: `019p_lsface_reproducibility-pass.docm` (with `019p_lsface_reproducibility-pass.pdf` and `_page_renders_019p/`) — Comprehensive cross-section reproducibility reconciliation (Abstract, Section 3.1, Section 4.3, Section 4.4, Discussion 5.1, Conclusions 6.1 & 6.2).
- **020p / 020b (Promoted to Mainline `../`)**:
  - `020p_lsface_canonical-selfmatch-promoted.docm` (with `.pdf` and `_page_renders_020p/`): Full XML-level mathematical styling ($m_{\text{min}}$, $\tau_{\text{reject}}$, $\tau_{\text{accept}}$, $p_5$) and validated bit-for-bit VBA macro preservation.
  - `020b_lsface_canonical-selfmatch-promoted.docm` (with `.pdf` and `_page_renders_020b/`): Calibrated Fig 3 drawing dimensions matching text column width, verified 16-page budget, and visual inspection renders.

## Protocol and Interpretation Context

- **Protocol**: One LFW source image per identity was enrolled and used as the source of every clean and transformed test probe (235,709 modified conditions across 5,749 identities × 41 deterministic transformations).
- **Interpretation**: The reported metrics reflect within-image transformation retention, not image-disjoint identification, pairwise verification, or an empirical FAR measurement. Strict detector failures (15,083 conditions, 6.40%) are scored as failures. Table 5 and Table 6 maintain independent, explicitly labeled evaluation roles.
- **Historical Evidence**: Replaces historical 86.66% LBPH / 98.22% SFace / 94.69% cascade retention numbers with canonical 77.02% LBPH / 88.90% SFace / 88.91% cascade retention (92.45% pooled escalation).
