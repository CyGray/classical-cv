from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.hybrid.gate import (
    DEPLOYED_LBPH_DESCRIPTOR,
    LBPHThresholdCompatibilityError,
    descriptor_metadata,
    load_thresholds,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS_PATH = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"
SELECTED_LBPH_DESCRIPTOR = {
    "id": "r3_n8_g6x6",
    "params": {"radius": 3, "neighbors": 8, "grid_x": 6, "grid_y": 6},
}


class LBPHThresholdCompatibilityTests(unittest.TestCase):
    def test_deployed_descriptor_matches_threshold_file(self) -> None:
        thresholds = load_thresholds(
            THRESHOLDS_PATH,
            expected_lbph_config=DEPLOYED_LBPH_DESCRIPTOR,
        )

        self.assertEqual(thresholds["lbph_descriptor"], DEPLOYED_LBPH_DESCRIPTOR)

    def test_selected_descriptor_fails_against_deployed_threshold_file(self) -> None:
        with self.assertRaisesRegex(
            LBPHThresholdCompatibilityError,
            r"descriptor mismatch.*r1_n8_g8x8.*r3_n8_g6x6",
        ):
            load_thresholds(
                THRESHOLDS_PATH,
                expected_lbph_config=SELECTED_LBPH_DESCRIPTOR,
            )

    def test_missing_metadata_is_backward_compatible_only_without_validation(self) -> None:
        thresholds = load_thresholds(THRESHOLDS_PATH)
        thresholds.pop("lbph_descriptor")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "thresholds.json"
            path.write_text(json.dumps(thresholds), encoding="utf-8")

            self.assertEqual(load_thresholds(path)["gate"], thresholds["gate"])
            with self.assertRaisesRegex(
                LBPHThresholdCompatibilityError,
                r"missing lbph_descriptor metadata.*r1_n8_g8x8",
            ):
                load_thresholds(path, expected_lbph_config=DEPLOYED_LBPH_DESCRIPTOR)

    def test_numeric_thresholds_are_unchanged(self) -> None:
        thresholds = load_thresholds(THRESHOLDS_PATH)

        self.assertEqual(
            thresholds["gate"],
            {
                "tau_accept": 67.03325520645528,
                "tau_reject": 140.13,
                "margin_min": 0.05,
            },
        )
        self.assertEqual(
            thresholds["quality"],
            {
                "tau_blur": 587.83,
                "luma_lo": 52.88,
                "luma_hi": 137.71,
                "tau_noise": 8.206,
                "tau_pose": 63.74,
                "px_min": 61,
            },
        )
        self.assertEqual(
            thresholds["lbph_far_anchors"],
            [[0.0, 0.0], [67.03325520645528, 0.0001], [88.4927, 0.01], [200.0, 1.0]],
        )
        self.assertEqual(
            thresholds["sface"],
            {
                "cosine_genuine": 0.363,
                "l2_genuine": 1.0313,
                "cosine_operating": 0.4144,
                "cosine_operating_1pct": 0.2883,
            },
        )

    def test_calibrator_refuses_selected_active_descriptor(self) -> None:
        from src.hybrid import calibrate

        with patch.object(calibrate, "active_lbph_descriptor", return_value=SELECTED_LBPH_DESCRIPTOR), \
             patch.object(calibrate, "deployed_lbph_descriptor", return_value=DEPLOYED_LBPH_DESCRIPTOR):
            with self.assertRaisesRegex(RuntimeError, r"ACTIVE LBPH descriptor r3_n8_g6x6"):
                calibrate.ensure_deployed_lbph_calibration()

    def test_gate_does_not_apply_deployed_fallback_to_selected_file(self) -> None:
        from src.hybrid import gate

        thresholds = load_thresholds(THRESHOLDS_PATH)
        thresholds["lbph_descriptor"] = SELECTED_LBPH_DESCRIPTOR
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "thresholds.json"
            path.write_text(json.dumps(thresholds), encoding="utf-8")
            with patch.object(gate, "_THRESHOLDS_JSON", path):
                gate._frozen_gate_defaults.cache_clear()
                try:
                    with self.assertRaisesRegex(
                        LBPHThresholdCompatibilityError,
                        r"descriptor mismatch.*r3_n8_g6x6.*r1_n8_g8x8",
                    ):
                        gate.GateThresholds()
                finally:
                    gate._frozen_gate_defaults.cache_clear()

    def test_descriptor_metadata_normalizes_central_config_shape(self) -> None:
        class CentralConfig:
            config_id = "r3_n8_g6x6"

            def to_dict(self):
                return {
                    "config_id": self.config_id,
                    "radius": 3,
                    "neighbors": 8,
                    "grid_x": 6,
                    "grid_y": 6,
                }

        self.assertEqual(descriptor_metadata(CentralConfig()), SELECTED_LBPH_DESCRIPTOR)


if __name__ == "__main__":
    unittest.main()
