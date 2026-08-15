"""Focused checks for staged LBPH enrollment provenance.

These tests intentionally skip until the core worker's
``src.classical_faces.lbph_config`` module is present.  They never touch a
dataset or the repository's model/cache directories.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np


class TestLBPHEnrollmentConfig(unittest.TestCase):
    def _configs(self):
        from src.independence_common import resolve_lbph_config

        try:
            deployed = resolve_lbph_config("deployed")
            selected = resolve_lbph_config("selected")
        except (RuntimeError, ModuleNotFoundError, AttributeError) as exc:
            self.skipTest(f"central LBPH config API not available yet: {exc}")
        return deployed, selected

    def test_staged_config_metadata_is_stable(self):
        from src.independence_common import lbph_config_metadata

        deployed, selected = self._configs()
        deployed_meta = lbph_config_metadata(deployed)
        selected_meta = lbph_config_metadata(selected)

        self.assertEqual(deployed_meta["id"], "r1_n8_g8x8")
        self.assertEqual(selected_meta["id"], "r3_n8_g6x6")
        self.assertEqual((deployed_meta["grid_x"], deployed_meta["grid_y"]), (8, 8))
        self.assertEqual((selected_meta["grid_x"], selected_meta["grid_y"]), (6, 6))
        self.assertNotEqual(deployed_meta, selected_meta)
        self.assertEqual(json.loads(json.dumps(deployed_meta)), deployed_meta)

    def test_serialized_model_parameters_are_checked_after_read(self):
        from src.independence_common import (
            create_lbph_recognizer_for_config,
            lbph_config_metadata,
        )
        from src.lbph.detect import validate_loaded_lbph_model

        deployed, selected = self._configs()
        try:
            import cv2  # noqa: F401
        except ModuleNotFoundError as exc:
            self.skipTest(f"OpenCV unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "lbph.yml"
            recognizer = create_lbph_recognizer_for_config(deployed)
            faces = [
                np.zeros((100, 100), dtype=np.uint8),
                np.full((100, 100), 255, dtype=np.uint8),
            ]
            recognizer.train(faces, np.array([0, 1], dtype=np.int32))
            recognizer.save(str(model_path))

            loaded = create_lbph_recognizer_for_config(deployed)
            loaded.read(str(model_path))
            validate_loaded_lbph_model(str(model_path), loaded, lbph_config_metadata(deployed))

            with self.assertRaises(RuntimeError):
                validate_loaded_lbph_model(
                    str(model_path), loaded, lbph_config_metadata(selected)
                )


if __name__ == "__main__":
    unittest.main()
