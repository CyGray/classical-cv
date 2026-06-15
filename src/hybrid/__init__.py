"""The hybrid gated cascade: LBPH fast path + SFace escalation behind a gate.

Public surface:

* :class:`~src.hybrid.recognizer.HybridRecognizer` - fused ``predict()`` with the
  four modes (``cascade`` / ``parallel`` / ``cv_only`` / ``dl_only``),
* :func:`~src.hybrid.recognizer.build_hybrid` - load LBPH + SFace + thresholds,
* :func:`~src.hybrid.recognizer.detect_sample` - shared YuNet front-end ->
  :class:`~src.hybrid.recognizer.FaceSample` for offline and live use.
"""

from src.hybrid.gate import GateDecision, GateThresholds, decide_escalation
from src.hybrid.quality import QualityReport, QualityThresholds, compute_quality
from src.hybrid.recognizer import (
    HYBRID_MODES,
    FaceSample,
    HybridDecision,
    HybridRecognizer,
    LBPHAdapter,
    LBPHMatch,
    SFaceAdapter,
    build_hybrid,
    detect_sample,
    load_thresholds,
    make_sample,
)

__all__ = [
    "HYBRID_MODES",
    "FaceSample",
    "HybridDecision",
    "HybridRecognizer",
    "LBPHAdapter",
    "LBPHMatch",
    "SFaceAdapter",
    "build_hybrid",
    "detect_sample",
    "load_thresholds",
    "make_sample",
    "GateDecision",
    "GateThresholds",
    "decide_escalation",
    "QualityReport",
    "QualityThresholds",
    "compute_quality",
]
