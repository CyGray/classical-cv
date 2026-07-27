# LS-Face: Paper Writing Guide

**Target venue:** IW-FCV 2026 (Tokushima, Sept 30 – Oct 2, 2026). Submission deadline **July 31, 2026**.
**Subject:** `docs/PAPER.md` — "Facial Recognition Using Hybrid Technologies Based on Independence Testing".
**Guide written:** 2026-07-27. All evidence claims below were checked against the artifacts in `reports/` on that date.

This is a writing guide, not a rewrite. It tells you what structure to build, what each figure and
table has to earn its space by doing, and — most importantly — which claims in the current draft are
defensible against a hostile reviewer and which are not yet.

---

## 0. Two decisions to make before writing a single sentence

Everything downstream depends on these. Make them today.

### Decision 1: short paper or long paper

The CFP offers two tracks, and they are not the same product:

| Track | Pages | Presentation | Post-workshop proceedings |
|---|---|---|---|
| Short | 2–11 | Poster only | **Not eligible** |
| Long | 12–15 | Oral / poster / both | Eligible, if you opt in at submission |

The current draft header targets "6 pages max, IEEE two-column (body ~3,600 words + 4 figures + 6
tables)". Three problems with that target:

1. **It buys the weakest outcome.** Six pages is a short paper: poster only, no proceedings. The
   work does not get archived.
2. **It does not fit anyway.** The draft body is **4,718 words** excluding tables, figure lines, and
   references — 31% over its own stated budget — plus 4 figures and **7** tables (the header says
   6). In IEEE two-column that is roughly 8–9 pages before you fix anything.
3. **You are under-using the content.** You have four databases, a 33-million-pair sweep, a paired
   per-probe analysis, a gate operating curve, and a negative result. That is long-paper material
   being compressed into a poster.

**Recommendation: submit as a long paper (12–15 pages) and opt into the proceedings.** The rest of
this guide assumes that. If you overrule this and go short, cut whole *contributions*, not sentences
— pick one of the three claims in §2 and drop the others entirely. A short paper that tries to keep
all three will read as a compressed long paper, which is the worst version.

### Decision 2: what to do about the LFW2 robustness run

`reports/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md` exists in the repository (5,749
identities × 41 modifications, added July 22 under v0.82.0). **It is not cited anywhere in the
draft, and it contradicts one of the abstract's headline claims.** Details in §6.1. You must either
include it and reframe the claim, or you are submitting a paper that your own repository refutes.

**Recommendation: include it.** Handled correctly it makes the paper *stronger* — it turns a
single-dataset claim into a measured in-domain/out-of-domain contrast, which is exactly the kind of
finding that survives review.

---

## 1. The spine: write this paragraph before anything else

Before restructuring, write the paper's story as one paragraph and check every section against it.
If a section does not serve this paragraph, it is supplementary material.

> A gate recognizer must be accurate, fast, cheap, and must reject strangers. Classical CV and
> lightweight DL each fail one half of that list. We build a gated cascade that routes each frame to
> the cheapest engine that can be trusted with it, and — this is the contribution — we *derive*
> every threshold and *verify* every complementarity assumption by exhaustive impostor comparison
> rather than by validation-split tuning. Doing so produces a system that works and a finding that
> contradicts the usual justification for hybrids: these two engines' errors are strongly positively
> correlated, yet the cascade still beats both engines' false-accept rates, because a cascade needs a
> competent gate and a conjunction, not independent errors.

That last clause is the paper's actual intellectual contribution. **Lead with it.** The current
draft buries it in §4.5 and treats it as a caveat. It is the finding.

---

## 2. Contribution framing: three claims, ranked

A reviewer will ask "what do I learn here that I did not know?" Answer with exactly three things,
in this order of strength:

**C1 — A cascade does not need error independence (novel finding).**
Measured over 33,045,252 LFW impostor pairs: the two engines' false accepts co-occur at **12.85×**
the independence expectation (Q = +0.86, Fisher p = 8.8×10⁻⁵²), yet the cascade's own false-accept
rate (**98 ppm**) sits below LBPH-only (**867 ppm**) and SFace-only (**190 ppm**). This refutes the
standard "fuse unlike recognizers because their errors are independent" argument on its own terms,
and explains why the cascade works anyway. This is your strongest, least predictable result.

**C2 — Thresholds from impostor distributions, not validation splits (method).**
The k-th-error-pair rule (Eq. 2) ties an operating point to an exact error count, needs no negative
pairs, and doubles as a data-health check — it independently surfaced the known LFW annotation error
(Andrew Caldecott / Andrew Gilligan) in three recognizer families. Add the transfer result: freeze
on the *hardest* database and transfer is conservative by construction.

**C3 — A measured, not assumed, complementarity profile (evaluation).**
The 41-modification suite with paired per-probe statistics: recovery rate 78.6%, both-wrong ceiling
3.3%, McNemar p = 2.5×10⁻⁶¹, gate ROC AUC 0.953. Note this claim splits: complementarity **holds**
on the accuracy axis and **fails** on the impostor axis. Say so in the abstract.

Do **not** frame the system itself (LS-Face) as the contribution. "We built a cascade" is
dimension-1 rejection bait — cascaded/early-exit inference is well explored. The contribution is
what the cascade *measured*.

---

## 3. Section structure and budget (long-paper, 12–15 pp)

Word budgets are body prose only, excluding tables, captions, and references.

| § | Section | Words | Must contain |
|---|---|---:|---|
| 1 | Introduction | 900 | Problem, the four-way requirement conflict, the three claims C1–C3, contribution bullets, roadmap |
| 2 | Related Work | 700 | Classical / deep / detection / **cascaded & early-exit recognition** / evaluation protocol |
| 3 | Method | 1,600 | System overview, impostor-sweep threshold rule, gate, robustness protocol, complementarity instruments, freeze-and-transfer protocol |
| 4 | Experiments | 3,200 | Setup, per-engine calibration, verification, robustness, cascade, joint sweep, transfer, **out-of-domain LFW2** |
| 5 | Discussion & Limitations | 700 | The four lessons, plus a real limitations subsection |
| 6 | Conclusion | 300 | Restate C1–C3 with numbers; future work |
| | **Total** | **~7,400** | ≈ 12–13 pp with 5 figures and 6 tables |

### What changes from the current draft

**Add a Related Work paragraph on cascaded / early-exit recognition.** This is the draft's biggest
structural hole. Right now §2 has four paragraphs (classical, deep, detection, evaluation) and none
of them positions the cascade against prior cascaded systems. A reviewer scoring "missing important
baselines" will land here first. You do not need to *run* a competing hybrid — you need to state
what prior cascades do and what LS-Face does differently (thresholds derived by impostor sweep and
frozen across databases, rather than tuned per deployment).

**Split Discussion out of Experiments.** The current §4.7 is a dense four-sentence-per-lesson
paragraph doing the work of a whole section. Give it its own numbered section with one subsection
per lesson, and add an explicit **Limitations** subsection (see §7 of this guide).

**Promote the negative result.** The absolute-margin calibration failure (currently one sentence at
the end of §4.4) is good science and reviewers reward it. Give it its own short subsection under the
cascade section, with the number: the absolute margin escalated 100% of held-out frames, collapsing
the cascade into always-SFace; the relative margin of Eq. (3) restored the 25% / 100% split without
fitting on test data.

**Delete the editorial header block.** Lines 3–7 of the draft (the length target, the trim order,
"Never trim the confidence intervals") are internal notes. They must not reach a reviewer. See also
§6.4 — one of the claims in that block is currently false.

### Paragraph discipline (apply throughout)

One paragraph, one message, stated in the first sentence. The draft mostly does this well. Where it
does not, the symptom is a paragraph that starts with a citation to a script path. Compare:

- Weak: "`src/hybrid/independence_test.py` scores every impostor pair with both engines and the
  gated cascade at once."
- Strong: "Scored on the same impostor pairs, the two engines fail together far more often than
  independence predicts — and the cascade wins anyway."

Put the *finding* in the topic sentence and the *file path* in a trailing clause or a footnote. Do
this for the opening sentence of §4.5, §4.6, and §3.4.

---

## 4. Figure plan

Five figures, each with a job. A reviewer forms an opinion from figures before reading prose, so
these are content, not decoration.

| Fig | Content | Job | Status |
|---|---|---|---|
| 1 | **Pipeline diagram** — frame → YuNet → LBPH+gate → (accept \| escalate) → SFace → decision, with the three gate conditions annotated | Make the method understandable in 10 seconds | **MISSING — build this** |
| 2 | Impostor distance distributions, three classical families (`fig2_interidentity_hist.png`) | Show LBPH separates impostors best; motivate the threshold rule | Exists |
| 3 | AR per modification (`fig3_ar_by_modification.png`) | Show LBPH's failure modes are *specific*, which is what makes gating possible | Exists |
| 4 | Speed–accuracy plane (`fig_hybrid_speed_accuracy.png`) | The money figure: cascade near SFace accuracy at near LBPH cost | Exists |
| 5 | **Joint-error figure** — observed vs expected joint false accepts per leg, log scale, with the cascade's own FAR overlaid | Carry C1, the paper's best finding | **MISSING — build this** |

**The pipeline figure is non-negotiable for a long paper.** Every method section in this venue has
one. Without it a reviewer reconstructs the cascade from prose, and reconstruction errors become
review complaints.

**Figure 5 is how C1 becomes visible.** Right now the joint-independence result lives entirely in
Table 6, which means it reads as a table of diagnostics rather than as the paper's headline. A
grouped bar chart — per leg: expected joint count, observed joint count, cascade FAR — makes
"12.9× the expectation, and the cascade still wins" a single glance.

Retire `fig1_tar_far_roc.png` from the main body if space is tight; Table 2 already carries the
operating point, and the ROC curve for n=56 genuine probes is visually thin. Move it to
supplementary.

**Fix the figure paths.** Figures 1–3 in the draft reference `../reports/figures/`, figure 4
references `figures/`. Both resolve, but pick one convention before typesetting so the LaTeX
`\graphicspath` is single-valued.

**Caption rule:** every caption must state the *conclusion*, not the contents. "Fig. 3. Accuracy
ratio per modification" is contents. "Fig. 3. LBPH's degradation is concentrated, not diffuse:
noise, motion blur, and darkening account for its losses, and these are exactly the regimes the
gate's quality probes detect" is a conclusion. Do this for all five.

---

## 5. Table plan

Six tables. The draft has seven and one of them is not pulling its weight.

| Tab | Content | Keep? |
|---|---|---|
| 1 | Evidence matrix (database → test → what it proves) | **Keep, move to §3.** It is a protocol table, not a result, and it orients the reader before the experiments start. |
| 2 | Classical recognizers: rank-1, TAR@FAR, FRR, EER, AR, feature, model | Keep. This is the engine-selection evidence. |
| 3 | 41-modification suite, all configurations, with recovery column | Keep — the core robustness result. |
| 4 | Clean split: rank-1 / TAR / FRR / FAR / escalation / latency / FPS | **Merge with Table 5.** One table, two blocks (clean / degraded), shared header. Halves the ink and makes the contrast the point. |
| 5 | Medium-degradation split | Merged into 4 |
| 6 | Joint impostor sweeps | Keep — carries C1. |
| 7 | Impostor separation and cascade cost across databases | Keep — carries the transfer claim. |
| **New** | **Out-of-domain LFW2 robustness** (see §6.1) | **Add.** |

### Table formatting rules

1. **Minimal ink.** No vertical rules. Three horizontal rules only: above header, below header,
   below last row (`booktabs`: `\toprule`, `\midrule`, `\bottomrule`).
2. **Bold exactly one thing per row-group** — the deployed configuration. The draft bolds the hybrid
   row in Tables 4/5 and the cascade FP column in Table 6; keep that discipline everywhere.
3. **Consistent precision.** Currently the draft mixes `98.21%`, `85.43%`, `85.4`, `76 ppm`, and
   `0.0747%` across tables. Pick: two decimals for percentages in result tables, ppm for anything
   below 0.1%, and never mix ppm and % within a single column. Table 6 currently mixes them (rows
   1–3 in %, row 4 in ppm) — split into two columns or convert all to ppm.
4. **CIs in brackets, same cell, smaller font.** Do not give CIs their own columns; you will run out
   of width in two-column format.
5. **Every table caption states n.** Table 2's `n=56` is currently in a note below the table; move it
   into the caption. A reviewer who sees `98.21%` without `n=56` in the same visual unit will accuse
   you of overclaiming.

---

## 6. Defensibility: the claim–evidence ledger

This is the part that decides accept/reject. The rule: **every number in the abstract and
introduction must trace to a committed artifact, and you must be able to point at the file.**

I checked the draft's numbers against `reports/` on 2026-07-27. The verified ones are listed in §6.5.
The four problems below need action before submission.

### 6.1 BLOCKING — the LFW2 robustness run contradicts the abstract

**The claim.** Abstract: "The cascade stays within 2 points of the better engine on all 12
families." §4.3: "The cascade tracks the better engine within 2 points on 12 of 12."

**The evidence for it.** `reports/benchmark/evidence/ls_db2_41mods.md` — true, on 2,296 probes drawn
from 56 held-out images of 28 in-domain identities.

**The evidence against it.** `reports/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md` — the same
suite on 5,749 LFW identities. The cascade falls outside the 2-point band on four families:

| Modification | Cascade | Best engine | Gap |
|---|---:|---:|---:|
| gaussian_noise | 65.6% | 83.1% (DL) | **17.5 pts** |
| rotation | 82.3% | 99.6% (DL) | **17.3 pts** |
| contrast_up | 93.4% | 99.7% (DL) | **6.3 pts** |
| brightness_down | 96.9% | 99.4% (DL) | **2.5 pts** |

Overall: cascade **94.69%** against the run-both parallel ceiling's **98.26%** — a **3.57-point**
gap, versus 0.40 points in-domain.

**What to do.** Do not delete the claim and do not keep it as written. Rewrite it as a scoped,
two-sided result, and add the LFW2 table:

> On the in-domain La Salle suite the cascade tracks the better engine within 2 points on all 12
> modification families and sits 0.40 points below the run-both ceiling. Out of domain the gate
> costs more: on the same suite applied to 5,749 LFW identities the cascade reaches 94.69% against
> the ceiling's 98.26%, and falls outside the 2-point band on four families, with rotation and heavy
> noise accounting for most of the gap. The gate is calibrated on La Salle's distance scale, and
> §4.6 shows that scale compresses by 15.9 points on LFW; the cascade's accuracy cost out of domain
> is the same compression seen from the identification side rather than the impostor side.

That paragraph is worth more than the original claim. It connects two of your own results, it
volunteers a weakness before a reviewer finds it, and it gives the limitations section something
concrete to propose fixing (re-derive the gate margin per deployment scale, or normalize the
distance scale before gating).

**Caveat on that artifact:** its latency column is incoherent (cv_only 94.35 ms against cascade
3.61 ms — a cascade cannot be 26× faster than its own first stage). That looks like a
segment-aggregation artifact of the 16-segment run. **Quote its accuracy numbers, not its latency
numbers**, and say in the caption that latency was not measured comparably on that leg.

### 6.2 BLOCKING — two committed runs of the same experiment disagree

There are two artifacts for the LS-DB2 41-modification suite and they do not match:

| Quantity | `evidence/ls_db2_41mods.md` (paper uses this) | `accuracy_ratio_hybrid.md` / `.json` |
|---|---:|---:|
| LBPH overall AR | 85.43% | **86.15%** |
| LBPH pooled | 84.54% [83.00–85.96] | **85.28% [83.77–86.67]** |
| DL stronger / tie | **9 / 3** | **8 / 4** |
| brightness_down | 73.7% | **77.7%** |
| contrast_up | 85.1% | **87.5%** |
| gamma_down | 97.6% (DL wins) | **98.2% (tie)** |

The abstract's "SFace wins 9 of 12 modification families" becomes **8 of 12** under the second run.
Meanwhile §3.4 claims the suite is "seeded per (image, modification, level), so CV, DL, and hybrid
score bit-identical probes" and §4.6 claims "a second machine reproduced every AR and FAR number
exactly, since the suite is seeded end to end."

Those two reproducibility claims are the ones a reviewer is most likely to test, and the repository
currently disproves them for the LBPH column.

**What to do, in order:**
1. Determine which run is canonical and why they differ. The SFace and cascade columns are identical
   across both runs; only LBPH moved. That points at the detector/no-face fallback path or a
   preprocessing change between runs, not at the seeding.
2. Regenerate both artifacts from the canonical code and delete the stale one.
3. If the drift cannot be eliminated before the deadline, **weaken the reproducibility claim to
   what is true**: state that DL and cascade results are bit-reproducible and that the LBPH leg
   varies by up to X points across runs, and report the LBPH column as a range or with a run-to-run
   standard deviation. A stated, bounded nondeterminism is defensible. An exactness claim that fails
   on rerun is not.

### 6.3 The §4.3 latency numbers match no artifact

Draft §4.3: "Mean latency on this suite: LBPH 5.6 ms, SFace 22.4 ms, cascade 16.0 ms, parallel
22.8 ms."

| Source | LBPH | SFace | Cascade | Parallel |
|---|---:|---:|---:|---:|
| Draft | 5.6 | 22.4 | 16.0 | 22.8 |
| `evidence/ls_db2_41mods.md` mean | 7.71 | 25.89 | 19.68 | 26.41 |
| `evidence/ls_db2_41mods.md` median | 5.74 | 23.66 | 20.25 | 24.58 |
| `accuracy_ratio_hybrid.json` mean | 7.74 | 28.63 | 18.83 | 25.20 |

No row matches. The derived claim in the same paragraph — the cascade sits "0.40 points under the
parallel ceiling **at 70% of its cost**" — is also wrong on either artifact: 19.68/26.41 = 75%,
18.83/25.20 = 75%.

**What to do.** Replace all four numbers with one artifact's values, state explicitly whether they
are means or medians, and recompute the cost ratio to **≈75%**. Latency is machine-dependent, so
also name the machine in the experimental setup (`hw_profile.json`).

### 6.4 "Every number is from a committed run" is currently false

The draft header asserts it. But `.gitignore:121–124` excludes `reports/benchmark/*.json`,
`reports/benchmark/*.md`, and `reports/benchmark/**/*.json` — which means
`reports/benchmark/evidence/ls_db2_41mods.md`, the artifact behind **Table 3, the recovery rate, the
McNemar test, and the gate AUC**, is untracked. So is `accuracy_ratio_hybrid.json`. The independence
artifacts (`reports/independence/**`) *are* tracked.

**What to do.** Either add a `!reports/benchmark/evidence/` negation to `.gitignore` and commit those
artifacts, or drop the sentence. Given that reproducibility is one of your selling points, commit
the artifacts. This is a five-minute fix with disproportionate credibility value.

### 6.5 Verified — these numbers are solid, quote them freely

Checked cell by cell against the artifacts; all match.

| Claim | Value | Artifact |
|---|---|---|
| LBPH verification | TAR 98.21% [90.6–99.7], FAR 76 ppm, FRR 1.79%, EER 0.07% | `reports/figures/METRICS.md` (tracked) |
| Rank-1, three families | 100% / 75% / 66.07% | `reports/figures/METRICS.md` |
| AR, three families | 85.43 / 47.69 / 30.54 | `reports/figures/METRICS.md` |
| SFace LFW parity | FP 0.0747%, 32,313,540 comparisons, 5,685 ids | `reports/independence/sface_lfw_parity.json` (tracked) |
| Recovery rate | 78.6% [74.0–82.5] = 279/355; w/x/y/z = 1923/18/279/76 | `reports/benchmark/evidence/ls_db2_41mods.md` |
| Both-wrong ceiling | 3.3% [2.7–4.1]; 32.1% on gaussian_noise | same |
| McNemar | p = 2.5×10⁻⁶¹ (draft says "< 10⁻⁶⁰" — correct) | same |
| Gate competence | AUC 0.953 (margin alone 0.898), TPR 0.975, FPR 0.573 | same |
| Table 6, all four legs | LBPH 0.66/1.67/15.74% & 867 ppm; SFace 1.80/1.56/1.98% & 190 ppm; both 0.053/0.185/0.688% & 2.1 ppm; cascade 1.39/1.22/1.27% & 98 ppm; obs/exp 4.45/7.12/2.20/12.85; Q +0.66/+0.80/+0.49/+0.86 | `reports/independence/hybrid/{lsdb1_i10, lsdb2_light_i10, lsdb2_medium_i10, lfw1}/summary.json` |
| Fisher p, LFW | 8.77×10⁻⁵² (draft says 9×10⁻⁵² and "below 10⁻⁵¹" — correct) | `.../lfw1/summary.json` |
| phi, LFW | 0.0048 (draft says 0.005 — correct) | same |
| Decorrelation under degradation | obs/exp 2.02 (light) → 1.28 (medium); Q +0.34 → +0.13; cascade 98.7 → 100.9 ppm | `.../lfw2_light/`, `.../lfw2_medium/` |
| LFW LBPH threshold | raw 19.18 at rank 330,453 = 10,000 ppm; rank 256/512 = raw 17.02/17.20 | `reports/independence/lbph_lfw1/summary.json` (tracked) |
| Annotation errors | rank 8 = Caldecott/Gilligan; global min = Carlos Beltran / Raul Ibanez, raw 10.12 | same |
| Table 7 transfer | 71.75 → 55.86 → 51.51 (1% point); 87.06 → 66.13 → 62.96 (median) | `lbph_lfw1/summary.json`, `lbph_latest/summary.json` |

---

## 7. Terminology: fix the "independence" overload

The paper uses "independence testing" for two unrelated things:

1. **§3.2** — the exhaustive all-pairs impostor sweep used to *derive thresholds*. Nothing
   statistical about independence here; the name refers to the pairs being independent identities.
2. **§3.5 / §4.5** — the statistical test of whether the two engines' *errors* are independent.

The title says "Based on Independence Testing." A reviewer reads that as sense (2), then reaches
§4.5 and finds the paper's own data rejecting error independence. That is a self-inflicted wound.

**Fix:** rename sense (1). Call it the **exhaustive impostor sweep** or **all-pairs impostor
calibration** throughout §3.2, §4.1, §4.6 and the title, and reserve "independence" strictly for the
error analysis. Suggested title:

> **LS-Face: Threshold Derivation by Exhaustive Impostor Comparison for a Gated Classical–Deep Face
> Recognition Cascade**

or, leading with C1:

> **A Cascade Does Not Need Independent Errors: Measured Complementarity in a Classical–Deep Face
> Recognition Gate**

The second is riskier and more memorable. Either is better than the current one, which promises a
result the paper disproves.

**Other terminology to stabilize:** pick one of "hybrid" / "cascade" / "gated cascade" and use it
exclusively (the draft uses all three, plus "fused system" and "the fused 98 ppm"). Pick one of
"modification" / "corruption" / "degradation". Use "LS-DB1/LS-DB2/LFW-DB1/LFW-DB2" consistently —
the draft also writes "La Salle DB1", "LS-DB1", and "the anchor" for the same thing.

---

## 8. The limitations section you need to write

Reviewers reward volunteered limitations and punish discovered ones. Write these four, each in two
or three sentences, each paired with what it would take to resolve:

1. **Closed-set, single-cohort enrollment.** 28 identities, matched studio conditions, gallery and
   probes share identities. Open-set identification is out of scope and unmeasured. State the
   consequence: the TAR numbers do not predict behavior against an unenrolled visitor who resembles
   an enrolled one.
2. **n = 56 carries the headline verification claim.** TAR 98.21% has a 95% CI of [90.6, 99.7]; a
   single probe moves it 1.79 points. The draft states this in a note under Table 2 — move it into
   the abstract's phrasing ("98.21% [90.6–99.7] over 56 held-out probes"). Similarly, Table 4's
   "FAR 0%" is an observation over 400 impostors, upper bound ≈0.95%, not a certified rate.
3. **The gate's calibration does not transfer as cleanly as the thresholds do.** This is §6.1 above.
   Thresholds frozen on the hardest leg transfer conservatively on the *impostor* axis; the gate's
   margin rule loses 3.57 points on the *accuracy* axis out of domain.
4. **No on-device measurement.** Every latency number is desktop. The Raspberry Pi 5 claim in the
   introduction is a design target, not a result. Either measure it before submission or reword the
   introduction to say "intended for" rather than implying it was validated there.

The draft's §4.7 already gestures at (4). Make all four explicit and numbered.

---

## 9. Reviewer question list, answered

Run this before submission. Current status marked.

**Contribution**
- What new knowledge does this give? → **Pass** once C1 is promoted to the abstract's lead finding.
- Is the failure case meaningful? → **Pass.** Edge face recognition under degradation is real.
- Is the idea non-obvious? → **Needs revision.** Cascades are well explored; the non-obvious part is
  the independence refutation. Frame accordingly (§2 of this guide).
- Is the gain surprising? → **Pass** for C1 (12.9× correlated errors, cascade still wins).

**Writing clarity**
- Can a reader reproduce the method? → **Needs revision.** No pipeline figure; τ_a, τ_r, m_min values
  are never actually given in the paper (only their derivation rule). State the numbers.
- Is every module motivated? → **Pass.**
- Terminology consistent? → **Needs revision.** See §7.
- One message per paragraph? → **Mostly pass.** Fix the file-path-first topic sentences.

**Experimental strength**
- Improvements meaningful? → **Pass.** 5.10% → 97.96% degraded rank-1 is not marginal.
- Consistent across settings? → **Needs revision.** §6.1 — not consistent out of domain, and the
  paper must say so.
- Strengths *and* failures reported honestly? → **Pass, and this is a strength.** The both-wrong
  ceiling, the negative calibration result, and the correlated-error finding all cut against the
  authors. Keep every one of them.

**Evaluation completeness**
- Ablations for key design choices? → **Pass.** Gate operating curve (25 settings), preprocessing
  comparison, parallel ceiling, absolute-vs-relative margin.
- Strong baselines under fair settings? → **Needs revision.** No prior hybrid/cascade compared. At
  minimum, position against them in Related Work.
- Metrics standard and sufficient? → **Pass.** TAR/FAR/FRR/EER per ISO/IEC 19795-1, Wilson CIs,
  McNemar, Yule's Q.
- Datasets challenging enough? → **Pass**, with the LFW2 leg included; **marginal** without it.

**Method design soundness**
- Setting realistic? → **Pass** for a gate; state the closed-set restriction.
- Hidden defects? → **Needs revision.** The reproducibility drift (§6.2) is the one a reviewer could
  find.
- Robust without per-case retuning? → **Pass on thresholds** (frozen, SHA-256 recorded, transferred
  unchanged); **qualified on the gate** (§6.1).
- Do benefits outweigh complexity? → **Pass.** 2× throughput at equal clean accuracy, and lower FAR
  than either engine alone.

---

## 10. Four-day execution order

Deadline is July 31. Work in this order; stop adding and start typesetting on day 3.

**Day 1 — resolve the blockers.**
Decide short vs long (§0.1). Reconcile the two LS-DB2 runs (§6.2) — this gates the abstract's
"9 of 12". Fix the latency numbers and the 70%→75% cost ratio (§6.3). Un-ignore and commit the
evidence artifacts (§6.4).

**Day 2 — restructure and add.**
Rename "independence testing" throughout (§7). Add the LFW2 out-of-domain subsection and table
(§6.1). Add the Related Work paragraph on cascades. Split Discussion from Experiments and write the
Limitations section (§8). State the actual τ_a, τ_r, m_min values.

**Day 3 — figures and tables.**
Build the pipeline figure and the joint-error figure. Merge Tables 4 and 5. Normalize precision and
units across all tables (§5). Rewrite every caption to state a conclusion.

**Day 4 — adversarial pass and typeset.**
Re-run §9's question list. Check every abstract and introduction number against §6.5's ledger one
final time. Typeset, check overfull boxes, submit.

**If you run out of time, cut in this order:** the per-engine threshold detail in §4.1, then Related
Work's classical paragraph, then the discussion of Q's floor artifact. **Never cut:** the confidence
intervals, the transfer results, the both-wrong ceiling, or the correlated-error finding. Those four
are what make the paper defensible.
