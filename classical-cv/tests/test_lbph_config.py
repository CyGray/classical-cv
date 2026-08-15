from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from src.classical_faces.lbph_config import (
    ACTIVE_LBPH_CONFIG,
    DEPLOYED_LBPH_CONFIG,
    SELECTED_LBPH_CONFIG,
    create_lbph_recognizer,
)
from src.hybrid import recognizer as recognizer_module
from src.hybrid.recognizer import LBPHAdapter


class LBPHConfigTests(unittest.TestCase):
    @staticmethod
    def _write_model(path: Path, config) -> None:
        model = create_lbph_recognizer(config)
        images = [
            np.full((100, 100), value, dtype=np.uint8)
            for value in (40, 80, 160, 220)
        ]
        model.train(images, np.array([1, 1, 2, 2], dtype=np.int32))
        model.write(str(path))

    @staticmethod
    def _write_labels(path: Path) -> None:
        path.write_text('{"one": 1, "two": 2}', encoding="utf-8")

    def test_profiles_are_immutable_serializable_and_have_expected_sizes(self):
        self.assertIs(ACTIVE_LBPH_CONFIG, DEPLOYED_LBPH_CONFIG)
        self.assertEqual(DEPLOYED_LBPH_CONFIG.id, DEPLOYED_LBPH_CONFIG.token)
        self.assertEqual(DEPLOYED_LBPH_CONFIG.id, "r1_n8_g8x8")
        self.assertEqual(DEPLOYED_LBPH_CONFIG.descriptor_bytes, 65536)
        self.assertEqual(SELECTED_LBPH_CONFIG.descriptor_bytes, 36864)
        self.assertEqual(DEPLOYED_LBPH_CONFIG.to_dict()["radius"], 1)
        with self.assertRaises(AttributeError):
            DEPLOYED_LBPH_CONFIG.radius = 2

    def test_yaml_round_trip_and_matching_validation(self):
        for config in (DEPLOYED_LBPH_CONFIG, SELECTED_LBPH_CONFIG):
            with self.subTest(config=config.id), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                model_path = root / f"{config.id}.yml"
                labels_path = root / "labels.json"
                self._write_model(model_path, config)
                self._write_labels(labels_path)

                adapter = LBPHAdapter(
                    model_path=str(model_path),
                    labels_path=str(labels_path),
                    lbph_config=config,
                )
                self.assertIs(adapter.lbph_config, config)
                self.assertEqual(adapter.recognizer.getRadius(), config.radius)
                self.assertEqual(adapter.recognizer.getNeighbors(), config.neighbors)
                self.assertEqual(adapter.recognizer.getGridX(), config.grid_x)
                self.assertEqual(adapter.recognizer.getGridY(), config.grid_y)

    def test_old_model_rejected_when_selected_descriptor_expected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_path = root / "old.yml"
            labels_path = root / "labels.json"
            self._write_model(model_path, DEPLOYED_LBPH_CONFIG)
            self._write_labels(labels_path)

            with self.assertRaisesRegex(ValueError, r"retrained.*requested descriptor"):
                LBPHAdapter(
                    model_path=str(model_path),
                    labels_path=str(labels_path),
                    lbph_config=SELECTED_LBPH_CONFIG,
                )

    def test_threshold_loader_receives_explicit_config(self):
        calls = []

        def fake_load(path, **kwargs):
            calls.append((path, kwargs))
            return {"gate": {}, "quality": {}}

        with patch.object(recognizer_module, "load_thresholds", fake_load):
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                model_path = root / "model.yml"
                labels_path = root / "labels.json"
                self._write_model(model_path, SELECTED_LBPH_CONFIG)
                self._write_labels(labels_path)
                recognizer_module.build_hybrid(
                    mode="cv_only",
                    thresholds_path="thresholds.yml",
                    lbph_model=str(model_path),
                    lbph_labels=str(labels_path),
                    require_sface=False,
                    lbph_config=SELECTED_LBPH_CONFIG,
                )

        self.assertEqual(
            calls,
            [("thresholds.yml", {"expected_lbph_config": SELECTED_LBPH_CONFIG})],
        )


if __name__ == "__main__":
    unittest.main()
