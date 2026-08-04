"""Regression tests for Complementarity Test 4(a) and 4(b)."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

from src.stats_utils import mcnemar_test


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MERGE_PATH = PROJECT_ROOT / "scripts" / "utils" / "merge_robustness_segments.py"
SPEC = importlib.util.spec_from_file_location("merge_robustness_segments", MERGE_PATH)
assert SPEC and SPEC.loader
MERGE = importlib.util.module_from_spec(SPEC)
# The A/B merge helpers do not need image transforms. Stub that module so this
# standard-library test remains runnable on machines without OpenCV installed.
MODIFICATIONS = types.ModuleType("src.benchmark.modifications")
MODIFICATIONS.DL41_DETECTOR_CANONICAL = frozenset()
MODIFICATIONS.get_modification_set = lambda _name: ([], 0)
_original_modifications = sys.modules.get("src.benchmark.modifications")
sys.modules["src.benchmark.modifications"] = MODIFICATIONS
try:
    SPEC.loader.exec_module(MERGE)
finally:
    if _original_modifications is None:
        del sys.modules["src.benchmark.modifications"]
    else:
        sys.modules["src.benchmark.modifications"] = _original_modifications


def _stat(w: int, x: int, y: int, z: int) -> dict:
    return {"probes": w + x + y + z, "table": {
        "both_right": w,
        "cv_only_right": x,
        "dl_only_right": y,
        "both_wrong": z,
    }}


def _payload(clean: dict, overall: dict, per_modification: dict | None = None) -> dict:
    per_modification = per_modification or {"mod_a": overall}
    return {"complementarity_battery": {
        "clean": clean,
        "overall_modified": overall,
        "per_modification": [
            {"modification": name, **stats}
            for name, stats in per_modification.items()
        ],
    }}


class McNemarTest(unittest.TestCase):
    def test_symmetric_discordant_counts_support_the_null(self) -> None:
        result = mcnemar_test(5, 5)
        self.assertFalse(result["degenerate"])
        self.assertEqual(result["statistic"], 0.0)
        self.assertEqual(result["p_chi2"], 1.0)
        self.assertEqual(result["p_exact"], 1.0)

    def test_no_discordant_pairs_is_degenerate(self) -> None:
        result = mcnemar_test(0, 0)
        self.assertTrue(result["degenerate"])
        self.assertIsNone(result["p_exact"])


class ComplementarityMergeTest(unittest.TestCase):
    def test_segment_tables_are_summed_before_rates_and_test(self) -> None:
        merged = MERGE._merge_complementarity_battery(
            [
                _payload(_stat(2, 1, 3, 4), _stat(10, 1, 4, 5)),
                _payload(_stat(3, 2, 5, 1), _stat(20, 2, 6, 2)),
            ],
            [("mod_a", None, [])],
        )

        overall = merged["overall_modified"]
        self.assertEqual(overall["table"], {
            "both_right": 30,
            "cv_only_right": 3,
            "dl_only_right": 10,
            "both_wrong": 7,
        })
        self.assertEqual(overall["probes"], 50)
        self.assertEqual(overall["recovery_rate_ci95"]["count"], 10)
        self.assertEqual(overall["recovery_rate_ci95"]["trials"], 17)
        self.assertAlmostEqual(overall["recovery_rate_ci95"]["percent"], 1000 / 17, places=10)
        self.assertEqual(overall["mcnemar"]["b"], 3)
        self.assertEqual(overall["mcnemar"]["c"], 10)

    def test_missing_battery_hard_fails(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "complementarity_battery"):
            MERGE._merge_complementarity_battery([{}], [("mod_a", None, [])])


if __name__ == "__main__":
    unittest.main()
