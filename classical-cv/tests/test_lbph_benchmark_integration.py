from __future__ import annotations

import csv
import json
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class _FakeLBPHConfig:
    config_id: str
    radius: int
    neighbors: int
    grid_x: int
    grid_y: int


class LBPHBenchmarkIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The central worker module is intentionally not part of this scoped
        # patch yet. Inject the planned API shape so these tests stay focused
        # on selector/cache/resume behavior and never touch a dataset/model.
        cls.deployed = _FakeLBPHConfig("r1_n8_g8x8", 1, 8, 8, 8)
        cls.selected = _FakeLBPHConfig("r3_n8_g6x6", 3, 8, 6, 6)
        fake_module = types.ModuleType("src.classical_faces.lbph_config")
        fake_module.DEPLOYED_LBPH_CONFIG = cls.deployed
        fake_module.SELECTED_LBPH_CONFIG = cls.selected
        fake_module.ACTIVE_LBPH_CONFIG = cls.deployed
        fake_module.create_lbph_recognizer = lambda config: ("recognizer", config)
        cls._module_key = "src.classical_faces.lbph_config"
        cls._previous_module = sys.modules.get(cls._module_key)
        sys.modules[cls._module_key] = fake_module

        from src import independence_common
        from scripts.pipeline import run_lfw2_robustness

        cls.common = independence_common
        cls.harness = run_lfw2_robustness

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._previous_module is None:
            sys.modules.pop(cls._module_key, None)
        else:
            sys.modules[cls._module_key] = cls._previous_module

    def test_selector_defaults_to_active_and_resolves_selected_id(self) -> None:
        self.assertEqual(
            self.common.lbph_config_metadata(self.common.resolve_lbph_config())["id"],
            "r1_n8_g8x8",
        )
        selected = self.common.resolve_lbph_config("r3_n8_g6x6")
        self.assertEqual(self.common.lbph_config_metadata(selected)["grid_x"], 6)
        self.assertEqual(
            self.common.lbph_config_metadata("r3_n8_g6x6")["radius"], 3
        )
        self.assertEqual(
            self.common.create_lbph_recognizer_for_config(selected),
            ("recognizer", self.selected),
        )

    def test_enrollment_cache_paths_are_descriptor_keyed(self) -> None:
        paths, manifest, metadata = self.harness.enrollment_cache_paths(
            42, "abcdef0123456789", False, self.selected
        )
        self.assertEqual(metadata["id"], "r3_n8_g6x6")
        self.assertIn("r3_n8_g6x6", manifest.name)
        self.assertIn("r3_n8_g6x6", paths["lbph_model"].name)
        self.assertNotEqual(
            paths["lbph_model"].name,
            self.harness.enrollment_cache_paths(
                42, "abcdef0123456789", False, self.deployed
            )[0]["lbph_model"].name,
        )

    def test_segment_resume_rejects_legacy_or_wrong_descriptor_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            seg_json = root / "segment.json"
            seg_csv = root / "segment.csv"

            seg_json.write_text(json.dumps({"parseable": True}), encoding="utf-8")
            seg_csv.write_text("modification\nclean\n", encoding="utf-8")
            self.assertFalse(
                self.harness.segment_outputs_match(seg_json, seg_csv, "r3_n8_g6x6")
            )

            seg_json.write_text(
                json.dumps({"lbph_config": {"id": "r3_n8_g6x6"}}),
                encoding="utf-8",
            )
            with seg_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["lbph_config_id"])
                writer.writeheader()
                writer.writerow({"lbph_config_id": "r1_n8_g8x8"})
            self.assertFalse(
                self.harness.segment_outputs_match(seg_json, seg_csv, "r3_n8_g6x6")
            )

            with seg_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["lbph_config_id"])
                writer.writeheader()
                writer.writerow({"lbph_config_id": "r3_n8_g6x6"})
            self.assertTrue(
                self.harness.segment_outputs_match(seg_json, seg_csv, "r3_n8_g6x6")
            )


if __name__ == "__main__":
    unittest.main()
