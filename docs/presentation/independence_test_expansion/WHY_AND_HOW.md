# Independence test: adding Wilson CI, Fisher's exact test, Yule's Q

Figures used below live in this same folder: `fig1_wilson_vs_wald.png`,
`fig2_contingency_table.png`, `fig3_yules_q_scale.png`,
`fig4_same_vs_different_mistakes.png`, `fig6_luck_range.png`.

The worked example near the end uses made-up numbers (not a real run), computed
through the project's actual `src/stats_utils.py` so the arithmetic is correct.

---

## The problem

- Right now we measure LBPH's error rate and SFace's error rate separately.
- We never check whether the two get fooled by the **same** impostor pairs or **different** ones.
- Same pairs → combining them barely helps. Different pairs → combining them helps a lot.
- The hybrid cascade is built on the second assumption. We've never actually checked it.

## The data we need — none of it is new

We already run every face against every other face (the impostor sweep). For each
pair we already compute two yes/no facts: did LBPH wrongly accept it, did SFace
wrongly accept it. Tally those into one table:

| | SFace wrong | SFace right |
|---|---:|---:|
| **LBPH wrong** | a | b |
| **LBPH right** | c | d |

`a` = both wrong, `b` = only LBPH wrong, `c` = only SFace wrong, `d` = both right.
Everything below is computed from `a, b, c, d`. See `fig2_contingency_table.png`.

---

## 1. Wilson score interval

**Why:** A rate by itself can be misleading. "0 errors in 756 tries" is not the same
claim as "0% chance of error." Our target error rates are rare (≤100 ppm) and one of
our sample sizes is small (756 comparisons) — exactly where the normal/textbook
interval formula breaks. It can literally report "0%, guaranteed forever" after seeing
zero errors, which is false. Wilson's version stays correct in that regime.

**Formula:**
```
p̂ = successes / trials,  z = 1.96 (95%)
center = (p̂ + z²/2n) / (1 + z²/n)
half   = [z / (1 + z²/n)] · sqrt( p̂(1-p̂)/n + z²/4n² )
CI = center ± half
```

**How we use it:** attach it to every rate we report — TAR, FAR, FRR, each engine's
FP rate, the cascade's FP rate. See `fig1_wilson_vs_wald.png`.

---

## 2. Fisher's exact test

**Stupidly simple version:** this test answers exactly **one** question — *"is this a
coincidence, or not?"* Nothing about good or bad yet, just real-or-luck.

Picture LBPH and SFace as two people flipping coins, completely unrelated to each
other. Sometimes both land heads on the same flip, purely by accident. If their
mistakes really were that unrelated, how many "both wrong on the same face" would you
expect to see — and how much does that number naturally bounce around, just from
randomness? Fisher's test works out that *entire range of what pure chance can
produce*, then checks whether our real, actual count lands comfortably inside that
range, or blows way past it.

**Figure:** `fig6_luck_range.png` — the blue bars are every outcome pure chance
could realistically produce (almost always somewhere between 0 and 6, out of 100).
Our real count was 14. It's not even on the chart. That's what "definitely not a
coincidence" looks like.

**On purpose, this test does not say whether that's good news or bad news** — only
that it's real. *Which direction* it points is a separate question, answered next by
Yule's Q.

**Exact math** (only needed for the write-up, not for understanding it):
```
P(X=x) = C(a+b, x) · C(c+d, a+c-x) / C(n, a+c)     (hypergeometric)
p_positive  = P(X ≥ a)   → small = errors co-occur
p_negative  = P(X ≤ a)   → small = errors avoid each other
p_two_sided = sum of all tables no more likely than the observed one
```

**How we use it:** run it on the `a,b,c,d` table. A tiny p-value means the overlap
(or lack of it) is real, not a coincidence — full stop, no direction implied yet.

---

## 3. Yule's Q and the double-fault rate

**Stupidly simple version:** look at the picture. Left side (different mistakes) = the
engines catch each other's errors — worth combining. Right side (same mistakes) = they
share a blind spot — combining barely helps. Yule's Q is one number, −1 to +1, saying
how close reality is to the left picture (−1) or the right picture (+1). Zero = neither.

**Figure:** `fig4_same_vs_different_mistakes.png` — this is the whole idea in one
picture: same accuracy for each engine in both panels, only *where* the mistakes land
differs, and that alone doubles how many impostors get caught (28 vs 14 out of 100).
`fig3_yules_q_scale.png` shows where a real Q value would sit on the −1..+1 scale once
we have one.

**Exact math** (only needed for the write-up, not for understanding it):
```
Q = (ad - bc) / (ad + bc)          range [-1, +1]
double_fault = a / n               (the floor: neither engine right, no fusion fixes it)
```

Not something we invented — the standard metric for this exact question in
classifier-ensemble research (Kuncheva & Whitaker, 2003), already reference [15] in
our own paper.

---

## Worked example (made-up numbers)

**Small sample, 1,000 pairs** — LBPH wrong on 14, SFace wrong on 9, 0 in common:

| | SFace wrong | SFace right |
|---|---:|---:|
| **LBPH wrong** | a=0 | b=14 |
| **LBPH right** | c=9 | d=977 |

Q = −1.0 (looks perfect) — but Fisher's p = 1.0. Meaningless: chance alone predicts
fewer than 1 joint failure at this sample size, so seeing 0 proves nothing.

**Same underlying rates, 1,000,000 pairs:**

| | SFace wrong | SFace right |
|---|---:|---:|
| **LBPH wrong** | a=40 | b=13,960 |
| **LBPH right** | c=8,960 | d=977,040 |

Chance would predict 126 joint failures; we see 40. Q = −0.52, Fisher's p ≈ 3×10⁻¹⁹.
Now it's real.

**Point:** a Q number from our 756-comparison La Salle sweep can't be trusted on its
own — it's too small a sample. The full LFW sweep is the one that can actually answer
this question.

---

## How we'll do it

1. No new data collection — reuse the existing impostor sweep for LBPH + SFace.
2. Per pair, keep the two flags already computed: LBPH false-accept? SFace false-accept?
3. Tally into the `a,b,c,d` table.
4. Compute: Wilson CI on each rate, Fisher's exact test on the table, Yule's Q and double-fault rate.
5. Run on La Salle first (fast check), then the full LFW sweep (the one with enough data to trust).
6. Put the resulting table + these two figures into paper §4.5.

The math is already implemented in `src/stats_utils.py` (~130 lines, no new
dependencies). What's left is running the full-scale version and writing it up.
