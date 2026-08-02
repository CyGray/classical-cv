// Hand-authored, like recommendation.md and the paper itself — not generated from the
// raw per-run JSON in content/results/**/summary.json. Every number here is transcribed
// from content/docs/paper.md §4 (the reviewed, committed numbers), cross-checked against
// recommendation.md and presentation/independence-expansion.md for the plain-language
// framing. If the paper's numbers change, this file needs a matching edit — it is not
// derived automatically, on purpose, the same way study_status.yml's leg notes are
// hand-stated rather than inferred from the filesystem.

export type ResultVerdict = "confirms" | "refutes" | "mixed" | "caveat" | "methodology";

export interface ResultStat {
  label: string;
  value: string;
  ci?: string;
  note?: string;
}

export interface ResultTest {
  id: string;
  name: string;
  question: string;
  method?: string;
  stats: ResultStat[];
  comparison?: string;
  verdict: ResultVerdict;
  conclusion: string;
  source: string;
}

export interface ResultGroup {
  id: string;
  title: string;
  intro?: string;
  tests: ResultTest[];
}

export const resultGroups: ResultGroup[] = [
  {
    id: "engine-selection",
    title: "Engine selection & verification",
    intro:
      "Which classical recognizer is actually deployable, decided by an impostor-distance threshold rule fixed before reading results, not by closed-set accuracy alone.",
    tests: [
      {
        id: "threshold-rule",
        name: "k-th error-pair threshold rule",
        question:
          "Where should each engine's accept/reject line sit, and does that line hold up under repeated sampling?",
        method:
          "Threshold set at the k-th closest impostor pair for a target FAR, on the raw impostor-distance distribution, rather than fit to a validation split.",
        stats: [
          { label: "LBPH", value: "85.88", note: "normalized threshold, LS-DB1" },
          { label: "Eigenfaces", value: "71.00", note: "normalized threshold, LS-DB1" },
          { label: "Fisherfaces", value: "66.38", note: "normalized threshold, LS-DB1" },
        ],
        comparison:
          "LBPH keeps impostors farthest apart of the three; per-run stability across 10 seeded repeats (68.03 ± 1.83 normalized for LBPH) sits materially below the pooled figure — a known renormalization artifact that leaves the raw-distance and realized-FAR operating points unaffected.",
        verdict: "methodology",
        conclusion:
          "Tying the operating point to an exact error count (not a validation split) is what let the study later admit, honestly, that La Salle's 756 comparisons only resolve FAR to about 1,300 ppm — deferring the 100 ppm claim to LFW rather than overstating what the smaller set could prove.",
        source: "Paper §4.1",
      },
      {
        id: "tar-far-verification",
        name: "TAR/FAR verification (Table 2)",
        question:
          "Which classical recognizer should carry the fast path — decided by rank-1 accuracy, or by TAR at a fixed FAR budget?",
        method:
          "Rank-1 on a held-out split, and TAR at 100 ppm FAR against 13,149 LFW impostors (95% Wilson CIs), n = 56 genuine probes.",
        stats: [
          { label: "LBPH", value: "98.21% TAR", ci: "[90.6, 99.7]", note: "Rank-1 100.00%, FAR 76 ppm, EER 0.07%" },
          { label: "Eigenfaces", value: "23.21% TAR", ci: "[14.1, 35.8]", note: "Rank-1 75.00%" },
          { label: "Fisherfaces", value: "10.71% TAR", ci: "[5.0, 21.5]", note: "Rank-1 66.07%" },
        ],
        comparison:
          "Rank-1 already orders the three the same way (100/75/66), but the gap widens sharply once FAR is fixed: only LBPH clears the spec block (TAR 90–95%, FAR < 100 ppm, FRR 1–5%) — the subspace methods' genuine/impostor distributions overlap intrinsically.",
        verdict: "caveat",
        conclusion:
          "Closed-set rank-1 is the wrong metric to decide a gate's fast path with — a gate must also reject strangers, so TAR at fixed FAR is the metric that actually matters, and it disqualifies both subspace methods outright rather than just ranking them lower.",
        source: "Paper §4.2, Table 2",
      },
    ],
  },
  {
    id: "robustness",
    title: "Robustness: where CV breaks and DL recovers",
    intro:
      "The 41-modification suite (2,296 probes) tests whether SFace is strong exactly where LBPH is weak, and how much of LBPH's failure SFace actually rescues.",
    tests: [
      {
        id: "accuracy-ratio",
        name: "41-modification Accuracy Ratio",
        question:
          "Is the DL engine stronger exactly on the modifications that break the classical engine?",
        stats: [
          { label: "LBPH", value: "85.43%", note: "bimodal: strong on photometric edits, weak on noise/blur/dark" },
          { label: "SFace", value: "96.50%" },
          { label: "Cascade", value: "96.11%", note: "within 0.40 pts of the parallel run-both ceiling, at 70% of its cost" },
        ],
        comparison:
          "SFace wins beyond the 2-point tie band on 9 of 12 modifications (exactly the regimes LBPH's bimodal profile predicts: heavy Gaussian noise 47.8%, motion blur 68.5%, strong darkening 73.7%); the other 3 are photometric ties where LBPH is already near ceiling. Pooled Wilson: LBPH 84.5% [83.0, 86.0], SFace 95.9% [95.0, 96.6], cascade 95.5% [94.6, 96.3].",
        verdict: "confirms",
        conclusion:
          "The robustness split is measured, not assumed: SFace never loses to LBPH beyond the tie band on any modification, and the cascade tracks the better engine within 2 points on 12 of 12.",
        source: "Paper §4.3, Table 3",
      },
      {
        id: "recovery-rate",
        name: "Recovery rate — P(SFace correct | LBPH wrong)",
        question:
          "Of the frames the fast engine misidentifies, what fraction does the accurate engine actually rescue?",
        method: "P(SFace correct | LBPH wrong), and its reverse, over the 41-mod probe set.",
        stats: [
          { label: "Recovery rate", value: "78.6%", ci: "[74.0, 82.5]", note: "279 of 355 LBPH misses, rescued by SFace" },
          { label: "Reverse rescue", value: "18 probes", note: "LBPH fixes only 18 of SFace's misses — strongly one-directional" },
          { label: "Both-wrong ceiling", value: "3.31%", ci: "[2.7, 4.1]", note: "the identification-axis floor no fusion of these two engines can beat" },
        ],
        comparison:
          "Recovery is 100% on 10 of 12 modifications and 93% under strong darkening; the one shared failure is heavy Gaussian noise (recovery only 38%, and 32.1% of noise probes beat both engines).",
        verdict: "confirms",
        conclusion:
          "This is the direct, asymmetric statement of \"DL covers where CV fails\" — not a slogan, a measured conditional probability, and it is why the hybrid's accuracy-axis complementarity claim holds.",
        source: "Paper §4.3",
      },
      {
        id: "mcnemar",
        name: "McNemar's exact test",
        question:
          "Is the recovery-rate asymmetry (SFace fixes LBPH's misses far more than the reverse) real, or could it be sampling noise?",
        method: "Paired significance test on the discordant identification outcomes (LBPH-right/SFace-wrong vs. LBPH-wrong/SFace-right).",
        stats: [{ label: "p-value", value: "< 10⁻⁶⁰" }],
        verdict: "confirms",
        conclusion:
          "The 279-vs-18 asymmetry behind the recovery rate is certified, not a coincidence of this particular probe set — SFace is the stronger engine on the hard frames, directly and significantly.",
        source: "Paper §4.3",
      },
    ],
  },
  {
    id: "cascade-gate",
    title: "The cascade & gate",
    intro:
      "Whether the fused system actually buys near-SFace accuracy at near-LBPH cost, and whether the escalation gate can be trusted to route on its own signal.",
    tests: [
      {
        id: "clean-vs-degraded",
        name: "Clean vs. degraded operating tables",
        question:
          "Does the cascade trade cost for accuracy sensibly — cheap when frames are easy, escalating when they're hard?",
        stats: [
          { label: "Clean split", value: "25% escalation", note: "10.03 ms, ≈99.7 fps — twice SFace-only's speed, same 100% TAR as either single engine" },
          { label: "Degraded split", value: "100% escalation", note: "rank-1 recovers 5.10% → 97.96%, matching SFace-only" },
        ],
        comparison:
          "Clean-split routing: 42/56 confident LBPH accepts, 7 quality-flag, 6 low-margin, 1 ambiguous-band — the gate keeps 75% of frames on the cheap path when it safely can.",
        verdict: "confirms",
        conclusion:
          "On clean frames accuracy is free and the real question is cost, which the cascade wins outright; on degraded frames every configuration converges because every frame is genuinely hard — both are the correct behavior, not a wash.",
        source: "Paper §4.4, Tables 4–5",
      },
      {
        id: "gate-auc",
        name: "Gate competence — ROC AUC",
        question:
          "Can LBPH's own confidence signal actually predict when LBPH is about to be wrong, or is escalation blind luck?",
        method: "ROC AUC of the LBPH distance (and relative margin) as a score for the binary label \"LBPH identified correctly,\" over the 2,296 modified probes.",
        stats: [
          { label: "Distance + margin", value: "0.953", note: "ROC AUC" },
          { label: "Relative margin alone", value: "0.898" },
          { label: "Per-modification range", value: "0.81 – 1.00" },
        ],
        comparison:
          "The deployed rule escalates 97.5% of the probes LBPH actually gets wrong; over-escalating probes LBPH would have gotten right anyway (57%) costs latency, not accuracy — the trade the cascade is designed to make.",
        verdict: "confirms",
        conclusion:
          "The cascade's routing is a measured property, not an inference from two operating points — the gate can genuinely tell when to escalate, so the whole design does not rest on luck.",
        source: "Paper §4.4",
      },
    ],
  },
  {
    id: "joint-independence",
    title: "Joint independence & security",
    intro:
      "Do the two engines false-accept the same impostor pairs? The security-axis question, tested on the full impostor sweep at the frozen thresholds.",
    tests: [
      {
        id: "wilson-interval",
        name: "Wilson score interval",
        question: "How much should a rate computed from a small or rare-event sample actually be trusted?",
        method:
          "center = (p̂ + z²/2n) / (1 + z²/n); half-width = [z / (1 + z²/n)]·√(p̂(1−p̂)/n + z²/4n²), z = 1.96 for 95%.",
        stats: [{ label: "Applied to", value: "every reported rate", note: "TAR, FAR, FRR, each engine's FP rate, the cascade's FP rate" }],
        verdict: "methodology",
        conclusion:
          "\"0 errors in 756 tries\" is not the same claim as \"0% chance of error\" — the textbook normal interval can report a false guarantee at exactly this sample size and error rarity; Wilson's version stays correct in that regime, which is why it wraps every rate in this study rather than only the headline ones.",
        source: "Paper §4.2–§4.5; presentation/independence-expansion.md",
      },
      {
        id: "fisher-exact",
        name: "Fisher's exact test",
        question: "Is the overlap (or lack of it) between the two engines' false accepts real, or could pure chance produce it?",
        method: "Hypergeometric test on the a/b/c/d joint-failure table; p_positive answers whether errors co-occur more than chance.",
        stats: [
          { label: "LS-DB1", value: "p = 0.012" },
          { label: "LS-DB2 light", value: "p = 7×10⁻⁹" },
          { label: "LS-DB2 medium", value: "p = 7×10⁻⁹" },
          { label: "LFW", value: "p = 9×10⁻⁵²" },
        ],
        comparison:
          "A single-repeat La Salle sweep had earlier shown LBPH at zero false accepts, which makes Fisher's test degenerate (an a=0 table cannot reject chance) — the 10-repeat pooled runs (50 of 7,560 admitted, 4 overlapping SFace) resolve that into the significant co-occurrence reported here.",
        verdict: "refutes",
        conclusion:
          "The overlap in false accepts is real on every leg with a populated joint cell, not sampling noise — it refutes the folklore assumption that unlike recognizers automatically make independent errors.",
        source: "Paper §4.5, Table 6",
      },
      {
        id: "yules-q",
        name: "Yule's Q / phi / double-fault",
        question: "Do the two engines fail on the same impostor pairs (coincident, Q > 0) or different ones (complementary, Q < 0)?",
        method: "Q = (ad − bc) / (ad + bc); double-fault = a / n (the FAR floor no fusion can beat).",
        stats: [
          { label: "LS-DB1", value: "Q = +0.66", note: "double-fault 0.053%" },
          { label: "LS-DB2 light", value: "Q = +0.80", note: "double-fault 0.185%" },
          { label: "LS-DB2 medium", value: "Q = +0.49", note: "double-fault 0.688%" },
          { label: "LFW", value: "Q = +0.86", note: "double-fault 2.1 ppm; phi = 0.005" },
        ],
        comparison:
          "This is the opposite sign from what a naive single-repeat run at low base rate had shown: at a=0 the formula collapses to exactly Q = −1 regardless of the real relationship, reading as \"maximally complementary\" when it is really just the low-count floor of the statistic — the pooled/large-sample numbers above are the ones to trust.",
        verdict: "refutes",
        conclusion:
          "Positive Q on every leg with a populated joint cell means the engines share hard impostor pairs (look-alikes, LFW's known annotation errors) rather than making independent mistakes — error independence, the textbook justification for fusing unlike recognizers, is refuted for this pair, and the paper reports that plainly instead of leaning on Q's earlier, degenerate −1.",
        source: "Paper §4.5, Table 6",
      },
      {
        id: "obs-over-exp",
        name: "Observed / expected joint-failure ratio",
        question: "How many times more often do the two engines fail on the same pair than independence would predict?",
        stats: [
          { label: "LS-DB1", value: "4.45×" },
          { label: "LS-DB2 light", value: "7.12×" },
          { label: "LS-DB2 medium", value: "2.20×" },
          { label: "LFW", value: "12.85×" },
        ],
        comparison:
          "The modified-LFW legs weaken this pattern without reversing it: joint excess falls from 12.9× on clean LFW to 2.0× (light degradation) and 1.3× (medium degradation), with Q dropping to +0.34 and +0.13 (p ≤ 10⁻¹⁵ and 3×10⁻⁷) while the cascade itself holds at 99 and 101 ppm.",
        verdict: "refutes",
        conclusion:
          "Degradation decorrelates the two engines rather than compounding their errors — a texture histogram and a learned embedding break down on different inputs, so this robustness-driven decorrelation and the §4.3 robustness result are not the same finding and should not be summarized with the same number.",
        source: "Paper §4.5",
      },
      {
        id: "cascade-fp-vs-engines",
        name: "Cascade false-accept rate vs. either single engine",
        question: "Despite correlated errors, does the fused cascade still out-perform both single engines on false accepts?",
        stats: [
          { label: "Cascade (LFW)", value: "98 ppm" },
          { label: "LBPH-only (LFW)", value: "867 ppm", note: "cascade is 8.8× lower" },
          { label: "SFace-only (LFW)", value: "190 ppm", note: "cascade is 1.9× lower" },
        ],
        comparison:
          "The same pattern holds on every La Salle leg where the comparison has power: 1.39% cascade vs. 1.80%/0.66% single-engine on LS-DB1; 1.22% vs. 1.67%/1.56% on the light split; 1.27% vs. 15.74%/1.98% on the medium split.",
        verdict: "confirms",
        conclusion:
          "The security case never rested on independent errors — it rests on the gate-plus-conjunction mechanism (a cascade false accept needs a confident LBPH accept, or an escalation SFace also accepts), which undercuts both single engines regardless of how correlated their individual mistakes are.",
        source: "Paper §4.5, Table 6",
      },
    ],
  },
  {
    id: "transfer",
    title: "Cross-database transfer",
    intro:
      "The thresholds are frozen on LS-DB1 (§4.1) and never re-tuned per dataset — every other leg here is a transfer check, not a re-calibration.",
    tests: [
      {
        id: "threshold-compression",
        name: "Impostor-distance compression across databases",
        question: "Does LBPH's impostor-distance threshold hold its value unchanged when applied to an unseen database?",
        stats: [
          { label: "LS-DB1 (anchor)", value: "71.75", note: "normalized 1% operating point" },
          { label: "Clean LFW", value: "55.86", note: "15.9-point compression from the anchor" },
          { label: "LFW + 41-mod", value: "51.51" },
        ],
        comparison:
          "The median compresses in step: 87.06 → 66.13 → 62.96 across the same three legs.",
        verdict: "mixed",
        conclusion:
          "The raw threshold value does not transfer intact across databases, but that is exactly why the study anchors on La Salle DB1, the hardest set, rather than treating any threshold as universal — a cutoff safe on the hard leg is conservative, not loose, everywhere easier.",
        source: "Paper §4.6",
      },
      {
        id: "cascade-far-transfer",
        name: "Cascade FAR: anchor vs. unseen databases",
        question: "Does the LS-DB1-anchored cascade stay safe (or get worse) when run unchanged on out-of-domain data?",
        stats: [
          { label: "LS-DB1 (anchor)", value: "1.39%", ci: "[1.15, 1.68]" },
          { label: "Every LFW leg", value: "≈0.01%", note: "98 ppm on the clean joint sweep" },
        ],
        comparison:
          "28 classmates shot under matched studio conditions are a harder impostor-discrimination task than LFW's larger, demographically diverse population — the anchor leg is the hard case, not the easy one. The gate also escalates 99.4–99.97% of LFW impostor pairs versus 92.9% on the anchor, leaning on SFace exactly where LBPH's own signal is least trustworthy.",
        verdict: "confirms",
        conclusion:
          "The frozen LS-DB1 thresholds hold up — cascade FAR is lower everywhere they transfer to, which is the direction a deployment transfer should fail in if it fails at all.",
        source: "Paper §4.6",
      },
    ],
  },
  {
    id: "synthesis",
    title: "Headline synthesis",
    intro: "The paper's own closing read of all of the above (§4.7, §5) — not a re-interpretation.",
    tests: [
      {
        id: "four-lessons",
        name: "Discussion: four lessons",
        question: "What does the full battery of tests, taken together, actually establish?",
        stats: [
          { label: "Recovery rate", value: "78.6%", note: "accuracy axis holds" },
          { label: "Gate AUC", value: "0.953", note: "the gate can route" },
          { label: "Cascade FP (LFW)", value: "98 ppm", note: "below both single engines" },
          { label: "Joint-error excess", value: "up to 12.9×", note: "security axis: independence refuted" },
        ],
        verdict: "mixed",
        conclusion:
          "Four lessons: (1) closed-set accuracy misleads — only LBPH survives a fixed-FAR test despite all three ranking sensibly on rank-1; (2) thresholds belong to impostor distributions, not validation splits, and should be frozen on the hardest available database; (3) complementarity is a measurement, not a slogan, and splits in two — it holds on the accuracy axis (78.6% recovery, gate AUC 0.953) and fails on the impostor axis (errors co-occur up to 12.9× expectation); (4) a cascade does not need independent errors, only a competent gate and a conjunction — the fused 98 ppm on LFW, below either engine alone, is the measured consequence of that mechanism, not of independence.",
        source: "Paper §4.7, §5",
      },
    ],
  },
];

export function allResultTests(): ResultTest[] {
  return resultGroups.flatMap((g) => g.tests);
}
