# LS-Face — How Everything Works (Plain-English Process Guide)

*A companion to `docs/PAPER.md`. The paper states **what** we found; this document explains **how** each process works and **why** we chose it, in plain language with analogies, worked examples, formulas, and the exact script that runs each step. Read this first if the paper's Method section feels dense.*

> **Status legend.** Numbers marked **[LIVE]** come from committed runs and are safe to quote. Numbers marked **[PENDING]** are produced by a script that exists but has not been run yet — see [§13 Update Instructions](#13-update-instructions-filling-in-real-results) for exactly what to run and which file to edit when the results land.

---

## Table of contents

1. [The problem in one picture](#1-the-problem-in-one-picture)
2. [The 7-stage pipeline (the map)](#2-the-7-stage-pipeline-the-map)
3. [Datasets: DB1 vs DB2, La Salle vs LFW](#3-datasets-db1-vs-db2-la-salle-vs-lfw)
4. [Preprocessing: detection, alignment, normalization](#4-preprocessing-detection-alignment-normalization)
5. [The three classical recognizers](#5-the-three-classical-recognizers)
6. [Independence testing: the heart of the method](#6-independence-testing-the-heart-of-the-method)
7. [The distance matrix and the k-th-error-pair threshold](#7-the-distance-matrix-and-the-k-th-error-pair-threshold)
8. [Turning a threshold into TAR / FAR / FRR / EER](#8-turning-a-threshold-into-tar--far--frr--eer)
9. [The 41-modification robustness suite (Accuracy Ratio)](#9-the-41-modification-robustness-suite-accuracy-ratio)
10. [Complementarity: Yule's Q, double-fault, Fisher's test](#10-complementarity-yules-q-double-fault-fishers-test)
11. [The hybrid cascade and its gate](#11-the-hybrid-cascade-and-its-gate)
12. [One frozen threshold set, four databases](#12-one-frozen-threshold-set-four-databases)
13. [Update instructions (filling in real results)](#13-update-instructions-filling-in-real-results)
14. [Master script → process map](#14-master-script--process-map)
15. [Glossary](#15-glossary)

---

## 1. The problem in one picture

We are building a **Smart Gate**: a camera that admits enrolled people and rejects strangers, in real time, on a cheap computer (eventually a Raspberry Pi 5). Three things pull against each other:

| We want… | Classical CV (LBPH, Eigen, Fisher) | Deep learning (SFace) |
|---|---|---|
| **Cheap / fast** | ✅ tiny, sub-millisecond on a CPU | ❌ 2–4× more compute per frame |
| **Robust** (bad light, blur, noise) | ❌ collapses | ✅ holds up |

**Analogy.** Classical CV is a **sprinter**: blazing fast on a clean track, but it trips on rough ground. Deep learning is an **all-terrain hiker**: slower, but it doesn't fall. Our thesis is that you don't have to choose — you send the sprinter first, and only call the hiker when the ground looks rough. That routing decision is what we call the **gate**, and the whole system is **LS-Face**.

To make any of this work we first need one unglamorous but decisive ingredient: **a trustworthy match threshold** — the cut-off distance below which we say "same person." Getting that threshold honestly, from data, without cheating, is what **independence testing** does, and it is the intellectual core of the project.

---

## 2. The 7-stage pipeline (the map)

Every image flows through the same seven stages. Keep this map in mind; the rest of the document zooms into each box.

```
Input image
  (1) Pre-processing      → noise reduction, contrast normalization
  (2) Face detection      → find the face, align, grayscale, resize to 100×100
  (3) Image database  ⇄  (4) Feature database
  (5) Independence test   → DETERMINE THE MATCH THRESHOLD
  (6) Face recognition    → identify / verify against the threshold
  (7) Evaluation          → measure TAR/FAR/FRR, robustness, complementarity
```

Stage 5 is unusual. In most tutorials you'd pick a threshold by trial and error on a validation set. We refuse to, because a threshold tuned on a tiny gallery does not survive contact with real strangers. Stage 5 replaces guessing with a **measurement**.

---

## 3. Datasets: DB1 vs DB2, La Salle vs LFW

Two axes, so four datasets. The naming trips people up, so here is the whole grid:

| | **DB1** (clean, 1 role: *set the threshold*) | **DB2** (41 modifications, role: *stress-test recognition*) |
|---|---|---|
| **La Salle** (our own, `lasalle_db1_processed`) | 28 people × ~12 tiles, pre-cropped 100×100. The **anchor** dataset. | Each held-out probe put through 41 corruptions (56 probes × 41 = 2,296). |
| **LFW** (public, `lfw-dataset`) | 5,749 people, 13,233 photos (~13,149 usable). The **impostor ocean**. | 41-modified LFW, one image per identity. |

**Why two databases?**
- **DB1 = clean** so it measures *identity separation only* — how far apart two different people look to the algorithm when nothing is degraded. That is exactly what a threshold should be built on.
- **DB2 = degraded** so it measures *robustness* — what happens when the image is dark, blurry, or noisy. That is what the gate has to survive.

**Why two sources?**
- **La Salle** mirrors deployment (our enrolled users, controlled shots) but is *small* — only 28 identities, so it cannot resolve very low error rates (see §7).
- **LFW** is *huge* — millions of cross-comparisons — so it gives the statistical power to certify a 100-ppm (0.01%) false-accept budget.

> **Memory rule (do not violate).** La Salle DB1 is the **anchor**: every threshold is derived there and *frozen*. LFW and DB2 are **transfer legs** — you test on them, you never re-tune on them. (See `[[frozen-threshold-anchor]]`.)

**Splits.** `data/split_lasalle/{train,test}` is the leakage-free split: 10 gallery + 2 held-out probe images per identity (280 train / 56 test), verified image-disjoint. The 41-modification suite is applied *only to probes*; the gallery is always clean originals.

**Scripts:** `scripts/setup_datasets.py` (download + link datasets), `scripts/augment_split_light_medium.py` (generate augmented tiers).

---

## 4. Preprocessing: detection, alignment, normalization

*Source of truth: `src/classical_faces/preprocess.py` (re-exported by `src/lbph/preprocess.py`).*

Before any recognizer sees a face, three things happen. Crucially, **training, evaluation, and the live camera loop all call the same function**, so the recognizer never sees a different-looking input at test time than it trained on.

### 4.1 Face detection — why we moved from Haar to YuNet

| | Viola-Jones **Haar cascade** [old] | **YuNet** CNN [selected] |
|---|---|---|
| La Salle recall (336 photos) | 86.9%, 43 false positives | **100%, 0 false positives** |
| Speed | 37.2 fps | 48.6 fps |
| Bonus | — | returns **5 landmarks** (eyes, nose, mouth) SFace needs for alignment |

Haar misses exactly the hard shots a gate must tolerate (non-frontal, dark). YuNet is faster, more accurate, smaller, and hands us landmarks for free. *Script: `src/benchmark/compare_detectors.py`.*

### 4.2 Alignment
`align_face_by_eyes()` rotates the crop so the eyes are level (analogy: straightening a crooked photo before filing it). For DL, YuNet's landmarks drive a 112×112 alignment instead.

### 4.3 Illumination normalization — Tan-Triggs

This is the step that makes LBPH competitive. `tan_triggs_normalize()` runs three sub-steps:

$$\text{gamma correction} \;\to\; \text{Difference-of-Gaussians} \;\to\; \text{two-stage contrast equalization}$$

**Plain English:** it flattens lighting so a face in shadow and the same face in sunlight look nearly identical to the algorithm. The output is mapped to `[0,255]` with a **fixed, image-independent scale** — that fixed scale is what lets distances stay comparable across different photos.

> **Key finding worth remembering:** there is *no single best normalization*. Tan-Triggs **lifts** LBPH (TAR 96.4% → 98.21%) but **hurts** the subspace methods, which prefer plain histogram equalization. That is why each recognizer carries its own `default_equalization` in `src/classical_faces/pipeline.py` — a per-engine contract, single-sourced so training and evaluation can't drift apart.

Every image is finally resized to **100×100 grayscale**.

---

## 5. The three classical recognizers

All three ship in OpenCV, need no GPU, and turn a face into a **feature vector** — a list of numbers — that we then compare with a **distance**. The analogy: each method is a different way of writing a face's "fingerprint," and recognition is checking whether two fingerprints are close.

| Recognizer | Idea (analogy) | Feature | Distance | OpenCV class |
|---|---|---|---|---|
| **LBPH** | "Describe the *texture* in each of 64 tiles of the face" — like describing a fabric by its weave, region by region. | Local Binary Pattern **histograms** | **Chi-squared** | `LBPHFaceRecognizer` |
| **Eigenfaces** (PCA) | "Every face is a blend of a few dozen *ghost faces*; store the recipe." | PCA projection | **Euclidean** | `EigenFaceRecognizer` |
| **Fisherfaces** (LDA) | Like Eigenfaces, but the ghost faces are chosen to *separate people*, not just describe them. | LDA projection | **Euclidean** | `FisherFaceRecognizer` |

Distances used (from `src/independence_common.py`):

$$\chi^2(a,b) = \tfrac{1}{2}\sum_i \frac{(a_i-b_i)^2}{a_i+b_i+\epsilon} \qquad\qquad d_{\text{euclid}}(a,b) = \lVert a-b\rVert_2$$

**Lower distance = more similar.** A distance of ~0 means "identical"; a large distance means "different people."

Each classical model trains a `.yml` model file + a `.json` label map. The four per-family scripts: `trainer.py`, `evaluate.py`, `detect.py`, `independence_test.py`, under `src/lbph/`, `src/eigenfaces/`, `src/fisherfaces/`.

> **Scope note (do not re-add deleted tracks).** The project is LBPH / Eigenfaces / Fisherfaces + the hybrid's SFace only. Other DL recognizers were removed on purpose; SFace is not removable. (See `[[model-scope-lbph-eigen-fisher]]`.)

---

## 6. Independence testing: the heart of the method

### 6.1 The problem it solves

To verify a face we say: **accept if distance < θ.** Everything rides on θ. But picking θ is normally easy *only if you have lots of labeled "same-person" and "different-person" pairs*. Real enrollment has neither — a handful of enrolled people and **zero examples of strangers**. So how do you set θ without ever having seen a stranger?

### 6.2 The trick

**Build a gallery with exactly one image per identity, then compare every image to every other image.** Because every pair is two *different* people, **every comparison is a stranger (impostor) pair by construction.** You have manufactured the exact data you were missing.

**Analogy.** You can't afford to hire actors to test your bouncer against fake IDs. So instead you line up all 28 regulars and have the bouncer compare each one's face to all 27 others. Every one of those comparisons is a "these are different people" test — and now you can see how often the bouncer would wrongly say "same person," and how strict a rule you'd need to stop that.

### 6.3 What one sweep gives you (three things at once)

1. **A threshold** at any false-accept rate you choose (§7).
2. **A health check** — if the impostor distances collapse toward zero, no usable threshold exists (the recognizer is broken).
3. **Annotation-error detection** — a near-zero distance between two supposedly different people flags either a mislabeled duplicate or a feature-space collapse. (On LFW all three families independently flagged the *same* known bad pair: Andrew Caldecott vs Andrew Gilligan. On La Salle the near-zero pairs traced to a normalization floor and a one-image LDA degeneracy — artifacts, not bad labels.)

*Scripts: `src/lbph/independence_test.py`, `src/eigenfaces/independence_test.py`, `src/fisherfaces/independence_test.py` (per family); shared math in `src/independence_common.py`; the streamed full-LFW path in `src/independence_streaming.py`.*

---

## 7. The distance matrix and the k-th-error-pair threshold

*Source of truth: `src/independence_common.py` (`compute_pairwise_distances`, `error_pair_threshold`, `error_pair_report`).*

### 7.1 The matrix

With **N** identities (one image each), compute the distance between every ordered pair (i, j), i ≠ j. That fills an **N × N distance matrix** with the diagonal (self-comparisons) left out:

$$C = N \times (N-1) \quad \text{ordered comparisons.}$$

The diagonal is dropped because a face compared to itself scores ~0 by memorization and means nothing.

| Dataset | N | C = N(N−1) |
|---|---:|---:|
| La Salle DB1 | 28 | **756** |
| LFW DB1 | 5,749 | **33,045,252** |

**Worked mini-example (N = 4).** Identities A, B, C, D. The matrix of impostor distances (diagonal blank) has 4 × 3 = 12 entries:

| | A | B | C | D |
|---|---|---|---|---|
| **A** | — | 88 | 40 | 71 |
| **B** | 88 | — | 63 | 22 |
| **C** | 40 | 63 | — | 55 |
| **D** | 71 | 22 | 55 | — |

Every one of those 12 numbers is a "different people" distance. Sort them ascending: `22, 22, 40, 40, 55, 55, 63, 63, 71, 71, 88, 88`.

### 7.2 Reading the threshold off the sorted list

Here is the whole idea in one sentence: **if you set the threshold at the k-th smallest impostor distance, then exactly k impostor pairs fall inside it — so your false-accept rate is exactly k / C.**

$$\text{FAR}(k) = \frac{k}{C}, \qquad \text{and for a target FAR } \alpha:\quad k^{*} = \lceil \alpha \cdot C \rceil,\quad \theta = s_{(k^{*})}.$$

In the toy example, choosing k = 2 gives θ = 22 (the 2nd smallest), so FAR = 2/12 = 16.7%: exactly the two closest impostor pairs (B–D both directions) would be wrongly accepted.

**Spec anchor points:**

| Dataset | C | Target FAR | k\* | θ (the k\*-th distance) | Realized FAR |
|---|---:|---|---:|---|---:|
| La Salle DB1 | 756 | 1% (10,000 ppm) | **8** | 8th-nearest impostor distance | 8/756 ≈ 1.058% |
| LFW DB1 | 33,045,252 | 10 ppm | **331** | 331st-nearest | ≈10 ppm |

The `ceil` formula reproduces both anchors exactly: `ceil(756 × 0.01) = 8` and `ceil(33,045,252 × 0.00001) = 331`.

### 7.3 Why small N cannot certify a small FAR

La Salle's 756 comparisons cannot resolve a rate finer than 1/756 ≈ **1,300 ppm**. You physically cannot point at "100 ppm" on a list of 756 numbers — the finest step is one pair. That is the honest reason the **100-ppm budget is certified on LFW** (millions of pairs), not on our home gallery. La Salle sets the *operating point*; LFW supplies the *statistical power*.

### 7.4 The measured thresholds **[LIVE]**

On La Salle DB1 (k = 8), the impostor threshold per family — **higher normalized value = impostors kept farther apart = better**:

| Recognizer | θ₈ raw | θ₈ normalized (0–100) |
|---|---:|---:|
| **LBPH (Tan-Triggs)** | 21.35 | **85.88** |
| Eigenfaces | 8,098.46 | 71.00 |
| Fisherfaces | 5,446.46 | 66.38 |

LBPH keeps strangers farthest apart, and is the **only** recognizer that can hold the 100-ppm budget when transferred to LFW. This is the quantitative reason LBPH is the classical engine that goes into the hybrid.

> **Figure:** `reports/figures/fig2_interidentity_hist.png` — the impostor-distance histograms these thresholds are read from.

### 7.5 One subtlety: mean-before-rank vs per-run

We run the sweep **10 times** with different one-image-per-person picks and average. There are two honest ways to summarize:
- **Mean-before-rank** (averages each pair's distance across runs, *then* ranks): the headline normalized figures above.
- **Per-run** (ranks *within* each run, then reports mean ± spread): materially lower and with a visible spread (LBPH 68.03% ± 1.83, etc.), because it doesn't hide run-to-run variability behind pooled normalization.

Both are reported so nothing is oversold. *Script: `scripts/per_run_thresholds.py` (backfills per-run thresholds from committed `_raw_runs/`), implemented by `per_run_error_pair_thresholds()` in `src/independence_common.py`.*

---

## 8. Turning a threshold into TAR / FAR / FRR / EER

*Source of truth: `src/benchmark/tar_at_far.py`.*

The independence test gives a threshold **on the feature-distance scale**. To deploy, we need the operating point on each recognizer's **native `predict()` scale**, measured against real genuine and impostor probes:

- **Genuine probes** = held-out La Salle test faces (enrolled people).
- **Impostor probes** = LFW faces (nobody enrolled), Haar-cropped so framing matches.

For a threshold T:

$$\text{FAR}(T)=\frac{\text{impostors accepted}}{\text{impostors}},\quad \text{TAR}(T)=\frac{\text{genuine accepted as the right person}}{\text{genuine}},\quad \text{FRR}=100\%-\text{TAR}.$$

The **EER** (Equal Error Rate) is the threshold where FAR = FRR — a single-number summary of separability (lower is better).

### 8.1 The decisive result **[LIVE]**

Rank-1 accuracy (just "is the top guess right?") ranks LBPH 100% / Eigen 75% / Fisher 66%. But a gate must also *reject strangers*, so the real metric is **TAR at a fixed FAR**:

| Recognizer | Rank-1 | TAR @100 ppm (95% CI) | FRR | EER | AR (41 mods) | Feature |
|---|---:|---:|---:|---:|---:|---:|
| **LBPH (Tan-Triggs)** | 100% | **98.21%** [90.6–99.7] | 1.79% | 0.07% | 85.43% | 64 KB |
| Eigenfaces | 75% | 23.21% [14.1–35.8] | 76.79% | 31.77% | 47.69% | 1,120 B |
| Fisherfaces | 66% | 10.71% [5.0–21.5] | 89.29% | 35.71% | 30.54% | 108 B |

**Lesson: closed-set accuracy misleads.** At a fixed FAR — the gate's real operating mode — only LBPH survives. The subspace methods' genuine and impostor distances overlap intrinsically. *Selection rule (committed before results, applied by `src/benchmark/compare_classical.py`): eligible = TAR ≥ 90% + feature < 1 KB + FPS ≥ 3; among eligible, highest AR wins.*

### 8.2 Why every rate carries a 95% Wilson interval

*Source: `src/stats_utils.py:wilson_interval`.* With only n = 56 genuine probes, **one probe moves TAR by 1.8 points.** A bare "98.21%" pretends to a precision we don't have. The **Wilson interval** is a confidence range that behaves correctly even at 0% or 100% (where the naive interval collapses to a dot). Rule of thumb: *if you quote a rate from small N, quote its interval.*

> **Figures:** `reports/figures/fig1_tar_far_roc.png` (TAR/FAR curve), `reports/figures/fig3_ar_by_modification.png` (robustness).

---

## 9. The 41-modification robustness suite (Accuracy Ratio)

*Source of truth: `src/benchmark/modifications.py`; runners `src/benchmark/accuracy_ratio.py` (classical) and `src/benchmark/accuracy_ratio_hybrid.py` (CV vs DL vs cascade).*

### 9.1 What it does

Take every clean probe and generate **41 deterministic degraded versions** — 12 corruption types across several severity levels:

| Type | Levels | Type | Levels |
|---|---|---|---|
| brightness up / down | ±15…60 | gaussian_noise | σ 5…20 |
| contrast up / down | 0.55…1.45 | gaussian_blur | k 3,5,7 |
| gamma up / down | 0.5…1.6 | motion_blur | k 3,5,7 |
| rotation | ±5,±10° | zoom | 0.90…1.10 |
| occlusion | 7.5–17.5% area | | |

`4+4+3+3+3+3+4+3+3+4+4+3 = 41` variants per image.

### 9.2 The metric

Present each degraded probe; it **matches** if the recognizer outputs the correct identity within the deployed threshold. With M probes and K matches:

$$\text{AR} = \frac{K}{M}$$

averaged per modification over its levels, then over modifications for the overall score.

### 9.3 The crucial engineering detail — bit-identical probes

Every probe is seeded by `stable_rng(seed, image, modification, level)`. **The same corruption always produces the exact same pixels**, so LBPH, SFace, and the cascade are all scored on *identical* images. Without this, "CV got 85%, DL got 90%" would be comparing apples to oranges. This is what makes the complementarity claim (§10) fair.

### 9.4 What it revealed **[LIVE for classical]**

LBPH's 85.43% overall AR is **bimodal**: it absorbs photometric edits (occlusion 98.8%, gamma ~98%, contrast-down 98.2%) but **breaks** on heavy noise (47.8%), motion blur (68.5%), and strong darkening (73.7%). Subspace methods fail geometrically (rotation 26%/14%). **Those exact failure modes — noise, blur, low light — become the gate's quality probes (§11).** The same-probe scoring of SFace, cascade, and parallel is **[PENDING]** (§13).

---

## 10. Complementarity: Yule's Q, double-fault, Fisher's test

*Source of truth: `src/stats_utils.py`; runner `src/hybrid/independence_test.py`.*

"The two engines complement each other" is a slogan until you measure it. Complementarity means **they fail on *different* inputs** — where one breaks, the other holds. We test that on the *same* N×(N−1) impostor sweep, scoring every pair with **both** engines, and cross-tabulate their errors into a **2×2 matrix**:

|  | **SFace errs** | **SFace correct** |
|---|---|---|
| **LBPH errs** | a (both wrong) | b (only LBPH wrong) |
| **LBPH correct** | c (only SFace wrong) | d (both right) |

From this one table come three complementary readings.

### 10.1 The intuitive ratio — observed vs expected joint errors

If the two engines failed *independently*, the number of pairs where **both** err would be:

$$E[\text{both}] = C \cdot P(\text{FP}_{\text{CV}}) \cdot P(\text{FP}_{\text{DL}})$$

If **observed ≤ expected**, the engines rarely fail together — a cascade can use one to catch the other's mistakes. (Reported as `observed_over_expected`; 1.0 = independent.)

### 10.2 Yule's Q — the diversity headline

$$Q = \frac{ad - bc}{ad + bc}, \qquad Q \in [-1, +1]$$

Read it like a correlation of *mistakes*:
- **Q < 0** → errors are **complementary** (fail on different pairs) ✅ what we want.
- **Q = 0** → errors independent.
- **Q > 0** → engines **fail together** ❌ (fusion buys little).

**Analogy.** Two weather forecasters. If they're always wrong on the *same* days, a second opinion is useless (Q > 0). If forecaster A blows the rainy days and B blows the sunny days, together they cover everything (Q < 0). Q measures which world you're in.

### 10.3 Double-fault — the floor no fusion can beat

$$\text{DF} = \frac{a}{C}$$

The fraction where **both** engines are wrong at once. No cascade, vote, or fancy fusion can ever do better than DF — if both are wrong, the system is wrong. It is the honest error floor of the whole approach.

### 10.4 Fisher's exact test — is the association real or noise?

*Source: `src/stats_utils.py:fisher_exact`.* On a small table, Q could be negative just by luck. Fisher's exact test puts a p-value on it:
- `p_positive` small → errors genuinely **co-occur** (would *refute* complementarity).
- `p_negative` small → errors genuinely **avoid** each other (supports complementarity).

It's exact (hypergeometric), needs no scipy, and stays fast even on the 33M-pair LFW table because false-accept counts are tiny.

### 10.5 What we're looking for **[PENDING]**

The verdict is **Q ≤ 0 with no significant positive association**, and a cascade false-accept count that undercuts both single engines (floored at DF). A reference baseline is already measured: on La Salle DB1, 756 comparisons put 20 impostor pairs inside SFace's genuine rule; the LBPH-at-τ_a overlap is what the full run fills in. See §13.

---

## 11. The hybrid cascade and its gate

*Source of truth: `src/hybrid/gate.py`, `src/hybrid/quality.py`, `src/hybrid/calibrate.py`, `src/hybrid/thresholds.json`.*

### 11.1 The cascade in one paragraph

Every frame takes the **cheap path first**: YuNet finds the face, LBPH predicts an identity and a distance. Then the **gate** decides: *can I trust this?* If yes, LBPH's answer stands and SFace never runs. If no, the frame **escalates** to SFace (align to 112×112, 128-D / 512-byte embedding, cosine match). If there's no DL gallery, it falls back to LBPH alone automatically.

### 11.2 The gate rule (`decide_escalation`)

Escalate to SFace if **any** of these fire:

1. **Quality flag** — the crop is blurry / dark / noisy / off-pose / too small (checked *first*, and it **overrides even a confident LBPH score**, because the corrupted regimes are exactly where LBPH's confidence is a liar).
2. **Ambiguous band** — `τ_accept < d₁ < τ_reject` (the score is in no-man's-land).
3. **Thin margin** — the runner-up identity is within `margin_min` of the best: `(d₂ − d₁)/d₁ < 0.05`.

Otherwise: `d₁ ≤ τ_accept` → **accept on LBPH**; `d₁ ≥ τ_reject` → **reject** (Unknown).

> **Why the margin is *relative*, not absolute — a real bug we hit.** LBPH's training distances are near zero (memorization). An *absolute* top-1/top-2 gap fitted on training data escalated **100%** of held-out frames — the cascade collapsed into always-SFace, defeating the whole point. Switching to a **relative** gap `(d₂−d₁)/d₁` (scale-free) restored the healthy 25% / 100% split. Lesson: never fit a gate parameter on distances that memorization has inflated.

### 11.3 The five quality probes (`compute_quality`)

Each cheap probe watches a regime the audit measured LBPH failing and SFace surviving:

| Probe | Measure | Flags when | Guards against |
|---|---|---|---|
| **blur** | variance-of-Laplacian | `< τ_blur` | motion blur (LBPH ~68.5%) |
| **low_light** | mean luma | outside `[luma_lo, luma_hi]` | darkening (LBPH ~73.7%) |
| **noise** | Immerkaer σ | `> τ_noise` | gaussian noise (LBPH ~47.8%) |
| **off_pose** | eye-roll / nose-yaw from landmarks | `> τ_pose` | non-frontal |
| **small_face** | YuNet box side | `< px_min` | tiny faces |

### 11.4 Where the thresholds come from (`calibrate.py` → `thresholds.json`)

No invented numbers — every value is **measured now** or **carried with provenance**:

| Value | Source |
|---|---|
| `tau_accept` = 73.04, `tau_reject` = 76.85 | *carried* from `reports/benchmark/tar_at_far.md` (LBPH @100 ppm / @1% vs 13,149 LFW impostors) |
| `margin_min` = 0.05 | *policy* (not dataset-fitted — see the bug in §11.2) |
| quality thresholds | *measured* from the clean-crop probe distributions (edges just outside the clean spread) |
| SFace `cosine_operating` | *measured* from the real LFW impostor cosine distribution |
| SFace genuine rule | cosine ≥ 0.363 **and** L2 ≤ 1.128 |

The gallery/enrollment side is always **clean originals**; only probes are ever modified.

### 11.5 The payoff **[LIVE]**

| Config | Clean rank-1 | Clean escalation | Clean ≈FPS | Degraded rank-1 |
|---|---:|---:|---:|---:|
| LBPH-only | 100% | 0% | 174 | 5.10% |
| SFace-only | 100% | 100% | 50 | 97.96% |
| **Hybrid** | **100%** | **25%** | **100** | **97.96%** |

On clean frames the gate keeps 75% on the cheap path → **~100 fps, twice SFace-only, same accuracy**. On degraded frames it escalates everything and recovers rank-1 from **5.10% → 97.96%**. That gap — 92.86 points — is complementarity, converted into a working system at zero cost on clean data.

> **Figures:** `docs/figures/fig_hybrid_speed_accuracy.png`, `fig_hybrid_escalation.png`, `fig_hybrid_quality_probes.png`.

---

## 12. One frozen threshold set, four databases

*Source of truth: `src/benchmark/evidence_matrix.py`.*

Good numbers on four *separately tuned* databases would only prove the method is **tunable** — every method is. The real claim is **transfer**: derive every threshold **once** on La Salle DB1, freeze it (the harness records the file's SHA-256 so every leg provably saw the same bytes), and apply it unchanged everywhere.

| Database | Test | What it proves |
|---|---|---|
| La Salle DB1 (clean) | independence sweep ×10 | in-domain FAR at the frozen thresholds |
| La Salle DB2 (41 mods) | accuracy ratio: CV / DL / cascade / parallel | robustness; per-modification winners |
| LFW DB1 (clean) | independence sweep | out-of-domain transfer with real power (millions of pairs) |
| LFW DB2 (41 mods) | independence sweep on modified probes | degradation + separation jointly, out of domain |

Read the resulting table two ways: **transfer** — if the cascade's FAR intervals on the LFW legs overlap the La Salle interval, the frozen thresholds generalize (a blow-up is a *finding*, reported not tuned away); **power** — La Salle bounds FAR no tighter than ~0.5%, so the LFW legs carry the statistical weight. The "parallel" mode (both engines every frame) is the accuracy ceiling the cascade must stay close to while escalating only a fraction of frames — otherwise the gate isn't earning its keep.

---

## 13. Update instructions (filling in real results)

The pipeline is built; several legs just haven't been *run*. Here is the exact procedure for each **[PENDING]** block. **General rule: never hand-edit a result number into the paper — run the script, copy from its committed output file, and delete the `[PENDING]` tag.**

### 13.1 Hybrid accuracy-ratio (Paper §4.3)
```bash
python -m src.benchmark.accuracy_ratio_hybrid            # writes reports/benchmark/accuracy_ratio_hybrid.md
```
Then in `docs/PAPER.md` §4.3: paste the per-modification table (each AR with its Wilson interval), the `cv_stronger`/`dl_stronger` winner tags, and the cascade-vs-parallel line. Delete the `[PENDING]`.

### 13.2 Joint independence test — Yule's Q, double-fault, Fisher (Paper §4.5)
```bash
python -m src.hybrid.independence_test --iterations 10   # writes outputs/hybrid/independence_test/summary.json
```
Copy into §4.5: per-engine FAR + Wilson CIs, `observed_joint_fp` vs `expected_joint_fp_if_independent`, **Yule Q** with its Fisher p-value, **double_fault**, and the cascade false-accept count. Interpretation checklist: Q ≤ 0 + no significant positive association → complementary; cascade count should undercut both engines; DF is the floor.

### 13.3 Evidence matrix — frozen-threshold transfer (Paper §4.6)
```bash
python -m src.benchmark.evidence_matrix                  # writes reports/benchmark/evidence_matrix.md
```
Paste the whole table into §4.6. Confirm the SHA-256 line proves every leg used the same `thresholds.json`. If an LFW-leg FAR interval does **not** overlap La Salle's, report it as a population-dependence finding — **do not re-tune**.

### 13.4 Full 33M-comparison LFW run (10-ppm certification)
```bash
python scripts/run_lfw_independence.py   # streamed top-K path (src/independence_streaming.py); helper: scripts/run_independence_thresholds.py
```
Certifies the 331st-error-pair / 10-ppm operating point on the full impostor ocean.

### 13.5 Refreshing thresholds (only if the gallery changes)
```bash
python -m src.hybrid.calibrate         # re-derives src/hybrid/thresholds.json from clean crops + LFW impostors
```
> ⚠️ Re-running `calibrate` re-freezes the anchor. Only do this if enrollment genuinely changed, and re-run the evidence matrix afterward so every leg still shares one byte-identical file. Do **not** re-calibrate per dataset — that would break the transfer claim (`[[frozen-threshold-anchor]]`).

### 13.6 Regenerating figures
```bash
python scripts/make_report_figures.py          # → reports/figures/*.png
python scripts/make_hybrid_report_figures.py   # → docs/figures/*.png
```

### 13.7 Checklist before submission
- [ ] Every `[PENDING]` in `docs/PAPER.md` replaced with a number from a committed output file.
- [ ] Every rate has a 95% Wilson CI.
- [ ] Figures regenerated and referenced paths resolve.
- [ ] `evidence_matrix.md` SHA-256 matches the current `thresholds.json`.
- [ ] No number typed by hand that a script could have produced.

---

## 14. Master script → process map

| Process | Script(s) | Output |
|---|---|---|
| Dataset setup / augmentation | `scripts/setup_datasets.py`, `scripts/augment_split_light_medium.py` | `data/…` |
| Preprocessing (detect, align, normalize) | `src/classical_faces/preprocess.py`, `src/classical_faces/detection.py` | in-memory 100×100 tiles |
| Detector comparison (Haar vs YuNet) | `src/benchmark/compare_detectors.py` | `docs/reports/DETECTOR_COMPARISON.md` |
| Train a classical model | `src/{lbph,eigenfaces,fisherfaces}/trainer.py` | `.yml` + `.json` |
| Evaluate a classical model | `src/{lbph,eigenfaces,fisherfaces}/evaluate.py` | `reports/evaluation/*.json` |
| **Independence sweep (per family)** | `src/{lbph,eigenfaces,fisherfaces}/independence_test.py` | `reports/independence/<model>_<db>/` |
| Independence math (shared) | `src/independence_common.py` | — |
| Full-LFW streamed sweep | `scripts/run_lfw_independence.py` (uses `src/independence_streaming.py`, `src/independence_report.py`) | independence reports |
| Per-run threshold stability | `scripts/per_run_thresholds.py` | console / JSON |
| **TAR / FAR / FRR / EER** | `src/benchmark/tar_at_far.py` | `reports/benchmark/tar_at_far.{json,md}` |
| Classical model selection rule | `src/benchmark/compare_classical.py` | comparison report |
| 41-modification suite (definitions) | `src/benchmark/modifications.py` | — |
| Accuracy Ratio (classical) | `src/benchmark/accuracy_ratio.py` | `reports/benchmark/accuracy_ratio.md` |
| Accuracy Ratio (CV/DL/cascade/parallel) | `src/benchmark/accuracy_ratio_hybrid.py` | `reports/benchmark/accuracy_ratio_hybrid.md` |
| **Yule's Q / double-fault / Fisher / Wilson** | `src/stats_utils.py` | — |
| **Joint independence + complementarity** | `src/hybrid/independence_test.py` | `outputs/hybrid/independence_test/summary.json` |
| Gate logic | `src/hybrid/gate.py` | — |
| Quality probes | `src/hybrid/quality.py` | — |
| Threshold calibration | `src/hybrid/calibrate.py` | `src/hybrid/thresholds.json` |
| Frozen-threshold transfer | `src/benchmark/evidence_matrix.py` | `reports/benchmark/evidence_matrix.{json,md}` |
| Figures | `scripts/make_report_figures.py`, `scripts/make_hybrid_report_figures.py` | `reports/figures/`, `docs/figures/` |
| Interactive entry point | `main.py` | menu-driven train/eval/detect/independence |

---

## 15. Glossary

| Term | Plain meaning |
|---|---|
| **Impostor pair** | A comparison between two *different* people. In independence testing, every pair is one by construction. |
| **θ (theta) / threshold** | Distance cut-off. `distance < θ` ⇒ "same person." |
| **FAR** | False Acceptance Rate — how often a stranger is let in. Lower = safer. |
| **TAR** | True Acceptance Rate — how often an enrolled person is correctly admitted. Higher = better. |
| **FRR** | False Rejection Rate = 100% − TAR — enrolled person wrongly turned away. |
| **EER** | Equal Error Rate — threshold where FAR = FRR; a one-number separability score. |
| **ppm** | Parts per million. 100 ppm = 0.01% = 100 errors per million. |
| **k-th error pair** | The k-th smallest impostor distance; set θ here and FAR = k/C exactly. |
| **N × (N−1)** | Number of ordered cross-identity comparisons for N one-image identities. |
| **AR** | Accuracy Ratio = matches / probes on the 41-modification suite. |
| **Yule's Q** | Diversity of two engines' *errors*; < 0 = complementary, > 0 = fail together. |
| **Double-fault (DF)** | Fraction where both engines err at once — the error floor of any fusion. |
| **Wilson interval** | A 95% confidence range on a rate that behaves at 0%/100%; mandatory for small N. |
| **Escalation** | The gate handing a hard frame from LBPH up to SFace. |
| **Frozen / anchor** | A threshold derived once on La Salle DB1 and never re-tuned; other datasets test transfer. |
| **Tan-Triggs** | Illumination normalization that flattens lighting; helps LBPH, hurts subspace methods. |

---

*Cross-references: `docs/PAPER.md` (the paper itself), `docs/READ THIS/BRIEFING.md` (project context), `docs/archive/report_docs/independence_test/MATHEMATICAL_FOUNDATION.md` (full formalism: order statistics, Beta/extreme-value results, bootstrap CIs).*
