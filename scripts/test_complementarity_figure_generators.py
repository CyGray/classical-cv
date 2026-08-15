"""Regression checks for the canonical complementarity manuscript figures.

Run with:
    python -m unittest scripts.test_complementarity_figure_generators
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.generate_complementarity_figures import regenerate, verify_existing
from scripts.visualization.complementarity_contract import (
    CanonicalComplementarityError,
    RECOVERY_SOURCE_RELATIVE,
    verify_canonical_source,
)
from scripts.visualization.generate_recovery_rate_donut import DEFAULT_INPUT


class CanonicalComplementarityFigureTests(unittest.TestCase):
    """Ensure the approved root entry point remains provenance-safe and repeatable."""

    def test_root_generator_is_byte_repeatable_and_svg_editable(self) -> None:
        with TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            regenerate(output_dir, verify_repeatability=True)
            verify_existing(output_dir)
            self.assertEqual(
                {
                    path.name
                    for path in output_dir.iterdir()
                    if path.suffix.lower() == ".svg"
                },
                {
                    "fig_recovery_rate_donut.svg",
                    "fig_gate_competence_stacked_bars.svg",
                },
            )

    def test_recovery_generator_rejects_a_noncanonical_source_path(self) -> None:
        with self.assertRaises(CanonicalComplementarityError):
            verify_canonical_source(Path(__file__), RECOVERY_SOURCE_RELATIVE)
        self.assertTrue(DEFAULT_INPUT.is_file())


if __name__ == "__main__":
    unittest.main()
