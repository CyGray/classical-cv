"""The escalation gate: decide when LBPH's answer is trustworthy.

Rule (``docs/archive/ARCHITECTURE_PLAN.md`` §4.2) - escalate the frame to SFace if **any**
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

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Mapping

from src.hybrid.quality import QualityReport

# The threshold file is tied to the descriptor that produced its raw LBPH
# distance scale.  Keep this fallback explicit: these numbers are for the
# deployed r1/n8/8x8 descriptor only, not for a candidate descriptor.
_FALLBACK_LBPH_DESCRIPTOR = {
    "id": "r1_n8_g8x8",
    "params": {"radius": 1, "neighbors": 8, "grid_x": 8, "grid_y": 8},
}

# Public alias used by calibration/tests and by callers that want to stamp or
# validate a threshold file without importing the recognizer adapter.
DEPLOYED_LBPH_DESCRIPTOR = _FALLBACK_LBPH_DESCRIPTOR

# Last-resort fallback if thresholds.json is missing/unreadable at import time.
# The frozen values themselves live in thresholds.json (the file the evidence
# matrix SHA-256-hashes); these literals must never be the only copy.
# tau_accept and tau_reject are FROZEN — see docs/READ THIS/FROZEN_THRESHOLDS.md before touching.
# 2026-08-02: tau_accept moved 67.0084 -> 67.03325520645528 (unified with the
# standalone LBPH sweep; see thresholds.json's provenance.gate.tau_accept and
# docs/audits/STATE-08-02.md). tau_reject moved 88.4927 -> 140.13 (CANONIZED,
# advisor sign-off, an FRR-budget pick — NOT an impostor-FAR-derived value like
# tau_accept; see docs/independence/TAU_REJECT_METHOD.md and thresholds.json's
# provenance.gate.tau_reject).
_FALLBACK_GATE_DEFAULTS = {"tau_accept": 67.03325520645528, "tau_reject": 140.13, "margin_min": 0.05}
_THRESHOLDS_JSON = Path(__file__).with_name("thresholds.json")


class LBPHThresholdCompatibilityError(ValueError):
    """Raised when thresholds are missing or tied to another LBPH descriptor."""


def _central_descriptor(name: str):
    """Return a descriptor object from the central config module when present.

    The staged descriptor module is intentionally optional for this worker:
    the compatibility layer must remain importable while that module is being
    added by the core rollout worker.
    """
    try:
        module = import_module("src.classical_faces.lbph_config")
    except (ImportError, ModuleNotFoundError):
        return None
    return getattr(module, name, None)


def _descriptor_mapping(config) -> dict | None:
    """Normalize the planned central descriptor API to stable metadata.

    Supported forms are the planned ``DEPLOYED``/``SELECTED``/``ACTIVE``
    objects (``config_id`` + ``to_dict`` or ``params``), and plain mappings so
    callers can validate a config without importing the central module.
    """
    if config is None:
        return None

    if isinstance(config, str):
        if config == "r1_n8_g8x8":
            return dict(DEPLOYED_LBPH_DESCRIPTOR)
        return {"id": config, "params": {}}

    raw: dict = {}
    if isinstance(config, Mapping):
        raw = dict(config)
    else:
        for attr in ("descriptor_id", "config_id", "id", "name"):
            value = getattr(config, attr, None)
            if value is not None:
                raw[attr] = value
                break
        params = getattr(config, "params", None)
        if isinstance(params, Mapping):
            raw["params"] = dict(params)
        to_dict = getattr(config, "to_dict", None)
        if callable(to_dict):
            converted = to_dict()
            if isinstance(converted, Mapping):
                raw.update(dict(converted))
        for attr in ("radius", "neighbors", "grid", "grid_x", "grid_y"):
            value = getattr(config, attr, None)
            if value is not None:
                raw[attr] = value

    descriptor_id = (
        raw.get("id")
        or raw.get("descriptor_id")
        or raw.get("config_id")
        or raw.get("name")
    )
    params_raw = raw.get("params")
    params = dict(params_raw) if isinstance(params_raw, Mapping) else {}
    for key in ("radius", "neighbors", "grid", "grid_x", "grid_y"):
        if key in raw and key not in params:
            params[key] = raw[key]
    if "grid" in params:
        params.setdefault("grid_x", params["grid"])
        params.setdefault("grid_y", params["grid"])

    required = ("radius", "neighbors", "grid_x", "grid_y")
    if descriptor_id is None or any(key not in params for key in required):
        return None
    try:
        normalized_params = {key: int(params[key]) for key in required}
    except (TypeError, ValueError):
        return None
    return {"id": str(descriptor_id), "params": normalized_params}


def deployed_lbph_descriptor() -> dict:
    """Return the deployed descriptor metadata, using the central API if present."""
    configured = _central_descriptor("DEPLOYED")
    if configured is None:
        return dict(DEPLOYED_LBPH_DESCRIPTOR)
    normalized = _descriptor_mapping(configured)
    if normalized is None:
        raise RuntimeError(
            "Unsupported src.classical_faces.lbph_config.DEPLOYED API; expected "
            "config_id/id plus radius, neighbors, grid_x, and grid_y"
        )
    return normalized


def active_lbph_descriptor() -> dict:
    """Return ``ACTIVE`` from the central API, with a deployed fallback."""
    configured = _central_descriptor("ACTIVE")
    if configured is None:
        return deployed_lbph_descriptor()
    normalized = _descriptor_mapping(configured)
    if normalized is None:
        raise RuntimeError(
            "Unsupported src.classical_faces.lbph_config.ACTIVE API; expected "
            "config_id/id plus radius, neighbors, grid_x, and grid_y"
        )
    return normalized


def descriptor_metadata(config) -> dict:
    """Normalize a descriptor config or fail with an actionable error."""
    normalized = _descriptor_mapping(config)
    if normalized is None:
        raise ValueError(
            "LBPH descriptor config must provide id/config_id and "
            "radius, neighbors, grid_x, and grid_y parameters"
        )
    return normalized


def validate_thresholds_descriptor(
    thresholds: Mapping,
    expected_lbph_config=None,
) -> None:
    """Validate the threshold file's LBPH descriptor against an expected config.

    Validation is opt-in.  A file without metadata remains readable when no
    expected config is supplied for backward compatibility, but it fails
    clearly when a caller asks for compatibility validation.
    """
    if expected_lbph_config is None:
        return
    expected = descriptor_metadata(expected_lbph_config)
    actual = thresholds.get("lbph_descriptor") if isinstance(thresholds, Mapping) else None
    if actual is None:
        raise LBPHThresholdCompatibilityError(
            "Threshold file is missing lbph_descriptor metadata; cannot validate "
            f"compatibility with {expected['id']}"
        )
    try:
        actual_normalized = descriptor_metadata(actual)
    except ValueError as exc:
        raise LBPHThresholdCompatibilityError(
            "Threshold file has invalid lbph_descriptor metadata: " + str(exc)
        ) from exc
    if actual_normalized != expected:
        raise LBPHThresholdCompatibilityError(
            "LBPH descriptor mismatch: threshold file is compatible with "
            f"{actual_normalized['id']} {actual_normalized['params']}, expected "
            f"{expected['id']} {expected['params']}"
        )


def load_thresholds(
    path: str | Path = _THRESHOLDS_JSON,
    *,
    expected_lbph_config=None,
) -> dict:
    """Load thresholds, optionally requiring LBPH descriptor compatibility."""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    validate_thresholds_descriptor(data, expected_lbph_config)
    return data


@lru_cache(maxsize=1)
def _frozen_gate_defaults() -> dict:
    try:
        full_config = json.loads(_THRESHOLDS_JSON.read_text())
        data = full_config["gate"]
    except (OSError, KeyError, ValueError):
        return dict(_FALLBACK_GATE_DEFAULTS)
    # A candidate descriptor must never inherit the deployed fallback values.
    # Files from before descriptor metadata existed remain readable, but an
    # explicit incompatible stamp fails loudly.
    if "lbph_descriptor" in full_config:
        validate_thresholds_descriptor(full_config, DEPLOYED_LBPH_DESCRIPTOR)
    return {k: float(data[k]) for k in _FALLBACK_GATE_DEFAULTS}


@dataclass(frozen=True)
class GateThresholds:
    tau_accept: float = field(default_factory=lambda: _frozen_gate_defaults()["tau_accept"])
    tau_reject: float = field(default_factory=lambda: _frozen_gate_defaults()["tau_reject"])
    margin_min: float = field(default_factory=lambda: _frozen_gate_defaults()["margin_min"])

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
