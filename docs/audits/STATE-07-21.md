# Research State Audit — 2026-07-21

**Status: 🟠 OPEN — awaiting Dr. Oh's confirmation (2026-07-22).**
Nothing in this document is settled. Three benchmark-validity findings are recorded
below with the evidence that produced them; each changes what may be reported in
`docs/PAPER.md`, and none should be written into the paper until Dr. Oh confirms
the interpretation and the remediation plan.

**Purpose:** record why the `robustness_lfw2` branch's LFW2 robustness numbers were
rejected, and why the DL (SFace) column is inflated *on every run including master*.
Every number below was read from on-disk artifacts (`reports/`, git objects) or
produced by a local run on 2026-07-21 — nothing from memory or planning docs.

**Companions:** [`STATE-07-10.md`](STATE-07-10.md) (prior state audit),
[`RUNS-07-19.md`](RUNS-07-19.md), `docs/READ THIS/FROZEN_THRESHOLDS.md`
(the frozen `tau_accept` / `l2_genuine` provenance).

---

## 0. TL;DR — three findings, all OPEN

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | The `robustness_lfw2` branch's LFW2 robustness reports were produced on a **different, pre-aligned dataset** (`*__processed.jpg`). The CV column is inflated ~12 points. The reports are not comparable to master and must not be merged or cited. | **High** — invalid result | 🟠 OPEN |
| 2 | The DL (SFace) column is **saturated by benchmark design** on *all* runs, master included: probes are distorted copies of the enrolled image, YuNet re-aligns geometric distortion away, and no impostors ever test the genuine threshold. AR is not a recognition-accuracy measure. | **High** — methodology | 🟠 OPEN |
| 3 | The threshold sweep (`sweep_gate_curve.py`) measures **closed-set rank-1 identification accuracy on genuine probes only** — not the verification accuracy `(TP+TN)/(TP+TN+FP+FN)` the professor's 2026-07-21 figure prescribes. No cross-family (impostor) comparisons exist, so FP/TN are structurally absent. Even with a train/test split the impostor:genuine ratio stays `(N_test − 1):1`, so raw accuracy is TN-dominated. | **High** — methodology | 🟠 OPEN |

Finding 2 is the one Dr. Oh (via the professor's comment) raised. Finding 1 was
found first and is the narrower of the two. Finding 3 is the protocol the
professor's 2026-07-21 figure prescribes for the threshold sweep — effectively
Finding 2's impostor-inclusive remediation, recorded separately because it also
governs how accuracy-vs-threshold is computed and reported.

---

## 1. Finding 1 — branch LFW2 robustness reports are invalid

### 1.1 What differs

`git log master..robustness_lfw2` is a **single commit** (`559886e`, "pushed reports
of robustness test of lfw2") and it touches **report files only** — zero code
changes. The harness is byte-identical across the two branches, so the divergence
comes entirely from what the run was pointed at.

| Metric (`reports/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md`) | master | `robustness_lfw2` |
|---|---:|---:|
| Originals dir | `C:\...\face-detection-g3\data\lfw-dataset` | `D:\...\classical-cv\data\lfw-dataset` |
| Probe filenames | `Antonio_Trillanes_0002.jpg` (raw) | `Antonio_Trillanes_0001__processed.jpg` |
| Clean acceptance (cv) | 100.00% | 100.00% |
| **Overall AR — cv_only** | **86.66%** | **98.12%** |
| Overall AR — dl_only | 98.22% | 97.21% |
| rotation (cv) | 68.9% | **100.0%** |
| gaussian_noise (cv) | 27.7% | **81.4%** |
| contrast_up (cv) | 78.1% | 99.0% |
| brightness_down (cv) | 73.4% | 97.1% |

Only the classical engine moves. DL is flat-to-slightly-worse. A ~12-point jump
confined to LBPH is not a plausible threshold or seed effect.

### 1.2 Mechanism — pre-aligned tiles neutralize the modification

The branch ran against `*__processed.jpg`: faces already detected, aligned, and
tightly cropped. Applying a modification on top of an aligned crop perturbs the LBPH
histogram far less than the same modification on a raw LFW tile. Direct evidence from
the `rotation,-10` rows of `accuracy_ratio_hybrid_seg2of16_probes.csv`:

| Branch | `lbph_distance` | `cv_correct` |
|---|---|---|
| `robustness_lfw2` (processed) | ≈ 58–66 | **1440 / 1440 True** |
| master (raw) | ≈ 75–80 | 987 / 1440 True (453 `confident_reject`) |

`gate.tau_accept = 70.6089` sits between those two bands. On processed tiles every
rotated probe lands under the threshold; on raw tiles a third of them cross it. Same
code, same threshold — the input decided the outcome.

Secondary tell: on the branch, **every clean probe escalates** with
`gate_reason = "quality:blur"`, where master reports `confident_accept`. The
processed tiles are soft enough to trip the blur quality probe universally, which is
independent confirmation that the image characteristics differ.

### 1.3 Not a threshold effect — verified by rerun

The current committed thresholds are already the updated ones:
`gate.tau_accept = 70.6089` (provenance: *frozen: LS-DB1 rank-8 impostor distance*)
and `sface.l2_genuine = 1.106796` (*frozen: hardcoded*), per
`src/hybrid/thresholds.json`; `src/sface/recognizer.py` uses
`COSINE_GENUINE_THRESHOLD = 0.363` / `L2_GENUINE_THRESHOLD = 1.106796`.

Rerunning segment 2 of 16 on the **raw local LFW** with those thresholds
(`reports/benchmark/lfw2_robustness_rerun/`, 14,760 modified probes):

| Modification | rerun (raw) cv | branch (processed) cv | master (raw) cv |
|---|---:|---:|---:|
| **Overall AR** | **85.58%** | 98.16% | 86.66% |
| rotation | 68.54% | 100.0% | 68.9% |
| gaussian_noise | 25.28% | 81.9% | 27.7% |
| contrast_up | 73.24% | 99.0% | 78.1% |
| gamma_down | 96.02% | 100.0% | 97.2% |
| occlusion | 100.00% | 100.0% | 100.0% |

The rerun reproduces master, not the branch. **The updated thresholds do not inflate
CV.** The dataset does.

### 1.4 Reproducibility constraint

`D:\Online Classes 7 - The College Experience\Shared Githubs\classical-cv\data\lfw-dataset`
is **not present on this machine**, so the branch run cannot be reproduced here — only
the raw-LFW baseline can. How those `__processed` tiles were generated is unknown and
is an open question for Dr. Oh.

### 1.5 One difference that is *not* suspicious

The branch reports drop the `parallel` column. That is expected: the `parallel`
(run-both) mode was removed from `src/hybrid/` (see AGENTS.md § Project Structure).
Master's report still carries a `parallel` column, which means **master's report
predates that removal** and is stale in its own way.

---

## 2. Finding 2 — the DL column is saturated by benchmark design

This applies to master, to the branch, and to the rerun equally. It is a property of
`src/benchmark/accuracy_ratio_hybrid.py`, not of any one run.

### 2.1 What AR actually measures

`matched = (decision.name == person)`. For `dl_only`, `decision.name` comes from
`SFaceGallery.score()`, which returns the nearest gallery identity **or `"Unknown"`**
if `is_genuine(cosine, l2)` fails (`cosine >= 0.363 AND l2 <= 1.106796`). So AR =
closed-set 1:N identification with a genuine-accept threshold, over genuine probes
only.

### 2.2 Four compounding inflators

1. **Probe is a distorted copy of the enrolled image.** Enrollment
   (`scripts/pipeline/run_lfw2_robustness.py: ensure_lfw2_enrollment`) and probing
   (`load_originals`) both call `select_originals(..., select_one_per_person=True,
   seed=42)` — the *same* file. SFace therefore compares distorted-self against
   clean-self, not two independent photographs of a person. Confirmed on disk:
   every `clean` row has `lbph_distance = 0.0` (exact self-match).
2. **YuNet re-aligns the distortion away.** `probe()` calls `detect_sample()` on the
   *modified* image; the resulting landmarks feed `SFaceAdapter.embed()` →
   `feature_from_row()` → `alignCrop`. Rotation and zoom are geometrically undone
   before SFace ever embeds. This is why `rotation` and `zoom` sit at ~99.5%.
3. **The genuine threshold has enormous headroom and is never stressed.**
   `cosine >= 0.363` is a ~1% FAR operating point for *different-identity* pairs.
   Same-image distorted pairs sit far above it. The rule effectively never fires.
4. **No impostors exist in this benchmark at all.** Only genuine self-probes are
   scored, so false accepts are never counted. A model that accepted everyone would
   score ~100% here.

### 2.3 The saturation signature in the data

From the 2026-07-21 rerun, segment 2 of 16 (raw LFW, 14,760 modified probes):

| Modification | dl_only |
|---|---:|
| contrast_up | 99.35% |
| contrast_down | 99.63% |
| gamma_up | 99.72% |
| gamma_down | 99.63% |
| **gaussian_noise** | **83.19%** |
| gaussian_blur | 99.63% |
| motion_blur | 99.72% |
| rotation | 99.51% |
| zoom | 99.44% |
| occlusion | 99.72% |

Overall AR: **cv 85.58% / dl 98.20% / cascade 94.43%.**

Every non-noise modification pins to 99.4–99.7%. A flat line across distortions of
very different physical character is a saturation signature, not a robustness result.
Only `gaussian_noise` moves, because pixel noise corrupts information that `alignCrop`
cannot restore — it is the one modification the design does not neutralize.

The complementarity battery shows the same thing from the pairing side:
`w/x/y/z = 12323 / 61 / 2136 / 240`, recovery `P(SFace ✓ | LBPH ✗) = 89.90%
[88.62–91.05]`, both-fail 1.63%, McNemar `x=61 vs y=2136, p_exact = 0`, gate
`AUC(d1) = 0.993`. LBPH is almost never right where SFace is wrong (x = 61). That is
near-total DL dominance — consistent with a task SFace finds trivial.

### 2.4 What this does and does not license

- It does **not** mean the hybrid is broken or the cascade is worthless.
- It **does** mean AR must not be presented as recognition accuracy or as evidence
  that SFace is ~98% robust. AR is *genuine retention under distortion of the
  enrolled image, measured after re-alignment* — an upper bound.
- The honest robustness/security instrument already exists: the impostor sweep in
  `src/hybrid/independence_test.py` (TAR@FAR, false-accept panel). That is what
  should carry any claim about accuracy.

### 2.5 Candidate remediations (for Dr. Oh to choose between)

1. **Different-image probes.** Enroll `_0001`, probe from a *different* image of the
   same identity. Requires restricting to LFW identities with ≥2 images (LFW is
   heavily singleton-dominated — the usable subset size is **not yet measured**; this
   is an open number).
2. **Report TAR@FAR instead of AR**, sourcing impostors as the independence sweep
   already does.
3. **Keep AR but relabel it honestly** in the paper as a self-retention upper bound,
   with the re-alignment caveat stated explicitly.
4. **Ablate the re-alignment** (embed without `alignCrop`) to separate "SFace is
   robust" from "YuNet undid the distortion."

These are not mutually exclusive. (3) is the minimum required for honesty; (1) or (2)
is required if the paper wants to claim robustness.

---

## 3. Finding 3 — the threshold sweep measures identification, not the verification accuracy the figure prescribes

On 2026-07-21 the professor supplied a figure defining the protocol for "calculating
accuracy while changing the threshold." This finding records what the figure asks
for, what our sweep actually computes, and why the two differ. It is the same root
cause as Finding 2 (no impostors are scored), seen from the protocol side.

### 3.1 What the figure prescribes

Decoding the figure onto our setup:

- Rows `F1 … Fn (=5749)` = the LFW identities (LFW has exactly 5749 people).
- Columns `F(i,1) … F(i,41)` = the **41-modification suite** applied to each identity.
- **Recognition (family)** (highlighted top row) = compare a face against *its own*
  41 modified versions → **genuine** pairs → TP / FN.
- **Recognition (all)** (the full block) = compare each face against **every other
  family too** → the cross-identity pairs are **impostor** pairs → FP / TN. This is
  the underlined instruction: *"compared not only with its own family but also with
  all other families."*
- Y-axis **"Independence Test (Threshold)"** = sweep the accept/reject similarity
  threshold and recompute the confusion matrix at each point.
- `Accuracy = (TP+TN)/(TP+TN+FP+FN)`, plotted vs threshold.

The left-hand confusion-matrix box is a generic 2×2 illustration; its genomics
wording ("variant allele / position call") is incidental and pins only the four cell
definitions and the formula.

### 3.2 What our sweep actually computes

`scripts/pipeline/sweep_gate_curve.py` reports `overall_ar_percent`, which is
**closed-set rank-1 identification accuracy on genuine probes only**:

- `matched = gate.lbph_accept and r["lbph_name"] == r["person"]`
  (`sweep_gate_curve.py:189`) — nearest gallery identity must equal the true label
  and pass the threshold.
- Every probe is a modified image of an **enrolled** identity; there are no
  cross-family comparisons, so **FP and TN are structurally absent** and the
  professor's denominator cannot be formed.
- The script itself flags the gap: *"FAR/ROC excepted - needs impostors"*
  (`sweep_gate_curve.py:310`).

So the mechanic the professor asked for first (vary threshold, measure accuracy) is
built, but the **quantity** is "Recognition (family)" only — genuine retention — not
the impostor-inclusive verification accuracy "Recognition (all)" requires.

### 3.3 A train/test split does not remove the class imbalance

The imbalance is structural in any 1:N matching matrix, not a split-size artifact.
For a test set of `N` identities with one enrolled template each and 41 modified
probes per identity:

- **Genuine** comparisons (probe vs own family): `41 × N`
- **Impostor** comparisons (probe vs every other family): `41 × N × (N − 1)`

$$\frac{\text{impostor}}{\text{genuine}} = N_\text{test} - 1$$

The ratio is driven by the identity count, not the split. A 20% test split lowers
`N_test` but leaves the ratio at `(N_test − 1):1` — still on the order of thousands
to one for any usable test set. Raw accuracy is therefore TN-dominated and reads
near-100% almost regardless of threshold, which is a known trap of the raw formula
on this matrix, not a robustness result.

### 3.4 Candidate remediations (for Dr. Oh to choose between)

1. **Balanced matched/mismatched pair sampling — the LFW View-2 protocol.** Use an
   *equal* number of genuine and impostor pairs (impostors drawn from all other
   families, honoring the underlined instruction). `(TP+TN)/total` then becomes
   meaningful and directly comparable to published LFW numbers.
2. **Report prevalence-independent metrics** alongside accuracy: TAR@FAR, ROC/AUC,
   EER, and the genuine-vs-impostor score histograms. Each is computed from a single
   class, so the ratio cannot distort it. This overlaps Finding 2's remediation #2.
3. **Balanced accuracy** `= (TPR + TNR)/2` if a single full-matrix number is required
   — algebraically the accuracy formula reweighted so the prevalence cannot inflate it.
4. **Scoring requirement.** Impostor pairs need each probe scored against *every*
   family (LBPH distance / SFace cosine to each identity). The current records store
   only `d1` (rank-1 distance) and `margin`, so a re-score is required — the existing
   probe generation and seeds can be reused unchanged.

(1) or (2) is required if the paper wants to present an accuracy-vs-threshold curve
from this figure; (3) is the minimum if a single number over the full matrix is
demanded. None should be written into `docs/PAPER.md` until Dr. Oh confirms the
metric.

---

## 4. Runs executed 2026-07-21

Output dir: `reports/benchmark/lfw2_robustness_rerun/` (JSON + MD + probes CSV per
segment, same filename convention as the harness, so segments can be merged later
with `scripts/utils/merge_robustness_segments.py`).

Command shape (one segment, resumable — the harness itself runs all segments, so
segments are invoked directly here):

```
python -m src.benchmark.accuracy_ratio_hybrid \
  --originals-dir data/lfw-dataset --select-one-per-person --seed 42 \
  --segment-count 16 --segment-index <N> \
  --lbph-model models/lfw2/lbph_seed42.yml \
  --lbph-labels models/lfw2/lbph_labels_seed42.json \
  --sface-gallery models/lfw2/sface_gallery_seed42.npy \
  --thresholds-json src/hybrid/thresholds.json --reuse-engine-scores \
  --output-json  reports/benchmark/lfw2_robustness_rerun/accuracy_ratio_hybrid_seg<N>of16.json \
  --output-md    reports/benchmark/lfw2_robustness_rerun/accuracy_ratio_hybrid_seg<N>of16.md \
  --battery-csv  reports/benchmark/lfw2_robustness_rerun/accuracy_ratio_hybrid_seg<N>of16_probes.csv
```

| Run | Scope | Status |
|---|---|---|
| Smoke (seg 1 of 574, 11 identities, 451 probes) | sanity + timing | ✅ done — cv 84.03 / dl 98.67 / cascade 95.33 |
| **seg 2 of 16** (≈360 identities, 14,760 probes) | headline comparison | ✅ done — cv 85.58 / dl 98.20 / cascade 94.43 |
| seg 1 of 16 | replication | 🔄 running at time of writing |
| seg 3 of 16 | replication | 🔄 queued |
| Merged 16-segment rerun | full baseline | ⬜ not run — decide after Dr. Oh's call |

Environment note: enrollment was **reused**, not rebuilt
(`models/lfw2/manifest_seed42.json` matches the local raw `data/lfw-dataset` at
seed 42). Free RAM at launch was 2.4 GB of 15.7 GB, so segments were run
sequentially rather than in parallel — the 0.67 GB LBPH `.yml` expands well beyond
its on-disk size in memory.

---

## 5. Consequences for the paper — do not action yet

Blocked on Dr. Oh's confirmation (2026-07-22):

- [ ] **Do not merge** `robustness_lfw2` into master, and do not cite its numbers.
- [ ] Decide whether master's LFW2 numbers are quotable at all, given they predate the
      `parallel`-mode removal.
- [ ] Decide the AR remediation (§2.5) before any §4.3 robustness table is written.
- [ ] If AR survives in any form, add the re-alignment + self-probe caveat to its
      caption — this is non-negotiable for honesty.
- [ ] Measure the LFW ≥2-image identity count if remediation (1) is chosen.
- [ ] Re-check whether the same self-probe design contaminates the classical
      41-modification runs cited from `STATE-07-10.md` §1.4 (likely, same harness).
- [ ] Decide the Finding 3 (§3.4) verification-sweep remediation before any
      accuracy-vs-threshold curve from the professor's figure is written. Do not
      present the current `overall_ar_percent` sweep as "Recognition (all)" accuracy —
      it is "Recognition (family)" only.

---

## 6. Open questions for Dr. Oh

1. Were the `*__processed.jpg` tiles on the D: machine an intentional protocol
   (test the deployed pipeline including alignment), or an accident? If intentional,
   master is the wrong baseline and *both* need re-running on the same inputs.
2. Is AR acceptable as a declared upper-bound metric, or must Paper 1 move to
   TAR@FAR for the robustness axis?
3. Does the self-probe issue change the standing complementarity claims (recovery
   rate, McNemar) from `STATE-07-10.md` §5.2, which used the same harness?
4. For the 2026-07-21 figure: is the intended metric balanced-pair verification
   accuracy (LFW View-2 style, §3.4 option 1), or should the threshold sweep report
   TAR@FAR / EER instead of raw `(TP+TN)/total` (§3.4 option 2)? Confirm the reading
   of "Recognition (family)" vs "Recognition (all)" as genuine vs impostor pairs.

---

## 7. All-families verification run + LFW1-derived thresholds (2026-07-21)

Direct execution of the professor's figure protocol (the "compare F1 with the
**entire** LFW2" instruction), done partially per the agreed budget. Script:
`scripts/pipeline/lfw_all_families_verify.py`. Output:
`reports/benchmark/lfw_all_families/` (`table.md`, `per_variant.csv`,
`summary.json`).

### 7.1 What was run

- **Protocol (exact):** enroll one **clean** anchor per identity; for every one
  of the 41 modification variants, build the modified probe `F(i, mod)` and score
  it against **all** clean anchors. Genuine pair = probe vs its own anchor
  (TP/FN); impostor pairs = probe vs every other anchor (FP/TN). This is the
  every-pair verification the figure prescribes — not the closed-set rank-1 the
  `sweep_gate_curve.py` sweep computed (§3).
- **Partial scope:** a seeded **575-identity** subset (~10% of 5749). Per
  modification: **575 genuine + 330,050 impostor** pairs. Runtime 515.6 s (~8.6
  min), one process, no segmentation needed at this size. LBPH scores are the
  native `predict_collect` scale (same scale as `tau_accept`); SFace is
  vectorised cosine/L2.
- **Engines:** LBPH, SFace, and the gated Hybrid cascade (per-pair form: below
  `tau_accept` → accept; in `[tau_accept, tau_reject)` → defer to the SFace
  genuine rule; ≥ `tau_reject` → reject).

### 7.2 LFW1-derived thresholds (vs the LS-DB1 frozen ones)

Re-derived here from **this run's LFW clean cross-identity impostor
distribution**, using the same recipe as the LS-DB1 values (tau_accept = LBPH
impostor distance at a FAR operating point; l2_genuine = mean of the impostor L2
distribution):

| Threshold | LS-DB1 (deployed / frozen) | LFW1-derived (this run) |
|---|---:|---:|
| LBPH `tau_accept` | **70.6089** (rank-8, ~1% FAR) | **81.04** @ 100 ppm · **88.40** @ 1% FAR |
| SFace `l2_genuine` | **1.106796** (hardcoded, ~impostor mean) | **1.355317** (impostor-L2 mean) |
| LBPH `tau_reject` | 76.85 (LFW-carried, `tar_at_far.md`) | 76.85 (kept — not re-derived) |
| SFace `cosine_genuine` | 0.363 | 0.363 (kept — not re-derived) |

**Transfer finding.** The LS-DB1 `tau_accept` (70.6089) is far stricter than any
usable LFW operating point: LFW's own accept edge is **81–88** depending on FAR.
Because even the 100 ppm LFW value (81.04) exceeds the carried `tau_reject`
(76.85), the escalation band `[tau_accept, tau_reject)` is **empty on LFW** — the
cascade never escalates and **Hybrid collapses to LBPH** (identical columns in
the table). A non-degenerate LFW hybrid would require re-deriving `tau_reject`
from LFW too (looser than the LFW accept edge); that was **not** done here — Kyle
scoped the re-derivation to `tau_accept` + `l2_genuine` only. The deployed system
is unchanged; the LFW1 numbers are diagnostic.

### 7.3 Results — raw accuracy is uninformative, balanced accuracy discriminates

At the LFW1-derived thresholds (tau_accept 81.04 @ 100 ppm):

- **Raw `(TP+TN)/all` pins at ≈ 99.9% for every modification and every engine**
  (LBPH/SFace/Hybrid overall 99.97 / 99.92 / 99.97). This is Finding 3's
  TN-domination made concrete: at 574:1 impostor:genuine, the TN mass swamps the
  metric and it cannot rank robustness. **Do not report the raw figure as the
  headline** — it is the trap the professor's raw-formula reading falls into.
- **Balanced accuracy ½(TPR+TNR) is the signal.** Overall over modifications:
  **LBPH 94.37% vs SFace 99.18%** (Hybrid = LBPH, see §7.2). Worst LBPH cases:
  `gaussian_noise` **69.0%** (SFace 92.4%), `brightness_down` 87.3%,
  `contrast_up` 89.9%, `rotation` 95.9%. SFace stays ≥ 99.8% everywhere except
  noise (92.4%). This reproduces the complementarity story (SFace recovers where
  LBPH degrades) on an **impostor-inclusive** basis, unlike the genuine-only AR
  of Finding 2.

### 7.4 Caveats

- **Partial (10%) + carried `tau_reject`.** Impostor pool = the other 574
  identities in the subset, not all 5749; and the empty band is partly an
  artifact of mixing an LFW-derived accept with an LS-DB1-era reject. Both are
  scoped choices, flagged here, not defects.
- **Same self-probe basis as Finding 2 for the genuine side** (clean anchor vs a
  modified copy of the *same* image, re-aligned by YuNet). The genuine (TP/FN)
  half therefore inherits Finding 2's upper-bound caveat; the impostor (FP/TN)
  half is the new, honest contribution. Do not write into `docs/PAPER.md` before
  Dr. Oh confirms the metric (open question 4).
