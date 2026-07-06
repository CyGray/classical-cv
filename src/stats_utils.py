"""Pure-stdlib statistics for the independence / complementarity analysis.

Everything here is exact or closed-form and needs only ``math``, so the same
functions run inside every benchmark script (and on machines without scipy).

Three tools, matched to three claims the paper makes:

* :func:`wilson_interval` - a 95% confidence interval on any binomial rate
  (FAR, AR, escalation). La Salle DB1 has only 756 impostor comparisons per
  sweep, so every rate MUST be reported with its interval or it overstates
  precision.
* :func:`fisher_exact` - exact test of association on the 2x2 error table
  (engine-A FP x engine-B FP). ``p_positive`` small = the engines fail
  together (errors are positively associated - NOT complementary);
  ``p_negative`` small = the engines fail on different pairs.
* :func:`error_diversity` - the standard multiple-classifier-system diversity
  measures (Kuncheva & Whitaker, Machine Learning 51, 2003): Yule's
  Q-statistic, the phi correlation, the disagreement measure, and the
  double-fault measure. Q < 0 means complementary errors; the double-fault
  rate is the floor no fusion of the two engines can beat.

2x2 convention used throughout (counts over the same N comparisons):

                     B errs   B correct
        A errs         a          b
        A correct      c          d
"""

from __future__ import annotations

import math

Z_95 = 1.959963984540054  # two-sided 95% normal quantile


# --------------------------------------------------------------------------- #
# Wilson score interval
# --------------------------------------------------------------------------- #
def wilson_interval(successes: int, trials: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score CI for a binomial proportion, as (low, high) fractions.

    Behaves sensibly at the extremes (0 or n successes) where the naive
    normal interval collapses to a point - exactly the regime small-N FAR
    estimates live in.
    """
    if trials <= 0:
        return (0.0, 1.0)
    n = float(trials)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def wilson_interval_percent(successes: int, trials: int, z: float = Z_95) -> dict:
    """Rate + Wilson CI, all in percent - the JSON-report-friendly form."""
    lo, hi = wilson_interval(successes, trials, z)
    return {
        "count": int(successes),
        "trials": int(trials),
        "percent": (100.0 * successes / trials) if trials else 0.0,
        "ci95_low_percent": 100.0 * lo,
        "ci95_high_percent": 100.0 * hi,
    }


# --------------------------------------------------------------------------- #
# Fisher's exact test (2x2)
# --------------------------------------------------------------------------- #
def _log_binom(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _hypergeom_logpmf(x: int, r1: int, r2: int, c1: int) -> float:
    """log P(X = x) for X ~ Hypergeom(row1=r1, row2=r2, col1=c1)."""
    return _log_binom(r1, x) + _log_binom(r2, c1 - x) - _log_binom(r1 + r2, c1)


def fisher_exact(a: int, b: int, c: int, d: int) -> dict:
    """Exact hypergeometric test on the 2x2 table [[a, b], [c, d]].

    Returns one-sided and two-sided p-values:

    * ``p_positive`` - P(X >= a): probability of seeing at least this many
      joint errors if the two engines' errors were independent. Small value
      = errors co-occur (positive association).
    * ``p_negative`` - P(X <= a): small value = errors avoid each other
      (negative association = complementary).
    * ``p_two_sided`` - sum of all outcomes no more likely than the observed
      table (the standard two-sided convention).

    Exact for any margins; cost is O(min(row1, col1)) pmf evaluations, so it
    is fast even on the 33M-comparison LFW table because FP counts are small.
    """
    if min(a, b, c, d) < 0:
        raise ValueError("2x2 cell counts must be non-negative")
    r1, r2 = a + b, c + d
    c1 = a + c
    n = r1 + r2
    if n == 0 or r1 == 0 or r2 == 0 or c1 == 0 or c1 == n:
        # A degenerate margin carries no information about association.
        return {"p_positive": 1.0, "p_negative": 1.0, "p_two_sided": 1.0,
                "degenerate": True}

    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    logpmf = {x: _hypergeom_logpmf(x, r1, r2, c1) for x in range(lo, hi + 1)}
    p_obs = math.exp(logpmf[a])

    p_pos = sum(math.exp(v) for x, v in logpmf.items() if x >= a)
    p_neg = sum(math.exp(v) for x, v in logpmf.items() if x <= a)
    # Two-sided: all tables with pmf <= observed pmf (with a tolerance for
    # floating-point ties, matching the scipy convention).
    p_two = sum(math.exp(v) for v in logpmf.values()
                if math.exp(v) <= p_obs * (1.0 + 1e-7))
    return {
        "p_positive": min(1.0, p_pos),
        "p_negative": min(1.0, p_neg),
        "p_two_sided": min(1.0, p_two),
        "degenerate": False,
    }


# --------------------------------------------------------------------------- #
# Classifier-diversity measures (Kuncheva & Whitaker 2003)
# --------------------------------------------------------------------------- #
def error_diversity(a: int, b: int, c: int, d: int) -> dict:
    """Pairwise diversity of two error indicators over the same N cases.

    ``a`` = both err, ``b`` = only A errs, ``c`` = only B errs, ``d`` = neither.

    * ``q_statistic`` (Yule's Q, in [-1, 1]): 0 = independent errors,
      > 0 = engines fail together, < 0 = complementary failures.
    * ``phi`` - the correlation coefficient of the two indicators.
    * ``disagreement`` = (b + c) / N: how often exactly one engine errs -
      the raw material a fusion rule can exploit.
    * ``double_fault`` = a / N: both wrong at once - the error floor of ANY
      fusion of these two engines.
    * ``observed_over_expected`` - a / (N * p_A * p_B), the intuitive ratio
      already reported by the sweeps (1.0 = independent).
    """
    n = a + b + c + d
    if n == 0:
        raise ValueError("empty 2x2 table")
    ad, bc = a * d, b * c
    q = (ad - bc) / (ad + bc) if (ad + bc) > 0 else None
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d
    phi_den = math.sqrt(float(r1) * r2 * c1 * c2)
    phi = (ad - bc) / phi_den if phi_den > 0 else None
    p_a = r1 / n
    p_b = c1 / n
    expected_both = n * p_a * p_b
    return {
        "table": {"both": a, "only_a": b, "only_b": c, "neither": d, "n": n},
        "q_statistic": q,
        "phi": phi,
        "disagreement": (b + c) / n,
        "double_fault": a / n,
        "expected_both_if_independent": expected_both,
        "observed_over_expected": (a / expected_both) if expected_both > 0 else None,
        "fisher": fisher_exact(a, b, c, d),
    }
