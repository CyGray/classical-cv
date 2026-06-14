"""Shared face preprocessing for the classical recognizers.

This is the single source of truth for how a face is turned into a 100x100
grayscale, contrast-normalized patch. It is used identically by training,
offline evaluation, and the live ``detect.py`` loops so the input distribution
the recognizer sees never differs between those stages.

The contract:

* Raw photo / live webcam frame -> Haar detect the largest face -> optional
  eye-alignment -> equalize -> resize. (``assume_already_cropped=False``)
* Pre-cropped face (e.g. ``data/split_lasalle`` 100x100 tiles) -> the image *is*
  the face -> optional eye-alignment -> equalize -> resize. No Haar detection and
  *no full-image fallback*. (``assume_already_cropped=True``)

``src/lbph/preprocess.py`` re-exports everything here (plus the historical
``extract_lbph_face`` alias) so existing imports keep working.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np

if TYPE_CHECKING:
    from src.classical_faces.detection import FaceDetector

IMG_SIZE = (100, 100)

__all__ = [
    "IMG_SIZE",
    "FacePreprocessResult",
    "resolve_eye_cascade_path",
    "maybe_downscale",
    "detect_largest_face_box",
    "align_face_by_eyes",
    "tan_triggs_normalize",
    "normalize_face",
    "extract_classical_face",
]


@dataclass
class FacePreprocessResult:
    face: np.ndarray | None
    reason: str | None
    detected_face: bool
    used_alignment: bool
    face_box: tuple[int, int, int, int] | None


def resolve_eye_cascade_path(configured_path: str | None) -> str:
    if configured_path:
        candidate = Path(configured_path)
        if candidate.exists():
            return str(candidate)
    return str(Path(cv.data.haarcascades) / "haarcascade_eye.xml")


def maybe_downscale(image_gray: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    if max_side <= 0:
        return image_gray, 1.0
    h, w = image_gray.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image_gray, 1.0
    scale = max_side / float(longest)
    resized = cv.resize(image_gray, (int(w * scale), int(h * scale)))
    return resized, scale


def detect_largest_face_box(
    image_gray: np.ndarray,
    face_cascade: cv.CascadeClassifier,
    min_face_size: int,
    scale_factor: float,
    min_neighbors: int,
) -> tuple[int, int, int, int] | None:
    faces = face_cascade.detectMultiScale(
        image_gray,
        scaleFactor=scale_factor,
        minNeighbors=min_neighbors,
        minSize=(min_face_size, min_face_size),
    )
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda box: int(box[2]) * int(box[3]))
    return int(x), int(y), int(w), int(h)


def align_face_by_eyes(
    face_gray: np.ndarray,
    eye_cascade: cv.CascadeClassifier,
) -> tuple[np.ndarray, bool]:
    h, w = face_gray.shape[:2]
    if h < 20 or w < 20:
        return face_gray, False

    upper = face_gray[: max(1, int(h * 0.65)), :]
    eyes = eye_cascade.detectMultiScale(
        upper,
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(max(8, w // 12), max(8, h // 12)),
    )
    if len(eyes) < 2:
        return face_gray, False

    eye_boxes = sorted(eyes, key=lambda e: int(e[2]) * int(e[3]), reverse=True)[:4]
    centers: list[tuple[float, float]] = []
    for ex, ey, ew, eh in eye_boxes:
        centers.append((float(ex + ew / 2.0), float(ey + eh / 2.0)))

    best_pair: tuple[tuple[float, float], tuple[float, float]] | None = None
    best_dist = 0.0
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            c1 = centers[i]
            c2 = centers[j]
            if abs(c1[1] - c2[1]) > (h * 0.25):
                continue
            dist = math.hypot(c2[0] - c1[0], c2[1] - c1[1])
            if dist > best_dist:
                best_dist = dist
                best_pair = (c1, c2)

    if best_pair is None or best_dist <= 1.0:
        return face_gray, False

    left_eye, right_eye = sorted(best_pair, key=lambda c: c[0])
    angle = math.degrees(math.atan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]))
    center = (w / 2.0, h / 2.0)
    rot = cv.getRotationMatrix2D(center, -angle, 1.0)
    aligned = cv.warpAffine(
        face_gray,
        rot,
        (w, h),
        flags=cv.INTER_LINEAR,
        borderMode=cv.BORDER_REPLICATE,
    )
    return aligned, True


def tan_triggs_normalize(
    face_gray: np.ndarray,
    gamma: float = 0.2,
    sigma0: float = 1.0,
    sigma1: float = 2.0,
    tau: float = 10.0,
    alpha: float = 0.1,
) -> np.ndarray:
    """Tan & Triggs (2010) illumination normalization.

    Gamma correction -> difference-of-Gaussians filtering -> two-stage contrast
    equalization. The output is mapped from [-tau, tau] to [0, 255] with a fixed
    (image-independent) scale so distances stay comparable across images.
    """
    x = np.power(np.maximum(face_gray.astype(np.float32) / 255.0, 1e-6), gamma)
    x = cv.GaussianBlur(x, (0, 0), sigma0) - cv.GaussianBlur(x, (0, 0), sigma1)
    x /= np.power(np.mean(np.power(np.abs(x), alpha)) + 1e-10, 1.0 / alpha)
    x /= np.power(np.mean(np.power(np.minimum(np.abs(x), tau), alpha)) + 1e-10, 1.0 / alpha)
    x = tau * np.tanh(x / tau)
    return np.clip((x + tau) * (255.0 / (2.0 * tau)), 0, 255).astype(np.uint8)


def normalize_face(
    face_gray: np.ndarray,
    img_size: tuple[int, int],
    equalization: str,
) -> np.ndarray:
    if equalization == "clahe":
        clahe = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        normalized = clahe.apply(face_gray)
    elif equalization == "tan-triggs":
        normalized = tan_triggs_normalize(face_gray)
    else:
        normalized = cv.equalizeHist(face_gray)
    return cv.resize(normalized, img_size)


def extract_classical_face(
    image_gray: np.ndarray,
    face_cascade: cv.CascadeClassifier | None,
    min_face_size: int,
    scale_factor: float,
    min_neighbors: int,
    img_size: tuple[int, int] = IMG_SIZE,
    equalization: str = "equalize",
    align_eyes: bool = True,
    eye_cascade: cv.CascadeClassifier | None = None,
    downscale_max_side: int = 0,
    assume_already_cropped: bool = False,
    detector: "FaceDetector | None" = None,
    image_bgr: np.ndarray | None = None,
) -> FacePreprocessResult:
    """Turn a grayscale image into a normalized face patch.

    When ``assume_already_cropped`` is True the whole image is treated as the
    face (no detection, no full-image fallback). Otherwise the largest detected
    face is used, and a miss is reported as ``no_face`` rather than silently
    falling back to the full frame.

    Detection backend: pass a ready :class:`~src.classical_faces.detection.FaceDetector`
    (Haar or YuNet) via ``detector`` and it is used as-is. For backward
    compatibility, callers that still pass a raw ``face_cascade`` get an
    equivalent Haar detector built on the fly, so both paths share one
    implementation. ``image_bgr`` (the original colour frame) is forwarded to
    the detector so YuNet can run on colour instead of a grayscale promotion.
    """
    h, w = image_gray.shape[:2]
    if h < min_face_size or w < min_face_size:
        return FacePreprocessResult(
            face=None,
            reason="image_too_small",
            detected_face=False,
            used_alignment=False,
            face_box=None,
        )

    if assume_already_cropped:
        x, y, fw, fh = 0, 0, w, h
    else:
        active_detector = detector
        if active_detector is None and face_cascade is not None:
            # Legacy callers pass a raw Haar cascade; wrap it so there is a
            # single detection code path shared with the --detector toggle.
            from src.classical_faces.detection import HaarFaceDetector

            active_detector = HaarFaceDetector(
                face_cascade,
                min_face_size=min_face_size,
                scale_factor=scale_factor,
                min_neighbors=min_neighbors,
                downscale_max_side=downscale_max_side,
            )
        if active_detector is None:
            return FacePreprocessResult(
                face=None,
                reason="no_face",
                detected_face=False,
                used_alignment=False,
                face_box=None,
            )
        face_box = active_detector.detect_largest(image_gray, image_bgr=image_bgr)
        if face_box is None:
            return FacePreprocessResult(
                face=None,
                reason="no_face",
                detected_face=False,
                used_alignment=False,
                face_box=None,
            )

        x, y, fw, fh = face_box

    # Safety bounds
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    fw = max(1, min(fw, w - x))
    fh = max(1, min(fh, h - y))

    face_roi = image_gray[y : y + fh, x : x + fw]
    if face_roi.size == 0:
        return FacePreprocessResult(
            face=None,
            reason="no_face",
            detected_face=False,
            used_alignment=False,
            face_box=None,
        )

    aligned = False
    if align_eyes and eye_cascade is not None and not eye_cascade.empty():
        face_roi, aligned = align_face_by_eyes(face_roi, eye_cascade)

    normalized = normalize_face(face_roi, img_size=img_size, equalization=equalization)
    return FacePreprocessResult(
        face=normalized,
        reason=None,
        detected_face=True,
        used_alignment=aligned,
        face_box=(x, y, fw, fh),
    )
