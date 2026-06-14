"""Pluggable face detectors for the classical recognizers.

Two detection backends behind one tiny interface so training, offline
evaluation and the live loops can switch between **Viola-Jones (Haar cascade)**
and **YuNet (CNN)** without any other code change:

* ``haar``  - :class:`cv.CascadeClassifier`, the historical default. Fast on
  CPU, frontal-only, no landmarks, sensitive to pose/illumination.
* ``yunet`` - :class:`cv.FaceDetectorYN` (the libfacedetection CNN shipped with
  OpenCV, ``face_detection_yunet_2023mar.onnx``). Robust to pose/scale/lighting,
  emits a confidence score and 5 facial landmarks, still real-time on CPU.

Both detectors return faces as ``(x, y, w, h)`` boxes in the coordinates of the
**full-resolution image the recognizer pipeline already works in**, so they are
drop-in interchangeable. The recognizer pipeline is grayscale; YuNet needs a
3-channel image, so :meth:`detect` accepts the original BGR frame when available
and otherwise promotes the grayscale image to BGR.

The single source of the default is the ``FACE_G3_DETECTOR`` environment
variable (``haar`` | ``yunet``); see :func:`resolve_default_backend`. Every
``trainer.py`` / ``evaluate.py`` / ``detect.py`` also exposes a ``--detector``
flag that overrides it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.datasets import root_path
from src.classical_faces.preprocess import detect_largest_face_box, maybe_downscale

VALID_BACKENDS: tuple[str, ...] = ("haar", "yunet")
DEFAULT_BACKEND = "haar"

# Reused across the project: the Haar cascade lives in haar/, the YuNet ONNX is
# the same weight file the DL track (yunet_mobilefacenet) already ships.
DEFAULT_HAAR_CASCADE_PATH = root_path("haar", "haarcascade_frontalface_default.xml")
DEFAULT_YUNET_MODEL_PATH = root_path(
    "models", "yunet_mobilefacenet", "face_detection_yunet_2023mar.onnx"
)

# YuNet defaults (match the DL track / OpenCV sample).
DEFAULT_YUNET_SCORE_THRESHOLD = 0.6
DEFAULT_YUNET_NMS_THRESHOLD = 0.3
DEFAULT_YUNET_TOP_K = 5000


def resolve_default_backend() -> str:
    """Detector backend from ``FACE_G3_DETECTOR`` (falls back to ``haar``)."""
    value = os.environ.get("FACE_G3_DETECTOR", "").strip().lower()
    return value if value in VALID_BACKENDS else DEFAULT_BACKEND


@dataclass
class Detection:
    """A single detected face in full-resolution image coordinates."""

    box: tuple[int, int, int, int]  # x, y, w, h
    score: float = 1.0
    landmarks: np.ndarray | None = None  # (5, 2) float32 or None (Haar has none)

    @property
    def area(self) -> int:
        return int(self.box[2]) * int(self.box[3])


class FaceDetector:
    """Common interface: detect faces in (gray, optional bgr) -> ``Detection`` list."""

    backend: str = "base"

    def detect(self, image_gray: np.ndarray, image_bgr: np.ndarray | None = None) -> list[Detection]:
        raise NotImplementedError

    def detect_largest(
        self, image_gray: np.ndarray, image_bgr: np.ndarray | None = None
    ) -> tuple[int, int, int, int] | None:
        """Largest detected face box (by area), or ``None`` if nothing found.

        This is the single entry point the preprocessing contract uses, so Haar
        and YuNet are interchangeable for every offline/live recognizer stage.
        """
        detections = self.detect(image_gray, image_bgr)
        if not detections:
            return None
        return max(detections, key=lambda d: d.area).box

    def describe(self) -> str:
        return self.backend


class HaarFaceDetector(FaceDetector):
    """Viola-Jones detector. Wraps the historical ``detect_largest_face_box``
    + ``maybe_downscale`` logic so the legacy path and the new toggle share one
    implementation (and cannot drift)."""

    backend = "haar"

    def __init__(
        self,
        cascade: cv.CascadeClassifier,
        *,
        min_face_size: int = 40,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        downscale_max_side: int = 0,
    ) -> None:
        self.cascade = cascade
        self.min_face_size = int(min_face_size)
        self.scale_factor = float(scale_factor)
        self.min_neighbors = int(min_neighbors)
        self.downscale_max_side = int(downscale_max_side)

    def detect(self, image_gray: np.ndarray, image_bgr: np.ndarray | None = None) -> list[Detection]:
        detect_gray, scale = maybe_downscale(image_gray, self.downscale_max_side)
        faces = self.cascade.detectMultiScale(
            detect_gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=(self.min_face_size, self.min_face_size),
        )
        out: list[Detection] = []
        for (x, y, w, h) in faces:
            if scale != 1.0:
                x = int(round(x / scale))
                y = int(round(y / scale))
                w = int(round(w / scale))
                h = int(round(h / scale))
            out.append(Detection(box=(int(x), int(y), int(w), int(h)), score=1.0, landmarks=None))
        return out

    def describe(self) -> str:
        return (
            f"haar(min_face={self.min_face_size}, scale_factor={self.scale_factor}, "
            f"min_neighbors={self.min_neighbors})"
        )


class YuNetFaceDetector(FaceDetector):
    """YuNet CNN detector (``cv.FaceDetectorYN``).

    Works on a BGR image; when only grayscale is supplied (the recognizer
    pipeline is grayscale) the gray image is promoted to 3-channel BGR. Boxes
    and landmarks are returned in full-resolution coordinates.
    """

    backend = "yunet"

    def __init__(
        self,
        model_path: str,
        *,
        score_threshold: float = DEFAULT_YUNET_SCORE_THRESHOLD,
        nms_threshold: float = DEFAULT_YUNET_NMS_THRESHOLD,
        top_k: int = DEFAULT_YUNET_TOP_K,
        min_face_size: int = 0,
        downscale_max_side: int = 0,
    ) -> None:
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"YuNet model not found: {model_path}. Expected the ONNX weights at "
                f"{DEFAULT_YUNET_MODEL_PATH} (shared with the yunet_mobilefacenet DL track)."
            )
        self.model_path = model_path
        self.score_threshold = float(score_threshold)
        self.nms_threshold = float(nms_threshold)
        self.top_k = int(top_k)
        self.min_face_size = int(min_face_size)
        self.downscale_max_side = int(downscale_max_side)
        # Input size is set per-frame via setInputSize(); start with a placeholder.
        self._detector = cv.FaceDetectorYN.create(
            model_path,
            "",
            (320, 320),
            self.score_threshold,
            self.nms_threshold,
            self.top_k,
        )

    def detect(self, image_gray: np.ndarray, image_bgr: np.ndarray | None = None) -> list[Detection]:
        if image_bgr is not None:
            color = image_bgr
        else:
            color = cv.cvtColor(image_gray, cv.COLOR_GRAY2BGR)

        detect_img, scale = maybe_downscale(color, self.downscale_max_side)
        dh, dw = detect_img.shape[:2]
        self._detector.setInputSize((dw, dh))
        _, faces = self._detector.detect(detect_img)
        if faces is None or len(faces) == 0:
            return []

        out: list[Detection] = []
        inv = 1.0 / scale if scale not in (0.0, 1.0) else 1.0
        for row in faces:
            x, y, w, h = (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
            if scale != 1.0:
                x, y, w, h = x * inv, y * inv, w * inv, h * inv
            if self.min_face_size > 0 and (w < self.min_face_size or h < self.min_face_size):
                continue
            score = float(row[14])
            landmarks = np.array(row[4:14], dtype=np.float32).reshape(5, 2)
            if scale != 1.0:
                landmarks = landmarks * inv
            out.append(
                Detection(
                    box=(int(round(x)), int(round(y)), int(round(w)), int(round(h))),
                    score=score,
                    landmarks=landmarks,
                )
            )
        return out

    def describe(self) -> str:
        return (
            f"yunet(score>={self.score_threshold}, nms={self.nms_threshold}, "
            f"model={Path(self.model_path).name})"
        )


def create_face_detector(
    backend: str,
    *,
    cascade_path: str | None = None,
    yunet_model_path: str | None = None,
    min_face_size: int = 40,
    scale_factor: float = 1.1,
    min_neighbors: int = 5,
    downscale_max_side: int = 0,
    yunet_score_threshold: float = DEFAULT_YUNET_SCORE_THRESHOLD,
    yunet_nms_threshold: float = DEFAULT_YUNET_NMS_THRESHOLD,
    yunet_top_k: int = DEFAULT_YUNET_TOP_K,
) -> FaceDetector:
    """Build the requested detector. ``backend`` is ``"haar"`` or ``"yunet"``.

    Raises ``ValueError`` for an unknown backend and ``FileNotFoundError`` when
    the chosen backend's weight file is missing.
    """
    normalized = (backend or "").strip().lower()
    if normalized == "haar":
        path = cascade_path or DEFAULT_HAAR_CASCADE_PATH
        cascade = cv.CascadeClassifier(path)
        if cascade.empty():
            raise FileNotFoundError(f"Could not load Haar cascade file: {path}")
        return HaarFaceDetector(
            cascade,
            min_face_size=min_face_size,
            scale_factor=scale_factor,
            min_neighbors=min_neighbors,
            downscale_max_side=downscale_max_side,
        )
    if normalized == "yunet":
        path = yunet_model_path or DEFAULT_YUNET_MODEL_PATH
        return YuNetFaceDetector(
            path,
            score_threshold=yunet_score_threshold,
            nms_threshold=yunet_nms_threshold,
            top_k=yunet_top_k,
            min_face_size=min_face_size,
            downscale_max_side=downscale_max_side,
        )
    raise ValueError(f"Unknown detector backend: {backend!r}. Valid: {VALID_BACKENDS}")
