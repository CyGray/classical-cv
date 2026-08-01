# Recommendation — Is Yule's Q the right test for LBPH↔SFace complementarity?

> **Status:** recommendation / methodology review. No code or paper changes applied.
> **Date:** 2026-07-09.
> **Question it answers:** *"Why are we using Yule's Q to test whether LBPH and SFace
> complement each other, when the real claim is that DL covers wherever CV fails? Why not
> test each engine's actual weakness (LBPH's accuracy, SFace's speed)? Does Yule's Q still
> earn us credit? Are there better tests?"*
>
> **Scope:** reviews §3.5 / §4.5 of `docs/PAPER.md`, `src/hybrid/independence_test.py`,
> and `src/stats_utils.py:error_diversity`. Cross-references the already-measured
> speed/accuracy results in §4.4 (Tables 3–4) and the robustness results in §4.3.

---

## 0. TL;DR — the verdict

**Your instinct is right, but the fix is smaller than you think, because the tests you
actually want are mostly already in the repo — they're just not the Q test.**

1. **Yule's Q is not the "does the hybrid work" test, and it was never carrying that
   claim.** Your paper already proves the hybrid works on two *other* axes: the
   speed↔accuracy operating points (§4.4, Tables 3–4: 25% escalation, ~100 fps at
   SFace-equal accuracy) and per-modification robustness (§4.3). Q lives in a *third,
   narrower* box — error independence on the impostor sweep (§4.5) — and answers only
   *"do the two engines false-accept the **same** impostor pairs?"*

2. **On your headline dataset (La Salle, 756 comparisons) Yule's Q is mathematically
   degenerate.** With SFace at ~20/756 false accepts and LBPH at a similarly low rate, the
   expected joint-error count is well under 1, so the observed both-fail cell is almost
   certainly 0 — and **Q = −1 *exactly* whenever that cell is 0**, regardless of anything
   else. It reports "maximally complementary" as an artifact of low base rates, not as a
   finding. Your own code already guards the fully-degenerate case (`"Yule Q = n/a"`).

3. **The base-rate-aware tests that answer the same question honestly are already
   computed** in `error_diversity()` / the sweep summary: observed-vs-expected joint FP,
   Fisher's exact `p_negative`, the double-fault floor, and — most important — the
   **cascade's own false-accept count**. Lead with those; they don't saturate.

4. **Q still earns *some* credit** (it's the citable Kuncheva–Whitaker diversity measure a
   reviewer expects to see), but only on the **LFW leg** (33M comparisons) where the
   both-fail cell is actually populated. Keep it there, demoted and captioned; drop it as
   the La Salle headline.

5. **The one genuinely missing test is gate competence:** does LBPH's own
   confidence/margin predict when LBPH is wrong? If it doesn't, the cascade cannot route,
   and *no* diversity number can rescue it. This is worth adding (see §5.4).

Decision table:

| Instrument | Axis it tests | Keep? | Where |
|---|---|---|---|
| Speed↔accuracy operating points (§4.4) | resource complementarity (LBPH speed vs SFace accuracy) | **Lead with it** | already have |
| Per-modification AR + recovery rate (§4.3) | robustness (where CV breaks, DL saves) | **Lead with it** — fill the [PENDING] DL/cascade columns | framework exists |
| Cascade FP count + double-fault (§4.5) | security error floor of the fusion | **Keep, promote** | already computed |
| Observed/expected joint FP + Fisher `p_negative` (§4.5) | error independence, base-rate-aware | **Keep, promote** | already computed |
| **Yule's Q** (§4.5) | error independence, base-rate-**blind** | **Demote** to LFW-only diagnostic | already computed |
| Gate confidence→correctness AUC | can the gate route at all? | **Add** (missing) | new |

---

## 1. What your system actually claims — three axes, not one

The confusion dissolves once "complementarity" is split into the three distinct claims your
architecture actually makes. They are tested by three different instruments, and Yule's Q
touches only one of them.

| # | Claim (in plain terms) | The right measurement | Your instrument | Status |
|---|---|---|---|---|
| **A. Resource** | LBPH is cheap but weak; SFace is accurate but slow; the cascade should buy near-SFace accuracy at near-LBPH cost | accuracy **and** latency at a chosen operating point (ideally a swept curve) | §4.4 Tables 3–4, Fig. 4 (speed–accuracy plane) | **Measured** (clean + degraded splits) |
| **B. Robustness** | The corruptions that break LBPH (noise, blur, darkening) are exactly the ones SFace survives | per-modification AR for CV vs DL, and the fraction of CV's failures DL recovers | §3.4 / §4.3 (41-mod AR); DL+cascade columns | **[PENDING]** — framework built, run not filled |
| **C. Security / error independence** | When the engines *do* false-accept an impostor, they rarely do it on the *same* impostor, so a fusion can filter one's mistakes with the other | joint FP vs the independence expectation, on the impostor sweep | §4.5 (`hybrid/independence_test.py`): obs/exp, Fisher, double-fault, cascade-FP, **and Yule's Q** | **[PENDING]** — code complete, run not filled |

Your original worry — *"why not test LBPH's low accuracy and SFace's low speed directly?"* —
is answered by **A and B, not by Q.** LBPH's low accuracy is exactly the 41-mod AR collapse
in §4.3 (Rank-1 5.10% on the degraded split, Table 4) and SFace's cost is exactly the
latency column in §4.4 (19.92 ms vs LBPH's 5.74 ms). Those tests already model the real
weaknesses. **Yule's Q is on axis C, which is about false-accepts (security), not about
accuracy or speed at all.** So for the specific weaknesses you named, Q is the wrong axis —
but you are not missing the right test, you already have it elsewhere.

---

## 2. What Yule's Q actually measures here (and why it reads as "complementarity")

On the impostor sweep every cross-identity pair is an impostor by construction. Each pair is
flagged `lbph_fp` (LBPH distance ≤ τ_accept) and/or `sface_fp` (cosine ≥ 0.363 ∧ L2 ≤ 1.128).
That gives the 2×2 table `error_diversity()` consumes
(`src/hybrid/independence_test.py:405`, convention from `src/stats_utils.py:22`):

|            | SFace FP | SFace OK |
|------------|:--------:|:--------:|
| **LBPH FP**|   a      |    b     |
| **LBPH OK**|   c      |    d     |

with

$$Q = \frac{ad - bc}{ad + bc}, \qquad DF = \frac{a}{C}, \qquad \text{disagreement} = \frac{b+c}{C}.$$

`a` = both engines false-accept the same impostor pair; `b`/`c` = exactly one does; `d` =
neither. `Q < 0` is read as "the engines fail on *different* pairs → complementary." That
reading is correct **in principle** and is the standard Kuncheva–Whitaker (2003)
interpretation. The problem is not the definition; it is what the definition does at your
sample size.

---

## 3. Why Yule's Q is the weakest instrument in the panel

### 3.1 It saturates to −1 at low base rates — which is La Salle's regime

Watch what happens to `Q = (ad − bc)/(ad + bc)` when the both-fail cell `a = 0`:

$$Q = \frac{0\cdot d - bc}{0\cdot d + bc} = \frac{-bc}{bc} = -1 \quad (\text{for any } b, c > 0).$$

**Q collapses to exactly −1 the moment the two engines never false-accept the same pair —
independent of `d`, independent of how large or small the individual error rates are.**
It cannot tell "genuinely complementary" apart from "both just have low FAR and by luck
didn't collide."

Now the La Salle numbers. §4.5 already reports SFace puts **20 of 756** impostor pairs inside
its genuine rule (a + c = 20 ≈ 2.6%). Take LBPH's FP total (a + b, still `[run to fill]` in
§4.5) at a comparable low rate — say ~15/756. Under the independence null the expected
joint-fail count is

$$\mathbb{E}[a] = \frac{(a+b)(a+c)}{C} \approx \frac{15 \times 20}{756} \approx 0.40.$$

So the *expected* number of shared false-accepts is **less than one half of one pair.**
Observing `a = 0` is the modal outcome under pure independence (Poisson(0.40) → P(a=0) ≈ 0.67).
And `a = 0` forces **Q = −1**. You would report "maximally complementary errors (Q = −1)"
from a table that is completely consistent with the engines being statistically independent.
That is not evidence; it is the low-base-rate floor of the statistic.

Contrast with the base-rate-aware members of the *same* panel on the *same* `a = 0` table:

| Statistic | Value at `a = 0`, `E[a] ≈ 0.40` | Honest reading |
|---|---|---|
| **Yule's Q** | **−1.000** | "maximally complementary" — **overstated** |
| observed/expected (`a / E[a]`) | 0.0 | below independence, but from ~0.4 expected — weak |
| Fisher `p_negative` (P(X ≤ a)) | ≈ 0.67 | **not significant** — correctly says "nothing proven here" |
| double-fault `a/C` | 0.000 | the fusion's FAR floor is ~0 here — **useful** |

Fisher's exact `p_negative ≈ 0.67` is the truth: at this base rate La Salle simply cannot
demonstrate error independence. Q's −1 hides that. This is the single strongest technical
reason to demote Q.

### 3.2 If instead `a > 0`, Q is confounded by the accuracy imbalance

The other regime is no kinder. LBPH and SFace have very unequal FARs and very unequal
identification accuracy. Kuncheva & Whitaker's own analysis (the paper you cite) shows the
Q/diversity family correlates poorly with actual ensemble gain precisely when member
strengths diverge — the marginals constrain Q so that its magnitude reflects the accuracy
gap as much as any true "diversity." So on the LFW leg, where `a` is finally non-zero, a
mid-range Q is not cleanly interpretable as "how complementary" — it is partly just "how
differently accurate." Your `phi` (already returned by `error_diversity`) is better behaved
here: at `a = 0` it scales with the base rates instead of pinning to −1, so if you want one
association number, **prefer `phi` over `Q`** — but the honest significance statement is
still Fisher, not either coefficient.

### 3.3 Q is blind to the two axes you actually care about

Q is computed on the **false-accept** table only. It has no term for latency and no term for
identification accuracy under degradation. It therefore cannot speak to:

- **SFace's cost / the cascade's speed win** — that is the latency and escalation-% columns
  of §4.4, nothing to do with Q.
- **LBPH's accuracy collapse under noise/blur, and SFace rescuing it** — that is the 41-mod
  AR of §4.3, a *genuine* identification test, again nothing to do with Q.

So even a perfect, well-defined Q would still leave both halves of "DL handles where CV
fails" unmeasured. It is structurally incapable of being the headline.

---

## 4. Does Yule's Q still earn credit? — Yes, but scoped

Keep it, for reasons that are real but narrow:

1. **Literature anchoring.** Q is *the* canonical pairwise diversity measure
   (Kuncheva & Whitaker, *Machine Learning* 51, 2003). A multiple-classifier-system reviewer
   expects to see a diversity measure reported; omitting it invites "why didn't you use the
   standard tool?" Reporting it (with `phi`, disagreement, double-fault — you compute all
   four) shows you know the field.
2. **A one-glance sign summary,** *where it is defined.* On the **LFW leg**
   (`--max-identities` large, 33M comparisons) the both-fail cell is populated, Q stops
   saturating, and it becomes a legitimate, comparable number.
3. **It is free** — already implemented, tested by usage, and emitted next to the tests that
   do the real work.

What it does **not** earn: the right to be the sentence that proves complementarity on La
Salle. On La Salle it is either −1 (saturated) or `n/a` (a zero-cell product) — your own
console output prints both cases. Present it there, if at all, as *"Q = −1 at this base rate
is the low-count floor, not a finding; see the Fisher and cascade-FP results."*

**One-line framing for the paper/defense:** *"Yule's Q shows the engines are diverse in
principle; it does not show the hybrid is good. The hybrid is good because SFace rescues the
modifications LBPH fails (§4.3 recovery rate) at a fraction of always-on DL cost (§4.4
latency), and because the fused cascade's own false-accept count undercuts either engine
(§4.5) — which is what we measure directly."*

---

## 5. The tests that actually test the real weaknesses — ranked

Ordered by how directly each supports the thesis. For each: the formula, what it proves, and
what you have vs. need.

### 5.1 (Primary) Resource complementarity — the speed↔accuracy operating curve

**Claim:** near-SFace accuracy at near-LBPH latency. **This is the whole hybrid.**

You already have the three-point version (§4.4, Tables 3–4, Fig. 4): LBPH-only / SFace-only /
cascade with Rank-1, TAR, FRR, escalation %, latency, FPS, on a clean and a degraded split.
That is genuinely the money result and it already dominates.

**Upgrade to a curve, not three points.** Sweep the gate's operating aggressiveness — the
`margin_min` and the τ_accept/τ_reject band in `src/hybrid/gate.py` — and plot **accuracy vs.
mean latency** (equivalently vs. escalation %). One curve per split. The cascade should trace
the efficient frontier between the LBPH-only and SFace-only corners; the deployed threshold is
one labelled point on it. This turns "we picked 25% escalation and it worked" into "here is the
whole speed/accuracy trade and here is where we chose to sit," which is a materially stronger
claim and pre-empts the "did you cherry-pick the threshold?" question.

### 5.2 (Primary) Robustness complementarity — per-modification AR + recovery rate

**Claim:** DL is strong exactly where CV is weak. Fill the **[PENDING]** DL/cascade columns in
§4.3 (`src/benchmark/accuracy_ratio_hybrid.py`). Then add the one number that states the
complementarity as a conditional, which is what your original question was really asking for:

$$\text{recovery rate} = \frac{\#\{\text{probes LBPH mis-identifies but SFace gets right}\}}{\#\{\text{probes LBPH mis-identifies}\}} = P(\text{SFace correct}\mid\text{LBPH wrong}).$$

"Of the frames the fast engine fails, the accurate engine rescues X%." Report it per
modification and overall. Its complement — probes **both** miss — is the identification-side
double-fault, the accuracy ceiling no fusion can beat. This is the direct, asymmetric,
identification-axis analogue of what Q gestures at on the security axis, and it is far more
legible to a reader. **Note this is *not* yet computed** — the sweep's
`p_sface_fp_given_lbph_fp` is on the false-accept axis, a different thing.

### 5.3 Security error-independence — done with the base-rate-aware panel, not Q

**Claim:** the fused system's FAR beats either engine's. Lead this section with the numbers
that don't saturate, all of which you already compute in the sweep summary:

- **Cascade FP count / rate** (`fp_cascade`, with Wilson CI) — the *actual* deployed system's
  false accepts. This is the result; everything else explains the mechanism behind it. It
  should undercut both single engines.
- **Double-fault `a/C`** — the FAR floor of *any* fusion of these two engines (a both-fail
  impostor pair is a cascade FP whether the gate escalates it or not, so
  `cascade_fp ≥ a` always). Report cascade-FP against this floor.
- **Observed/expected joint FP** (`observed_over_expected`) — 1.0 = independent errors,
  <1 = decorrelated. Base-rate-aware, unlike Q.
- **Fisher's exact `p_negative`** — the honest significance test for "errors avoid each
  other more than chance." On La Salle it will (correctly) be non-significant; on LFW it has
  power. This is what carries the statistical claim.
- **Yule's Q / phi** — report on the **LFW leg only**, as the literature-standard diversity
  summary, captioned as in §4. On La Salle, footnote that it saturates.

Because 756 comparisons bound FAR no tighter than ~0.5–1% (your own §4.6 point), **the LFW
leg — not La Salle — must carry axis C.** Prioritise running
`src/hybrid/independence_test.py` with a large `--max-identities` on LFW; that is the run that
makes *every* axis-C statistic, Q included, actually mean something.

### 5.4 (Add — currently missing) Gate competence: does confidence predict correctness?

This is the load-bearing assumption no current test checks. A cascade can only route CV's
failures to DL if CV's *own* signal (the LBPH distance `d₁` and relative margin
`(d₂−d₁)/d₁`) is predictive of whether LBPH is about to be wrong. Measure it directly:

- Treat the gate signal (distance, or margin, or the combined rule) as a score for the
  binary label "LBPH identified correctly." Compute **ROC AUC** (and a precision/recall on
  "escalate the wrong-LBPH frames").
- **AUC ≈ 1.0:** the gate can perfectly tell when to escalate — the cascade is sound.
  **AUC ≈ 0.5:** LBPH cannot tell when it is wrong, so escalation is blind and the whole
  design rests on luck, no matter how complementary the engines are.

You have circumstantial evidence the gate routes well (§4.4: on the degraded split the gate
escalates 100% of frames, 89/98 on a quality flag; on clean it keeps 75% cheap with no
accuracy loss). Turning that into an AUC makes the gate's competence a *measured* property
rather than an inference from two operating points. This is the highest-value addition on
this list after filling the [PENDING] runs.

### 5.5 (Optional) Significance of the accuracy gap: McNemar

If you want a significance statement that SFace is more accurate than LBPH on the *same*
probes (paired, which a bare accuracy comparison is not), run **McNemar's test** on the
discordant identification outcomes: statistic `(|b−c|−1)² / (b+c)`, χ² with 1 df, on the
"LBPH-right/SFace-wrong" vs "LBPH-wrong/SFace-right" cells of the 41-mod probes. Cheap,
standard, and it directly certifies the premise that SFace is the stronger engine on the hard
frames. `error_diversity`/`fisher_exact` already give you the machinery to add it.

---

## 6. Concrete actions

| # | Action | File(s) | Priority |
|---|---|---|---|
| 1 | Run the §4.5 hybrid independence sweep on **LFW** (large `--max-identities`), not just La Salle — this is what makes axis C (and Q) meaningful | `src/hybrid/independence_test.py` | **High** |
| 2 | In §4.5, **lead with** cascade-FP (vs double-fault floor), observed/expected, and Fisher `p_negative`; move Yule's Q to a captioned LFW-only diagnostic | `docs/PAPER.md` §4.5, §3.5 | **High** |
| 3 | Fill the **[PENDING]** §4.3 DL/cascade AR columns and add the **recovery rate** `P(SFace correct \| LBPH wrong)` per modification | `src/benchmark/accuracy_ratio_hybrid.py`, `docs/PAPER.md` §4.3 | **High** |
| 4 | Add **gate AUC** (LBPH confidence/margin → LBPH-correct) as a new measurement and a line in §4.4 | new (near `src/hybrid/gate.py`); `docs/PAPER.md` §4.4 | **High** |
| 5 | Upgrade §4.4 from three points to a **swept speed–accuracy curve** over the gate thresholds | `src/benchmark/`, `docs/PAPER.md` §4.4, Fig. 4 | Medium |
| 6 | Report **`phi`** alongside/instead of Q where a single association coefficient is wanted (it does not saturate to −1 at `a=0`) | already in `error_diversity`; `docs/PAPER.md` §3.5 | Low |
| 7 | (Optional) Add **McNemar** on the 41-mod discordant identifications | new, near `src/stats_utils.py`; `docs/PAPER.md` §4.3 | Low |

---

## 7. Suggested wording changes in the paper

- **§3.5, Eq. (6):** keep Q and DF in the equation, but change the surrounding text from
  presenting Q as the complementarity verdict to: *"we report the Kuncheva–Whitaker diversity
  measures (Q, φ, disagreement, double-fault) for comparability with the ensemble literature;
  the complementarity claim itself rests on the base-rate-aware quantities — the cascade's own
  false-accept count against the double-fault floor, the observed/expected joint-error ratio,
  and Fisher's exact test — because Q saturates to −1 whenever the engines share no
  false-accept, which at La Salle's base rate is the expected outcome under independence."*
- **§4.5:** when filling the `[run to fill]` gaps, present the order in §5.3 above. If Q is
  −1 or `n/a` on La Salle, state *why* (low count), and point to the LFW leg for the defined
  value. Do not report a bare La Salle "Q = −1" as evidence of complementarity.
- **§4.7 (Discussion):** you already write "complementarity is a measurement, not a slogan" —
  this recommendation is that sentence taken literally: the measurement is the recovery rate +
  latency + cascade-FP, and Q is the literature courtesy, not the measurement.

---

## References

- L. Kuncheva, C. Whitaker. *Measures of Diversity in Classifier Ensembles and Their
  Relationship with the Ensemble Accuracy.* Machine Learning 51, 2003. (Q, φ, disagreement,
  double-fault; and the caveat that these correlate weakly with ensemble gain when member
  accuracies differ.)
- G. Giacinto, F. Roli. *Design of effective multiple classifier systems by clustering of
  classifiers.* ICPR 2000. (Double-fault as the fusion error floor.)
- Q. McNemar. *Note on the sampling error of the difference between correlated proportions.*
  Psychometrika, 1947. (Paired significance test for the accuracy gap.)
- In-repo: `src/stats_utils.py` (`error_diversity`, `fisher_exact`, `wilson_interval`),
  `src/hybrid/independence_test.py` (the joint sweep), `src/hybrid/gate.py` (the cascade
  gate), `docs/PAPER.md` §3.4–3.5, §4.3–4.6.
