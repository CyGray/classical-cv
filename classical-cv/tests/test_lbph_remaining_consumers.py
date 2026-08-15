from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2 as cv
import numpy as np

from src.classical_faces.lbph_config import DEPLOYED, SELECTED, create_lbph_recognizer
from src.classical_faces.pipeline import SPECS, load_recognizer
from src.hybrid.gate import LBPHThresholdCompatibilityError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS_PATH = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"


class LBPHRemainingConsumerTests(unittest.TestCase):
    @staticmethod
    def _write_model(path: Path, config) -> None:
        recognizer = create_lbph_recognizer(config)
        faces = [
            np.full((100, 100), value, dtype=np.uint8)
            for value in (32, 96, 160, 224)
        ]
        recognizer.train(faces, np.array([1, 1, 2, 2], dtype=np.int32))
        recognizer.write(str(path))

    def test_pipeline_loader_checks_serialized_lbph_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "deployed.yml"
            self._write_model(model_path, DEPLOYED)

            loaded = load_recognizer(
                SPECS["lbph"], str(model_path), expected_lbph_config=DEPLOYED
            )
            self.assertEqual(int(loaded.getGridX()), 8)
            with self.assertRaisesRegex(ValueError, r"must be retrained"):
                load_recognizer(
                    SPECS["lbph"], str(model_path), expected_lbph_config=SELECTED
                )

    def test_priority_runners_expose_lbph_config_selector(self) -> None:
        modules = (
            "src.lbph.independence_test",
            "src.hybrid.independence_test",
            "scripts.pipeline.lfw_all_families_verify",
            "scripts.pipeline.sweep_gate_curve",
            "scripts.pipeline.tau_reject_tradeoff_curve",
            "scripts.pipeline.derive_hybrid_sface_threshold",
        )
        for module_name in modules:
            module = importlib.import_module(module_name)
            with self.subTest(module=module_name), patch.object(
                sys, "argv", [module_name, "--lbph-config", "selected"]
            ):
                self.assertEqual(module.parse_args().lbph_config, "selected")

    def test_selected_descriptor_rejects_current_threshold_file_before_runner_work(self) -> None:
        checks = (
            ("scripts.pipeline.lfw_all_families_verify", "main"),
            ("scripts.pipeline.sweep_gate_curve", "main"),
            ("scripts.pipeline.tau_reject_tradeoff_curve", "main"),
            ("scripts.pipeline.derive_hybrid_sface_threshold", "main"),
        )
        for module_name, entrypoint in checks:
            module = importlib.import_module(module_name)
            with self.subTest(module=module_name), patch.object(
                sys,
                "argv",
                [
                    module_name,
                    "--lbph-config",
                    "selected",
                    "--thresholds-json",
                    str(THRESHOLDS_PATH),
                ],
            ):
                with self.assertRaises(LBPHThresholdCompatibilityError):
                    getattr(module, entrypoint)()


if __name__ == "__main__":
    unittest.main()
