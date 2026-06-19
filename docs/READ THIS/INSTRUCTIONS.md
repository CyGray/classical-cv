# Paper Edit Instructions — LS-Face

*Generated from interview with CommandCode (2026-06-19)*

---

## My Role
- **Edit existing draft** — I have a paper draft at `docs/PAPER.md`. I want edits, not a rewrite from scratch.

## Target Venue
- **IW-FCV 2026** — Tokushima University, Japan (Sept 30 – Oct 2, 2026)
- Guidelines: `docs/READ THIS/IW-FCV_2026_Call_for_Papers.md`
- Long Paper: 12–15 pages (eligible for oral/poster + post-workshop proceedings)
- Short Paper: 2–11 pages (poster only)
- **Deadline: July 31, 2026**
- We should target **Long Paper (12–15 pages)** with post-workshop proceedings consideration.

## Creative Freedom
- **Do as much as necessary** to make the paper strong and submission-ready.
- **Strictly follow the current voice, format, and structure** of the existing paper. Do not change the tone, section ordering, or writing style unless it's clearly wrong for IW-FCV.
- Polish, expand, and deepen — don't reinvent.

## Writing Style
- **Scan and strictly follow the current paper's writing style.** The existing draft is formal academic with clear, direct technical prose. Match that. Do not shift to passive-voice-heavy traditional academic writing unless the draft itself does that.

## Starting Point
- **Both.** I've read the existing draft at `docs/PAPER.md` AND explored the full codebase (`src/`, `models/`, `reports/`, `data/`, etc.).
- Cross-check every number in the paper against actual run artifacts.
- Fill in missing details from the codebase where appropriate.

## Revision Process
- **Section by section.** Do not dump a full rewritten paper in one shot.
- We'll go section by section: Abstract → Introduction → Related Work → Proposed Approach → Experiments/Results/Discussion → Conclusion → References.
- I (the user) will review and approve each section before moving to the next.

## Specific Requirements
1. **Expand the paper to 12–15 pages** for Long Paper format at IW-FCV 2026.
2. **Keep all existing content** — nothing gets removed unless replaced by something strictly better.
3. **Add depth** where the draft is thin (Related Work, Proposed Approach methodology details, experimental setup).
4. **Fill in missing metadata** — author names, affiliation, email.
5. **Update/verify all numbers** against the actual run artifacts in `reports/`.
6. **Ensure all figures and tables are properly referenced.**
7. **Format references in IEEE style** (already close — verify and standardize).
8. **Add a keywords list** if missing.

## What's Available
- Full paper draft: `docs/PAPER.md`
- Conference guidelines: `docs/READ THIS/IW-FCV_2026_Call_for_Papers.md`
- Spec compliance: `docs/reports/SPEC_COMPARISON.md`
- Hybrid report: `docs/reports/HYBRID_CV_DL_REPORT.md`
- Detector comparison: `docs/reports/DETECTOR_COMPARISON.md`
- Architecture plan: `docs/ARCHITECTURE_PLAN.md`
- Implementation plan: `docs/ARCHITECTURE_IMPLEMENTATION_PLAN.md`
- Dataset analysis: `docs/DATASET_MATRIX.md`
- Changelog: `docs/changelogs/CHANGELOG.md`
- Figures: `docs/figures/fig_hybrid_*.png`
- All reports: `reports/benchmark/*`, `reports/evaluation/*`
