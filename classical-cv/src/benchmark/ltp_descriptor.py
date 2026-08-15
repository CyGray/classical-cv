"""Deterministic Local Ternary Pattern descriptors for smoke benchmarks.

The input contract is deliberately narrow: :meth:`LTPDescriptor.extract`
accepts one already detected/aligned, single-channel face crop on the usual
8-bit intensity scale.  Detection, alignment, resizing, and any common
equalization stay in the shared benchmark harness so every recognizer can see
the same pixels.  The Tan--Triggs variant applies the project's existing
Tan--Triggs normalization as descriptor-intrinsic preprocessing.

This module does not calibrate an accept threshold.  It produces split LTP
histograms for threshold-free nearest-template matching with symmetric
chi-square distance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from src.classical_faces.preprocess import tan_triggs_normalize


_BINS_PER_PATTERN: Final[int] = 256
_PATTERN_HALVES: Final[int] = 2
_OFFSETS: Final[tuple[tuple[int, int], ...]] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
    (1, 0),
    (1, -1),
    (0, -1),
)
_VALID_VARIANTS: Final[tuple[str, ...]] = ("ltp", "tan_triggs_ltp")


def _validate_gray(gray: np.ndarray) -> np.ndarray:
    """Return a float32 view/copy after enforcing the descriptor input contract."""

    image = np.asarray(gray)
    if image.ndim != 2:
        raise ValueError(f"LTP expects a 2-D grayscale image, got shape {image.shape}")
    if image.size == 0:
        raise ValueError("LTP expects a non-empty grayscale image")
    if not np.issubdtype(image.dtype, np.number):
        raise TypeError(f"LTP expects a numeric image dtype, got {image.dtype}")

    image_f32 = image.astype(np.float32, copy=False)
    if not np.all(np.isfinite(image_f32)):
        raise ValueError("LTP input contains NaN or infinite values")
    minimum = float(np.min(image_f32))
    maximum = float(np.max(image_f32))
    if minimum < 0.0 or maximum > 255.0:
        raise ValueError(
            "LTP expects intensities on the 0..255 scale; "
            f"observed range [{minimum}, {maximum}]"
        )
    return image_f32


def _split_ltp_codes(
    gray: np.ndarray,
    *,
    threshold: float,
    radius: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Encode the positive and negative halves of an eight-neighbour LTP.

    Bits are ordered clockwise from north-west.  A neighbour is positive when
    ``neighbour >= centre + threshold`` and negative when
    ``neighbour <= centre - threshold``.  Values inside that band contribute
    zero to both binary halves.
    """

    image = _validate_gray(gray)
    if radius < 1:
        raise ValueError(f"radius must be >= 1, got {radius}")
    if threshold <= 0.0 or not np.isfinite(threshold):
        raise ValueError(f"threshold must be finite and > 0, got {threshold}")

    height, width = image.shape
    if height <= 2 * radius or width <= 2 * radius:
        raise ValueError(
            f"image shape {image.shape} is too small for LTP radius {radius}"
        )

    centre = image[radius : height - radius, radius : width - radius]
    positive = np.zeros(centre.shape, dtype=np.uint8)
    negative = np.zeros(centre.shape, dtype=np.uint8)

    for bit, (unit_dy, unit_dx) in enumerate(_OFFSETS):
        dy = unit_dy * radius
        dx = unit_dx * radius
        neighbour = image[
            radius + dy : height - radius + dy,
            radius + dx : width - radius + dx,
        ]
        positive |= (neighbour >= centre + threshold).astype(np.uint8) << bit
        negative |= (neighbour <= centre - threshold).astype(np.uint8) << bit

    return positive, negative


def ltp_histogram(
    gray: np.ndarray,
    *,
    threshold: float = 5.0,
    radius: int = 1,
    grid_x: int = 8,
    grid_y: int = 8,
) -> np.ndarray:
    """Extract a spatially tiled split-LTP histogram.

    Each grid cell contributes one independently L1-normalized 256-bin
    positive histogram followed by its 256-bin negative histogram.  The
    returned descriptor is a contiguous one-dimensional ``float32`` array of
    length ``grid_x * grid_y * 512``.
    """

    if grid_x < 1 or grid_y < 1:
        raise ValueError(f"grid dimensions must be >= 1, got ({grid_x}, {grid_y})")

    positive, negative = _split_ltp_codes(
        gray,
        threshold=float(threshold),
        radius=int(radius),
    )
    code_height, code_width = positive.shape
    if code_height < grid_y or code_width < grid_x:
        raise ValueError(
            "LTP code image is smaller than the requested spatial grid: "
            f"codes={positive.shape}, grid=({grid_y}, {grid_x})"
        )

    y_edges = np.linspace(0, code_height, grid_y + 1, dtype=np.int32)
    x_edges = np.linspace(0, code_width, grid_x + 1, dtype=np.int32)
    length = grid_x * grid_y * _PATTERN_HALVES * _BINS_PER_PATTERN
    descriptor = np.empty(length, dtype=np.float32)
    cursor = 0

    for grid_row in range(grid_y):
        y0, y1 = int(y_edges[grid_row]), int(y_edges[grid_row + 1])
        for grid_col in range(grid_x):
            x0, x1 = int(x_edges[grid_col]), int(x_edges[grid_col + 1])
            for codes in (positive, negative):
                histogram = np.bincount(
                    codes[y0:y1, x0:x1].reshape(-1),
                    minlength=_BINS_PER_PATTERN,
                ).astype(np.float32)
                histogram /= float(histogram.sum())
                descriptor[cursor : cursor + _BINS_PER_PATTERN] = histogram
                cursor += _BINS_PER_PATTERN

    return descriptor


def chi_square_distance(
    first: np.ndarray,
    second: np.ndarray,
    *,
    epsilon: float = 1e-10,
) -> float:
    """Return symmetric chi-square distance between two histogram vectors."""

    left = np.asarray(first, dtype=np.float32).reshape(-1)
    right = np.asarray(second, dtype=np.float32).reshape(-1)
    if left.shape != right.shape:
        raise ValueError(f"descriptor shapes differ: {left.shape} != {right.shape}")
    if left.size == 0:
        raise ValueError("descriptors must be non-empty")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise ValueError("descriptors contain NaN or infinite values")
    if np.any(left < 0.0) or np.any(right < 0.0):
        raise ValueError("chi-square histogram descriptors must be non-negative")
    if epsilon <= 0.0 or not np.isfinite(epsilon):
        raise ValueError(f"epsilon must be finite and > 0, got {epsilon}")

    left64 = left.astype(np.float64, copy=False)
    right64 = right.astype(np.float64, copy=False)
    difference = left64 - right64
    denominator = left64 + right64 + float(epsilon)
    return float(0.5 * np.sum((difference * difference) / denominator, dtype=np.float64))


@dataclass(frozen=True, slots=True)
class LTPDescriptor:
    """Fixed-parameter LTP extractor and histogram matcher for a benchmark."""

    variant: str = "ltp"
    threshold: float = 5.0
    radius: int = 1
    grid_x: int = 8
    grid_y: int = 8

    def __post_init__(self) -> None:
        if self.variant not in _VALID_VARIANTS:
            raise ValueError(
                f"unknown LTP variant {self.variant!r}; expected one of {_VALID_VARIANTS}"
            )
        if self.radius < 1:
            raise ValueError(f"radius must be >= 1, got {self.radius}")
        if self.threshold <= 0.0 or not np.isfinite(self.threshold):
            raise ValueError(f"threshold must be finite and > 0, got {self.threshold}")
        if self.grid_x < 1 or self.grid_y < 1:
            raise ValueError(
                f"grid dimensions must be >= 1, got ({self.grid_x}, {self.grid_y})"
            )

    @property
    def name(self) -> str:
        """Stable harness/report name."""

        return self.variant

    @property
    def descriptor_length(self) -> int:
        return self.grid_x * self.grid_y * _PATTERN_HALVES * _BINS_PER_PATTERN

    @property
    def descriptor_bytes(self) -> int:
        """Bytes occupied by one extracted float32 enrollment template."""

        return self.descriptor_length * np.dtype(np.float32).itemsize

    @property
    def params(self) -> dict[str, object]:
        """Serializable metadata for a diagnostic run record."""

        metadata: dict[str, object] = {
            "variant": self.variant,
            "radius": self.radius,
            "neighbors": len(_OFFSETS),
            "sampling": "square_8_clockwise_from_northwest",
            "threshold": float(self.threshold),
            "grid_x": self.grid_x,
            "grid_y": self.grid_y,
            "histogram_bins_per_half": _BINS_PER_PATTERN,
            "histogram_normalization": "l1_per_cell_per_half",
            "distance": "symmetric_chi_square_half_sum",
            "input": "aligned_grayscale_0_255_no_internal_resize",
        }
        if self.variant == "tan_triggs_ltp":
            metadata["intrinsic_preprocessing"] = {
                "name": "tan_triggs",
                "gamma": 0.2,
                "sigma0": 1.0,
                "sigma1": 2.0,
                "tau": 10.0,
                "alpha": 0.1,
                "implementation": "src.classical_faces.preprocess.tan_triggs_normalize",
            }
        else:
            metadata["intrinsic_preprocessing"] = None
        return metadata

    def extract(self, gray: np.ndarray) -> np.ndarray:
        """Extract one deterministic descriptor from a shared grayscale crop."""

        image = _validate_gray(gray)
        if self.variant == "tan_triggs_ltp":
            image = tan_triggs_normalize(image)
        return ltp_histogram(
            image,
            threshold=self.threshold,
            radius=self.radius,
            grid_x=self.grid_x,
            grid_y=self.grid_y,
        )

    def distance(self, first: np.ndarray, second: np.ndarray) -> float:
        """Match two descriptors; lower is more similar."""

        return chi_square_distance(first, second)


STANDARD_LTP: Final[LTPDescriptor] = LTPDescriptor(variant="ltp")
TAN_TRIGGS_LTP: Final[LTPDescriptor] = LTPDescriptor(variant="tan_triggs_ltp")
LTP_VARIANTS: Final[dict[str, LTPDescriptor]] = {
    STANDARD_LTP.name: STANDARD_LTP,
    TAN_TRIGGS_LTP.name: TAN_TRIGGS_LTP,
}


__all__ = [
    "LTPDescriptor",
    "LTP_VARIANTS",
    "STANDARD_LTP",
    "TAN_TRIGGS_LTP",
    "chi_square_distance",
    "ltp_histogram",
]
