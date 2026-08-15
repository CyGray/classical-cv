from __future__ import annotations

import unittest

import numpy as np

from src.benchmark.hog_descriptor import (
    HOG_VARIANTS,
    STANDARD_HOG,
    HOGDescriptor,
    cosine_distance,
    euclidean_distance,
)


def _pattern_image() -> np.ndarray:
    y, x = np.mgrid[0:100, 0:100]
    image = (
        85.0
        + 0.7 * x
        + 0.25 * y
        + 30.0 * np.sin(x / 6.0)
        + 24.0 * np.cos(y / 9.0)
    )
    return np.clip(image, 0, 255).astype(np.uint8)


class HOGDescriptorTests(unittest.TestCase):
    def test_default_geometry_shape_dtype_and_determinism(self) -> None:
        first = STANDARD_HOG.extract(_pattern_image())
        second = STANDARD_HOG.extract(_pattern_image().copy())

        self.assertEqual(STANDARD_HOG.name, "hog")
        self.assertEqual(STANDARD_HOG.descriptor_length, 2_916)
        self.assertEqual(STANDARD_HOG.descriptor_bytes, 11_664)
        self.assertEqual(first.shape, (STANDARD_HOG.descriptor_length,))
        self.assertEqual(first.dtype, np.float32)
        self.assertEqual(first.nbytes, STANDARD_HOG.descriptor_bytes)
        self.assertTrue(first.flags.c_contiguous)
        self.assertTrue(np.isfinite(first).all())
        np.testing.assert_array_equal(first, second)

    def test_cosine_distance_is_zero_symmetric_and_non_negative(self) -> None:
        first = STANDARD_HOG.extract(_pattern_image())
        second = STANDARD_HOG.extract(np.roll(_pattern_image(), shift=4, axis=1))

        self.assertAlmostEqual(cosine_distance(first, first), 0.0, places=12)
        forward = cosine_distance(first, second)
        backward = cosine_distance(second, first)
        self.assertGreater(forward, 0.0)
        np.testing.assert_allclose(forward, backward, rtol=1e-12, atol=1e-12)
        self.assertAlmostEqual(STANDARD_HOG.distance(first, second), forward, places=12)

    def test_zero_vector_cosine_distance_is_defined(self) -> None:
        zero = np.zeros(STANDARD_HOG.descriptor_length, dtype=np.float32)
        nonzero = np.ones(STANDARD_HOG.descriptor_length, dtype=np.float32)

        self.assertEqual(cosine_distance(zero, zero), 0.0)
        self.assertEqual(cosine_distance(zero, nonzero), 1.0)

    def test_euclidean_variant_uses_the_same_descriptor_contract(self) -> None:
        variant = HOGDescriptor(distance_metric="euclidean")
        first = variant.extract(_pattern_image())
        second = variant.extract(np.roll(_pattern_image(), shift=2, axis=0))

        self.assertEqual(variant.name, "hog_euclidean")
        self.assertAlmostEqual(
            variant.distance(first, second), euclidean_distance(first, second)
        )
        self.assertGreater(variant.distance(first, second), 0.0)

    def test_registry_and_metadata_are_harness_ready(self) -> None:
        self.assertEqual(HOG_VARIANTS, {"hog": STANDARD_HOG})
        params = STANDARD_HOG.params
        self.assertEqual(params["algorithm"], "histogram_of_oriented_gradients")
        self.assertEqual(params["distance"], "cosine")
        self.assertEqual(params["cell_size"], [10, 10])
        self.assertEqual(params["block_cells"], [2, 2])
        self.assertEqual(params["descriptor_bytes"], 11_664)
        self.assertEqual(params["static_state_bytes"], 0)

    def test_invalid_images_fail_loudly_without_resizing(self) -> None:
        cases = (
            (np.zeros((100, 100, 3), dtype=np.uint8), "2-D grayscale"),
            (np.zeros((96, 96), dtype=np.uint8), "does not resize"),
            (np.full((100, 100), np.nan, dtype=np.float32), "finite"),
            (np.full((100, 100), 256.0, dtype=np.float32), "0..255"),
        )
        for image, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    STANDARD_HOG.extract(image)

    def test_invalid_geometry_and_match_shapes_fail_loudly(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer number of HOG cells"):
            HOGDescriptor(win_size=(99, 100))
        with self.assertRaisesRegex(ValueError, "divisible by block_stride"):
            HOGDescriptor(block_cells=(3, 3), block_stride_cells=(2, 2))
        with self.assertRaisesRegex(ValueError, "descriptors with shape"):
            STANDARD_HOG.distance(np.zeros(2), np.zeros(2))


if __name__ == "__main__":
    unittest.main()
