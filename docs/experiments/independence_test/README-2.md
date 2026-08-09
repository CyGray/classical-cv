## Independence Artifact Rules

Every artifact in this directory is indexed in `../../RESULTS_MANIFEST.json`.
Read `../../metadata/PROVENANCE_AUDIT.md` before citation. Full-frame hybrid
LFW1 LBPH outputs require a box-cropped rerun and are audit-only; threshold
figures must use the native `predict_collect()` LBPH scale or SFace L2 scale
as applicable.

### Figure Rules 
For the independence test figures, I need the **histogram with the KDE curve + the vertical long-dotted line that signifies the threshold**.

Thresholds must be expressed in native predict scale (Chi-square distance for LBPH and L2 for SFace). There are 4 thresholds:
1. Standalone LBPH
2. Standalone SFace
3.1 Hybrid LBPH (`tau_accept` and `tau_reject`)
3.2 Hybrid SFace
