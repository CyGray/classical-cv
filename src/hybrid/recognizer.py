"""The ``Recognizer`` protocol, the LBPH/SFace adapters, and ``HybridRecognizer``.

This is the seam where the classical fast path (LBPH) and the DL escalation path
(SFace) meet behind one ``predict()``. The adapters are **additive**: the LBPH
adapter wraps the existing ``cv.face.LBPHFaceRecognizer`` + the clean-split model
and ``RecognizerSpec`` without touching ``pipeline.py``; the SFace adapter wraps
``src/sface``. Both expose the same shape - ``score(sample) -> Match`` and
``far_of(raw) -> FAR`` - so the gate compares them through calibrated FAR, never
through raw scores (LBPH raw is a distance, SFace raw is a cosine).

``HybridRecognizer.predict()`` runs the gated cascade (default) and reports which
engine decided, whether it escalated, and both raw scores for the honest reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import cv2 as cv
import numpy as np

from src.classical_faces.detection import Detection, FaceDetector, create_face_detector
from src.classical_faces.pipeline import SPECS
from src.hybrid.gate import GateDecision, GateThresholds, decide_escalation
from src.hybrid.quality import QualityReport, QualityThresholds, compute_quality
from src.lbph.preprocess import IMG_SIZE, normalize_face
from src.sface.recognizer import (
    SFACE_FEATURE_BYTES,
    SFaceFarModel,
    SFaceGallery,
    SFaceMatch,
    SFaceRecognizer,
    default_sface_model_path,
    detection_to_yunet_row,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_THRESHOLDS_PATH = str(PROJECT_ROOT / "src" / "hybrid" / "thresholds.json")
DEFAULT_LBPH_MODEL = str(PROJECT_ROOT / "models" / "lbph" / "lasalle_clean.yml")
DEFAULT_LBPH_LABELS = str(PROJECT_ROOT / "models" / "lbph" / "labels_lasalle_clean.json")
DEFAULT_SFACE_GALLERY = str(PROJECT_ROOT / "models" / "sface" / "gallery.npy")
DEFAULT_SFACE_LABELS = str(PROJECT_ROOT / "models" / "sface" / "labels.json")
DEFAULT_SFACE_IMPOSTORS = str(PROJECT_ROOT / "models" / "sface" / "impostors-lfw.npy")

HYBRID_MODES = ("cascade", "parallel", "cv_only", "dl_only")


# --------------------------------------------------------------------------- #
# The shared face sample (one detection, packaged for both engines)
# --------------------------------------------------------------------------- #
@dataclass
class FaceSample:
    """One detected face, prepared so each engine applies its own normalisation.

    Stage-0 (YuNet) emits box + 5 landmarks; downstream LBPH uses grayscale
    100x100 + Tan-Triggs while SFace uses ``alignCrop`` 112x112 RGB - the
    alignment contract (PLAN §10 / Phase 1.3) is kept explicit here so neither
    silently changes.
    """

    image_bgr: np.ndarray            # full frame / tile (SFace alignCrop input)
    yunet_row: np.ndarray | None     # (15,) face row for alignCrop, or None
    face_gray: np.ndarray            # raw gray face region (LBPH normalises this)
    quality_gray: np.ndarray         # 100x100 raw gray for the quality probes
    landmarks: np.ndarray | None     # (5,2) YuNet landmarks, or None
    face_px: int                     # min(box_w, box_h)
    score: float = 1.0


def _clamp_box(box, width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = box
    x = max(0, min(int(x), width - 1))
    y = max(0, min(int(y), height - 1))
    w = max(1, min(int(w), width - x))
    h = max(1, min(int(h), height - y))
    return x, y, w, h


def make_sample(
    detection: Detection,
    *,
    image_bgr: np.ndarray,
    image_gray: np.ndarray,
    assume_cropped: bool,
) -> FaceSample:
    """Package a detector ``Detection`` + frame into a ``FaceSample``.

    ``assume_cropped`` matches how the clean LBPH model was trained: a pre-cropped
    tile *is* the face, so LBPH normalises the whole tile rather than the YuNet
    sub-box. For live full frames the YuNet box ROI is used instead.
    """
    h, w = image_gray.shape[:2]
    box = _clamp_box(detection.box, w, h)
    bx, by, bw, bh = box
    if assume_cropped:
        face_gray = image_gray
    else:
        face_gray = image_gray[by : by + bh, bx : bx + bw]
        if face_gray.size == 0:
            face_gray = image_gray
    quality_gray = cv.resize(face_gray, (100, 100), interpolation=cv.INTER_AREA)
    yunet_row = detection_to_yunet_row(box, detection.landmarks, detection.score)
    return FaceSample(
        image_bgr=image_bgr,
        yunet_row=yunet_row,
        face_gray=face_gray,
        quality_gray=quality_gray,
        landmarks=detection.landmarks,
        face_px=int(min(bw, bh)),
        score=float(detection.score),
    )


def detect_sample(
    detector: FaceDetector,
    *,
    image_bgr: np.ndarray,
    image_gray: np.ndarray | None = None,
    assume_cropped: bool = False,
) -> FaceSample | None:
    """Run the (shared) detector and package the largest face, or ``None``."""
    if image_gray is None:
        image_gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
    detections = detector.detect(image_gray, image_bgr)
    if not detections:
        return None
    largest = max(detections, key=lambda d: d.area)
    return make_sample(
        largest, image_bgr=image_bgr, image_gray=image_gray, assume_cropped=assume_cropped
    )


# --------------------------------------------------------------------------- #
# Matches + the Recognizer protocol
# --------------------------------------------------------------------------- #
@dataclass
class LBPHMatch:
    name: str                                # nearest identity (pre-gate)
    distance: float                          # LBPH distance (lower better)
    margin: float                            # top1<->top2 distance gap
    far: float                               # calibrated FAR at this distance
    all_distances: dict[str, float] = field(default_factory=dict)


@runtime_checkable
class Recognizer(Protocol):
    name: str
    kind: str  # "lbph" | "sface"

    def score(self, sample: FaceSample): ...
    def far_of(self, raw: float) -> float: ...


# --------------------------------------------------------------------------- #
# LBPH adapter (additive wrapper over the existing recognizer + RecognizerSpec)
# --------------------------------------------------------------------------- #
class LBPHAdapter:
    name = "LBPH"
    kind = "lbph"

    def __init__(
        self,
        *,
        model_path: str = DEFAULT_LBPH_MODEL,
        labels_path: str = DEFAULT_LBPH_LABELS,
        equalization: str | None = None,
        far_anchors: list[list[float]] | None = None,
    ) -> None:
        self.spec = SPECS["lbph"]
        self.equalization = equalization or self.spec.default_equalization
        self.recognizer = cv.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        self.recognizer.read(model_path)
        with open(labels_path, "r", encoding="utf-8") as f:
            labels_raw = json.load(f)
        self.id_to_name = {int(idx): name for name, idx in labels_raw.items()}
        self.labels = sorted(labels_raw.keys())
        # FAR anchor points (distance, far) for far_of() interpolation. Defaults
        # are the calibrated LBPH edges vs LFW impostors (100 ppm / 1%).
        self._far_anchors = sorted(
            (far_anchors or [[0.0, 0.0], [73.04, 1e-4], [76.85, 1e-2], [200.0, 1.0]]),
            key=lambda p: p[0],
        )

    def _normalize(self, sample: FaceSample) -> np.ndarray:
        return normalize_face(sample.face_gray, img_size=IMG_SIZE, equalization=self.equalization)

    def score(self, sample: FaceSample) -> LBPHMatch:
        face = self._normalize(sample)
        collector = cv.face.StandardCollector_create()
        self.recognizer.predict_collect(face, collector)
        results = collector.getResults(True)  # [(label, distance), ...] sorted
        per_label: dict[int, float] = {}
        for label, dist in results:
            label = int(label)
            dist = float(dist)
            if label not in per_label or dist < per_label[label]:
                per_label[label] = dist
        if not per_label:
            pred_id, dist = self.recognizer.predict(face)
            per_label = {int(pred_id): float(dist)}
        ranked = sorted(per_label.items(), key=lambda kv: kv[1])
        best_label, best_dist = ranked[0]
        second_dist = ranked[1][1] if len(ranked) > 1 else best_dist + 999.0
        # Relative top1<->top2 gap: scale-free so it transfers from the inflated
        # train distances to the held-out ones (see gate.py).
        margin = float((second_dist - best_dist) / max(best_dist, 1e-6))
        all_distances = {self.id_to_name.get(lbl, str(lbl)): d for lbl, d in per_label.items()}
        return LBPHMatch(
            name=self.id_to_name.get(best_label, "Unknown"),
            distance=float(best_dist),
            margin=margin,
            far=self.far_of(best_dist),
            all_distances=all_distances,
        )

    def far_of(self, raw: float) -> float:
        """Interpolate FAR for an LBPH distance in log space across the anchors.

        This is a reporting estimate from the calibrated edges, not a full LBPH
        independence sweep; the gate uses ``tau_accept``/``tau_reject`` directly.
        """
        anchors = self._far_anchors
        if raw <= anchors[0][0]:
            return float(anchors[0][1])
        if raw >= anchors[-1][0]:
            return float(anchors[-1][1])
        for (d0, f0), (d1, f1) in zip(anchors, anchors[1:]):
            if d0 <= raw <= d1:
                if d1 == d0:
                    return float(f1)
                t = (raw - d0) / (d1 - d0)
                lo = max(f0, 1e-9)
                hi = max(f1, 1e-9)
                return float(np.exp(np.log(lo) + t * (np.log(hi) - np.log(lo))))
        return float(anchors[-1][1])


# --------------------------------------------------------------------------- #
# SFace adapter (wrap src/sface to the same protocol)
# --------------------------------------------------------------------------- #
class SFaceAdapter:
    name = "SFace"
    kind = "sface"

    def __init__(
        self,
        *,
        model_path: str | None = None,
        gallery_path: str = DEFAULT_SFACE_GALLERY,
        impostors_path: str | None = DEFAULT_SFACE_IMPOSTORS,
        recognizer: SFaceRecognizer | None = None,
        gallery: SFaceGallery | None = None,
        far_model: SFaceFarModel | None = None,
    ) -> None:
        self.recognizer = recognizer or SFaceRecognizer(model_path or default_sface_model_path())
        if gallery is not None:
            self.gallery = gallery
        elif Path(gallery_path).exists():
            self.gallery = SFaceGallery.load(gallery_path)
        else:
            raise FileNotFoundError(
                f"SFace gallery not found: {gallery_path}. Run the hybrid enroll "
                "action first (src/hybrid/enroll.py)."
            )
        self.labels = self.gallery.labels
        if far_model is not None:
            self.far_model = far_model
        elif impostors_path and Path(impostors_path).exists():
            self.far_model = SFaceFarModel.from_features_npy(impostors_path)
        else:
            self.far_model = None

    def embed(self, sample: FaceSample) -> np.ndarray:
        if sample.yunet_row is not None:
            return self.recognizer.feature_from_row(sample.image_bgr, sample.yunet_row)
        return self.recognizer.feature_from_crop(sample.image_bgr)

    def score(self, sample: FaceSample) -> SFaceMatch:
        feature = self.embed(sample)
        return self.gallery.score(self.recognizer, feature)

    def far_of(self, raw: float) -> float:
        if self.far_model is None:
            return float("nan")
        return self.far_model.far_of(raw)


# --------------------------------------------------------------------------- #
# The fused decision + HybridRecognizer
# --------------------------------------------------------------------------- #
@dataclass
class HybridDecision:
    name: str                 # final thresholded identity (or "Unknown")
    name_raw: str             # deciding engine's nearest identity (no threshold)
    engine: str               # "lbph" | "sface"
    escalated: bool
    reason: str               # gate reason
    mode: str
    lbph_name: str
    lbph_distance: float
    lbph_margin: float
    sface_name: str | None = None
    sface_cosine: float | None = None
    sface_l2: float | None = None
    sface_far: float | None = None
    quality: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "name_raw": self.name_raw,
            "engine": self.engine,
            "escalated": self.escalated,
            "reason": self.reason,
            "mode": self.mode,
            "lbph_name": self.lbph_name,
            "lbph_distance": round(self.lbph_distance, 3),
            "lbph_margin": round(self.lbph_margin, 3),
            "sface_name": self.sface_name,
            "sface_cosine": None if self.sface_cosine is None else round(self.sface_cosine, 4),
            "sface_l2": None if self.sface_l2 is None else round(self.sface_l2, 4),
            "sface_far": None if self.sface_far is None else self.sface_far,
            "quality": self.quality,
        }


class HybridRecognizer:
    """LBPH fast path + SFace escalation behind a gate (the gated cascade)."""

    def __init__(
        self,
        *,
        lbph: LBPHAdapter,
        sface: SFaceAdapter | None,
        gate_thresholds: GateThresholds,
        quality_thresholds: QualityThresholds,
        mode: str = "cascade",
    ) -> None:
        if mode not in HYBRID_MODES:
            raise ValueError(f"Unknown hybrid mode {mode!r}. Valid: {HYBRID_MODES}")
        if mode in {"cascade", "parallel", "dl_only"} and sface is None:
            raise ValueError(f"mode={mode!r} needs an SFace adapter, but none was provided.")
        self.lbph = lbph
        self.sface = sface
        self.gate_thresholds = gate_thresholds
        self.quality_thresholds = quality_thresholds
        self.mode = mode

    @property
    def labels(self) -> list[str]:
        return self.lbph.labels

    def _sface_decision(self, sample: FaceSample, base: dict) -> HybridDecision:
        sface_match = self.sface.score(sample)
        far = self.sface.far_of(sface_match.cosine)
        return HybridDecision(
            name=sface_match.name,
            name_raw=sface_match.name if sface_match.name != "Unknown" else _argmax_name(sface_match),
            engine="sface",
            sface_name=sface_match.name,
            sface_cosine=sface_match.cosine,
            sface_l2=sface_match.l2,
            sface_far=None if far != far else far,  # NaN -> None
            **base,
        )

    def predict(self, sample: FaceSample) -> HybridDecision:
        lbph_match = self.lbph.score(sample)
        quality = compute_quality(
            gray_roi=sample.quality_gray,
            landmarks=sample.landmarks,
            face_px=sample.face_px,
            thresholds=self.quality_thresholds,
        )

        if self.mode == "dl_only":
            base = dict(
                escalated=True, reason="dl_only", mode=self.mode,
                lbph_name=lbph_match.name, lbph_distance=lbph_match.distance,
                lbph_margin=lbph_match.margin, quality=quality.to_dict(),
            )
            return self._sface_decision(sample, base)

        if self.mode == "cv_only":
            accept = lbph_match.distance <= self.gate_thresholds.tau_reject
            return HybridDecision(
                name=lbph_match.name if accept else "Unknown",
                name_raw=lbph_match.name,
                engine="lbph",
                escalated=False,
                reason="cv_only",
                mode=self.mode,
                lbph_name=lbph_match.name,
                lbph_distance=lbph_match.distance,
                lbph_margin=lbph_match.margin,
                quality=quality.to_dict(),
            )

        gate = decide_escalation(
            lbph_distance=lbph_match.distance,
            lbph_margin=lbph_match.margin,
            quality=quality,
            thresholds=self.gate_thresholds,
        )

        if self.mode == "parallel":
            # Both engines run every frame; SFace wins when it accepts, else a
            # confident LBPH accept stands, else Unknown.
            sface_match = self.sface.score(sample)
            far = self.sface.far_of(sface_match.cosine)
            if sface_match.accepted:
                final, engine, raw = sface_match.name, "sface", sface_match.name
            elif gate.lbph_accept:
                final, engine, raw = lbph_match.name, "lbph", lbph_match.name
            else:
                final, engine, raw = "Unknown", "sface", sface_match.name
            return HybridDecision(
                name=final, name_raw=raw, engine=engine, escalated=True,
                reason="parallel:" + gate.reason, mode=self.mode,
                lbph_name=lbph_match.name, lbph_distance=lbph_match.distance,
                lbph_margin=lbph_match.margin, sface_name=sface_match.name,
                sface_cosine=sface_match.cosine, sface_l2=sface_match.l2,
                sface_far=None if far != far else far, quality=quality.to_dict(),
            )

        # cascade (default)
        if gate.escalate:
            base = dict(
                escalated=True, reason=gate.reason, mode=self.mode,
                lbph_name=lbph_match.name, lbph_distance=lbph_match.distance,
                lbph_margin=lbph_match.margin, quality=quality.to_dict(),
            )
            return self._sface_decision(sample, base)

        return HybridDecision(
            name=lbph_match.name if gate.lbph_accept else "Unknown",
            name_raw=lbph_match.name,
            engine="lbph",
            escalated=False,
            reason=gate.reason,
            mode=self.mode,
            lbph_name=lbph_match.name,
            lbph_distance=lbph_match.distance,
            lbph_margin=lbph_match.margin,
            quality=quality.to_dict(),
        )


def _argmax_name(match: SFaceMatch) -> str:
    if not match.all_cosines:
        return match.name
    return max(match.all_cosines.items(), key=lambda kv: kv[1])[0]


# --------------------------------------------------------------------------- #
# Threshold + factory helpers
# --------------------------------------------------------------------------- #
def load_thresholds(path: str = DEFAULT_THRESHOLDS_PATH) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_hybrid(
    *,
    mode: str = "cascade",
    thresholds_path: str = DEFAULT_THRESHOLDS_PATH,
    lbph_model: str = DEFAULT_LBPH_MODEL,
    lbph_labels: str = DEFAULT_LBPH_LABELS,
    sface_gallery: str = DEFAULT_SFACE_GALLERY,
    sface_model: str | None = None,
    sface_impostors: str | None = DEFAULT_SFACE_IMPOSTORS,
    require_sface: bool = True,
) -> HybridRecognizer:
    """Load LBPH + SFace + thresholds into a ready ``HybridRecognizer``.

    ``require_sface=False`` (or ``mode=cv_only``) tolerates a missing SFace
    gallery and degrades to the CPU-only LBPH fallback (PLAN §4.3 / §10).
    """
    cfg = load_thresholds(thresholds_path)
    gate_thresholds = GateThresholds.from_dict(cfg.get("gate"))
    quality_thresholds = QualityThresholds.from_dict(cfg.get("quality"))
    lbph = LBPHAdapter(
        model_path=lbph_model,
        labels_path=lbph_labels,
        far_anchors=cfg.get("lbph_far_anchors"),
    )

    sface: SFaceAdapter | None = None
    needs_sface = mode in {"cascade", "parallel", "dl_only"}
    if needs_sface or require_sface:
        try:
            sface = SFaceAdapter(
                model_path=sface_model,
                gallery_path=sface_gallery,
                impostors_path=sface_impostors,
            )
        except FileNotFoundError:
            if needs_sface and require_sface:
                raise
            sface = None
            if needs_sface:
                print("[WARN] SFace gallery missing; falling back to cv_only mode.")
                mode = "cv_only"

    return HybridRecognizer(
        lbph=lbph,
        sface=sface,
        gate_thresholds=gate_thresholds,
        quality_thresholds=quality_thresholds,
        mode=mode,
    )
