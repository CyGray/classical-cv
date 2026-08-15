from __future__ import annotations

import unittest

import numpy as np

from src.benchmark.lpq_descriptor import (
    MULTISCALE_LPQ,
    STANDARD_LPQ,
    LPQDescriptor,
    _lpq_codes,
    chi_square_distance,
)


def _synthetic_face(size: int = 100) -> np.ndarray:
    yy, xx = np.mgrid[:size, :size]
    return ((3 * xx + 5 * yy + 17 * (xx // 11) + 9 * (yy // 13)) % 256).astype(
        np.uint8
    )


def _random_face(size: int = 100) -> np.ndarray:
    return np.random.default_rng(20260813).integers(
        0, 256, size=(size, size), dtype=np.uint8
    )


def _naive_codes(image: np.ndarray, window_size: int) -> np.ndarray:
    radius = window_size // 2
    coordinates = range(-radius, radius + 1)
    beta = 1.0 / window_size
    frequencies = (
        (beta, 0.0),
        (0.0, beta),
        (beta, beta),
        (beta, -beta),
    )
    output = np.empty(
        (image.shape[0] - 2 * radius, image.shape[1] - 2 * radius),
        dtype=np.uint8,
    )
    image64 = image.astype(np.float64)

    for out_y, center_y in enumerate(range(radius, image.shape[0] - radius)):
        for out_x, center_x in enumerate(range(radius, image.shape[1] - radius)):
            responses: list[float] = []
            for horizontal, vertical in frequencies:
                coefficient = 0.0j
                for offset_y in coordinates:
                    for offset_x in coordinates:
                        coefficient += image64[
                            center_y - offset_y, center_x - offset_x
                        ] * np.exp(
                            -2j
                            * np.pi
                            * (horizontal * offset_x + vertical * offset_y)
                        )
                responses.extend((float(coefficient.real), float(coefficient.imag)))
            code = sum((value >= 0.0) << bit for bit, value in enumerate(responses))
            output[out_y, out_x] = code
    return output


class LPQDescriptorTests(unittest.TestCase):
    def test_standard_descriptor_contract(self) -> None:
        descriptor = STANDARD_LPQ.extract(_synthetic_face())

        self.assertEqual(descriptor.dtype, np.float32)
        self.assertEqual(descriptor.shape, (8 * 8 * 256,))
        self.assertEqual(STANDARD_LPQ.descriptor_bytes, descriptor.nbytes)
        self.assertGreater(STANDARD_LPQ.static_state_bytes, 0)
        self.assertEqual(
            STANDARD_LPQ.params["static_state_bytes"],
            STANDARD_LPQ.static_state_bytes,
        )
        self.assertTrue(np.isfinite(descriptor).all())
        self.assertTrue(np.all(descriptor >= 0.0))

        cell_histograms = descriptor.reshape(8 * 8, 256)
        np.testing.assert_allclose(cell_histograms.sum(axis=1), 1.0, atol=1e-7)

    def test_extraction_is_deterministic_and_positive_scale_invariant(self) -> None:
        # A non-degenerate texture avoids testing the arbitrary sign of an
        # analytically zero Fourier component in the piecewise-linear fixture.
        image = _random_face()
        first = STANDARD_LPQ.extract(image)
        second = STANDARD_LPQ.extract(image.copy())
        scaled = STANDARD_LPQ.extract(image.astype(np.float64) * 2.5)

        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(first, scaled)

    def test_undecorrelated_codes_match_direct_stft_definition(self) -> None:
        image = _random_face(9)
        actual = _lpq_codes(
            image.astype(np.float64),
            window_size=3,
            rho=0.90,
            decorrelate=False,
        )
        expected = _naive_codes(image, window_size=3)

        np.testing.assert_array_equal(actual, expected)

    def test_multiscale_concatenates_fixed_scales(self) -> None:
        descriptor = MULTISCALE_LPQ.extract(_synthetic_face())

        self.assertEqual(descriptor.shape, (3 * 8 * 8 * 256,))
        self.assertEqual(MULTISCALE_LPQ.params["window_sizes"], [3, 5, 7])
        self.assertEqual(MULTISCALE_LPQ.params["descriptor_bytes"], descriptor.nbytes)

    def test_chi_square_distance(self) -> None:
        first = STANDARD_LPQ.extract(_synthetic_face())
        second_image = np.rot90(_synthetic_face()).copy()
        second = STANDARD_LPQ.extract(second_image)

        self.assertAlmostEqual(chi_square_distance(first, first), 0.0)
        self.assertAlmostEqual(
            chi_square_distance(first, second),
            chi_square_distance(second, first),
        )
        self.assertGreater(chi_square_distance(first, second), 0.0)
        self.assertEqual(
            STANDARD_LPQ.distance(first, second), chi_square_distance(first, second)
        )

    def test_invalid_inputs_and_parameters_fail_loudly(self) -> None:
        with self.assertRaisesRegex(ValueError, "2-D grayscale"):
            STANDARD_LPQ.extract(np.zeros((100, 100, 3), dtype=np.uint8))
        with self.assertRaisesRegex(ValueError, "does not fit"):
            STANDARD_LPQ.extract(np.zeros((5, 5), dtype=np.uint8))
        with self.assertRaisesRegex(ValueError, "odd"):
            LPQDescriptor(window_sizes=(4,))
        with self.assertRaisesRegex(ValueError, "same shape"):
            chi_square_distance(np.zeros(2), np.zeros(3))


if __name__ == "__main__":
    unittest.main()
