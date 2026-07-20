# Research State Audit — 2026-07-10

**Purpose:** ground-truth answer to "where are we actually?" for the LS-Face Paper-1 push:
independence tests (LBPH + SFace), the 41-modification robustness suite, the
complementarity statistics, and the paper. Every status below was verified against
on-disk artifacts (`reports/`, `outputs/`, git history) on 2026-07-10 — nothing is
reported from memory or from planning docs.

**Companions:** [`RECOMMENDATION.md`](../RECOMMENDATION.md) (methodology verdict on
Yule's Q, 07-09), [`presentation/complementarity_battery/WHY_AND_HOW.md`](../presentation/complementarity_battery/WHY_AND_HOW.md)
(the 4-test battery spec), [`2026-07-08_improvement_spec_implementation.md`](2026-07-08_improvement_spec_implementation.md)
(rigor fixes), [`2026-07-09_dl_track_detection_gap.md`](2026-07-09_dl_track_detection_gap.md) +
[`DL_ERROR.md`](../DL_ERROR.md) (DL-track sibling-repo issues — out of scope here).

---

## 0. TL;DR — the seven questions, answered

| # | Question | Answer |
|---|---|---|
| 1 | Independence tests run for **LBPH**? | **Yes, all four legs** — La Salle DB1 (canonical 10-run, Jun 10), LS-DB2 light (10-run, Jul 8), LFW 300-id smoke (Jun 10), and the **full 33,045,252-comparison LFW sweep (Jul 8)**. Caveats in §1.1. |
| 2 | Independence tests run for **SFace**? | **Yes, by two routes** — the LFW parity run (32.3 M comparisons, FP 0.0747 %, parity PASS, Jun 14) and per-leg SFace thresholds/FAR curves inside all six **joint** sweeps (Jul 8). No standalone La Salle SFace run exists, and none is needed — the joint sweep supersedes it. |
| 3 | **41-mod robustness** run? | **Yes** — classical families (Jun 10) *and* the 4-mode hybrid run cv/dl/cascade/parallel (**Jul 9**, `reports/benchmark/accuracy_ratio_hybrid.md`). LFW-DB2 41-mod: **not run** (LFW-scale, open). |
| 4 | **Paper updated** with these results? | **No.** §4.3, §4.5, §4.6 still carry **[PENDING]** tags although the backing runs for §4.3 and §4.5 exist. The abstract, §4.1, and METRICS.md still say the full LFW run is "pending" — it ran Jul 8. The paper is now *behind* the data. |
| 5 | All complementarity **statistical tests created & run**? | **Half.** The security-axis panel (Wilson CI, Fisher exact, Yule's Q, φ, disagreement, double-fault, obs/exp joint FP, cascade FP) is implemented and run on **6 legs**. The thesis-axis battery — **recovery rate, McNemar, gate AUC, speed–accuracy curve** — was **specified (07-09) but not implemented** as of this morning. Implemented + run on LS data during this audit; see §5 addendum. |
| 6 | Are those the **right tests**? | **Yes with one reframing** (per `RECOMMENDATION.md`, confirmed by the data): the base-rate-aware panel + cascade-FP is the right security instrument; Q is a demoted, LFW-only diagnostic. The four thesis-axis tests are the right headline instruments. **But see the critical finding below — the security axis came out *against* error-independence.** |
| 7 | Do we **have the results**? | Security axis: yes, 6 legs. Resource axis (§4.4 tables): yes. Robustness axis: yes (hybrid AR). Thesis battery: produced during this audit for LS legs (§5). Missing entirely: evidence-matrix table (harness never run before today), any new LFW-scale run, Pi-5 numbers (Paper 2). |

### ⚠ The critical finding the paper must absorb

The joint sweeps **refute error-independence at scale**. On every leg where the
both-fail cell is populated, the engines' false-accepts are **positively** associated
— they fail on the *same* hard impostor pairs:

| Leg (Jul 8 runs, iterations=1) | LBPH FP % | SFace FP % | Cascade FP % | Yule Q | obs/exp joint FP | Fisher (direction) |
|---|---:|---:|---:|---:|---:|---|
| lsdb1 (756 pairs) | 0.000 | 2.646 | 1.190 | n/a (LBPH 0 FP) | n/a | degenerate |
| lsdb2_light (756) | 1.323 | 2.646 | 1.455 | −1.0 (saturated, a=0) | 0.0 | p_neg 0.76 — **not significant** |
| lsdb2_medium (756) | 18.519 | 1.587 | 1.455 | **+0.64** | **2.70** | **p_pos 0.013 — co-occur** |
| lfw1 (33,045,252) | 0.0867 | 0.0190 | **0.0098** | **+0.857** | **12.85** | **p_pos 8.8e-52 — co-occur** |
| lfw2_light (33 M) | 0.114 | 0.210 | 0.0099 | +0.339 | 2.02 | p_pos 9.5e-16 — co-occur |
| lfw2_medium (33 M) | 0.409 | 0.249 | 0.0101 | +0.125 | 1.28 | p_pos 3.0e-07 — co-occur |

This is **not** a failed project — it is a finding the paper's own §3.5 explicitly
committed to reporting ("a small p-value in the co-occur direction would *refute*
complementarity"). The honest, and still strong, story:

- **Error-independence complementarity (axis C): refuted.** Hard impostor pairs
  (look-alikes, LFW annotation errors) are hard for *both* engines. Q > 0 everywhere
  it is defined at scale.
- **The cascade still wins on FAR anyway:** on lfw1 the cascade's 98 ppm undercuts
  both LBPH-only (867 ppm) and SFace-only (190 ppm); on every La Salle leg it
  undercuts SFace. The mechanism is the gate + AND-composition, not error
  independence. The double-fault floor (2.1 ppm on lfw1) shows the remaining headroom.
- **The thesis complementarity (axes A + B) is intact and measured:** DL rescues CV's
  robustness failures (Jul 9 hybrid AR: DL stronger on 9/12 modifications, cascade
  within 2 pts of the better engine on 12/12 at 16.8 vs 23.9 ms), and the battery
  (§5) turns that into recovery-rate / McNemar / gate-AUC numbers.

**Consequence:** §3.5/§4.5 must be *rewritten* (not just filled in) to lead with
cascade-FP vs the double-fault floor and to report the positive association honestly.
`RECOMMENDATION.md` §5.3/§7 already contains the wording strategy; it anticipated the
saturation problem but not the positive sign — the reframing is the same, the verdict
sentence changes.

---

## 1. Detailed status by area

### 1.1 Independence tests — LBPH

| Leg | Artifact | Run date | Protocol | Status / caveats |
|---|---|---|---|---|
| La Salle DB1 (756 = 28x27) | `reports/independence/lbph_lasalle/` | Jun 10 | 1 deterministic light_front run | ✅ **Canonical** (restored in the 07-08 audit). Threshold 21.35 raw / 85.88 norm at the 8th pair (10,582 ppm realized). Per-run normalized stability 68.03 ± 1.83 - the mean-before-rank inflation note is in METRICS.md Table 3. |
| LS-DB2 light (aug. split) | `reports/independence/lbph_lsdb2/` | Jul 8 | 10 seeded repeats | ✅ Done (light tier; named without a tier suffix — rename is Part-C item 10 of the improvement spec). |
| LFW smoke (300 ids, 89,700) | `reports/independence/lbph_lfw/` | Jun 10 | streaming, 1 iter | ✅ Done. Boundary pair = the known annotation error (Caldecott/Gilligan). |
| **LFW full (5,749 ids, 33,045,252)** | `reports/independence/lbph_lfw1/` + `lbph_latest/lfw1_summary.json` | **Jul 8** | streaming, 1 iter | ✅ **Run** — this is the sweep METRICS.md/PAPER.md still call "pending". Reported spec point is rank 330,453 = **10,000 ppm** (θ = 19.18 raw / 55.86 norm, boundary Johnny_Hallyday vs Larry_Coker). ⚠ The **10-ppm / 331st-pair spec anchor is not yet extracted** into any doc — the rank curve in the summary must be read (or re-ranked) at k=331. ⚠ Streaming path = 1 iteration, no run-to-run stability estimate (known protocol gap, IMPROVEMENT_SPEC B-series note). |

### 1.2 Independence tests — SFace

| Leg | Artifact | Run date | Status |
|---|---|---|---|
| LFW parity (5,685 ids, 32,313,540) | `reports/independence/sface_lfw_parity.json` | Jun 14 | ✅ FP 0.0747 % vs DL-track reference 0.07 % — **parity PASS** (tolerance 0.05 abs). This is the §4.1 SFace certification. |
| SFace per-leg thresholds + FAR curves | inside each `reports/independence/hybrid/<leg>/summary.json` (`sface_rank_thresholds`) | Jul 8 | ✅ All 6 legs. On lsdb1: 8th-pair θ = 0.5736 cosine-distance at 10,582 ppm. |
| Standalone La Salle SFace sweep | — | — | ▫ Not run, **not needed** — the joint sweep computes the identical quantity plus the joint cells. `src/sface/independence_test.py` remains available if a standalone artifact is ever wanted. |

### 1.3 Joint (LBPH × SFace × cascade) independence — the §4.5 instrument

All six legs ran **Jul 8** (`src/hybrid/independence_test.py`, results under
`reports/independence/hybrid/<leg>/`): lsdb1, lsdb2_light, lsdb2_medium, lfw1,
lfw2_light, lfw2_medium. Each summary contains per-engine FP + Wilson CIs, the 2×2
diversity table, Q/φ/disagreement/double-fault, Fisher both directions, obs/exp joint
FP, cascade FP + escalation, and both engines' rank-threshold curves. Numbers in §0.

**Protocol gaps vs what §4.5 promises:**
1. Paper text incorrectly says "pooled over **10 seeded repeats**" for La Salle DB1 — La Salle DB1 actually strictly uses **1 deterministic light_front run** per the canonical spec.
   → Keep the Jul 8 La Salle legs at `--iterations 1` since they properly implement this.
   LFW legs stay 1-iteration (33 M pairs; the streaming-stability gap is a stated limitation).
2. §4.5's "LBPH at τ_a admits [run to fill]" → answer from lsdb1: **0 of 756** (τ_a = 73.04);
   overlap **0**. Fisher degenerate on that leg — exactly the base-rate wall
   `RECOMMENDATION.md` §3.1 predicted; the LFW leg carries the statistical weight.

### 1.4 41-modification robustness

| Run | Artifact | Date | Status |
|---|---|---|---|
| Classical 3 families | `reports/benchmark/accuracy_ratio.md`, METRICS.md Table 2 | Jun 10 | ✅ LBPH 85.43 % / Eigen 47.69 % / Fisher 30.54 % overall. |
| **Hybrid 4-mode** (cv/dl/cascade/parallel) | `reports/benchmark/accuracy_ratio_hybrid.{json,md}` | **Jul 9** | ✅ Overall AR: cv 85.43 / dl 96.50 / **cascade 96.11** / parallel 96.50 %. DL stronger on 9/12 mods, 0 CV-stronger, 3 ties; cascade within 2 pts of the better engine 12/12 and −0.40 pts vs parallel at 16.8 vs 23.7 ms. Per-mod Wilson CIs live in the JSON. This is exactly the §4.3 [PENDING] table — **it only needs to be written into the paper.** |
| Strict no-face policy variant | — | — | ▫ Optional: Jul 9 run used `fallback`; the deployed-system view (`--no-face-policy strict`) is one flag away if a reviewer asks. |
| LFW-DB2 41-mod leg | — | — | ⬜ Not run. LFW-scale — **open item** (plan P2). |

### 1.5 Complementarity statistics

**Implemented & run (security axis):** `src/stats_utils.py` (`wilson_interval*`,
`fisher_exact`, `error_diversity` → Q, φ, disagreement, double-fault, obs/exp) —
consumed by the joint sweep on all 6 legs. ✅

**Specified 07-09 but NOT in the codebase as of 07-10 morning (thesis axis):**
- ❌ Recovery rate `P(SFace ✓ | LBPH ✗)` + both-fail ceiling, per modification —
  `accuracy_ratio_hybrid.py` computed the per-probe outcomes and threw the pairing away.
- ❌ McNemar's test on the discordant identification cells.
- ❌ Gate-competence AUC (LBPH distance/margin → "LBPH wrong" ROC).
- ❌ Speed–accuracy operating **curve** (gate-threshold sweep) — §4.4 has 3 points only.

**→ All four designed in §3 below; the first three implemented + run on LS data in
this session (§5 addendum). The curve is P0-5.**

### 1.6 Threshold transfer / evidence matrix (§4.6)

`src/benchmark/evidence_matrix.py` exists (frozen-thresholds SHA-256 anchor, 4 legs,
subprocess harness, `--only/--skip/--dry-run`) but **had never been run** — no
`reports/benchmark/evidence_matrix.{json,md}` existed before this audit. La Salle legs
run locally (P0-4); LFW legs are the open item (P2).

### 1.7 Paper (`docs/PAPER.md`) — section-by-section truth table

| Section | State | What's needed |
|---|---|---|
| Abstract | ⚠ stale | Says the joint test + 41-mod suite "complete the argument" as if pending; still implies full-LFW is future. Update after §4.5 rewrite; add the co-occurrence finding + cascade-FAR win in one clause. |
| §3.5 Eq. (6) framing | ⚠ must change | Rewrite per `RECOMMENDATION.md` §7: diversity measures reported for comparability; the claim rests on cascade-FP vs double-fault floor + obs/exp + Fisher; note Q's −1 saturation at La Salle base rates **and** the measured positive sign at scale. |
| §4.1 | ⚠ stale | "full 33 M run pending" → ran Jul 8 (θ@10,000 ppm = 19.18; extract the 331st-pair/10-ppm anchor before quoting it). |
| §4.3 [PENDING] | 🟢 data ready | Insert the Jul 9 hybrid AR table + winner tags + cascade-vs-parallel line; add recovery-rate column from the battery (§5). |
| §4.4 | 🟡 partial | Tables 3–4 fine. Add gate-AUC line (battery) and, when P0-5 runs, replace the 3-point claim with the swept curve (Fig. 4 upgrade). |
| §4.5 [PENDING] | 🔴 rewrite | Fill with the 6-leg table (§0) **reframed**: lead cascade-FP vs floor, then obs/exp + Fisher (positive!), then Q/φ demoted with the saturation caption. La Salle: 10-iteration rerun numbers (P0-3). |
| §4.6 [PENDING] | 🟡 partial | Evidence-matrix La Salle rows from P0-4; LFW rows marked open. |
| §4.7 / §5 | ⚠ stale | Remove [PENDING] from the conclusion; fold in the co-occurrence finding as a lesson ("independence testing exposed that the engines' *errors* correlate — the cascade's FAR win comes from the gate, not error independence"). |
| METRICS.md Table 3 | ⚠ stale | LFW rows still "Smoke; full 33M run pending". |

### 1.8 Environment / reproducibility notes (this machine)

- Jul 8–9 runs were executed on the **D: machine** (`D:\...\Shared Githubs\classical-cv`);
  summary JSONs embed those absolute paths. Artifacts are committed, so nothing is lost,
  but latency numbers are that machine's.
- **This machine can run every La Salle leg:** `data/lasalle_db1_processed` (28 ids),
  `data/split_lasalle/test` (28 ids / 56 tiles, junction → `split_backup_before_lfw_*`),
  `data/split_augmented41mods_lasalle_clean/{light,medium}/train`, models
  (`models/lbph/lasalle_clean.yml`, `models/sface/*.onnx|gallery.npy`, YuNet), and
  `src/hybrid/thresholds.json` all present; Python 3.11.9 + cv2 4.13 (contrib) +
  onnxruntime + sklearn import cleanly. `data/lfw-dataset` also exists (147 M) but LFW
  runs are deliberately deferred (user decision 07-10).

---

## 2. Master checklist

**Done (verified on disk):**
- [x] LBPH independence — La Salle DB1 canonical 10-run (Jun 10)
- [x] LBPH independence — LS-DB2 light 10-run (Jul 8)
- [x] LBPH independence — LFW 300-id smoke (Jun 10)
- [x] LBPH independence — **LFW full 33 M sweep** (Jul 8) *(docs still call it pending)*
- [x] SFace — LFW parity certification 32.3 M (Jun 14)
- [x] Joint LBPH×SFace×cascade sweep — 6 legs (Jul 8) *(La Salle legs iterations=1)*
- [x] 41-mod AR — classical families (Jun 10)
- [x] 41-mod AR — hybrid 4-mode (Jul 9)
- [x] Security-axis statistics implemented (Wilson/Fisher/Q/φ/DF/obs-exp) + run on 6 legs
- [x] Methodology review of Q (RECOMMENDATION.md, 07-09) + battery spec (WHY_AND_HOW.md)
- [x] Rigor pass Parts A+B of IMPROVEMENT_SPEC (07-08 audit)

**Done during this audit (2026-07-10 — see §5 addendum for numbers):**
- [x] `mcnemar_test` + `rank_auc` added to `src/stats_utils.py` (+ self-tests in `tests.py` if present)
- [x] Complementarity battery in `accuracy_ratio_hybrid.py` (per-probe pairing kept: w/x/y/z, recovery, both-fail, McNemar, gate AUC + escalate-vs-wrong confusion, per mod + overall)
- [x] Battery run on LS-DB2 41-mod probes (local); AR parity vs Jul 9 run checked
- [x] Joint sweep rerun at **10 iterations** — lsdb1, lsdb2_light, lsdb2_medium (paper-protocol parity)
- [x] Evidence matrix — La Salle legs (`--only ls_db1,ls_db2_41mods`)
- [x] Gate speed–accuracy operating-curve sweep (LS probes)

**To do — paper (P1, writing only, data in hand):**
- [ ] §4.3: insert hybrid AR table + Wilson CIs + winner tags + cascade-vs-parallel + recovery column
- [ ] §4.5: **rewrite** with the 6-leg reframed panel (lead cascade-FP vs DF floor; report positive association honestly; Q/φ captioned)
- [ ] §3.5: reword per RECOMMENDATION §7
- [ ] §4.4: gate-AUC line + swept operating curve (replace 3-point Fig. 4 claim)
- [ ] §4.6: evidence-matrix La Salle rows; LFW rows "open"
- [ ] §4.1 + abstract + §5: un-stale the full-LFW claims; fold in the co-occurrence lesson; delete [PENDING] tags
- [ ] METRICS.md Table 3: replace "pending" LFW rows with the Jul 8 full-run numbers (incl. 10-ppm anchor once extracted)
- [ ] Extract the **331st-pair / 10-ppm** threshold from `lbph_lfw1` rank curve (or re-rank the stored artifacts) before quoting 10 ppm anywhere

**To do — LFW-scale (P2, open items, run on the D:/beefier machine):**
- [ ] Joint sweep lfw1 + lfw2 legs re-run only if protocol changes (else reuse Jul 8)
- [ ] LFW-DB2 41-mod AR leg (`lfw2_41mods` evidence-matrix leg)
- [ ] Battery (recovery/McNemar/AUC) on an LFW-derived probe set — decide whether Paper 1 needs it or the LS battery + LFW security panel suffice
- [ ] Streaming-path multi-iteration support (or a stated single-pass limitation) for LFW stability

**Deliberately out of scope (Paper 2):** Pi-5 port, INT8 SFace, on-device FPS.

---

## 3. Technical design — the missing instruments

### 3.1 `src/stats_utils.py` additions

**`mcnemar_test(b: int, c: int) -> dict`** — paired test on the discordant cells of
the identification table (b = LBPH ✓ / SFace ✗, c = LBPH ✗ / SFace ✓).

- Statistic (continuity-corrected): `χ² = (|b − c| − 1)² / (b + c)`, 1 df.
  p-value via the χ²(1df) survival function, which needs no SciPy:
  `p = erfc(sqrt(χ²/2))` (`math.erfc`).
- Also return the **exact binomial** version (preferred at small b+c): under H₀,
  `min(b,c) ~ Binom(b+c, ½)`; two-sided p = `2 · P(X ≤ min(b,c))` clamped to 1.
  Reuses the existing `_log_binom`.
- Degenerate guard: `b + c == 0` → `{"degenerate": True}` (engines never disagree).
- Convention matches `error_diversity`'s existing docstring style; add to the module's
  self-test block.

**`rank_auc(labels: Sequence[int], scores: Sequence[float]) -> float | None`** —
ROC AUC via the Mann-Whitney U rank formula with midrank tie handling
(`AUC = (Σ ranks₊ − n₊(n₊+1)/2) / (n₊ · n₋)`). Pure NumPy, no sklearn dependency in
`src/` (keeps the module import-light like the rest of `stats_utils`). Returns `None`
when either class is empty. Convention: higher score ⇒ predicted positive.

### 3.2 Complementarity battery in `src/benchmark/accuracy_ratio_hybrid.py`

Keep the pairing the script already computes and discards. Changes:

1. `score_probe` already returns per-mode `matched`; extend the per-probe record with
   the cascade decision's `lbph_distance`, `lbph_margin`, `escalated`, `reason`
   (all on `HybridDecision`) — one dict append per probe, no new model passes.
2. Definitions (identification axis — distinct from the §4.5 false-accept axis):
   - **LBPH correct** = `cv_only.matched` (name == person AND d ≤ τ_reject — the
     deployed cv_only accept semantics).
   - **SFace correct** = `dl_only.matched` (genuine rule).
   - Per modification and overall, tally `w/x/y/z`, then:
     `recovery = y/(y+z)` (guard y+z=0), `both_fail = z/N`,
     `mcnemar_test(x, y)`.
   - **Gate competence:** label = "LBPH wrong" (¬cv_only.matched); scores =
     `lbph_distance` (AUC↑ = distance predicts failure) and `−lbph_margin`;
     plus the deployed binary gate: TPR/FPR/precision of `escalated` against the
     label, and the escalation-reason mix on the wrong-LBPH probes.
     Computed overall, on modified probes only, and per modification (AUC only where
     both classes non-empty).
3. Requires `cv_only,dl_only` in `--modes` (else the battery block is skipped with a
   note); cascade adds the gate stats. Emit into the JSON payload as
   `complementarity_battery` and into the MD as two tables (per-mod recovery/McNemar;
   gate AUC + confusion). Optional `--battery-csv` writes the per-probe pairing rows
   for audit.
4. Battery pass conditions (pre-registered in WHY_AND_HOW §"Pass conditions"):
   recovery high & concentrated on LBPH-collapse mods; gate AUC > 0.8; McNemar
   p < 0.05 with y ≫ x; curve point on the frontier.

### 3.3 Gate operating-curve sweep (`scripts/sweep_gate_curve.py`, new)

- Sweep the gate's aggressiveness around the frozen point: grid over
  `margin_min ∈ {0, 0.025, 0.05, 0.1, 0.2}` × `τ_a shift ∈ {−8, −4, 0, +4, +8}`
  (τ_r shifted equally; quality probes untouched — they are calibrated, not swept).
- For each setting: cascade mode only, same 41-mod probes + clean set, record
  overall AR, mean latency, escalation %. LBPH-only and SFace-only corners from the
  same run (they are threshold-independent anchors).
- Output `reports/benchmark/gate_operating_curve.{json,md}` + a matplotlib PNG
  (AR vs mean latency, deployed point highlighted, corners labelled). The paper claim:
  the deployed setting sits on (or near) the efficient frontier.
- Cost: ~25 settings × 2,352 probes ≈ minutes on LS data; run a reduced 3×3 grid if
  time-constrained (still a curve, not 3 points).

### 3.4 Runs to (re)do and their exact commands

| Run | Command | Where |
|---|---|---|
| Joint sweep, paper protocol, lsdb1 | `python -m src.hybrid.independence_test --iterations 10 --output-dir reports/independence/hybrid/lsdb1_i10` | local |
| Joint sweep, lsdb2 light/medium | same with `--dataset-dir data/split_augmented41mods_lasalle_clean/<tier>/train --output-dir reports/independence/hybrid/lsdb2_<tier>_i10` | local |
| Hybrid AR + battery | `python -m src.benchmark.accuracy_ratio_hybrid` (defaults) — verify AR parity against the committed Jul 9 MD before trusting latency deltas | local |
| Evidence matrix, LS legs | `python -m src.benchmark.evidence_matrix --only ls_db1,ls_db2_41mods` | local |
| Gate curve | `python scripts/sweep_gate_curve.py` | local |
| LFW legs (matrix, 41-mod, any joint re-runs) | evidence matrix `--only lfw1,lfw2_41mods` | **D: machine — open** |

### 3.5 Paper-edit design (P1)

Section-by-section edit list in §1.7. Two structural rules from RECOMMENDATION.md:
(1) §4.5 ordering = cascade-FP (vs DF floor) → obs/exp → Fisher → Q/φ captioned;
(2) never present a La Salle Q as evidence (saturated or degenerate); the LFW legs
carry axis C. New rule from the data: present Q > 0 as a *finding about hard pairs*,
and make the cascade's FAR undercut the deliverable. Keep §4.7's "complementarity is
a measurement, not a slogan" and cash it out with the battery numbers.

---

## 4. Implementation plan

**P0 — today, local, small data (all executed this session; see §5):**
1. `stats_utils`: `mcnemar_test`, `rank_auc` (+ degenerate guards). 
2. Battery in `accuracy_ratio_hybrid.py` (§3.2) — JSON `complementarity_battery` block + MD tables.
3. Re-run joint sweeps at 10 iterations: lsdb1, lsdb2_light, lsdb2_medium → new `*_i10` report dirs (the Jul 8 iterations=1 dirs stay untouched as the committed record).
4. Evidence matrix, La Salle legs only.
5. Gate operating-curve sweep + plot.
6. Append measured results to this document (§5).

**P1 — paper + docs update (writing, ~half a day, no new runs):**
7. §4.3 fill; §4.5 rewrite; §3.5 reword; §4.4 AUC+curve; §4.6 LS rows; §4.1/abstract/§5 de-stale; METRICS.md Table 3 refresh; delete stale [PENDING] tags. Extract the 331st-pair anchor from `lbph_lfw1` first.

**P2 — LFW-scale, deferred (open items, D: machine):**
8. Evidence-matrix LFW legs (lfw1 joint reuse or re-run; lfw2_41mods AR leg).
9. Decide: battery at LFW scale, or scope Paper 1's battery to LS + LFW security panel.
10. Streaming multi-iteration (or a stated limitation paragraph).

**P3 — optional hardening:**
11. Strict no-face-policy AR variant; rename `lbph_lsdb2` → tier-suffixed dir (spec Part C); phi reported beside Q everywhere Q appears.

---

## 5. Addendum — runs executed during this audit (2026-07-10)

*Filled in at the end of the session; every number below is from a local run on this
machine (latencies are this machine's, not the D: machine's).*

### 5.1 Cross-machine reproducibility — PASS

Re-running `python -m src.benchmark.accuracy_ratio_hybrid` here reproduced the Jul 9
D:-machine run **bit-exactly on every AR number** (all 12 per-modification ARs, all
four modes, overall 85.43 / 96.50 / 96.11 / 96.50, cascade-vs-parallel −0.40, 12/12
within tolerance). The seeded probe suite is machine-independent; only latency
differs (here: cv 5.62 / dl 22.44 / cascade 15.99 / parallel 22.77 ms — vs 5.49 /
23.87 / 16.81 / 23.70 on D:). The §4.3 table can be quoted from either run.

### 5.2 Complementarity battery — first real numbers (new instrument)

`accuracy_ratio_hybrid.py` now keeps the per-probe pairing (`complementarity_battery`
block in the JSON + MD; per-probe rows in `accuracy_ratio_hybrid_probes.csv`).
`src/stats_utils.py` gained `mcnemar_test` (exact binomial + continuity-corrected χ²)
and `rank_auc` (Mann-Whitney midrank AUC), self-tested against reference values.

On the 2,296 modified probes (identification table w/x/y/z = **1923 / 18 / 279 / 76**):

| Test | Pre-registered pass bar (WHY_AND_HOW) | Measured | Verdict |
|---|---|---|---|
| Recovery rate P(SFace ✓ \| LBPH ✗) | high, concentrated where LBPH collapses | **78.6% [74.0–82.5]** (279/355); **100% on 10 of 12 mods** (brightness_down 93%, motion_blur/rotation/zoom/blur 100%) | **PASS** (with the noise caveat below) |
| Both-fail ceiling | reported honestly | **3.31% [2.7–4.1]** overall — concentrated almost entirely in **gaussian_noise** (recovery 38%, both-fail 32.1%) | heavy noise breaks *both* engines; this is the fusion's honest ceiling and must be stated in §4.3 |
| McNemar (x=18 vs y=279) | p < 0.05 with y ≫ x | **p_exact ≈ 2.5×10⁻⁶¹** | **PASS** — the DL-stronger gap is real, not sampling noise |
| Gate AUC (LBPH distance → "LBPH wrong") | > 0.8 | **0.953** (margin signal 0.898; per-mod AUC 0.81–1.00) | **PASS** — routing is signal, not luck |
| Deployed gate confusion | — | TPR **0.975** (escalates 97.5% of wrong-LBPH probes), FPR 0.573, precision 0.237 | the gate buys accuracy by over-escalating right probes — the cost is latency, not accuracy, which is exactly the §4.4 trade |
| Clean probes | — | 56/0/0/0 — every engine perfect | matches Tables 3 |

Escalation reasons on the LBPH-wrong probes it rescues: quality = 298, low_margin = 37,
ambiguous_band = 11 — the quality probes carry the routing, as §4.3's design intended.

### 5.3 Gate operating curve — §4.4's missing sweep (new instrument)

`scripts/sweep_gate_curve.py` (new): each probe scored once per engine, 25 gate
settings (margin_min × τ-band shift) evaluated as pure routing arithmetic. Output:
`reports/benchmark/gate_operating_curve.{json,md,png}`.

- The deployed gate (τ_a 73.04, τ_r 76.85, m 0.05) delivers **AR 96.11% at 64%
  escalation** — 99.6% of the always-escalate ceiling (96.50%) at 2/3 of its
  escalation. Near-frontier: the "we chose deliberately" claim holds.
- `margin_min = 0.2` degenerates to always-escalate and reproduces dl_only exactly
  (96.50%) — a built-in sanity anchor.
- Shifting the τ band **down** is catastrophic (confident-rejects turn genuine probes
  into Unknown: clean acceptance falls to 76.8–85.7%). Shifting **up** mildly helps AR
  — but only because impostors are absent from the AR suite; the joint sweep's FAR is
  the counterweight that pins τ_a. Good faithful framing for §4.4.
- Caveat for the paper figure: the sweep times bare engine calls (SFace alone ≈ 9.5 ms
  here), while the AR benchmark times full `predict()` (dl_only 22.4 ms incl. LBPH +
  quality pass) — so the sweep's frontier is *conservative* toward the cascade. Use
  **escalation %** as the cost axis (machine-independent) or re-measure latency on the
  target machine.

### 5.4 Joint independence at the paper's 10-iteration protocol (La Salle legs)

New dirs: `reports/independence/hybrid/{lsdb1_i10, lsdb2_light_i10, lsdb2_medium_i10}`
(the Jul 8 iterations=1 dirs left untouched). Pooled over 7,560 comparisons each:

| Leg | LBPH FP % | SFace FP % | both | cascade FP % | Q | obs/exp | Fisher p_pos | esc % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lsdb1_i10 | 0.661 [0.50–0.87] | 1.799 [1.52–2.12] | 0.053 | 1.389 [1.15–1.68] | +0.66 | 4.45 | **0.012** | 85.4 |
| lsdb2_light_i10 | 1.667 | 1.561 | 0.185 | **1.217** | +0.80 | 7.12 | **7.4e-09** | 94.6 |
| lsdb2_medium_i10 | 15.741 | 1.984 | 0.688 | **1.270** | +0.49 | 2.20 | **6.9e-09** | 100.0 |

**This strengthens §0's critical finding.** The Jul 8 lsdb1 leg's "LBPH FP = 0 /
degenerate Fisher" was an artifact of the single seed-42 image pick: at 10 picks LBPH
admits 50/7,560 and the positive co-occurrence becomes significant on **every** La
Salle leg, consistent with LFW. There is no leg left where the errors avoid each
other. Meanwhile the cascade undercuts **both** engines on lsdb2_light and
lsdb2_medium (and on lfw1 from Jul 8), and undercuts SFace on lsdb1. §4.5's reference
sentence should quote these 1-iteration deterministic `light_front` numbers for La Salle, correcting the paper's 
incorrect "pooled over 10 seeded repeats" protocol.

### 5.5 Evidence matrix — La Salle legs

`python -m src.benchmark.evidence_matrix --only ls_db1,ls_db2_41mods` — first-ever run
of the harness. Both legs **OK**, `reports/benchmark/evidence_matrix.{json,md}` written,
thresholds anchored at sha256 `0b51dfdc61be25f7…` (never re-tuned on any leg):

| Leg | Result | Cross-check |
|---|---|---|
| ls_db1 (independence, 10 iters, 7,560 pairs) | LBPH FAR 0.661% / SFace 1.799% / cascade 1.389%; obs/exp 4.45, Q +0.66, Fisher p(co-occur) 0.012 | **identical** to §5.4's lsdb1_i10 (same seeds) — third reproduction check of the session |
| ls_db2_41mods (AR, 2,296 probes/mode) | pooled cv 84.54% / dl 95.91% / cascade 95.51% / parallel 95.91%; cascade −0.40 pts vs parallel, 12/12 in tolerance | identical to §5.1's run |
| lfw1, lfw2_41mods | **not run** (excluded via `--only`) | the open P2 legs; §4.6 quotes La Salle rows now, LFW rows marked open |

One wording note: the matrix MD's boilerplate "Reading the matrix" still describes
Q < 0 as the complementarity signal — the measured direction is Q > 0 everywhere, so
§4.6 should read the matrix as the *threshold-transfer* instrument (do the frozen-τ
FAR intervals hold across legs?) and defer the association story to §4.5's reframing.

### 5.6 Full-LFW LBPH threshold: the 10-ppm anchor is bracketed, not extracted

`reports/independence/lbph_lfw1/summary.json` carries a 26-point rank curve
(power-of-2 ladder + the 10,000-ppm spec rank). It **brackets** the 331st-pair / 10-ppm
anchor — raw θ ∈ (17.0228 @ rank 256 / 7.7 ppm, 17.1982 @ rank 512 / 15.5 ppm) — but
does not contain rank 331 itself, and no comparisons CSV was stored at LFW scale.
Extracting the exact anchor is an LFW-scale re-rank (P2). Two boundary-pair notes for
the annotation-error check: rank 8 is the known Caldecott/Gilligan pair; the new
**global minimum pair is Carlos_Beltran vs Raul_Ibanez** (raw 10.12, ranks 1–2) — two
MLB players, eyeball before trusting the extreme tail.

### 5.7 Repo-hygiene finding

`.gitignore` lines 122–123 ignore **all** of `reports/benchmark/*.md` and
`reports/benchmark/**/*.json` — so the Jul 9 hybrid AR report, today's battery/curve
outputs, and the evidence matrix are **not in version control** (the independence
reports are). The paper's §4.3/§4.4/§4.6 source tables currently live only on
whichever machine ran them. Recommend committing at least the canonical MDs
(`accuracy_ratio_hybrid.md`, `gate_operating_curve.{md,png}`, `evidence_matrix.md`)
or carving exceptions in `.gitignore`.
