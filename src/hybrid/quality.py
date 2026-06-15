"""Cheap quality probes on the crop LBPH already holds.

Each probe targets a regime the classical-track audit measured LBPH failing and
SFace winning (see ``docs/ARCHITECTURE_PLAN.md`` and the 41-modification
accuracy-ratio suite):

* **blur**       - variance-of-Laplacian ``< tau_blur``   (LBPH motion_blur ~68.5%)
* **low_light**  - mean luma outside ``[luma_lo, luma_hi]`` (LBPH brightness_down ~73.7%)
* **noise**      - Immerkaer sigma ``> tau_noise``          (LBPH gaussian_noise ~47.8%)
* **off_pose**   - eye-roll / nose-yaw angle ``> tau_pose`` (from YuNet's 5 landmarks)
* **small_face** - YuNet box side ``< px_min``

Every probe returns a boolean flag *and* its raw measurement so the calibration
step can set each threshold at the measured LBPH<->SFace crossover rather than a
guess. The thresholds shipped here are placeholders until ``calibrate.py`` runs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2 as cv
import numpy as np


@dataclass(frozen=True)
class QualityThresholds:
    tau_blur: float = 60.0       # variance-of-Laplacian below this => blurry
    luma_lo: float = 50.0        # mean gray below this => too dark
    luma_hi: float = 205.0       # mean gray above this => too bright
    tau_noise: float = 12.0      # Immerkaer noise sigma above this => noisy
    tau_pose: float = 18.0       # roll/yaw angle (deg) above this => off-pose
    px_min: int = 80             # face box side (px) below this => too small

    @classmethod
    def from_dict(cls, data: dict | None) -> "QualityThresholds":
        if not data:
            return cls()
        fields = cls.__dataclass_fields__
        return cls(**{k: type(getattr(cls(), k))(v) for k, v in data.items() if k in fields})

    def to_dict(self) -> dict:
        return {
            "tau_blur": self.tau_blur,
            "luma_lo": self.luma_lo,
            "luma_hi": self.luma_hi,
            "tau_noise": self.tau_noise,
            "tau_pose": self.tau_pose,
            "px_min": self.px_min,
        }


@dataclass
class QualityReport:
    blur_var: float
    luma_mean: float
    noise_sigma: float
    pose_angle: float
    face_px: int
    flags: dict[str, bool] = field(default_factory=dict)

    @property
    def any_flag(self) -> bool:
        return any(self.flags.values())

    @property
    def active_flags(self) -> list[str]:
        return [name for name, on in self.flags.items() if on]

    def to_dict(self) -> dict:
        return {
            "blur_var": round(self.blur_var, 3),
            "luma_mean": round(self.luma_mean, 2),
            "noise_sigma": round(self.noise_sigma, 3),
            "pose_angle": round(self.pose_angle, 2),
            "face_px": self.face_px,
            "flags": dict(self.flags),
        }


def variance_of_laplacian(gray: np.ndarray) -> float:
    return float(cv.Laplacian(gray, cv.CV_64F).var())


def estimate_noise_sigma(gray: np.ndarray) -> float:
    """Immerkaer (1996) fast noise variance estimate via a Laplacian-like mask."""
    h, w = gray.shape[:2]
    if h < 3 or w < 3:
        return 0.0
    mask = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)
    conv = np.abs(cv.filter2D(gray.astype(np.float64), -1, mask))
    sigma = conv.sum() * math.sqrt(0.5 * math.pi) / (6.0 * (w - 2) * (h - 2))
    return float(sigma)


def pose_angle_from_landmarks(landmarks: np.ndarray | None) -> float:
    """Combined off-pose angle (deg) from YuNet's 5 landmarks.

    Returns ``max(|eye-roll|, nose-yaw-proxy)`` in degrees. The roll is the eye
    line tilt; the yaw proxy is the nose's horizontal offset from the eye
    midpoint, normalised by inter-ocular distance and mapped to degrees. Frontal
    upright faces score ~0; tilted or turned faces score high.
    """
    if landmarks is None:
        return 0.0
    pts = np.asarray(landmarks, dtype=np.float32).reshape(-1, 2)
    if pts.shape[0] < 3:
        return 0.0
    right_eye, left_eye, nose = pts[0], pts[1], pts[2]
    dx = float(left_eye[0] - right_eye[0])
    dy = float(left_eye[1] - right_eye[1])
    roll = abs(math.degrees(math.atan2(dy, dx)))
    if roll > 90.0:
        roll = 180.0 - roll
    inter_ocular = math.hypot(dx, dy)
    if inter_ocular < 1e-3:
        return roll
    eye_mid_x = 0.5 * (right_eye[0] + left_eye[0])
    yaw_ratio = abs(float(nose[0] - eye_mid_x)) / inter_ocular
    yaw_proxy = min(90.0, yaw_ratio * 90.0)
    return max(roll, yaw_proxy)


def compute_quality(
    *,
    gray_roi: np.ndarray,
    landmarks: np.ndarray | None,
    face_px: int,
    thresholds: QualityThresholds,
) -> QualityReport:
    """Run every probe on the LBPH crop + YuNet landmarks and flag bad regimes."""
    blur_var = variance_of_laplacian(gray_roi)
    luma_mean = float(np.mean(gray_roi)) if gray_roi.size else 0.0
    noise_sigma = estimate_noise_sigma(gray_roi)
    pose_angle = pose_angle_from_landmarks(landmarks)

    flags = {
        "blur": blur_var < thresholds.tau_blur,
        "low_light": luma_mean < thresholds.luma_lo or luma_mean > thresholds.luma_hi,
        "noise": noise_sigma > thresholds.tau_noise,
        "off_pose": pose_angle > thresholds.tau_pose,
        "small_face": face_px < thresholds.px_min,
    }
    return QualityReport(
        blur_var=blur_var,
        luma_mean=luma_mean,
        noise_sigma=noise_sigma,
        pose_angle=pose_angle,
        face_px=int(face_px),
        flags=flags,
    )
