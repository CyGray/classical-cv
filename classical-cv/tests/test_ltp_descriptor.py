from __future__ import annotations

import unittest

import numpy as np

from src.benchmark.ltp_descriptor import (
    LTP_VARIANTS,
    STANDARD_LTP,
    TAN_TRIGGS_LTP,
    LTPDescriptor,
    _split_ltp_codes,
    chi_square_distance,
)


def _pattern_image() -> np.ndarray:
    y, x = np.mgrid[0:100, 0:100]
    image = (
        80.0
        + 0.8 * x
        + 0.4 * y
        + 35.0 * np.sin(x / 7.0)
        + 20.0 * np.cos(y / 11.0)
    )
    return np.clip(image, 0, 255).astype(np.uint8)


class LTPDescriptorTests(unittest.TestCase):
    def test_split_codes_have_documented_bit_order_and_threshold_edges(self) -> None:
        image = np.array(
            [
                [110, 94, 103],
                [0, 100, 105],
                [106, 100, 95],
            ],
            dtype=np.uint8,
        )

        positive, negative = _split_ltp_codes(image, threshold=5.0, radius=1)

        self.assertEqual(positive.shape, (1, 1))
        self.assertEqual(negative.shape, (1, 1))
        self.assertEqual(int(positive[0, 0]), (1 << 0) | (1 << 3) | (1 << 6))
        self.assertEqual(int(negative[0, 0]), (1 << 1) | (1 << 4) | (1 << 7))

    def test_descriptor_shape_dtype_normalization_and_determinism(self) -> None:
        image = _pattern_image()
        for variant in (STANDARD_LTP, TAN_TRIGGS_LTP):
            with self.subTest(variant=variant.name):
                first = variant.extract(image)
                second = variant.extract(image.copy())

                self.assertEqual(first.dtype, np.float32)
                self.assertEqual(first.shape, (variant.descriptor_length,))
                self.assertEqual(first.nbytes, variant.descriptor_bytes)
                self.assertEqual(variant.descriptor_bytes, 131_072)
                np.testing.assert_array_equal(first, second)
                cell_halves = first.reshape(variant.grid_y * variant.grid_x, 2, 256)
                np.testing.assert_allclose(cell_halves.sum(axis=2), 1.0, atol=1e-7)

    def test_chi_square_distance_is_zero_symmetric_and_non_negative(self) -> None:
        first = STANDARD_LTP.extract(_pattern_image())
        second_image = np.roll(_pattern_image(), shift=3, axis=1)
        second = STANDARD_LTP.extract(second_image)

        self.assertAlmostEqual(chi_square_distance(first, first), 0.0, places=12)
        forward = chi_square_distance(first, second)
        backward = chi_square_distance(second, first)
        self.assertGreater(forward, 0.0)
        np.testing.assert_allclose(forward, backward, rtol=1e-12, atol=1e-12)
        self.assertAlmostEqual(STANDARD_LTP.distance(first, second), forward, places=12)

    def test_registry_and_metadata_are_harness_ready(self) -> None:
        self.assertEqual(set(LTP_VARIANTS), {"ltp", "tan_triggs_ltp"})
        self.assertIsNone(STANDARD_LTP.params["intrinsic_preprocessing"])
        tan_triggs = TAN_TRIGGS_LTP.params["intrinsic_preprocessing"]
        self.assertIsInstance(tan_triggs, dict)
        assert isinstance(tan_triggs, dict)
        self.assertTrue(tan_triggs["implementation"].endswith("tan_triggs_normalize"))
        self.assertEqual(STANDARD_LTP.params["neighbors"], 8)
        self.assertEqual(
            STANDARD_LTP.params["distance"], "symmetric_chi_square_half_sum"
        )

    def test_invalid_images_fail_loudly(self) -> None:
        cases = (
            (np.zeros((10, 10, 3), dtype=np.uint8), "2-D grayscale"),
            (np.full((10, 10), np.nan, dtype=np.float32), "NaN or infinite"),
            (np.full((10, 10), 256.0, dtype=np.float32), "0..255"),
        )
        for image, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    STANDARD_LTP.extract(image)

    def test_grid_larger_than_code_image_fails_loudly(self) -> None:
        descriptor = LTPDescriptor(grid_x=8, grid_y=8)
        with self.assertRaisesRegex(
            ValueError, "smaller than the requested spatial grid"
        ):
            descriptor.extract(np.zeros((9, 9), dtype=np.uint8))

    def test_distance_rejects_mismatched_or_negative_histograms(self) -> None:
        with self.assertRaisesRegex(ValueError, "shapes differ"):
            chi_square_distance(np.zeros(2), np.zeros(3))
        with self.assertRaisesRegex(ValueError, "non-negative"):
            chi_square_distance(np.array([0.0, -1.0]), np.zeros(2))


if __name__ == "__main__":
    unittest.main()
