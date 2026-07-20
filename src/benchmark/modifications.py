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

_TRANSFORM_BY_NAME: dict[str, object] = {name: fn for name, fn, _levels in MODIFICATIONS}
_LEVELS_BY_NAME: dict[str, list] = {name: levels for name, _fn, levels in MODIFICATIONS}


def stable_rng(seed: int, *tokens: object) -> np.random.Generator:
    """Deterministic per-(image, modification, level) generator - identical
    tokens always give the identical modified probe, across scripts."""
    token = "/".join(str(t) for t in tokens)
    return np.random.default_rng(seed + zlib.crc32(token.encode("utf-8")))


def apply_variant(image: np.ndarray, name: str, level, rng: np.random.Generator) -> np.ndarray:
    """Apply the (name, level) transform - reuses the exact function objects in
    ``MODIFICATIONS``, so output is bit-identical to any other caller (e.g.
    ``accuracy_ratio_hybrid.py``) for the same (image, name, level, rng)."""
    fn = _TRANSFORM_BY_NAME.get(name)
    if fn is None:
        raise ValueError(f"Unknown modification {name!r}. Valid: {sorted(_TRANSFORM_BY_NAME)}")
    return fn(image, level, rng)


# --------------------------------------------------------------------------- #
# Severity tiers (light/medium/heavy) per variant - for the systematic single-
# modification suite (docs/SYSTEMATIC_INDEPENDENCE_TEST.md sec 3.1). Kyle can
# adjust the exact cut points later; this is a severity-ranked first pass.
# --------------------------------------------------------------------------- #
TIERS = ("light", "medium", "heavy")

TIER_MAP: dict[str, dict[float, str]] = {
    "brightness_up": {15: "light", 30: "medium", 45: "medium", 60: "heavy"},
    "brightness_down": {-15: "light", -30: "medium", -45: "medium", -60: "heavy"},
    "contrast_up": {1.15: "light", 1.30: "medium", 1.45: "heavy"},
    "contrast_down": {0.85: "light", 0.70: "medium", 0.55: "heavy"},
    "gamma_up": {1.2: "light", 1.4: "medium", 1.6: "heavy"},
    "gamma_down": {0.8: "light", 0.65: "medium", 0.5: "heavy"},
    "gaussian_noise": {5: "light", 10: "medium", 15: "medium", 20: "heavy"},
    "gaussian_blur": {3: "light", 5: "medium", 7: "heavy"},
    "motion_blur": {3: "light", 5: "medium", 7: "heavy"},
    "rotation": {-10: "heavy", -5: "light", 5: "light", 10: "heavy"},
    "zoom": {0.90: "heavy", 0.95: "light", 1.05: "light", 1.10: "heavy"},
    "occlusion": {0.075: "light", 0.125: "medium", 0.175: "heavy"},
}


def _check_tier_map() -> None:
    expected = {(name, level) for name, _fn, levels in MODIFICATIONS for level in levels}
    covered = {
        (name, level) for name, level_map in TIER_MAP.items() for level in level_map
    }
    missing = expected - covered
    extra = covered - expected
    if missing or extra:
        raise AssertionError(
            f"TIER_MAP / MODIFICATIONS mismatch: missing={sorted(missing)} extra={sorted(extra)}"
        )
    counts = {tier: 0 for tier in TIERS}
    for level_map in TIER_MAP.values():
        for tier in level_map.values():
            counts[tier] += 1
    expected_counts = {"light": 14, "medium": 13, "heavy": 14}
    if counts != expected_counts:
        raise AssertionError(f"TIER_MAP tier counts {counts} != expected {expected_counts}")


_check_tier_map()


def variant_tier(name: str, level) -> str:
    """Tier ('light'/'medium'/'heavy') for one (name, level) variant."""
    level_map = TIER_MAP.get(name)
    if level_map is None:
        raise ValueError(f"Unknown modification {name!r}. Valid: {sorted(TIER_MAP)}")
    if level not in level_map:
        raise ValueError(
            f"Unknown level {level!r} for modification {name!r}. "
            f"Valid levels: {sorted(level_map)}"
        )
    return level_map[level]


_ALL_VARIANT_SPECS = sorted(
    f"{name}:{level}" for name, levels in _LEVELS_BY_NAME.items() for level in levels
)


def parse_variant(spec: str) -> tuple[str, float]:
    """Parse "name:level" (e.g. "motion_blur:5", "contrast_down:0.55",
    "rotation:-10") into the exact (name, level) pair from ``MODIFICATIONS`` -
    the returned level is the SAME object (int stays int, float stays float),
    not a freshly-parsed value, so it hashes/compares identically to the
    MODIFICATIONS entry. Raises ValueError listing valid variants on any
    mismatch."""
    name, sep, level_str = spec.partition(":")
    if not sep:
        raise ValueError(
            f"Invalid variant spec {spec!r} (expected 'name:level'). "
            f"Valid variants: {_ALL_VARIANT_SPECS}"
        )
    levels = _LEVELS_BY_NAME.get(name)
    if levels is None:
        raise ValueError(
            f"Unknown modification {name!r} in {spec!r}. Valid variants: {_ALL_VARIANT_SPECS}"
        )
    try:
        parsed = float(level_str)
    except ValueError:
        raise ValueError(
            f"Non-numeric level in {spec!r}. Valid variants: {_ALL_VARIANT_SPECS}"
        ) from None
    for level in levels:
        if float(level) == parsed:
            return name, level
    raise ValueError(
        f"Unknown level {level_str!r} for modification {name!r} in {spec!r}. "
        f"Valid variants: {_ALL_VARIANT_SPECS}"
    )
