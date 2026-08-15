"""Transparent HOG nearest-template descriptor for diagnostic benchmarks.

This module deliberately owns only algorithm-intrinsic feature extraction and
matching.  Detection, alignment, crop selection, resizing, and common image
preprocessing remain responsibilities of the shared benchmark pipeline.

The default geometry is fixed for the repository's 100x100 normalized face
crops: 10x10-pixel cells, overlapping 2x2-cell blocks, and nine unsigned
orientation bins.  OpenCV performs standard L2-Hys block normalization.  The
resulting float32 vector is compared with cosine distance by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

import cv2 as cv
import numpy as np


DistanceMetric = Literal["cosine", "euclidean"]
_VALID_DISTANCE_METRICS: Final[tuple[str, ...]] = ("cosine", "euclidean")


def _pair(value: tuple[int, int], *, name: str) -> tuple[int, int]:
    try:
        pair = tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain two positive integers") from exc
    if len(pair) != 2 or any(item <= 0 for item in pair):
        raise ValueError(f"{name} must contain two positive integers")
    return pair


def _validate_feature(feature: np.ndarray, *, label: str) -> np.ndarray:
    array = np.asarray(feature)
    if array.ndim != 1:
        raise ValueError(f"{label} HOG descriptor must be one-dimensional")
    if array.size == 0:
        raise ValueError(f"{label} HOG descriptor must not be empty")
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{label} HOG descriptor must have a numeric dtype")
    array64 = array.astype(np.float64, copy=False)
    if not np.isfinite(array64).all():
        raise ValueError(f"{label} HOG descriptor must contain only finite values")
    return array64


def cosine_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Return a stable cosine distance, including well-defined zero vectors."""

    left = _validate_feature(first, label="first")
    right = _validate_feature(second, label="second")
    if left.shape != right.shape:
        raise ValueError(
            f"HOG descriptor shapes differ: {left.shape} != {right.shape}"
        )

    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0.0 and right_norm == 0.0:
        return 0.0
    if left_norm == 0.0 or right_norm == 0.0:
        return 1.0

    similarity = float(np.dot(left, right) / (left_norm * right_norm))
    similarity = float(np.clip(similarity, -1.0, 1.0))
    return max(0.0, 1.0 - similarity)


def euclidean_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Return Euclidean distance between two finite HOG descriptors."""

    left = _validate_feature(first, label="first")
    right = _validate_feature(second, label="second")
    if left.shape != right.shape:
        raise ValueError(
            f"HOG descriptor shapes differ: {left.shape} != {right.shape}"
        )
    return float(np.linalg.norm(left - right))


@dataclass(frozen=True, slots=True)
class HOGDescriptor:
    """Fixed-parameter OpenCV HOG extractor and nearest-template matcher.

    Size tuples follow OpenCV's ``(width, height)`` convention.  ``extract``
    accepts only a shared grayscale crop whose array shape exactly matches the
    configured window; it never resizes or otherwise changes pipeline pixels.
    """

    win_size: tuple[int, int] = (100, 100)
    cell_size: tuple[int, int] = (10, 10)
    block_cells: tuple[int, int] = (2, 2)
    block_stride_cells: tuple[int, int] = (1, 1)
    bins: int = 9
    distance_metric: DistanceMetric = "cosine"
    gamma_correction: bool = True
    signed_gradients: bool = False

    def __post_init__(self) -> None:
        win_size = _pair(self.win_size, name="win_size")
        cell_size = _pair(self.cell_size, name="cell_size")
        block_cells = _pair(self.block_cells, name="block_cells")
        block_stride_cells = _pair(
            self.block_stride_cells, name="block_stride_cells"
        )
        object.__setattr__(self, "win_size", win_size)
        object.__setattr__(self, "cell_size", cell_size)
        object.__setattr__(self, "block_cells", block_cells)
        object.__setattr__(self, "block_stride_cells", block_stride_cells)

        if self.bins < 1:
            raise ValueError(f"bins must be >= 1, got {self.bins}")
        if self.distance_metric not in _VALID_DISTANCE_METRICS:
            raise ValueError(
                f"unknown HOG distance metric {self.distance_metric!r}; "
                f"expected one of {_VALID_DISTANCE_METRICS}"
            )

        win_width, win_height = win_size
        cell_width, cell_height = cell_size
        block_width, block_height = self.block_size
        stride_width, stride_height = self.block_stride

        if win_width % cell_width or win_height % cell_height:
            raise ValueError("win_size must be an integer number of HOG cells")
        if block_width > win_width or block_height > win_height:
            raise ValueError("HOG block_size must fit inside win_size")
        if (
            block_stride_cells[0] > block_cells[0]
            or block_stride_cells[1] > block_cells[1]
        ):
            raise ValueError("HOG block stride must not exceed block size")
        if (win_width - block_width) % stride_width or (
            win_height - block_height
        ) % stride_height:
            raise ValueError(
                "win_size minus block_size must be divisible by block_stride"
            )

        # Construct once during validation so unsupported OpenCV geometry fails
        # at adapter creation rather than halfway through a benchmark run.
        self._opencv_descriptor()

    @property
    def name(self) -> str:
        """Stable result-table name for the configured matcher."""

        return "hog" if self.distance_metric == "cosine" else "hog_euclidean"

    @property
    def block_size(self) -> tuple[int, int]:
        return (
            self.cell_size[0] * self.block_cells[0],
            self.cell_size[1] * self.block_cells[1],
        )

    @property
    def block_stride(self) -> tuple[int, int]:
        return (
            self.cell_size[0] * self.block_stride_cells[0],
            self.cell_size[1] * self.block_stride_cells[1],
        )

    @property
    def descriptor_length(self) -> int:
        win_width, win_height = self.win_size
        block_width, block_height = self.block_size
        stride_width, stride_height = self.block_stride
        blocks_x = 1 + (win_width - block_width) // stride_width
        blocks_y = 1 + (win_height - block_height) // stride_height
        return (
            blocks_x
            * blocks_y
            * self.block_cells[0]
            * self.block_cells[1]
            * self.bins
        )

    @property
    def descriptor_bytes(self) -> int:
        """Bytes occupied by one extracted float32 enrollment template."""

        return self.descriptor_length * np.dtype(np.float32).itemsize

    @property
    def static_state_bytes(self) -> int:
        """HOG has fixed code/configuration and no learned model state."""

        return 0

    @property
    def params(self) -> dict[str, object]:
        """JSON-serializable metadata for an exploratory diagnostic run."""

        return {
            "algorithm": "histogram_of_oriented_gradients",
            "variant": self.name,
            "win_size": list(self.win_size),
            "cell_size": list(self.cell_size),
            "block_cells": list(self.block_cells),
            "block_size": list(self.block_size),
            "block_stride_cells": list(self.block_stride_cells),
            "block_stride": list(self.block_stride),
            "orientation_bins": self.bins,
            "signed_gradients": self.signed_gradients,
            "gamma_correction": self.gamma_correction,
            "block_normalization": "opencv_l2_hys",
            "l2_hys_threshold": 0.2,
            "distance": self.distance_metric,
            "input_contract": (
                "shared_2d_grayscale_"
                f"{self.win_size[1]}x{self.win_size[0]}_face_crop_no_resize"
            ),
            "input_conversion": "round_to_nearest_uint8",
            "descriptor_dtype": "float32",
            "descriptor_length": self.descriptor_length,
            "descriptor_bytes": self.descriptor_bytes,
            "static_state_bytes": self.static_state_bytes,
        }

    def _opencv_descriptor(self) -> cv.HOGDescriptor:
        return cv.HOGDescriptor(
            self.win_size,
            self.block_size,
            self.block_stride,
            self.cell_size,
            self.bins,
            1,  # derivative aperture
            -1.0,  # automatic Gaussian window sigma
            cv.HOGDescriptor_L2Hys,
            0.2,
            self.gamma_correction,
            64,  # pyramid levels; unused by compute(), retained for provenance
            self.signed_gradients,
        )

    def extract(self, gray: np.ndarray) -> np.ndarray:
        """Extract one deterministic float32 HOG vector without resizing."""

        image = np.asarray(gray)
        expected_shape = (self.win_size[1], self.win_size[0])
        if image.ndim != 2:
            raise ValueError(
                f"HOG expects a 2-D grayscale crop, got an array with shape {image.shape}"
            )
        if image.shape != expected_shape:
            raise ValueError(
                f"HOG expects crop shape {expected_shape}, got {image.shape}; "
                "the descriptor does not resize pipeline pixels"
            )
        if not np.issubdtype(image.dtype, np.number):
            raise TypeError("HOG input must have a numeric dtype")

        image64 = image.astype(np.float64, copy=False)
        if not np.isfinite(image64).all():
            raise ValueError("HOG input must contain only finite values")
        minimum = float(np.min(image64))
        maximum = float(np.max(image64))
        if minimum < 0.0 or maximum > 255.0:
            raise ValueError(
                "HOG expects intensities on the 0..255 scale; "
                f"observed range [{minimum}, {maximum}]"
            )

        image_u8 = np.ascontiguousarray(np.rint(image64), dtype=np.uint8)
        descriptor = self._opencv_descriptor().compute(
            image_u8, winStride=(0, 0), padding=(0, 0)
        )
        if descriptor is None:
            raise RuntimeError("OpenCV HOG extraction returned no descriptor")
        feature = np.ascontiguousarray(descriptor.reshape(-1), dtype=np.float32)
        if feature.shape != (self.descriptor_length,):
            raise RuntimeError(
                "internal HOG descriptor-size mismatch: "
                f"expected {self.descriptor_length}, got {feature.shape}"
            )
        return feature

    def distance(self, first: np.ndarray, second: np.ndarray) -> float:
        """Compare two descriptors; lower is more similar."""

        left = np.asarray(first)
        right = np.asarray(second)
        expected_shape = (self.descriptor_length,)
        if left.shape != expected_shape or right.shape != expected_shape:
            raise ValueError(
                "HOG matcher expects descriptors with shape "
                f"{expected_shape}, got {left.shape} and {right.shape}"
            )
        if self.distance_metric == "cosine":
            return cosine_distance(left, right)
        return euclidean_distance(left, right)


STANDARD_HOG: Final[HOGDescriptor] = HOGDescriptor()
HOG_VARIANTS: Final[dict[str, HOGDescriptor]] = {STANDARD_HOG.name: STANDARD_HOG}


__all__ = [
    "HOGDescriptor",
    "HOG_VARIANTS",
    "STANDARD_HOG",
    "cosine_distance",
    "euclidean_distance",
]
