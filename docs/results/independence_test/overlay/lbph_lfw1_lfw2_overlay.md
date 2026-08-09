# LBPH Independence Test: LFW1 vs LFW2 (light) Distance Curve

Figure: `lbph_lfw1_lfw2_overlay.png` (this folder). Standalone LBPH track
(`src/lbph/independence_test.py`, `reports/independence/lbph_latest/`) — both
series are the **approximate** density (dashed line): reconstructed via PCHIP
interpolation of each report's `distance_statistics.percentiles`, because the
raw per-pair CSVs for the LFW legs are not persisted to disk (`outputs/` is
gitignored). Same normalized 0–100 scale used everywhere in this track, so
the two series and the La Salle DB1 anchor below are directly comparable.

## Key numbers

| Dataset | n (unique pairs) | min | 1st-pct (~1% FAR pt.) | median | mean | max |
|---|---:|---:|---:|---:|---:|---:|
| **LS-DB1 (anchor)** | 756 | 69.70 | 71.75 | 87.06 | 86.29 | 100.0 |
| LFW1 (clean) | 16,522,626 | 29.47 | 55.86 | 66.13 | 66.28 | 100.0 |
| LFW2 (light, 41-mod) | 16,522,626 | 26.38 | 51.51 | 62.96 | 63.13 | 100.0 |

"1st-pct" = the normalized distance below which the bottom 1% of impostor
pairs fall — i.e. where a same-track, per-dataset 1%-FAR threshold would sit
if one were derived locally (LS-DB1's own rank-8/756 error-pair threshold is
70.40, essentially equal to its 1st percentile at this sample size).

## Discussion

The whole curve shifts left as the test set changes, and it shifts in two
separable steps:

1. **LS-DB1 → LFW1 (same track, unconstrained faces): −15.9 points at the
   1%-FAR point** (71.75 → 55.86), and the median drops by almost 21 points
   (87.06 → 66.13). LS-DB1's impostor pairs are 28 classmates shot under
   matched studio conditions; LFW1 is 5,749 public figures under uncontrolled
   pose/lighting/expression. LBPH's chi-square histogram distance is
   evidently far more sensitive to *photographic* variation than to
   *identity* variation — an unconstrained population looks "closer together"
   to LBPH than a controlled one does, independent of whether the people
   actually resemble each other.
2. **LFW1 → LFW2 (light) (same identities, 41-mod synthetic degradation
   added): a further −4.35 points** (55.86 → 51.51) at the 1%-FAR mark, and
   median/mean drop ~3 points each. Much smaller than step 1, but monotonic
   in the expected direction — the light-severity corruption suite compresses
   the distribution slightly further on top of the unconstrained-photography
   effect already paid in step 1.

Both LFW curves also show a visibly heavier left tail than LS-DB1 in the
figure (min distance 29.47/26.38 vs. 69.70) — a small number of LFW impostor
pairs sit almost as close as genuine matches would, something the 756-pair
anchor sample never has enough range to exhibit at all.

## Conclusion

1. LBPH's raw impostor-distance distribution is **not stable across
   datasets** — it compresses substantially under both unconstrained
   photography (dominant effect) and synthetic degradation (secondary,
   additive effect).
2. The shift is monotonic and directionally consistent with what the
   hybrid's SFace-side FAR curve independently shows for the same three
   datasets (see `sface_lsdb1_lfw1_lfw2_overlay.png` / companion write-up) —
   both engines see LFW as a "closer-together" impostor population than
   LS-DB1, from two entirely different feature representations.
3. Per [[frozen-threshold-anchor]], none of this is grounds to re-tune — it
   is exactly the kind of transfer-degradation finding that protocol exists
   to surface and report, not paper over.

## Implications

- **A threshold picked at face value from LFW1's own distribution would be
  far looser than LS-DB1's**, which is precisely why this repo never derives
  thresholds per-dataset — a LFW-tuned cutoff would fail to reproduce
  LS-DB1's guarantees, and an LS-DB1-tuned cutoff, applied unchanged, is
  *conservative* everywhere else instead of loose. This curve is the
  concrete evidence for why the anchor-and-freeze design is the safer
  direction of transfer.
- **This is one reason the hybrid gate escalates almost every probe on the
  LFW legs** (measured 99.4–99.97% escalation vs. 92.9% on LS-DB1, per the
  hybrid summaries) — LBPH's own distance signal is systematically less
  trustworthy on unconstrained data, so the gate correctly leans on SFace
  there far more than it needs to on the anchor.
- Because the effect is already visible LFW1→LFW1(clean), **any future
  dataset with LFW-like unconstrained photography should be assumed to need
  the same escalation-heavy regime**, not treated as an LBPH-track anomaly
  specific to the 41-mod suite.
