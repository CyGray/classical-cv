"""Focused serialization checks for the staged Pi LBPH descriptor rollout."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2 as cv
import numpy as np


PORTING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORTING_ROOT))

from lbph_config import (  # noqa: E402
    DEPLOYED_DESCRIPTOR,
    SELECTED_DESCRIPTOR,
    descriptor_from_mapping,
    inspect_lbph,
    make_lbph,
    release_descriptor_from_manifest,
    validate_loaded_lbph,
)


class LBPHDescriptorConfigTests(unittest.TestCase):
    @staticmethod
    def _tiny_faces() -> tuple[list[np.ndarray], np.ndarray]:
        rows = np.arange(100, dtype=np.uint8)
        cols = rows[:, None]
        faces = [
            np.tile(rows, (100, 1)),
            np.tile(rows[::-1], (100, 1)),
            np.tile(cols, (1, 100)),
            np.tile(cols[::-1], (1, 100)),
        ]
        return faces, np.asarray([0, 0, 1, 1], dtype=np.int32)

    @staticmethod
    def _write_model(path: Path, descriptor) -> None:
        faces, labels = LBPHDescriptorConfigTests._tiny_faces()
        recognizer = make_lbph(descriptor)
        recognizer.train(faces, labels)
        recognizer.save(str(path))

    def test_threshold_metadata_is_deployed_profile(self) -> None:
        thresholds_path = PORTING_ROOT / "config" / "thresholds.json"
        payload = json.loads(thresholds_path.read_text(encoding="utf-8"))
        descriptor = descriptor_from_mapping(
            payload["lbph_descriptor"], source=str(thresholds_path)
        )
        self.assertEqual(descriptor, DEPLOYED_DESCRIPTOR)
        self.assertEqual(payload["lbph_descriptor"]["selected_candidate_id"], "r3_n8_g6x6")

    def test_read_restores_old_model_and_matching_validation_passes(self) -> None:
        with TemporaryDirectory() as directory:
            model_path = Path(directory) / "old_r1_n8_g8x8.yml"
            self._write_model(model_path, DEPLOYED_DESCRIPTOR)

            # Deliberately use the selected constructor. read() must override
            # it with the serialized old profile.
            loaded = make_lbph(SELECTED_DESCRIPTOR)
            loaded.read(str(model_path))

            self.assertEqual(inspect_lbph(loaded), DEPLOYED_DESCRIPTOR)
            validate_loaded_lbph(
                loaded, DEPLOYED_DESCRIPTOR, context="temporary old model"
            )
            with self.assertRaisesRegex(RuntimeError, "descriptor mismatch"):
                validate_loaded_lbph(
                    loaded, SELECTED_DESCRIPTOR, context="temporary old model"
                )

    def test_read_restores_selected_model_and_matching_validation_passes(self) -> None:
        with TemporaryDirectory() as directory:
            model_path = Path(directory) / "new_r3_n8_g6x6.yml"
            self._write_model(model_path, SELECTED_DESCRIPTOR)

            # Deliberately use the deployed constructor. The serialized
            # candidate profile must still be observed after read().
            loaded = make_lbph(DEPLOYED_DESCRIPTOR)
            loaded.read(str(model_path))

            self.assertEqual(inspect_lbph(loaded), SELECTED_DESCRIPTOR)
            validate_loaded_lbph(
                loaded, SELECTED_DESCRIPTOR, context="temporary new model"
            )
            with self.assertRaisesRegex(RuntimeError, "descriptor mismatch"):
                validate_loaded_lbph(
                    loaded, DEPLOYED_DESCRIPTOR, context="temporary new model"
                )

    def test_legacy_manifest_with_matching_old_model_is_accepted(self) -> None:
        with TemporaryDirectory() as directory:
            model_path = Path(directory) / "legacy_r1_n8_g8x8.yml"
            self._write_model(model_path, DEPLOYED_DESCRIPTOR)

            legacy_manifest = {
                "created_utc": "2026-08-09T06:49:39Z",
                "samples": 28,
                "parity": "same central rows rebuild both engines",
            }
            expected, is_legacy = release_descriptor_from_manifest(
                legacy_manifest,
                DEPLOYED_DESCRIPTOR,
                source="temporary legacy manifest",
            )
            self.assertTrue(is_legacy)
            self.assertEqual(expected, DEPLOYED_DESCRIPTOR)

            loaded = make_lbph(SELECTED_DESCRIPTOR)
            loaded.read(str(model_path))
            validate_loaded_lbph(
                loaded,
                expected,
                context="legacy manifest with matching old model",
            )


if __name__ == "__main__":
    unittest.main()
