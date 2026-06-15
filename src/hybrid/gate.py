"""The escalation gate: decide when LBPH's answer is trustworthy.

Rule (``docs/ARCHITECTURE_PLAN.md`` §4.2) - escalate the frame to SFace if **any**
of:

1. the LBPH score lands in the ambiguous band ``tau_accept < d_cv < tau_reject``,
2. the top-1/top-2 LBPH margin is thin (``margin < m_min``) - a near-tie between
   two enrolled identities, and
3. **any** quality flag fired (blur / low-light / noise / off-pose / small-face).

The margin is a **relative** gap ``(d2 - d1) / d1`` so it is scale-free: train
distances are inflated by memorisation, held-out distances are not, so an
absolute gap calibrated on one does not transfer to the other. A relative gap of
``margin_min = 0.05`` means "escalate when the runner-up identity is within 5% of
the best distance," i.e. a genuine ambiguity rather than a confident match.

Clause 3 is deliberately allowed to **override a confident LBPH score**: in the
hard regimes the classical audit measured, LBPH's confidence is exactly what
proved unreliable, so a clean-looking distance under a quality flag is not
trusted.

Non-escalated outcomes: ``d_cv <= tau_accept`` -> accept on LBPH;
``d_cv >= tau_reject`` -> reject (Unknown) on LBPH. LBPH raw is a **distance**
(lower is better), so ``tau_accept < tau_reject``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.hybrid.quality import QualityReport


@dataclass(frozen=True)
class GateThresholds:
    tau_accept: float = 73.04   # <= this LBPH distance => confident accept
    tau_reject: float = 76.85   # >= this LBPH distance => confident reject
    margin_min: float = 0.05    # min relative top1<->top2 gap (d2-d1)/d1 to trust LBPH

    @classmethod
    def from_dict(cls, data: dict | None) -> "GateThresholds":
        if not data:
            return cls()
        fields = cls.__dataclass_fields__
        return cls(**{k: float(v) for k, v in data.items() if k in fields})

    def to_dict(self) -> dict:
        return {
            "tau_accept": self.tau_accept,
            "tau_reject": self.tau_reject,
            "margin_min": self.margin_min,
        }


@dataclass
class GateDecision:
    escalate: bool
    reason: str          # confident_accept | confident_reject | ambiguous_band |
                         # low_margin | quality:<flag>[,<flag>]
    lbph_accept: bool    # LBPH-local accept (only meaningful when not escalated)


def decide_escalation(
    *,
    lbph_distance: float,
    lbph_margin: float,
    quality: QualityReport,
    thresholds: GateThresholds,
) -> GateDecision:
    # Clause 3 first: a quality flag overrides even a confident LBPH score.
    if quality.any_flag:
        return GateDecision(
            escalate=True,
            reason="quality:" + ",".join(quality.active_flags),
            lbph_accept=False,
        )

    # Clause 1: ambiguous score band.
    if thresholds.tau_accept < lbph_distance < thresholds.tau_reject:
        return GateDecision(escalate=True, reason="ambiguous_band", lbph_accept=False)

    # Clause 2: thin top-1/top-2 separation, even outside the band.
    if lbph_margin < thresholds.margin_min:
        return GateDecision(escalate=True, reason="low_margin", lbph_accept=False)

    # Confident LBPH outcome - no accelerator needed for this frame.
    if lbph_distance <= thresholds.tau_accept:
        return GateDecision(escalate=False, reason="confident_accept", lbph_accept=True)
    return GateDecision(escalate=False, reason="confident_reject", lbph_accept=False)
