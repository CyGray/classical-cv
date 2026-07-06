"""The shared 41-variant modification suite (12 types x levels = 41 variants).

Single source of truth for the DB2-style modified-image benchmark, used by:

* ``src/benchmark/accuracy_ratio.py``        - classical families (LBPH/Eigen/Fisher)
* ``src/benchmark/accuracy_ratio_hybrid.py`` - LBPH vs SFace vs hybrid cascade

Every transform takes ``(gray_or_bgr_image, level, rng)`` and returns the same
shape/dtype. Noise/occlusion consume the rng; deterministic transforms ignore
it. Seed via :func:`stable_rng` per (image, modification, level) so any script
that applies the suite produces the *identical* modified probe - that is what
makes cross-family AR numbers comparable.

NOTE: the official 41-modification list from the team spec sheet should be
confirmed; this suite is the documented stand-in (the counts match: 41
variants/original, La Salle DB2 = 280 x 41 = 11,480 when train originals are
included).
"""

from __future__ import annotations

import math
import zlib

import cv2 as cv
import numpy as np


def _u8(image: np.ndarray) -> np.ndarray:
    return np.clip(image, 0, 255).astype(np.uint8)


def _brightness(img: np.ndarray, offset: float, _rng) -> np.ndarray:
    return _u8(img.astype(np.float32) + offset)


def _contrast(img: np.ndarray, factor: float, _rng) -> np.ndarray:
    return _u8((img.astype(np.float32) - 128.0) * factor + 128.0)


def _gamma(img: np.ndarray, gamma: float, _rng) -> np.ndarray:
    table = _u8(((np.arange(256, dtype=np.float32) / 255.0) ** (1.0 / max(gamma, 1e-6))) * 255.0)
    return cv.LUT(img, table)


def _gaussian_noise(img: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    return _u8(img.astype(np.float32) + rng.normal(0.0, sigma, img.shape).astype(np.float32))


def _gaussian_blur(img: np.ndarray, ksize: int, _rng) -> np.ndarray:
    k = int(ksize) | 1
    return cv.GaussianBlur(img, (k, k), 0)


def _motion_blur(img: np.ndarray, ksize: int, _rng) -> np.ndarray:
    k = max(3, int(ksize) | 1)
    kernel = np.zeros((k, k), dtype=np.float32)
    kernel[k // 2, :] = 1.0 / float(k)
    return cv.filter2D(img, -1, kernel)


def _rotation(img: np.ndarray, angle_deg: float, _rng) -> np.ndarray:
    h, w = img.shape[:2]
    matrix = cv.getRotationMatrix2D(((w - 1) / 2.0, (h - 1) / 2.0), angle_deg, 1.0)
    return cv.warpAffine(img, matrix, (w, h), flags=cv.INTER_LINEAR,
                         borderMode=cv.BORDER_REFLECT_101)


def _zoom(img: np.ndarray, zoom: float, _rng) -> np.ndarray:
    h, w = img.shape[:2]
    matrix = cv.getRotationMatrix2D(((w - 1) / 2.0, (h - 1) / 2.0), 0.0, zoom)
    return cv.warpAffine(img, matrix, (w, h), flags=cv.INTER_LINEAR,
                         borderMode=cv.BORDER_REFLECT_101)


def _occlusion(img: np.ndarray, area_fraction: float, rng: np.random.Generator) -> np.ndarray:
    h, w = img.shape[:2]
    target = max(1.0, area_fraction * h * w)
    rect_h = int(max(4, round(math.sqrt(target))))
    rect_w = int(max(4, round(target / rect_h)))
    rect_h, rect_w = min(rect_h, h), min(rect_w, w)
    y0 = int(rng.integers(0, max(1, h - rect_h + 1)))
    x0 = int(rng.integers(0, max(1, w - rect_w + 1)))
    out = img.copy()
    patch = out[y0: y0 + rect_h, x0: x0 + rect_w]
    fill = int(np.median(patch)) if patch.size else 128
    out[y0: y0 + rect_h, x0: x0 + rect_w] = _u8(
        0.55 * patch.astype(np.float32) + 0.45 * fill
    )
    return out


# (modification name, transform, [levels]) -> 4+4+3+3+3+3+4+3+3+4+4+3 = 41 variants
MODIFICATIONS: list[tuple[str, object, list[float]]] = [
    ("brightness_up", _brightness, [15, 30, 45, 60]),
    ("brightness_down", _brightness, [-15, -30, -45, -60]),
    ("contrast_up", _contrast, [1.15, 1.30, 1.45]),
    ("contrast_down", _contrast, [0.85, 0.70, 0.55]),
    ("gamma_up", _gamma, [1.2, 1.4, 1.6]),
    ("gamma_down", _gamma, [0.8, 0.65, 0.5]),
    ("gaussian_noise", _gaussian_noise, [5, 10, 15, 20]),
    ("gaussian_blur", _gaussian_blur, [3, 5, 7]),
    ("motion_blur", _motion_blur, [3, 5, 7]),
    ("rotation", _rotation, [-10, -5, 5, 10]),
    ("zoom", _zoom, [0.90, 0.95, 1.05, 1.10]),
    ("occlusion", _occlusion, [0.075, 0.125, 0.175]),
]

VARIANT_COUNT = sum(len(levels) for _, _, levels in MODIFICATIONS)


def stable_rng(seed: int, *tokens: object) -> np.random.Generator:
    """Deterministic per-(image, modification, level) generator - identical
    tokens always give the identical modified probe, across scripts."""
    token = "/".join(str(t) for t in tokens)
    return np.random.default_rng(seed + zlib.crc32(token.encode("utf-8")))
