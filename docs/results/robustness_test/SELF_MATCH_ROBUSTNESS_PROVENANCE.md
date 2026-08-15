# Paper 1 Same-Source Robustness Provenance

## Canonical Paper 1 decision

Paper 1 uses the one-image-per-identity SAME-SOURCE self-match test as its
canonical robustness protocol. For each of 5,749 LFW identities, one source
image is enrolled or used for training and that same image is transformed into
41 controlled modified probes. Each modified probe is therefore judged against
the identity representation built from its own source image.

This design measures within-image degradation retention, also described as
transform sensitivity: how often a recognizer continues to accept the same
image after a controlled transformation. It deliberately does not ask whether
the system recognizes a new photograph of the same person.

The canonical source report is
[`benchmark/lfw2_robustness/accuracy_ratio_hybrid.md`](benchmark/lfw2_robustness/accuracy_ratio_hybrid.md).
`RESULTS_MANIFEST.json` already classifies that artifact as a
`canonical_snapshot`; that status is deliberate. The artifact is the selected
Paper 1 robustness result when cited with the protocol and limitations in this
note. Its status does not make it evidence for protocols the run did not
execute.

## Reported result

The report gives the following overall rates across its 41 controlled
modifications:

| Mode | Reported overall rate |
|---|---:|
| LBPH (`cv_only`) | 86.66% |
| SFace (`dl_only`) | 98.22% |
| Hybrid cascade (`cascade`) | 94.69% |

In Paper 1 prose, identify these as same-source transform-sensitivity or
degradation-retention rates. The source artifact uses the field label
"Overall AR"; that historical report label must not be expanded into a claim
of different-photo identification accuracy.

## Recorded run configuration

- Population: 5,749 LFW source images, one source image per enrolled/trained
  identity.
- Probe construction: 41 variants generated from each identity's enrolled
  source image, with seed 42. This is the report's original 41-variant
  configuration, historically named the `legacy` 41-variant suite in protocol
  routing material.
- Source/probe relationship: SAME-SOURCE self-match; no image-disjoint probe is
  introduced by this experiment.
- No-face policy: `fallback`; when detection fails, the run follows its
  whole-tile fallback path instead of counting a strict failure.
- LBPH-only acceptance boundary: 76.85.
- Cascade gate boundaries: `tau_accept = 67.0084` and
  `tau_reject = 76.85`.
- SFace genuine rule: cosine >= 0.363 and L2 <= 1.018.
- Aggregation: the report averages levels within each modification and then
  averages across modifications; it also records pooled rates separately.

These values describe the configuration that produced the report. They must
not be silently replaced by the current deployed thresholds or presented as a
rerun under current configuration. The configuration is corroborated by the
unchanged historical record in
`classical-cv/docs/audits/STATE-08-01.md`; this provenance note does not rewrite
that audit.

## Supported interpretation

The experiment supports a bounded statement: under the recorded thresholds,
fallback policy, population, and 41-transform suite, SFace retained acceptance
more consistently than LBPH, while the cascade's overall retention lay between
the two standalone modes. This is evidence about sensitivity to controlled
within-image degradation.

The experiment does not establish any of the following:

- different-photo, gallery/probe-disjoint, or 1-to-N identification accuracy;
- pairwise verification performance;
- a FAR measured by this experiment or calibration at a claimed FAR;
- open-set, security-gate, target-device, or deployment validation;
- general identity recognition from one training image; or
- that one-image-per-identity training is generally optimal.

Any FAR associated with a threshold must come from its separate calibration
evidence, not from this same-source experiment.

## Relationship to retained image-disjoint evidence

The repository separately retains the LFW image-disjoint identification result
of 1.41% for LBPH, 80.65% for SFace, and 80.65% for the cascade, documented in
[`ROBUSTNESS_RESULT_PROVENANCE.md`](ROBUSTNESS_RESULT_PROVENANCE.md). Those
results answer a different question and remain available with their existing
provenance. The finalized Paper 1 decision excludes them from Paper 1; it does
not delete, invalidate, or reclassify them.

Pairwise-verification and other robustness artifacts likewise remain governed
by their own recorded protocols and manifest entries. Their presence in the
same result category does not make their metrics interchangeable with this
same-source result.

## Citation-ready scope sentence

> Under the one-image-per-identity same-source transform-sensitivity protocol,
> using 5,749 LFW source images and 41 controlled variants per source, the
> recorded overall retention rates were 86.66% for LBPH, 98.22% for SFace, and
> 94.69% for the cascade.

Follow that sentence with an explicit limitation that the probes are modified
copies of their own enrolled source images and that the experiment is not an
image-disjoint identification, pairwise-verification, FAR, open-set, or
deployment evaluation.
