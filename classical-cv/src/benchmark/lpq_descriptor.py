"""Transparent Local Phase Quantization descriptors for smoke benchmarks.

The descriptor intentionally owns only LPQ-specific work.  Detection,
alignment, resizing, and common photometric preprocessing stay in the shared
benchmark pipeline; :meth:`LPQDescriptor.extract` expects the resulting 2-D
grayscale crop.  This keeps LPQ, LBPH, and other candidates on identical
pixels in apples-to-apples experiments.

The implementation follows the original LPQ construction (Ojansivu and
Heikkila, 2008): four local short-term Fourier coefficients, optional
first-order-Markov decorrelation, sign quantization into 256 labels, and
spatial label histograms.  It depends only on NumPy and OpenCV.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import cv2 as cv
import numpy as np

__all__ = [
    "LPQDescriptor",
    "MULTISCALE_LPQ",
    "STANDARD_LPQ",
    "chi_square_distance",
    "multiscale_lpq",
    "standard_lpq",
]


_HISTOGRAM_BINS = 256
_CHI_SQUARE_EPS = 1e-10


def chi_square_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Return the symmetric half-chi-square distance between histograms.

    Inputs must be same-length, finite, non-negative one-dimensional arrays.
    The factor of ``0.5`` matches the project's transparent histogram matcher
    convention; raw values are descriptor-specific and must not be compared
    with OpenCV LBPH ``predict_collect`` distances.
    """

    left = np.asarray(a)
    right = np.asarray(b)
    if left.ndim != 1 or right.ndim != 1:
        raise ValueError("chi-square inputs must be one-dimensional")
    if left.shape != right.shape:
        raise ValueError(
            f"chi-square inputs must have the same shape, got {left.shape} and {right.shape}"
        )
    if not np.issubdtype(left.dtype, np.number) or not np.issubdtype(
        right.dtype, np.number
    ):
        raise TypeError("chi-square inputs must be numeric")

    left64 = left.astype(np.float64, copy=False)
    right64 = right.astype(np.float64, copy=False)
    if not np.isfinite(left64).all() or not np.isfinite(right64).all():
        raise ValueError("chi-square inputs must contain only finite values")
    if np.any(left64 < 0.0) or np.any(right64 < 0.0):
        raise ValueError("chi-square inputs must be non-negative histograms")

    delta = left64 - right64
    return float(
        0.5
        * np.sum(
            (delta * delta) / (left64 + right64 + _CHI_SQUARE_EPS),
            dtype=np.float64,
        )
    )


@dataclass(frozen=True, slots=True)
class LPQDescriptor:
    """Fixed-parameter LPQ descriptor suitable for nearest-template matching.

    Parameters
    ----------
    window_sizes:
        Odd STFT support sizes.  One size is standard LPQ; multiple sizes are
        independently histogrammed and concatenated in the supplied order.
    grid_size:
        ``(rows, columns)`` spatial grid.  The default 8x8 grid mirrors the
        spatial resolution of the repository's current LBPH descriptor on its
        shared 100x100 face crops.
    rho:
        Adjacent-pixel correlation used by the original first-order-Markov
        decorrelation model.
    decorrelate:
        Apply the fixed Markov/SVD response rotation before sign quantization.
    label:
        Optional stable result-table name.
    """

    window_sizes: tuple[int, ...] = (7,)
    grid_size: tuple[int, int] = (8, 8)
    rho: float = 0.90
    decorrelate: bool = True
    label: str | None = None

    def __post_init__(self) -> None:
        windows = tuple(int(value) for value in self.window_sizes)
        grid = tuple(int(value) for value in self.grid_size)
        object.__setattr__(self, "window_sizes", windows)
        object.__setattr__(self, "grid_size", grid)

        if not windows:
            raise ValueError("window_sizes must contain at least one size")
        if len(set(windows)) != len(windows):
            raise ValueError("window_sizes must not contain duplicates")
        if any(size < 3 or size % 2 == 0 for size in windows):
            raise ValueError("every LPQ window size must be odd and at least 3")
        if len(grid) != 2 or any(value <= 0 for value in grid):
            raise ValueError("grid_size must contain two positive integers")
        if not np.isfinite(self.rho) or not 0.0 <= float(self.rho) < 1.0:
            raise ValueError("rho must be finite and in the interval [0, 1)")
        if self.label is not None and not self.label.strip():
            raise ValueError("label must be non-empty when supplied")

    @property
    def name(self) -> str:
        """Stable human-readable variant name."""

        if self.label is not None:
            return self.label
        sizes = "_".join(str(size) for size in self.window_sizes)
        prefix = "lpq" if len(self.window_sizes) == 1 else "lpq_multiscale"
        return f"{prefix}_w{sizes}"

    @property
    def descriptor_length(self) -> int:
        """Number of float32 elements emitted by :meth:`extract`."""

        rows, columns = self.grid_size
        return len(self.window_sizes) * rows * columns * _HISTOGRAM_BINS

    @property
    def descriptor_bytes(self) -> int:
        """Bytes per enrolled float32 template."""

        return self.descriptor_length * np.dtype(np.float32).itemsize

    @property
    def static_state_bytes(self) -> int:
        """Bytes in the fixed filter banks/decorrelation rotations for this variant."""

        total = sum(
            kernel.nbytes
            for window_size in self.window_sizes
            for kernel in _filter_bank(window_size)
        )
        if self.decorrelate:
            total += sum(
                _decorrelation_rotation(window_size, float(self.rho)).nbytes
                for window_size in self.window_sizes
            )
        return int(total)

    @property
    def params(self) -> dict[str, Any]:
        """JSON-serializable parameter/provenance metadata for a run record."""

        rows, columns = self.grid_size
        return {
            "algorithm": "local_phase_quantization",
            "variant": self.name,
            "window_sizes": list(self.window_sizes),
            "frequency_beta_by_window": [1.0 / size for size in self.window_sizes],
            "grid_rows": rows,
            "grid_columns": columns,
            "histogram_bins_per_cell": _HISTOGRAM_BINS,
            "histogram_normalization": "per_cell_l1",
            "decorrelation": (
                "first_order_markov_svd_rotation" if self.decorrelate else "none"
            ),
            "rho": float(self.rho),
            "distance": "symmetric_half_chi_square",
            "input_contract": "shared_2d_grayscale_normalized_face_crop",
            "descriptor_dtype": "float32",
            "descriptor_length": self.descriptor_length,
            "descriptor_bytes": self.descriptor_bytes,
            "static_state_bytes": self.static_state_bytes,
        }

    def extract(self, gray: np.ndarray) -> np.ndarray:
        """Extract a deterministic one-dimensional float32 LPQ descriptor."""

        image = _validate_gray(gray)
        features: list[np.ndarray] = []
        for window_size in self.window_sizes:
            codes = _lpq_codes(
                image,
                window_size=window_size,
                rho=float(self.rho),
                decorrelate=self.decorrelate,
            )
            features.append(_spatial_histograms(codes, self.grid_size))

        descriptor = np.concatenate(features).astype(np.float32, copy=False)
        if descriptor.shape != (self.descriptor_length,):
            raise RuntimeError(
                "internal LPQ descriptor-size mismatch: "
                f"expected {self.descriptor_length}, got {descriptor.shape}"
            )
        return descriptor

    def distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compare two descriptors with symmetric half-chi-square distance."""

        return chi_square_distance(a, b)


def standard_lpq(
    *,
    window_size: int = 7,
    grid_size: tuple[int, int] = (8, 8),
    rho: float = 0.90,
    decorrelate: bool = True,
) -> LPQDescriptor:
    """Build the fixed single-scale LPQ smoke-test variant."""

    return LPQDescriptor(
        window_sizes=(window_size,),
        grid_size=grid_size,
        rho=rho,
        decorrelate=decorrelate,
        label=f"lpq_w{window_size}",
    )


def multiscale_lpq(
    *,
    window_sizes: tuple[int, ...] = (3, 5, 7),
    grid_size: tuple[int, int] = (8, 8),
    rho: float = 0.90,
    decorrelate: bool = True,
) -> LPQDescriptor:
    """Build the fixed 3/5/7-window multi-scale LPQ smoke-test variant."""

    sizes = tuple(int(size) for size in window_sizes)
    joined = "_".join(str(size) for size in sizes)
    return LPQDescriptor(
        window_sizes=sizes,
        grid_size=grid_size,
        rho=rho,
        decorrelate=decorrelate,
        label=f"lpq_multiscale_w{joined}",
    )


def _validate_gray(gray: np.ndarray) -> np.ndarray:
    image = np.asarray(gray)
    if image.ndim != 2:
        raise ValueError(
            f"LPQ expects a 2-D grayscale crop, got an array with shape {image.shape}"
        )
    if not np.issubdtype(image.dtype, np.number):
        raise TypeError("LPQ input must have a numeric dtype")
    if image.size == 0:
        raise ValueError("LPQ input must not be empty")

    image64 = np.ascontiguousarray(image, dtype=np.float64)
    if not np.isfinite(image64).all():
        raise ValueError("LPQ input must contain only finite values")
    return image64


@lru_cache(maxsize=None)
def _filter_bank(window_size: int) -> tuple[np.ndarray, ...]:
    radius = window_size // 2
    coordinates = np.arange(-radius, radius + 1, dtype=np.float64)
    yy, xx = np.meshgrid(coordinates, coordinates, indexing="ij")
    beta = 1.0 / float(window_size)
    frequencies = (
        (beta, 0.0),
        (0.0, beta),
        (beta, beta),
        (beta, -beta),
    )

    filters: list[np.ndarray] = []
    for horizontal, vertical in frequencies:
        complex_kernel = np.exp(
            -2j * np.pi * (horizontal * xx + vertical * yy)
        )
        filters.append(np.ascontiguousarray(complex_kernel.real, dtype=np.float64))
        filters.append(np.ascontiguousarray(complex_kernel.imag, dtype=np.float64))

    for kernel in filters:
        kernel.setflags(write=False)
    return tuple(filters)


@lru_cache(maxsize=None)
def _decorrelation_rotation(window_size: int, rho: float) -> np.ndarray:
    """Return the original LPQ Markov-model SVD response rotation."""

    radius = window_size // 2
    coordinates = np.arange(-radius, radius + 1, dtype=np.float64)
    yy, xx = np.meshgrid(coordinates, coordinates, indexing="ij")
    positions = np.column_stack((yy.ravel(), xx.ravel()))
    displacement = positions[:, None, :] - positions[None, :, :]
    euclidean_distance = np.sqrt(
        np.sum(displacement * displacement, axis=2, dtype=np.float64)
    )
    sample_covariance = np.power(float(rho), euclidean_distance)

    response_filters = np.stack(
        [kernel.ravel() for kernel in _filter_bank(window_size)], axis=0
    )
    response_covariance = response_filters @ sample_covariance @ response_filters.T
    response_covariance = 0.5 * (
        response_covariance + response_covariance.T
    )

    _, _, right_singular_vectors = np.linalg.svd(
        response_covariance, full_matrices=True
    )
    rotation = np.ascontiguousarray(right_singular_vectors.T, dtype=np.float64)

    # Eigenvector signs are mathematically arbitrary.  Canonicalizing each
    # column prevents needless descriptor changes between repeated runs on the
    # same covariance model.
    for column in range(rotation.shape[1]):
        pivot = int(np.argmax(np.abs(rotation[:, column])))
        if rotation[pivot, column] < 0.0:
            rotation[:, column] *= -1.0

    rotation.setflags(write=False)
    return rotation


def _lpq_codes(
    image: np.ndarray,
    *,
    window_size: int,
    rho: float,
    decorrelate: bool,
) -> np.ndarray:
    height, width = image.shape
    if height < window_size or width < window_size:
        raise ValueError(
            f"LPQ window {window_size} does not fit input shape {image.shape}"
        )

    radius = window_size // 2
    responses: list[np.ndarray] = []
    for kernel in _filter_bank(window_size):
        # filter2D performs correlation.  Reversing the kernel implements the
        # convolution in the LPQ STFT definition.  Cropping removes all border
        # samples, so the selected OpenCV border mode cannot enter a code.
        convolution_kernel = np.ascontiguousarray(kernel[::-1, ::-1])
        filtered = cv.filter2D(
            image,
            ddepth=cv.CV_64F,
            kernel=convolution_kernel,
            borderType=cv.BORDER_REFLECT_101,
        )
        responses.append(filtered[radius : height - radius, radius : width - radius])

    response_vectors = np.stack(responses, axis=-1)
    if decorrelate:
        response_vectors = response_vectors @ _decorrelation_rotation(window_size, rho)

    bit_weights = np.left_shift(
        np.uint16(1), np.arange(response_vectors.shape[-1], dtype=np.uint16)
    )
    codes = np.sum(
        (response_vectors >= 0.0).astype(np.uint16) * bit_weights,
        axis=-1,
        dtype=np.uint16,
    )
    return codes.astype(np.uint8)


def _spatial_histograms(
    codes: np.ndarray,
    grid_size: tuple[int, int],
) -> np.ndarray:
    rows, columns = grid_size
    height, width = codes.shape
    if height < rows or width < columns:
        raise ValueError(
            f"LPQ code map {codes.shape} is too small for spatial grid {grid_size}"
        )

    row_edges = np.linspace(0, height, rows + 1, dtype=np.int64)
    column_edges = np.linspace(0, width, columns + 1, dtype=np.int64)
    histograms: list[np.ndarray] = []
    for row in range(rows):
        for column in range(columns):
            block = codes[
                row_edges[row] : row_edges[row + 1],
                column_edges[column] : column_edges[column + 1],
            ]
            histogram = np.bincount(
                block.ravel(), minlength=_HISTOGRAM_BINS
            ).astype(np.float32)
            histogram /= float(block.size)
            histograms.append(histogram)

    return np.concatenate(histograms).astype(np.float32, copy=False)


STANDARD_LPQ = standard_lpq()
MULTISCALE_LPQ = multiscale_lpq()
