# Robustness Test Results

For Paper 1, the canonical robustness protocol is the one-image-per-identity
SAME-SOURCE self-match transform-sensitivity test. One LFW source image is
enrolled or trained for each identity, and that same image is reused as the
source for 41 controlled modified probes. The result therefore measures
within-image degradation retention, not recognition of a different photograph
of the same person.

The canonical Paper 1 source is
[`benchmark/lfw2_robustness/accuracy_ratio_hybrid.md`](benchmark/lfw2_robustness/accuracy_ratio_hybrid.md).
Its reported overall rates are 86.66% for LBPH, 98.22% for SFace, and 94.69%
for the cascade. Cite those values with the recorded run configuration:
5,749 LFW source images; seed 42; the report's 41-variant configuration;
fallback handling when no face is detected; LBPH-only boundary 76.85;
cascade boundaries 67.0084/76.85; and the SFace dual rule cosine >= 0.363
and L2 <= 1.018. These are historical run settings, not the current deployed
thresholds.

Read [`SELF_MATCH_ROBUSTNESS_PROVENANCE.md`](SELF_MATCH_ROBUSTNESS_PROVENANCE.md)
before using the result. It records the protocol, operating point, supported
claim, and exclusions. In particular, this experiment does not measure
different-photo identification, pairwise verification, FAR, open-set or
deployment validity, or whether one-image training is generally optimal.

The separate image-disjoint LFW identification results (1.41% LBPH, 80.65%
SFace, and 80.65% cascade) remain retained with their existing repository
provenance but are outside Paper 1's selected robustness evidence. This scope
decision neither removes nor reclassifies them.

All robustness tables belong here, never in `../complementarity_test/`. Check
`../RESULTS_MANIFEST.json` and `../metadata/PROVENANCE_AUDIT.md` before
citation. PNG tables/figures are not automatically manuscript-ready: preserve
their status, and regenerate a verified native table or vector figure for the
camera-ready manuscript.
