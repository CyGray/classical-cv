# Robustness Test — Simple Overview

## Paper 1 protocol decision

Paper 1 uses a **controlled same-source (self-match) robustness protocol**.
For each identity, one source image is enrolled or used for training, and that
same source image is transformed to create the clean and modified probes. The
test asks whether the system retains the source identity as controlled damage
is applied.

This is an intentional protocol choice for Paper 1 because it isolates
**within-image degradation retention**, also called **transform sensitivity**,
and supports modification-specific diagnostics. It does not test whether the
system recognizes the person in a different photograph.

The recorded source run reports 41-modification retention of **86.66% for LBPH**,
**98.22% for SFace**, and **94.69% for the hybrid cascade**. These values are
canonical for Paper 1 only under the same-source interpretation. The source
report's historical `AR` field name does not turn them into recognition
accuracy.

## What this test checks

Real camera images can be dark, blurry, noisy, rotated, rescaled, cropped, or
partly occluded. The test applies those changes in a controlled way to one
known source image and compares three system modes:

| Mode | What it is |
| --- | --- |
| **CV Only** | The classical engine alone (LBPH) |
| **DL Only** | The deep-learning engine alone (SFace) |
| **Hybrid Cascade** | LBPH first, with SFace escalation under the recorded gate rules |

Because every mode receives the same transformed source probes, the
per-modification differences show which engine or cascade is more sensitive
to each controlled change.

## What “enrolled photo” and “probe” mean here

One image per identity has two linked roles:

1. It is the identity's enrolled/training source.
2. It is the source from which the clean and modified probes are generated.

The source reuse is the defining feature of the Paper 1 protocol. A clean
probe is therefore a self-match, and a modified probe is a transformed
version of that same enrolled image. The test remains useful because damage
can change detection, preprocessing, LBPH distance, SFace similarity, the
nearest identity, and the cascade route. What it deliberately removes is
cross-photo variation in pose, expression, capture conditions, and identity
appearance.

## What the result may and may not be called

The result may be described as:

- same-source robustness;
- self-match robustness;
- within-image degradation retention;
- transform sensitivity; or
- source-identity retention under controlled modifications.

It must not be described as:

- different-photo identification accuracy;
- pairwise verification accuracy;
- FAR, open-set accuracy, or unknown-person performance;
- real-world or deployment performance; or
- proof that one-image training is optimal.

No impostor or unknown probes are scored by this experiment, so it cannot
measure FAR or open-set behavior. Any FAR value shown beside the historical
retention table comes from a separate impostor-based threshold calibration,
not from this robustness run.

## Historical audit reconciliation

`docs/audits/STATE-08-01.md` correctly established that enrollment and probe
generation reused the exact same selected image. It also correctly rejected
the resulting numbers when they were presented as recognition accuracy. Those
historical facts remain unchanged.

The finalized Paper 1 decision changes the research question, not the audit
record. The same-source values are invalid as recognition-accuracy claims but
are selected as the canonical evidence for the correctly scoped Paper 1
question: how well each mode retains a source identity under controlled image
degradation.

## Separate LFW evidence that Paper 1 excludes

The repository also contains a valid **gallery/probe-disjoint 1:N LFW
identification** run. Its all-41 threshold-gated results are **1.41% for
LBPH**, **80.65% for SFace**, and **80.65% for the cascade**. Those values
answer a different question because each probe is a different photograph of
the enrolled person. They remain valid repository evidence for that protocol,
but they are explicitly excluded from Paper 1 and must not be merged with,
substituted for, or used to reinterpret the same-source retention values.

The pairwise-verification results are a third protocol. They score genuine
and impostor pairs and likewise remain outside Paper 1.

## The complete Paper 1 flow

1. **Select one source image per identity** with the recorded deterministic
   selection rule.
2. **Enroll or train each identity from that source** in LBPH and SFace.
3. **Create the clean self-match probe** from the same source.
4. **Generate every controlled modification** from that source with the
   recorded deterministic seed.
5. **Score identical probes in all three modes** so per-mode comparisons use
   the same pixels.
6. **Count retained source-identity decisions** under each mode's recorded
   accept rule.
7. **Report each modification separately**, then aggregate using the source
   report's recorded averaging rule.
8. **Treat escalation and latency as diagnostics**, not as evidence that the
   experiment measured verification, FAR, or real-world deployment accuracy.

## Where the evidence lives

- Canonical same-source report used by Paper 1:
  `docs/results/robustness_test/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md`
- Reproduction run record:
  `docs/results/robustness_test/benchmark/lfw2_robustness_rerun/accuracy_ratio_hybrid.md`
- Historical protocol audit:
  `classical-cv/docs/audits/STATE-08-01.md`
- Separate, Paper-1-excluded disjoint result summary:
  `docs/results/robustness_test/ROBUSTNESS_RESULT_PROVENANCE.md`
- Live protocol distinctions:
  `.claude/skills/robustness-protocol-map/SKILL.md`

`classical-cv/reports/` and `classical-cv/outputs/` are working/run-record
locations, not citation sources. Check the robustness-results README,
`docs/results/RESULTS_MANIFEST.json`, and the provenance audit before citing
an artifact.

---

# Comprehensive Version

## 1. Canonical Paper 1 measurement contract

Let identity (i) have one selected source image (x_i). The same (x_i)
is used to construct that identity's enrollment representation and every
controlled probe (T_{m,l}(x_i)), where (m) is the modification and (l)
is its recorded level.

For a given mode, a probe is retained when the system's selected identity is
(i) and the mode's recorded accept rule passes. For modification (m) and
level (l):

\[
R_{m,l}=100\times\frac{K_{m,l}}{M_{m,l}},
\]

where (K_{m,l}) is the number of retained source-identity decisions and
(M_{m,l}) is the number of generated probes evaluated under the source
report's no-face policy. Overall retention follows the source report's
recorded per-modification aggregation; it is not recomputed using a different
weighting merely to compare it with another protocol.

The clean row is a self-match baseline. It shows whether the recorded pipeline
can re-detect and accept the enrolled source before synthetic damage. It is
not a held-out recognition baseline.

## 2. Why this is controlled robustness rather than recognition accuracy

The protocol intentionally holds identity appearance and source capture
constant. This makes modification-specific drops easier to attribute to the
controlled transform, detector, preprocessing, matcher, threshold, or cascade
route. It does not expose the system to a different photograph of the same
person and therefore cannot support a cross-photo generalization claim.

Other enrolled identities can still compete in the gallery, so a transformed
probe may lose its source identity and count as a retention failure. However,
the run contains no different-photo genuine queries and no explicit impostor
or unknown queries. Consequently:

- retention is a valid controlled robustness outcome;
- “identification accuracy” is not a valid label for it;
- verification accuracy cannot be computed;
- FAR/FPIR cannot be estimated; and
- deployment or open-set conclusions require separate evidence.

## 3. Protocol boundary table

| Protocol | Enrollment/probe relationship | Valid outcome | Paper 1 status |
| --- | --- | --- | --- |
| **Same-source self-match** | One source per identity is enrolled/trained and transformed into its own probes | Within-image degradation retention and per-modification transform sensitivity | **Canonical Paper 1 robustness method** |
| **Gallery/probe-disjoint 1:N identification** | Probe is a different photo of its enrolled identity; all gallery identities compete | Rank-1 and threshold-gated TPIR/AR for different-photo identification | Valid repository evidence, **excluded from Paper 1** |
| **Pairwise verification** | A probe is scored against genuine and impostor partners | TAR, FAR, and accuracy at a named operating point | Valid separate protocol, **excluded from Paper 1** |

Do not compare headline percentages across these rows without naming the
protocol, pairing, operating point, no-face policy, modification set, and
aggregation rule.

## 4. Modifications and reproducibility

The Paper 1 source report uses its recorded 41-variant configuration
(internally named `legacy`)
across brightness, contrast, gamma, Gaussian noise, Gaussian blur, motion
blur, rotation, zoom, and occlusion families. Multiple recorded levels within
the families produce the 41 variants. Report per-modification results before
the overall mean so a strong average cannot hide a specific failure mode.

Reproduction must preserve the source report's:

- one-source-per-identity selection and seed;
- exact source image reuse for enrollment and probe generation;
- modification names, levels, pixel operations, and deterministic RNG tokens;
- engine preprocessing and model artifacts;
- threshold/gate rules and their provenance;
- no-face policy;
- mode list; and
- aggregation rule.

Changing any of these produces a new run and requires a new provenance record;
it must not silently replace the Paper 1 values.

## 5. Engine decisions and threshold scope

The three mode rules are implemented in the live recognizer and gate code:

| Mode | Recorded decision concept |
| --- | --- |
| `cv_only` | Source identity selected by LBPH and LBPH accept edge passed |
| `dl_only` | Source identity selected by SFace and its genuine-match rule passed |
| `cascade` | LBPH fast path or SFace escalation under the recorded gate rules |

Read `classical-cv/src/hybrid/thresholds.json` and the exact historical run
record before quoting a threshold. The robustness experiment applies a
decision rule; it does not derive that rule's FAR. A threshold's separately
calibrated FAR describes the calibration corpus and method, not the
same-source probe population.

## 6. Reporting contract

Paper 1 reporting should include:

- the one-source enrollment/probe relationship;
- clean self-match retention;
- per-modification or per-family retention;
- the overall recorded retention for LBPH, SFace, and cascade;
- the exact modification set and aggregation rule;
- threshold and no-face-policy provenance; and
- the explicit absence of different-photo probes and impostor/unknown probes.

Use **retention** in prose and table headings. If a source JSON or recorded
report uses `ar_percent`, treat that as a historical schema field and map it
to the correctly scoped retention term; do not inherit an over-broad
“Accuracy Ratio” interpretation.

Recommended language:

> One source image per identity was enrolled and transformed into the clean
> and modified probes. The reported percentages therefore measure
> source-identity retention under controlled degradation, not different-photo
> recognition, pairwise verification, FAR, or open-set performance.

## 7. Relationship to the Independence Test

The robustness test asks how a known enrolled source decision changes after
controlled transformations. The independence tests use cross-identity score
distributions to calibrate or diagnose operating points. They can provide
threshold provenance, but they do not convert same-source retention into FAR
or verification accuracy. Keep the robustness result and the threshold-basis
evidence as separate claims.

## 8. Separate protocol execution

Omitting `--split-manifest` selects the same-source transform-sensitivity path
in `src/benchmark/accuracy_ratio_hybrid.py`; that is the protocol family
selected for Paper 1. Reproduction of the recorded Paper 1 values must use the
artifact's exact recorded arguments and model state rather than assuming
today's defaults reproduce a historical run.

Passing `--split-manifest data/splits/lfw_ident_split_seed42.json` selects the
gallery/probe-disjoint 1:N identification protocol. Run and report that path
only as separate repository evidence, never as a replacement Paper 1 result.
Use `src/benchmark/accuracy_ratio_verification.py` for the separate pairwise
verification protocol.
