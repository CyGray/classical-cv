# SFace Independence Test: LS-DB1 vs LFW1 / LFW2 FAR Curve

Figure: `sface_lsdb1_lfw1_lfw2_overlay.png` (this folder). Hybrid track
(`src/hybrid/independence_test.py`, `reports/independence/hybrid/`) — all
four series are the reported rank-based FAR curve (marked line, log-y),
because raw per-pair CSVs aren't persisted (`outputs/` is gitignored); no
raw sample survives for exact-FAR reconstruction on any of these four legs,
so this is the same approximation tier as the SFace leg of the existing
4-dataset `sface_cross_dataset_curve.png` preset, just narrowed to the three
datasets asked for (LS-DB1, LFW1, LFW2) plus LFW2's medium-severity leg for
completeness.

## Key numbers (from each dataset's own `summary.json`, gate = frozen LS-DB1 thresholds)

| Dataset | n | LBPH-alone FP% | SFace-alone FP% | **Cascade FP%** | Escalation% | Yule's Q | obs/exp joint FP | Fisher p (positive) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **LS-DB1 (anchor)** | 756 | 0.000 | 2.646 [1.72–4.05] | **1.190** [0.63–2.25] | 92.86 | n/a (degenerate, a=0) | n/a | 1.0 |
| LFW1 (clean) | 33,045,252 | 0.087 | 0.019 | **0.0098** [0.0094–0.0101] | 99.97 | +0.857 | 12.85× | 8.8×10⁻⁵² |
| LFW2 (light) | 33,045,252 | 0.114 | 0.210 | **0.0099** | 99.44 | +0.339 | 2.02× | 9.5×10⁻¹⁶ |
| LFW2 (medium) | 33,045,252 | 0.409 | 0.249 | **0.0101** | 99.41 | +0.125 | 1.28× | 3.0×10⁻⁷ |

FP% = false-accept rate under the deployed gate rule (`d ≤ tau_accept` for
LBPH-alone; the DL genuine rule for SFace-alone); cascade FP% is the actual
deployed decision (gate + escalation) — the number that matters operationally.
Q and obs/exp are on the LBPH-FP × SFace-FP 2×2 table (Kuncheva–Whitaker);
positive Q/obs-over-expected-&gt;1 means the two engines fail on the *same*
pairs more than chance predicts, i.e. **less** complementary than hoped.

## Discussion

Two findings that run in opposite directions:

1. **The cascade FP rate is stable and low on every LFW leg (~0.01%,
   overlapping CIs) but an order of magnitude higher on the anchor itself**
   (1.19%, CI 0.63–2.25%). LS-DB1's 756-comparison sample is small enough
   that its CI is wide, but even its low end (0.63%) sits well above every
   LFW leg's high end (0.0101%). This is not the direction transfer
   degradation usually runs — LS-DB1 is 28 people from one shared cohort
   (classmates, matched lighting/pose/background), which is a genuinely
   *harder* impostor-discrimination task for both engines than LFW's larger,
   demographically diverse public-figure population. LFW isn't "easier
   because it's bigger" — the FAR% columns for LBPH-alone and SFace-alone
   individually are already lower-order-of-magnitude on LFW than the raw
   distance-compression story in the companion LBPH write-up would suggest
   in isolation; the gate's escalation behavior (below) is what keeps the
   *cascade* number pinned down despite that.
2. **Error independence (Yule's Q) gets worse, not better, at the scale
   that can actually measure it.** LS-DB1's Q is degenerate (0 joint
   failures out of 756 — [[frozen-threshold-anchor|too small a sample]] to
   say anything). The LFW1 full sweep (33M comparisons) is large enough to
   populate the joint-failure cell for real, and it shows LBPH and SFace
   false-accepting the *same* impostor pairs 12.85× more often than
   independent failures would predict (Fisher p ≈ 9×10⁻⁵²) — strong evidence
   the two engines share some blind spots, not that they're statistically
   independent. That correlation *weakens* as synthetic degradation is added
   (12.85× → 2.02× → 1.28× from LFW1 → light → medium) — degradation seems
   to decorrelate the two engines' remaining errors rather than compound
   them, plausibly because the two feature representations (LBPH texture
   histograms vs. SFace's learned embedding) break down for different
   reasons under blur/rotation.

## Conclusion

1. The deployed cascade holds its false-accept rate to ~0.01% uniformly
   across all three LFW legs, with LS-DB1 — the anchor the thresholds were
   *tuned on* — being the harder case at ~1.2%, not the easier one.
2. Yule's Q only becomes trustworthy at the LFW1 scale (matches the existing
   [[complementarity-thesis|methodology review]] in `docs/RECOMMENDATION.md`
   §4), and once trustworthy it says the errors are **positively**
   correlated on clean LFW — real, not accidental, overlap — which is a
   more honest and less flattering number than the degenerate LS-DB1 Q
   would suggest on its own.
3. Individual-engine FP rates (LBPH-alone, SFace-alone) swing by an order of
   magnitude or more across legs in ways that don't move together — SFace is
   worst on the anchor (2.65%) and best on clean LFW (0.019%); LBPH is the
   reverse trend (worst on LFW2-medium at 0.41%, best on the anchor at
   0.0%). No single engine is reliable alone across all four legs; the
   cascade's stability is what actually survives transfer.

## Implications

- **Anchoring the frozen thresholds on LS-DB1 — the hardest dataset in the
  suite, not the easiest — is a design choice that pays off empirically
  here.** Thresholds tuned to be safe on a harder, closed cohort turn out
  conservative (not loose) when applied unchanged to easier, more diverse
  populations. This is the strongest evidence yet in this repo for
  [[frozen-threshold-anchor]]'s core bet: "LS-DB1 is the deployment
  population," not the convenient one.
- **The positive Yule's Q on LFW1 is a genuine finding to carry into
  `docs/PAPER.md` §4.5/§3.5, not a reason to distrust the metric.** Per
  `docs/RECOMMENDATION.md` item 4, Q was always meant to be demoted to the
  LFW leg where the both-fail cell is populated — this run is that leg, and
  it reports real (if modest) shared error, which is a more defensible
  claim than the degenerate LS-DB1 "Q = −1" artifact would have been.
- **The engines' individual weak points don't overlap with the datasets they
  cover for each other** (SFace weakest on the anchor where LBPH is
  strongest; LBPH weakest under heavy synthetic degradation where SFace
  holds up better) — this is the practical argument for keeping the cascade
  rather than either engine alone, independent of what the Q statistic says
  about pairwise error overlap.
- Because obs/exp correlation *drops* under degradation (12.85× → 1.28×),
  **robustness/degradation testing (§4.3) and complementarity testing
  (§4.5) are measuring different things and shouldn't be summarized with one
  number** — a system that looks less complementary on clean data can still
  look more complementary once inputs degrade.
