from __future__ import annotations

import json
import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

import cv2 as cv
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_rpi import HybridCascade, route_after_quality  # noqa: E402
from lbph_config import SELECTED_DESCRIPTOR, inspect_lbph, make_lbph  # noqa: E402
from quality import QualityThresholds, compute_quality  # noqa: E402


class R3IntegrationTests(unittest.TestCase):
    def test_candidate_config_is_r3_and_candidate_only(self) -> None:
        config = json.loads((ROOT / "config" / "thresholds.json").read_text(encoding="utf-8"))
        self.assertEqual(config["status"], "candidate_only")
        self.assertEqual(config["lbph_descriptor"]["id"], "r3_n8_g6x6")
        self.assertEqual(config["gate"]["tau_accept"], 52.372394898355424)

    def test_paired_releases_share_upstream_cohort(self) -> None:
        manifests = []
        for enrollment_root in (ROOT / "enrollment" / "baseline-r1", ROOT / "enrollment"):
            pointer = json.loads((enrollment_root / "current.json").read_text(encoding="utf-8"))
            manifest_path = enrollment_root / pointer["release"] / "manifest.json"
            manifests.append(json.loads(manifest_path.read_text(encoding="utf-8")))
        self.assertEqual([manifest["samples"] for manifest in manifests], [360, 360])
        self.assertEqual(manifests[0]["identities"], manifests[1]["identities"])
        self.assertEqual(manifests[0]["selection"], manifests[1]["selection"])
        self.assertEqual(manifests[0]["selection"]["seed"], 42)
        self.assertEqual(manifests[0]["selection"]["samples_per_identity"], 10)

    def test_hardware_api_shape_matches_upstream_contract(self) -> None:
        constructor = inspect.signature(HybridCascade).parameters
        self.assertEqual(list(constructor)[0], "base_dir")
        self.assertIn("models_dir", constructor)
        self.assertEqual(inspect.signature(HybridCascade.infer).return_annotation, "list[dict]")

        script = ROOT / "ex-pc-detect.py"
        spec = importlib.util.spec_from_file_location("pc_detect_contract", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        self.assertEqual(module.normalize_results({"status": "accepted"}), [{"status": "accepted"}])
        self.assertEqual(module.normalize_results([]), [])

    def test_setup_logs_are_separate(self) -> None:
        script = ROOT / "ex-pc-detect.py"
        spec = importlib.util.spec_from_file_location("pc_detect_log_contract", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        old_log = module.SETUPS["1"]["log_file"]
        new_log = module.SETUPS["2"]["log_file"]
        self.assertNotEqual(old_log, new_log)
        self.assertEqual(old_log.name, "config1-old-r1.log")
        self.assertEqual(new_log.name, "config2-new-r3.log")

    def test_quality_route_bypasses_lbph(self) -> None:
        self.assertEqual(
            route_after_quality(True, None, tau_accept=52.0, tau_reject=140.0),
            "sface_quality",
        )

    def test_clear_quality_requires_lbph_distance(self) -> None:
        with self.assertRaises(ValueError):
            route_after_quality(False, None, tau_accept=52.0, tau_reject=140.0)
        self.assertEqual(route_after_quality(False, 40.0, 52.0, 140.0), "lbph_accept")
        self.assertEqual(route_after_quality(False, 80.0, 52.0, 140.0), "sface_ambiguous")
        self.assertEqual(route_after_quality(False, 150.0, 52.0, 140.0), "lbph_reject")

    def test_quality_probe_reports_trigger(self) -> None:
        report = compute_quality(
            gray_roi=np.full((100, 100), 80, dtype=np.uint8),
            landmarks=np.asarray([[30, 40], [70, 40], [50, 52], [35, 70], [65, 70]], dtype=np.float32),
            face_px=100,
            thresholds=QualityThresholds(tau_blur=1.0),
        )
        self.assertTrue(report.any_flag)
        self.assertIn("blur", report.active_flags)

    @unittest.skipUnless(hasattr(cv, "face"), "opencv-contrib-python required")
    def test_selected_constructor_serializes_expected_descriptor(self) -> None:
        recognizer = make_lbph(SELECTED_DESCRIPTOR)
        self.assertEqual(inspect_lbph(recognizer), SELECTED_DESCRIPTOR)


if __name__ == "__main__":
    unittest.main()
