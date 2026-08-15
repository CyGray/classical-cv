# Research Strengthening and Defensibility Roadmap

**Project:** LS-Face / classical-to-deep face-recognition cascade  
**Audit date:** 2026-08-13  
**Purpose:** repository-wide scientific and manuscript audit, followed by a prioritized experiment and engineering backlog  
**Status:** working review document; audit-time calculations below are diagnostic, not new canonical results

## 1. Executive verdict

The project contains useful evidence, but the current manuscript is not yet defensible as proof that the proposed hybrid system improves recognition, security, or efficiency.

The evidence currently supports a narrower conclusion:

1. On the tested La Salle DB1 split and internal 41-transform battery, SFace is much more robust than thresholded LBPH and repairs most LBPH failures.
2. The deployed LBPH-to-SFace gate reproduces SFace accuracy because it escalates often. It has not shown an accuracy advantage over SFace, and the current recognition-stage timing shows it is slower on the transformed LSDB workload.
3. On wild LFW images, the strict LBPH operating point largely collapses, forcing nearly every query to SFace. This is an important failure boundary, not evidence of an efficient cascade.
4. Current low-FAR language is too strong. Pairwise false-match calibration is mixed with 1:N identification, the cascade denominator is wrong in one canonical result, threshold calibration leaks into the LFW robustness test, and deployment uses different gallery rules from calibration.

The strongest honest paper is therefore one of these:

- **Preferred if new experiments succeed:** a risk-constrained, cost-aware selective-computation system that is statistically non-inferior to SFace and demonstrably cheaper on the measured deployment workload.
- **Preferred if they do not:** a rigorous failure-boundary study showing when a classical-first face cascade saves compute, when domain shift makes it collapse to the deep model, and why pairwise low-FMR calibration does not establish 1:N system security.
- **Ambitious redesign:** replace LBPH as the first stage with a genuinely cheap learned recognizer or quality/risk estimator, and keep the present system as a well-audited baseline.

Do not submit the present security, independence, FAR, or efficiency claims unchanged. Complete the P0 work in Section 4 first.

## 2. Audit scope and baseline

The audit covered:

- the workspace/repository protocol maps and result-governance rules;
- the latest live manuscript, [lsface.docm](manuscript/lsface.docm);
- the four canonical result areas: algorithm selection, threshold/independence, complementarity, and robustness;
- relevant selection, threshold, recognizer, gate, timing, robustness, merge, cache, and provenance code paths;
- the claim-evidence register and result manifest;
- small read-only/post-hoc smoke analyses using existing canonical rows, plus targeted LSDB gallery-rule checks.

Baseline details:

- Workspace commit: `d4cbfd1ceeb4e344f7d0cbb278f74b51afe2a66a` on `master`, with pre-existing uncommitted work.
- Live manuscript SHA-256: `66AD2D5DC08C5ADF38C1E2E995F9995B27929766241E850D04E1784007C1D4C7`.
- The live manuscript is byte-identical to `docs/manuscript/copy/014_lsface_dl-trio-selection-final-verified.docm`.
- The sequential `docs/manuscript/versions/` archive currently ends at `010b`, so the live/014 lineage is not represented by the required numbered archive sequence.
- The manuscript is approximately 14 pages and 3,785 words, with six tables and four logical figures.

This was not a fresh full benchmark campaign. Audit-time smoke results should be used to choose experiments, not copied into the paper as final evidence. A final manuscript edit also needs a clean Word-to-PDF render and page-by-page visual check.

## 3. What is defensible now

| Evidence | Defensible wording | Wording to avoid |
|---|---|---|
| [Classical LSDB selection](results/algo_test/lsdb_selection_2026-08-10/) | “On this deterministic LSDB split, LBPH was the strongest of the three tested classical recognizers: 96.43% test TAR and 100% Rank-1.” | “LBPH won a fully precommitted selection protocol” or “generalizes best.” The stored campaign did not enforce the stated memory/FPS/AR rule, and its executed source is not recoverable from the recorded commit. |
| [DL trio selection](results/algo_test/lsdb_selection_dl_trio_2026-08-11/) | “SFace and FaceNet both scored 56/56; SFace was selected as a deployment-compatible tie-break because its stored embedding is 512 B versus 2,048 B.” | “SFace is significantly more accurate.” SFace/FaceNet are tied; SFace versus ArcFace has only two discordant cases and exact paired McNemar `p = 0.5`. |
| [LBPH LFW threshold artifact](results/independence_test/independence/lbph_lfw1/native_predict_scale_yunet.json) | “67.0332552 is an empirical calibration-tail operating point: rank 165 among 16,522,626 ordered comparisons, realized 9.986 ppm on that calibration construction.” | “Validated 10-ppm system FAR,” “security guarantee,” or population-level error bound. |
| [SFace LFW threshold artifact](results/independence_test/independence/sface_lfw1/standalone_l2_yunet.json) | “1.03062785 is an empirical one-template LFW calibration point.” | Treating the rounded deployed `1.0313`, a multi-shot centroid gallery, and the standalone artifact as exactly the same experiment. |
| [LFW robustness output](../classical-cv/outputs/benchmark/lfw2_robustness_canon/) | Rank-1 is a useful descriptive result on the specified known-probe split. The stored rounded AR values match the raw output. | Calling thresholded AR independent final testing: 563/1,680 test probes were directly used in threshold selection. Do not call the known-probe-only test open-set. |
| [LSDB-DL41 complementarity](results/complementarity_test/reruns/lsdb_dl41_2026-08-10/) | “Across 28 identities, SFace consistently repaired many thresholded LBPH errors in the internal transform suite.” Identity-cluster recovery estimate: 81.56%, 95% bootstrap CI about 79.74–83.13%; all 28 identity effects favor SFace, exact sign/randomization `p = 7.45e-9`. | Row-level McNemar `p < 1e-300` as inferential evidence; the 2,296 rows are 56 source images × 41 correlated transforms. Avoid “mutual complementarity”: LBPH-only correct cases are zero under the thresholded definition. |
| [Gate curve](results/complementarity_test/reruns/lsdb_dl41_2026-08-10/gate_operating_curve.json) | “LBPH distance and negative margin predict threshold-free LBPH Rank-1 error on this suite.” Identity-cluster AUCs are approximately 0.9502 [0.9278, 0.9665] and 0.9532 [0.9345, 0.9675]. | Turning an in-sample AUC into proof that the deployed gate is optimal or transferable. The gate still needs nested selection and a locked test. |

### Important distinction

The project currently uses “independence” for several different ideas: cross-identity score enumeration, image-disjoint gallery/probe selection, model complementarity, and statistical independence of trials. These are not equivalent. Rename the method to **exhaustive cross-identity empirical tail calibration** unless a formal independence hypothesis and valid dependence-aware test are introduced.

For traceability, the current LFW snapshot contains 68,880 modified rows (`1,680 × 41`). Its descriptive clean AR values are 2.2619% LBPH, 92.0238% SFace, and 92.0238% cascade; its all-41 AR values are 1.4141%, 80.6475%, and 80.6461%. All-41 Rank-1 values are 4.2567%, 85.0929%, and 85.0915%. Escalation is about 97.51%. These numbers match the raw files after rounding, but thresholded values must be rerun after leakage and provenance repairs.

The audit cluster calculations used deterministic seed `20260813`: 200,000 identity/base-image bootstrap replicates for recovery and 1,000 identity bootstrap replicates for AUC. They should be reproduced by a checked-in analysis script before publication.

## 4. P0: validity blockers to fix before submission

### P0.1 Correct the security unit: FMR is not FPIR

In [independence_test.py](../classical-cv/src/hybrid/independence_test.py), the cascade makes at most one 1:N decision per query, but the result divides accepted queries by `N(N-1)` pair comparisons.

For the finalized LSDB snapshot:

- identities/queries: 28;
- ordered cross-identity comparisons: 756;
- cascade accepted impostor-only queries: 2;
- currently reported quantity: `2/756 = 0.2646%`;
- correct query-level false-positive identification rate for that constructed test: `2/28 = 7.1429%`.

That is a 27× denominator error. Fix the code, schema, tables, figures, captions, claim register, and any downstream prose. Keep these estimands separate:

- **FMR/FAR:** false match rate for verification comparisons;
- **FPIR:** fraction of unknown 1:N search transactions returning any identity;
- **TPIR/DIR:** fraction of enrolled probes correctly identified and accepted;
- **FNIR:** fraction of enrolled probes not correctly identified/accepted;
- **Rank-1/CMC:** identity ranking without conflating rejection.

At a hypothetical independent per-comparison FMR of 10 ppm and 5,748 impostor opportunities, `1 - (1 - 10^-5)^5748 ≈ 5.59%`. Real scores are dependent, so this is only an illustration; the solution is empirical query-level FPIR on the actual gallery.

Also correct the LSDB pair analysis. SFace’s 756 ordered symmetric rows represent 378 unique identity pairs; its two directed false matches are one unordered pair. The point estimate remains `1/378 = 0.2646%`, but the effective sample size and interval change. All pairwise intervals must account for shared identities; ordinary Wilson intervals over 756 rows are anti-conservative.

### P0.2 Remove LFW calibration/evaluation leakage

Both LBPH and SFace threshold scripts use the seed-42 selector in [run_lfw_independence.py](../classical-cv/scripts/pipeline/run_lfw_independence.py). The robustness split is independently sampled from the same identity folders by [make_lfw_identification_split.py](../classical-cv/scripts/utils/make_lfw_identification_split.py).

Exact overlap audit:

- robustness probes: 1,680;
- exact robustness probe images also selected for threshold calibration: 563 (`33.51%`);
- calibration pick equals the robustness gallery image: 597;
- calibration pick is another image of that identity: 520;
- all 1,680 robustness identities participate in threshold calibration.

Consequences:

- thresholded AR/TPIR is not held-out final evidence;
- LBPH `67.0332552` and standalone SFace `1.03062785` are both affected;
- Rank-1 itself is threshold-free and is not numerically changed by this threshold leakage, but its scope remains this one known-identity LFW construction.

Redesign:

1. Split identities before selecting any image, model, threshold, gate rule, or quality cutoff.
2. Use development identities for model fitting and inner calibration.
3. Lock outer identities and images for one-time final evaluation.
4. If the intended product is closed-set recognition of enrolled users, calibrate global thresholds on separate development identities, then enroll final users with separate gallery images and evaluate only fresh probes.
5. Include unknown identities not enrolled in the gallery for direct FPIR.
6. If data are scarce, use repeated nested grouped cross-validation by identity and aggregate each outer prediction once.

Correct the existing memo that calls the current LFW manifest “identity-disjoint.” It is gallery/probe image-disjoint within overlapping identities, not calibration/evaluation identity-disjoint.

### P0.3 Match calibration to the deployed gallery rule

The deployed and calibrated systems are different:

- LFW LBPH calibration uses one selected template per identity.
- Deployment LBPH contains 280 templates, ten per each of 28 identities, and [LBPHAdapter.score](../classical-cv/src/hybrid/recognizer.py) takes the minimum distance per label.
- LFW standalone SFace calibration uses a selected single embedding per identity.
- Deployment SFace averages the enrolled embeddings, normalizes the centroid, and scores against that centroid.

Audit-time LSDB smoke test, using 56 probes and 1,512 impostor identity comparisons, demonstrates why this matters:

| Diagnostic | Result |
|---|---:|
| LBPH one-template rank-15 edge | 74.6129 |
| LBPH ten-template/min-per-label matched edge | 70.5967 |
| One-template edge applied to ten-template gallery | 8.267% FAR versus intended 0.992% |
| Frozen 67.033 on ten-template LSDB gallery | 0/1,512 observed false matches; TAR 60.71% |
| SFace ten-shot centroid rank-15 edge | 1.05226 |
| Frozen 1.0313 on ten-shot LSDB centroids | 7/1,512 false matches = 0.463%; TAR 100% |
| Singleton SFace edges applied to centroids | 1.73×–4.00× target FAR; mean 2.55× |

These are diagnostic LSDB results, not replacement thresholds and not evidence about LFW. They show that calibration can move substantially when the enrollment aggregation changes. Recalibrate and test the exact production rule at `m = 1, 2, 4, 8, 10+` templates per identity, with the intended gallery identity count and domain.

### P0.4 Build a real open-set identification test

The current LFW robustness split contains:

- 5,749 gallery identities;
- 1,680 probes, all belonging to enrolled identities;
- 4,069 singleton identities that are gallery-only;
- no un-enrolled/unknown probes.

Therefore it cannot measure end-to-end false-positive identification. Build a protocol with:

- known enrolled probes for TPIR/FNIR and CMC;
- unknown identities for FPIR;
- fixed gallery-size conditions;
- a no-face/detection-failure outcome;
- exact query-level decisions and scores;
- TPIR at predeclared FPIR targets, OSCR, CMC, DET, and confidence intervals.

For the actual deployment, a decisive test is unknown external faces queried against the real 28-person, ten-shot LSDB gallery. This is more relevant than calibrating LFW identities against an LFW gallery and transferring the threshold to a campus gallery.

### P0.5 Fix the low-tail threshold method and language

The manuscript equation `k = ceil(alpha C)` does not guarantee an empirical realized rate no greater than `alpha` under an inclusive `score <= threshold` rule. Use an explicit order-statistic convention:

1. Let `a = floor(alpha C)` be the maximum allowed accepted calibration comparisons.
2. Sort scores in acceptance order.
3. Choose a threshold strictly between the `a`th and `(a+1)`th scores when possible.
4. Handle ties explicitly; never split equal scores silently.
5. Report both the requested rate and realized accepted count/rate.
6. Estimate threshold uncertainty on development data, then validate once on disjoint queries/identities.

With zero observed errors, the rough “rule of three” upper 95% bound is `3/n`. Demonstrating an upper bound near 10 ppm requires roughly 300,000 independent query-level trials with zero false identifications. Millions of correlated pair rows do not automatically supply that evidence.

Replace “10-ppm FAR guarantee” with “empirical calibration operating point” until a disjoint, deployment-matched validation supports stronger wording.

### P0.6 Verify and freeze the 41-transform protocol

The manuscript says 41 variants across 12 transformation types and describes a levels-then-modifications aggregation. The implemented DL41 battery is 41 one-level variants across **17 categories**: 17 light, 13 medium, and 11 heavy. Its headline metric weights all 41 variants equally.

[modifications.py](../classical-cv/src/benchmark/modifications.py) explicitly implements a repository-owned “reasonable-best” interpretation. The external team’s exact pixel generator is unavailable, and [41mods_table/TODO.md](results/robustness_test/41mods_table/TODO.md) records unresolved specification questions. This makes current “same protocol as the DL team” language indefensible.

Required work:

- establish a normative transform specification for every variant;
- resolve brightness, color quantization, blur, crop/scale, rotation border, aspect, translation, skew, and perspective semantics;
- generate one set of golden input/output images;
- record pixel hashes and library versions;
- add unit tests for shape, dtype, parameter, deterministic output, and expected hash;
- run stochastic corruption with multiple fixed seeds rather than one noise draw;
- publish both all-41 and matcher-only-37 summaries, because the four detector-canonical transforms can mix detector/orientation behavior with matcher behavior;
- report detector success, strict no-face failures, and matcher error separately;
- label old results “internal deterministic synthetic stress suite” until equivalence is proven.

The current harness also claims direct comparability with `deep-learning/ar-table.py`, but the protocols differ. The legacy script performs same-image 1:1 genuine transform sensitivity, uses a stale threshold, and macro-averages 17 categories after averaging their tiers. The current harness performs thresholded 1:N identification and weights 41 variants equally. Audit-time reaggregation of the canonical LSDB rows changed LBPH from 30.79% to 34.28% and SFace/cascade from 87.24% to 89.74%. Mark historical tables non-comparable unless all engines use one manifest, pixel generator, metric, threshold, and aggregation rule.

Do not use the modified-independence path as DL41 evidence without repair: it converts images to grayscale before applying transforms, so color transformations cannot match the color pipeline. Also quarantine the legacy `deep-learning/tests.py` “verification” output, which allows self-retrieval and therefore does not provide a valid independent genuine test.

### P0.7 Replace pseudoreplicated statistics

The 2,296 LSDB-DL41 rows are not 2,296 independent observations. They are:

- 28 identities;
- two source test images per identity;
- 41 deterministic transforms per source image.

Use identity as the primary sampling unit and source image as a nested cluster. A defensible analysis should include:

- identity-cluster bootstrap confidence intervals;
- paired identity-level permutation/sign tests;
- a hierarchical bootstrap `identity -> source image -> stochastic transform draw` where randomness exists;
- effect sizes and intervals, not only p-values;
- Holm correction or false-discovery-rate control for 41 per-transform tests;
- sensitivity analyses at both identity and source-image levels.

The main complementarity result survives this correction:

- recovery: `1296/1589 = 81.5607%`;
- identity-cluster bootstrap 95% CI: approximately `79.740–83.128%`;
- every one of 28 identity-level effects favors SFace;
- exact identity sign/randomization `p = 7.45e-9`.

Report the existing row-level McNemar result only as a descriptive contingency count, not an inferential p-value.

### P0.8 Repair algorithm selection

The claim register describes a precommitted classical rule requiring TAR at least 90%, feature size below 1 KB, live FPS at least 3, and then 41-modification AR. The selected LBPH representation is 65,536 B, so it fails the stated eligibility rule. The campaign script did not compute/apply the full rule, AR, or FPS, and the stored result contains a post-hoc engineering exception.

There is also a split problem: lexicographic filename allocation gives the same light/pose views to calibration (including `light_right.jpg` and `light_up.jpg`) and uses the reported test performance to choose the winner. That “test” set is therefore a selection set, not untouched final evidence.

Choose one defensible path:

- **Strict:** honor the old rule and report that no classical candidate was eligible.
- **Recommended:** predeclare a new realistic system-level rule, explain why the old per-feature `<1 KB` constraint was invalid, and rerun selection with a locked final test.

New rule should constrain actual deployable resources: model file size, bytes per enrolled identity, peak RSS, cold load time, warm p50/p95 latency, energy/query, detector cost, and accuracy/security endpoints. Use repeated pose/light/session-grouped splits and reserve an external final session.

For the DL trio, use cautious wording. On `n = 56`:

- SFace and FaceNet: 100%, Wilson 95% CI 93.58–100%;
- ArcFace: 96.43%, Wilson 95% CI 87.88–99.02%;
- SFace versus ArcFace: two discordant probes, exact paired McNemar `p = 0.5`.

SFace is defensibly selected by a prespecified deployment/footprint tie-break, not an accuracy win. Repeat evaluation with each model’s native preprocessing and a separate common-preprocessing track; the present SFace-style YuNet alignment and LAB-CLAHE pipeline is not inherently fair to ArcFace and FaceNet, and it does not exactly match deployment.

### P0.9 Make timing measure what the labels claim

`HybridRecognizer.predict(mode="dl_only")` still executes LBPH and quality scoring before SFace. With score memoization, mode order changes which work is cached. Without memoization, “dl_only” includes LBPH. The current AR timer also excludes detection and much of I/O/preprocessing. Therefore Table 5’s mode latency is not a clean comparison of LBPH-only, SFace-only, and cascade.

Required fixes:

- branch to a true SFace-only path before LBPH;
- benchmark engine functions directly for component timing;
- benchmark full detector-to-decision latency separately;
- randomize/interleave mode order or run isolated processes;
- use warm-up and repeated trials;
- report cold start, warm p50/p95/p99, throughput, peak RSS, energy/query, and thermal behavior;
- report exact hardware, OS, OpenCV/ONNX settings, thread count, power mode, gallery size, and cache state;
- run on the target Raspberry Pi, not only the development machine.

### P0.10 Make every canonical artifact self-verifying

Current LFW robustness JSON/CSV numbers match the manuscript after rounding, but the run does not embed enough provenance to prove which thresholds, code, models, detector, images, command line, or environment produced it. Resume and merge code can also combine stale/incompatible segments silently.

Every new run needs an immutable fingerprint over:

- full resolved configuration and exact command line;
- code commit, dirty flag, patch hash, and executed-script hashes;
- dataset archive/tree, split-manifest, and individual enrollment-image hashes;
- LBPH model/label pair, SFace model, YuNet model, and any preprocessing asset hashes;
- exact numeric thresholds and threshold-file hash;
- Python/OpenCV/NumPy/ONNX/runtime package lock;
- hardware/OS/threading/power configuration;
- seeds, segment bounds, expected row counts, and output schema version.

Segment workers should write atomic completion markers containing the run fingerprint, row count, and CSV/JSON hashes. Merge must hard-fail on a missing segment, gap, overlap, duplicate row key, mismatched fingerprint/schema/seed/mode/threshold, or unexpected count. Enrollment caches must include image-content, model, preprocessing-code, and runtime hashes. A custom LBPH model must never be accepted without its matching label map.

The result manifest also needs semantic statuses. Its generator still defaults nearly every non-PNG file to `canonical_snapshot`; this has labeled known legacy/fallback reports as canonical. On 2026-08-13, the gate accept-protection replay became the first explicit reviewed-campaign allowlist entry, using `canonical_descriptive_only`. Continue replacing the broad heuristic with reviewed allowlists and automated protocol assertions. Useful states include:

- `canonical_validated`;
- `canonical_descriptive_only`;
- `historical_noncomparable`;
- `needs_provenance_review`;
- `rerun_required`;
- `reference_specification`.

Current manifest audit counts make this urgent: 162 files are listed, 148 are labeled `canonical_snapshot`, eight gate-replay artifacts are labeled `canonical_descriptive_only`, 44 source scripts are unrecorded, 22 declared source paths are missing, and eight entries have null commits. Hash consistency proves that a stored file has not changed; it does not prove that its scientific protocol is valid.

The classical selection provenance is one concrete example. Its `run_provenance.json` records commit `6e269e...`, but that commit does not contain the cited scoring script. The current script hash is `3288ce8816f73b9e81421e70b1089be035aae389505a7b646a8eb65b7f805306`, which cannot establish the hash of the historically executed source. Preserve the existing result as descriptive and rerun it under the new contract.

## 5. Audit-time smoke tests: what they suggest

These post-hoc calculations are hypothesis generators. They may be reported as canonical descriptive-only results when their same-data scope is explicit, but independent data remain necessary before a deployment-policy, open-set, or general-performance claim.

### 5.1 Gate ablation on the 2,296 modified LSDB rows

| Routing policy reconstructed from stored rows | AR (%) | Escalation (%) |
|---|---:|---:|
| Current deployed rule | 87.2387 | 71.5157 |
| Quality cannot override `d <= tau_accept`; deployed margin trigger retained | 87.2387 | 59.2334 |
| Remove margin trigger | 87.1951 | 71.1672 |
| Ambiguous distance band only | 87.1951 | 58.8850 |
| Quality triggers only | 59.9739 | 42.2474 |
| Margin trigger only | 61.2369 | 33.1882 |
| LBPH only | 30.7927 | 0 |
| Always SFace | 87.2387 | N/A: direct baseline, no routing stage |

Interpretation:

- Quality flags added about 12.28 percentage points of escalation and no accuracy on this battery.
- The margin trigger added about 0.35 points of escalation and one correct row.
- `tau_reject` changes from 132.13 through 148.13 did not move the stored curve, consistent with a near-inert hard-reject branch.
- The accept-protection candidate reduced escalations of thresholded LBPH-correct probes from 289/707 to 7/707 and the stored recognition-stage arithmetic mean from 11.9585 to 10.8125 ms. It remained slower than direct SFace at 8.3253 ms.

The replay is canonically archived at `results/complementarity_test/reruns/gate_accept_protection_descriptive_2026-08-13/` as `canonical_descriptive_only`. It supports a bounded routing observation and motivates the simpler candidate, but it does not justify changing the runtime gate; the same rows shaped and evaluated the policy. Target-device testing is explicitly outside this result's scope.

### 5.2 A cost lower bound for the present sequential architecture

Stored recognition-stage anchors on the transformed LSDB workload are:

- LBPH: 5.2494 ms;
- SFace: 8.3253 ms;
- deployed cascade: 11.9585 ms at 71.5157% escalation.

These imply an observed incremental escalated-stage cost of about 9.3813 ms. The cascade would need escalation below about 32.79% to beat the observed SFace-only mean, or below 36.95% under an idealized additive assumption using 8.3253 ms as the second-stage cost.

However, `1296/2296 = 56.45%` of modified rows are SFace-only recoveries. An oracle router restricted to preserving every one of those recoveries must therefore escalate at least 56.45%. At the observed component costs, its lower-bound mean is about 10.545 ms—still 26.7% slower than SFace-only.

This is a decisive design constraint: on this workload, no routing threshold can make the current sequential LBPH-first architecture both exactly as accurate as SFace and faster under the recorded costs. Improvement requires at least one of:

- tolerate a predeclared small accuracy loss;
- make the first stage much cheaper;
- share preprocessing or avoid duplicate work;
- make the second stage cheaper when escalated;
- use a workload dominated by easy clean frames;
- replace LBPH with a better low-cost first stage.

### 5.3 Workload crossover

On the 56 clean LSDB probes, the reconstructed cascade mean was about 8.79 ms versus 9.494 ms for SFace, with 46.43% escalation. On modified probes, it was about 13.329 ms versus 9.279 ms. A two-component mixture crosses over at approximately **14.8% hard/modified traffic**. Above that fraction, the current cascade loses its mean-latency advantage under these stored timings.

This makes the real deployment workload distribution a first-class experimental variable. Log and label real streams rather than assuming the 41-transform mixture represents production. Also check tails: even where clean mean improved, the reconstructed clean p95 was worse for the cascade.

## 6. Master experiment program

### Tier A — decisive validity experiments

| ID | Experiment | Design | Primary outputs / pass condition |
|---|---|---|---|
| A1 | Leakage-free protocol | Identity-grouped development/calibration/final partitions; lock manifests before scoring. Repeat outer folds if needed. | Zero path/hash overlap; no outer identity informs models, thresholds, gate, quality rules, or model selection. |
| A2 | Deployment-exact open set | Actual 28-person, ten-shot LSDB gallery; fresh enrolled probes and external unknown people. Repeat across sessions/cameras. | Query-level TPIR at fixed FPIR, FNIR, CMC/OSCR, detector failure; clustered CIs. |
| A3 | Gallery-size/template-count scaling | Cross `m={1,2,4,8,10}` templates/person with gallery identities `G={28,100,500,1000,...}` where data permit; LBPH min aggregation and SFace centroid/alternative pooling. | Threshold, TPIR, FPIR, latency, memory versus `m` and `G`; no transferred one-shot claims. |
| A4 | Direct joint cascade calibration | Run the exact three-way gate on unknown queries. Select all cutoffs jointly on calibration data under a system FPIR constraint. | Measured cascade FPIR, not union bound; locked final TPIR/FPIR. |
| A5 | Corrected LSDB independence snapshot | Deduplicate symmetric pairs where applicable; retain query IDs; fix cascade denominator; use identity-aware uncertainty. | Correct FMR and query-level FPIR tables; regression tests catch `N` versus `N(N-1)`. |
| A6 | Frozen transform conformance | Normative DL41 spec, golden images and hashes, unit tests, visually reviewed montage. | Every transform deterministic/versioned or has a declared stochastic seed distribution. |
| A7 | Leakage-free robustness rerun | Locked final base images; all 41 variants; multiple draws for stochastic transforms; strict failure accounting. | All-41 and matcher-only-37 results; detector/matcher decomposition; identity-cluster CIs. |
| A8 | Gate ablation and random baseline | Current gate, band-only, margin-only, each quality flag, no hard reject, random gate at matched escalation, always-LBPH, always-SFace, oracle router. Tune only inside development folds. | Paired accuracy-cost curves and non-inferiority interval versus SFace. |
| A9 | True end-to-end target timing | Isolated implementations on Raspberry Pi and development machine; detector through decision; cold/warm repeated interleaved trials. | p50/p95/p99 latency, throughput, peak RSS, load time, energy, thermals; bootstrap CIs. |
| A10 | Reproducibility rerun | New fingerprinted segmented run, then an independent rerun from a clean environment. | Bit-identical manifests/config; statistically identical outputs; no unverified cache/segment reuse. |

### Tier B — experiments that make the paper strong

#### B1. Real target-domain capture

Collect independent sessions, not more transforms of the same pixels. Cross:

- subject/session/day;
- camera and resolution;
- indoor/outdoor, front/back/side light, low light;
- distance, yaw/pitch, motion blur, masks, glasses, partial occlusion;
- single and multiple faces;
- enrolled and unknown visitors;
- still-image and video/temporal decision modes.

Document consent, demographics only where ethically permitted, capture protocol, inclusion/exclusion, failures, and data retention. Hold one session completely untouched until final evaluation.

#### B2. Detector-versus-matcher decomposition

For every condition, report:

1. image delivered;
2. face detected;
3. correct face selected when multiple faces exist;
4. landmarks/alignment valid;
5. gallery identity ranks first;
6. score clears threshold;
7. final gate action.

This prevents rotation/crop failures from being misreported as recognizer robustness. Compare largest-face-only selection with tracked/declared target selection.

#### B3. Fair model selection

Evaluate SFace, FaceNet, ArcFace, and efficient alternatives in two tracks:

- **Native track:** each model’s intended detector, alignment, normalization, input size, and score.
- **Controlled track:** one common crop/alignment pipeline, with deviations documented.

Report model binary, dependencies, peak RSS, embeddings/user, load latency, warm latency, energy, accuracy, and FPIR—not embedding bytes alone. Suitable efficient baselines include EdgeFace, MixFaceNets, and a quantized direct SFace deployment.

#### B4. Risk-coverage and accuracy-cost curves

Treat escalation as selective prediction. For each gate, sweep coverage/escalation and report:

- selective risk among LBPH-accepted cases;
- total TPIR/FNIR/FPIR;
- mean and tail cost;
- energy/query;
- calibration curves for predicted failure probability;
- confidence bands;
- the Pareto frontier.

Optimize an explicit development-only objective, for example:

`min E[cost]`, subject to `FPIR <= alpha` and `TPIR_cascade - TPIR_SFace >= -delta`.

Predeclare `alpha`, the non-inferiority margin `delta`, and the production workload mixture.

#### B5. Score fusion and stronger ceilings

The current “both wrong” count is not a ceiling for fusion. Test:

- calibrated score-level fusion;
- identity-level candidate union/top-k reranking;
- learned logistic gate using distance, margin, quality, and detector confidence;
- a small tree/monotonic model constrained for interpretability;
- oracle top-1 router and oracle candidate-union ceiling;
- two-lightweight-DL cascades.

All learned/calibrated policies must be nested inside development folds. Compare them with simple rules at equal escalation and equal FPIR.

#### B6. Calibration transfer and drift

Measure threshold stability across:

- LFW versus LSDB versus new campus sessions;
- cameras and days;
- one-shot versus multi-shot enrollment;
- centroid, medoid, max/min, and quality-weighted template pooling;
- gallery additions/removals;
- aging or delayed re-capture;
- preprocessing and detector-version changes.

Report score-distribution shift and whether recalibration is required. Never silently transfer a threshold between these conditions.

#### B7. Low-tail uncertainty

Use disjoint calibration and final test sets. Add:

- exact accepted counts and denominators;
- Clopper-Pearson or suitable query-cluster intervals;
- identity bootstrap of the threshold and final metric;
- tie sensitivity;
- empirical extreme-tail plots;
- optional extreme-value modeling as a sensitivity analysis, never as the sole result;
- minimum sample-size justification for each target FPIR.

#### B8. Robustness beyond single transforms

After the DL41 spec is frozen, add:

- severity response curves rather than only three labels;
- combined corruptions such as low light + blur + compression;
- transform-order sensitivity;
- multiple noise seeds;
- natural corruptions from real captures;
- a separate detector-robustness battery;
- per-identity random effects and failure exemplars.

Do not tune thresholds on the same corrupted test battery.

#### B9. Video and temporal policy

The intended gate likely sees streams, not independent stills. Evaluate:

- first-frame, majority-vote, score aggregation, and track-level decisions;
- time-to-decision;
- false accepts per encounter/hour, not only per frame;
- repeated correlated frames from one person;
- tracking failures and multiple faces;
- compute saved by escalating only once per track.

A track-level cascade may be much more favorable than the current per-image design.

#### B10. Security and presentation attacks

Face recognition alone is not a complete home/access security system. Either narrow the scope to **bona fide face identification** or evaluate:

- printed-photo, replay-screen, mask, and injection attacks;
- passive or active presentation-attack detection;
- attack presentation classification error rate and bona fide presentation classification error rate;
- fallback behavior, rate limiting, audit logging, and second-factor policy.

Use the ISO/IEC 30107-3 presentation-attack testing framework when making PAD/security claims.

#### B11. Fairness and subgroup validity

Remove claims about “East/West facial structure” or “bio-mechanical diversity” unless there is ethical approval, relevant metadata, sufficient subgroup sample sizes, and a predeclared analysis. If fairness is in scope:

- report subgroup detector failure, FNIR, FPIR, and uncertainty;
- control image quality and capture-condition confounds;
- include intersectional strata only with adequate samples;
- perform threshold and calibration sensitivity;
- avoid biological explanations unsupported by the design.

#### B12. Data and label hygiene

Audit duplicate and mislabeled identities before low-tail calibration. Two exact cross-identity pixel duplicates were found in the local LFW tree:

- `Bart_Hendricks_0001` = `Ricky_Ray_0001`;
- `Carlos_Beltran_0001` = `Raul_Ibanez_0001`.

These create zero-distance “impostor” pairs. Verify against the source, publish the decision rule, and report threshold sensitivity with duplicate groups retained and removed. Also audit near duplicates, corrupted files, face-detection misses, and identity counts.

## 7. Statistical analysis plan

Use the following default units and analyses:

| Question | Sampling unit | Recommended analysis |
|---|---|---|
| Known-person identification | identity/query, clustered by identity/session | TPIR/FNIR/Rank-1 with identity bootstrap; paired differences between systems |
| Unknown-person 1:N search | unknown query/encounter | FPIR with exact/cluster interval; report gallery size |
| Verification | unique identity-pair structure | FMR/FNMR; dyadic/identity-aware bootstrap or permutation |
| Transform robustness | identity, then source image; transform is repeated condition | hierarchical bootstrap/mixed model; per-transform multiplicity correction |
| Gate comparison | same queries across policies | paired bootstrap/permutation; non-inferiority plus cost difference |
| Timing | repeated trial nested in image/device/run | distribution and hierarchical bootstrap; p50/p95/p99, not mean only |
| Model selection | outer identity/session fold | nested grouped CV; untouched final set |

Predeclare:

- primary outcome and one primary operating point;
- secondary/exploratory outcomes;
- inclusion and no-face rules;
- non-inferiority margin;
- confidence level and multiplicity method;
- seeds and number of repeats;
- stopping rule/sample size;
- which identity/session is the generalization unit.

Publish raw per-query decisions and scores where privacy permits. Always show denominators. A high p-value is not equivalence; use confidence intervals or a formal equivalence/non-inferiority design.

## 8. Code and artifact repair backlog

### Immediate tests

1. Synthetic `N=3` test proving cascade FPIR denominator is 3 queries, not 6 pairs.
2. Symmetric-distance test proving unordered-pair deduplication and correct intervals.
3. Threshold order-statistic tests for zero allowed accepts, ties, and inclusive/exclusive boundaries.
4. Runtime-config test proving artifact threshold = JSON threshold = recognizer threshold.
5. Fail-closed test when thresholds/config/model labels are missing.
6. Multi-shot enrollment test proving all templates/embeddings are retained and identity labels are stable.
7. Cache-key mutation test: changing an image, model, detector, preprocessing source, or OpenCV version invalidates enrollment.
8. Segment merge tests for gaps, overlaps, duplicates, missing files, mismatched run fingerprints, and wrong row counts.
9. True `dl_only` call-graph/timing test proving no LBPH or quality work runs.
10. Golden transform tests for all 41 variants.

### Configuration cleanup

- Make one typed, schema-validated threshold/config file authoritative.
- Remove the SFace source-constant/JSON split brain.
- Correct the LBPH metadata that associates 67.033 with `1e-4`; its artifact realizes about `9.986e-6` on calibration.
- Remove stale SFace `1.128` documentation/defaults.
- Prevent calibration code from regenerating obsolete thresholds or provenance.
- Version the decision rule, threshold semantics, preprocessing, and gallery aggregation together.

### Artifact contract

Each result directory should contain at least:

- `run_provenance.json`;
- immutable input/split manifest;
- resolved config;
- raw per-query/per-comparison rows;
- summary derived only from those rows;
- hashes for every item;
- validation report;
- environment lock;
- exact command and log;
- explicit scientific status and limitations.

Never infer provenance from timestamps or filenames. Never cite working files under `classical-cv/outputs/` until promoted with this contract.

## 9. Manuscript revision plan

### 9.1 Reframe the contribution

The present title, “Facial Recognition Using Hybrid Technologies Based on Independence Testing,” is broad and uses “independence” inaccurately. Better title directions:

1. **When Does a Classical-to-Deep Face Recognition Cascade Save Compute? A Leakage-Free Open-Set Evaluation**
2. **Failure Boundaries of an LBPH-to-SFace Cascade Under Domain Shift and Image Corruption**
3. **Risk-Constrained Selective Face Recognition on Edge Hardware**

The paper should not claim that a cascade is novel merely because LBPH precedes SFace. The contribution can instead be:

- a deployment-matched open-set evaluation protocol;
- exhaustive but carefully scoped empirical tail calibration;
- a falsifiable cost-aware gate objective;
- dependence-aware robustness statistics;
- a measured boundary showing when selective computation succeeds or fails.

### 9.2 Abstract

Rewrite after the P0 reruns. It should contain:

- task and threat model;
- data and identity/session split;
- exact baselines;
- one security operating point stated as FPIR or FMR correctly;
- accuracy and cost with confidence intervals;
- the negative boundary if the cascade does not beat SFace;
- a scoped conclusion.

Remove generic phrases such as “organically links,” unsupported security claims, and unsourced East/West anatomical claims.

### 9.3 Introduction

Use this logic:

1. Edge face recognition faces a measurable risk-cost tradeoff.
2. A cheap-first cascade helps only if easy queries are common, accepted safely, and the first-stage overhead is smaller than avoided deep inference.
3. Pairwise low-FMR calibration does not automatically control 1:N transaction FPIR.
4. The study asks explicit research questions:
   - Can a deployment-matched gate remain non-inferior to SFace?
   - At what workload/escalation rate does it save latency/energy?
   - How do gallery size, domain shift, and corruptions change that boundary?
5. List contributions that the experiments actually establish.

### 9.4 Related Work

The present four short paragraphs and 12 references are insufficient. Add:

- open-set face identification and IJB protocols;
- verification FMR versus 1:N FPIR;
- selective prediction, rejection, and early-exit cascades;
- face-image quality and quality-aware recognition;
- lightweight/edge face recognition and quantization;
- corruption/domain robustness;
- demographic effects and image-quality confounds;
- presentation-attack detection;
- primary citations for ArcFace and Tan–Triggs, which are used but not adequately grounded.

End with a comparison table: prior work, stages, gate signal, open-set metric, gallery size, hardware/energy, robustness, and provenance.

### 9.5 Method

Specify:

- closed-set versus open-set tasks and threat model;
- gallery enrollment count and aggregation per engine;
- detector model/hash, detection threshold, largest-face rule, landmarks, alignment, crop, color space, CLAHE, resize, and failure handling;
- LBPH parameters and exact distance semantics;
- SFace model/hash, embedding normalization, centroid rule, and L2/cosine relationship;
- the full three-way gate in pseudocode;
- how `tau_accept`, `tau_reject`, margin, quality thresholds, and SFace cutoff are learned using development data only;
- separate FMR, FPIR, TPIR, FNIR, CMC, AR, and escalation definitions;
- hierarchical statistical units;
- explicit cost objective and hardware timing boundary.

Correct equation numbering. The current manuscript uses `(1)` twice, then shifts later equations. Replace the low-tail rank equation as described in P0.5. Repair the broken sentence ending “refutes independence, .”

### 9.6 Experiments

Correct Table 1 and dataset language:

- LSDB selection uses 8 fit, 2 calibration, and 2 reported selection/test images per identity—not the blanket 10-gallery/2-probe statement used elsewhere.
- The finalized LSDB cross-identity snapshot is one 28-identity run, not “10 seeded repeats.”
- LFW robustness is known-probe 1:N identification, not an independence sweep or open-set test.
- DL41 is 41 variants across 17 categories, not 12 types.
- State all identity, image, pair, and query denominators.

Add baselines and ablations from Section 6, including random routing at matched escalation and oracle bounds. Report all-41, matcher-only-37, clean, severity, category, detector-success, and strict failure outcomes.

### 9.7 Results and discussion

Remove the current Table 5 FAR column or rename it “calibration estimate / analytic upper bound” until a joint query-level test exists. Pairwise LBPH/SFace calibration rates and a cascade union bound are not comparable with 1:N robustness AR.

Present paired differences and confidence intervals. Discuss these facts directly:

- LFW: SFace and cascade have effectively equal AR while escalation is about 97.51%.
- LSDB-DL41: SFace and cascade both have 87.24% AR; cascade is 11.96 ms versus SFace 8.33 ms in recognition-stage anchors.
- Thresholded complementarity is one-way: zero LBPH-only successes and 1,296 SFace-only successes.
- The present result is SFace rescue/selective routing, not mutual algorithmic complementarity.

If the corrected study does not show a Pareto improvement, treat that as the result. Explain the cost lower bound and workload crossover rather than hiding them.

### 9.8 Limitations, ethics, and security scope

Add an explicit section covering:

- small/local LSDB sample and identity/session generalization;
- synthetic-corruption limits;
- LFW age/domain/label/duplicate limitations;
- incomplete demographic evidence;
- threshold uncertainty at rare errors;
- absence or presence of PAD;
- privacy/consent and data handling;
- hardware and software specificity;
- failure to infer statistical independence from exhaustive pairs.

### 9.9 Figures, tables, and Word layout

Content fixes:

- Fig. 1: use correct unique-pair/query units, correct intervals, and readable labels.
- Fig. 2: 41 labels are unreadable; split by category/severity or move the full table to supplement. Show conditional denominators.
- Fig. 3: add clustered confidence bands and a risk/coverage or precision-recall view.
- Fig. 4: include always-SFace, random-at-equal-escalation, oracle, and Pareto baselines.
- Table 4: restore the numeric “Current threshold” column that was present in `010b`, or explicitly explain its removal.
- Table 5: do not mix calibration FMR, union bounds, and identification AR.

Formatting defects found in the live DOCM:

- `References` is styled as `figurecaption`, not Heading 1.
- The first Related Work paragraph is Heading 3.
- “Frozen cascade...” is body text rather than a subsection heading.
- one paragraph starts with `(i)` without a lead-in;
- a method sentence ends with “refutes independence, .”;
- equation `(1)` is duplicated;
- several `/` caption-like paragraphs and large blank areas need visual cleanup;
- figure labels are small/overlapping;
- page 14 is half empty while methods and limitations are underspecified.

The current document’s VBA project differs from the macro specimen and `010b`. This is a lineage anomaly to resolve, not proof of damage. Before camera-ready delivery, archive the exact baseline and derivative under the required sequential naming rule, compare `vbaProject.bin` hashes to the intended parent, export PDF, and inspect every changed and reflowed page.

### 9.10 Claim-evidence register

Expand [claim-evidence-register.md](manuscript/claim-evidence-register.md) to include Abstract and Introduction. Advisor ownership does not exempt claims from evidence review. Give every quantitative or security-relevant claim one row containing:

- exact claim text;
- dataset and source hash;
- split and independence unit;
- preprocessing/model/gallery rule;
- threshold source;
- metric/denominator/aggregation;
- uncertainty method;
- raw artifact and provenance record;
- scientific status;
- permitted wording and limitation.

Mark `classical-cv/docs/PAPER.md` stale or synchronize it deliberately. It contains old thresholds and speed language and must not be used as a prose source for the current DOCM.

## 10. External standards and literature to anchor the redesign

Use primary/official sources and verify exact versions during the manuscript rewrite:

- [ISO/IEC 19795-1:2021](https://www.iso.org/standard/73515.html): biometric performance-testing principles, error reporting, throughput, and applicability.
- [NIST FRTE 1:N Identification](https://pages.nist.gov/frvt/html/frvt1N.html): 1:N identification metrics and operational framing.
- [IJB-A](https://openaccess.thecvf.com/content_cvpr_2015/html/Klare_Pushing_the_Frontiers_2015_CVPR_paper.html), [IJB-B](https://openaccess.thecvf.com/content_cvpr_2017_workshops/w6/html/Whitelam_IARPA_Janus_Benchmark-B_CVPR_2017_paper.html), and [NIST face challenges/IJB-C](https://www.nist.gov/programs-projects/face-challenges): open-set, template-based, unconstrained evaluation references.
- [SelectiveNet](https://proceedings.mlr.press/v97/geifman19a.html): selective prediction and risk-coverage framing.
- [SER-FIQ](https://openaccess.thecvf.com/content_CVPR_2020/html/Terhorst_SER-FIQ_Unsupervised_Estimation_of_Face_Image_Quality_Based_on_Stochastic_CVPR_2020_paper.html), [MagFace](https://openaccess.thecvf.com/content/CVPR2021/html/Meng_MagFace_A_Universal_Representation_for_Face_Recognition_and_Quality_Assessment_CVPR_2021_paper.html), and [AdaFace](https://openaccess.thecvf.com/content/CVPR2022/html/Kim_AdaFace_Quality_Adaptive_Margin_for_Face_Recognition_CVPR_2022_paper.html): face quality and quality-aware recognition alternatives.
- [EdgeFace](https://arxiv.org/abs/2307.01838), [MixFaceNets](https://arxiv.org/abs/2107.13046), and the [Lightweight Face Recognition Challenge](https://openaccess.thecvf.com/content_ICCVW_2019/html/LSR/Deng_Lightweight_Face_Recognition_Challenge_ICCVW_2019_paper.html): efficient learned baselines.
- [NIST demographic effects](https://pages.nist.gov/frvt/html/frvt_demographics.html) and [RFW](https://openaccess.thecvf.com/content_ICCV_2019/papers/Wang_Racial_Faces_in_the_Wild_Reducing_Racial_Bias_by_Information_ICCV_2019_paper.pdf): subgroup evaluation and image-quality confounding.
- [ISO/IEC 30107-3:2023](https://www.iso.org/standard/79520.html), [NIST passive software PAD evaluation](https://www.nist.gov/publications/face-analysis-technology-evaluation-fate-part-10-performance-passive-software-based), and [CASIA-SURF](https://openaccess.thecvf.com/content_CVPR_2019/html/Zhang_A_Dataset_and_Benchmark_for_Large-Scale_Multi-Modal_Face_Anti-Spoofing_CVPR_2019_paper.html): presentation-attack scope and evaluation.

## 11. Decision gates

### Gate 1 — scientific validity

Proceed to a final paper only when:

- calibration and final evaluation have zero forbidden image/identity overlap;
- the exact deployed gallery/enrollment rule is evaluated;
- query-level open-set FPIR is measured directly;
- transformed rows are analyzed with identity/source-image clustering;
- transform definitions and hashes are frozen;
- every headline artifact is self-verifying.

### Gate 2 — positive cascade claim

Claim an efficiency benefit only if a locked target-hardware evaluation shows:

- cascade TPIR is non-inferior to SFace at the same FPIR;
- mean energy/latency is lower for a predeclared real workload;
- tail latency is acceptable;
- confidence intervals exclude a practically irrelevant saving;
- no detector, subgroup, or attack condition hides a material regression.

If this gate fails, do not tune repeatedly on the final set. Publish/reframe the negative boundary or redesign the first stage.

### Gate 3 — architecture choice

- If quality/margin signals do not improve the independent accuracy-cost frontier, remove them.
- If `tau_reject` remains inert, simplify to accept-or-escalate.
- If direct quantized SFace is faster, safer, and simpler, abandon the LBPH-first deployment claim.
- If a cheap learned first stage Pareto-dominates LBPH, keep LBPH only as a historical baseline.
- If track-level/video escalation changes the economics, make encounter-level operation the primary deployment design.

## 12. Recommended execution order

1. Freeze the current evidence as historical; correct manuscript language without promoting new claims.
2. Fix denominator, threshold/config, true `dl_only`, enrollment, cache, segment merge, and provenance code; add regression tests.
3. Freeze a verified transform implementation and audit LFW duplicates/overlap.
4. Create identity/session-disjoint development and locked final manifests.
5. Run deployment-exact multi-shot open-set calibration and final evaluation.
6. Run nested gate ablations, random/oracle baselines, and direct joint FPIR.
7. Run full clustered robustness evaluation with stochastic repeats.
8. Run Raspberry Pi end-to-end latency, memory, energy, and thermal experiments.
9. Add real multi-session target data and at least one external open-set/unconstrained benchmark.
10. Decide positive cascade versus negative-boundary versus redesigned-architecture story using the gates above.
11. Rewrite the manuscript, evidence register, tables, and figures from only validated artifacts.
12. Archive the exact DOCM lineage, preserve macros, export PDF, and visually inspect all pages.

## 13. One-sentence recommendation

Treat the current work as a strong diagnostic baseline, repair the evaluation around deployment-matched open-set FPIR and clustered inference, and let a preregistered accuracy-cost experiment decide whether the final contribution is a successful selective cascade or an honest, useful demonstration of where that cascade fails.
