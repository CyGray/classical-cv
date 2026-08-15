"""Regenerate the two canonical LSDB-DL41 complementarity manuscript figures.

This root-level entry point is the approved manuscript route for the recovery
rate and gate-competence SVGs.  It verifies each input against both the
results manifest and the campaign run-provenance record before drawing, then
checks that each finished SVG remains editable and source-linked.

Examples
--------
python -m scripts.generate_complementarity_figures
python -m scripts.generate_complementarity_figures --verify-only
python -m scripts.generate_complementarity_figures --verify-repeatability
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from scripts.visualization.complementarity_contract import (
    CanonicalSource,
    GATE_SOURCE_RELATIVE,
    RECOVERY_SOURCE_RELATIVE,
    WORKSPACE_ROOT,
    sha256_file,
    verify_canonical_source,
    verify_editable_svg,
)
from scripts.visualization.generate_gate_competence_stacked_bars import (
    DEFAULT_INPUT as GATE_INPUT,
    DEFAULT_OUTPUT as GATE_OUTPUT,
    REQUIRED_SVG_TEXT as GATE_REQUIRED_SVG_TEXT,
    load_routing,
    render_figure as render_gate_figure,
)
from scripts.visualization.generate_recovery_rate_donut import (
    DEFAULT_INPUT as RECOVERY_INPUT,
    DEFAULT_OUTPUT as RECOVERY_OUTPUT,
    REQUIRED_SVG_TEXT as RECOVERY_REQUIRED_SVG_TEXT,
    load_counts,
    render_figure as render_recovery_figure,
)


DEFAULT_OUTPUT_DIR = WORKSPACE_ROOT / "docs" / "manuscript" / "figures"


@dataclass(frozen=True)
class FigureSpec:
    """One canonical source-to-SVG rendering contract."""

    name: str
    source_path: Path
    source_relative_path: str
    output_name: str
    required_svg_text: tuple[str, ...]
    renderer: Callable[[Path, Path], Path]


def figure_specs(output_dir: Path) -> tuple[FigureSpec, FigureSpec]:
    """Return the two approved figure contracts for a chosen output directory."""

    return (
        FigureSpec(
            name="recovery rate",
            source_path=RECOVERY_INPUT,
            source_relative_path=RECOVERY_SOURCE_RELATIVE,
            output_name=RECOVERY_OUTPUT.name,
            required_svg_text=RECOVERY_REQUIRED_SVG_TEXT,
            renderer=render_recovery_figure,
        ),
        FigureSpec(
            name="gate competence",
            source_path=GATE_INPUT,
            source_relative_path=GATE_SOURCE_RELATIVE,
            output_name=GATE_OUTPUT.name,
            required_svg_text=GATE_REQUIRED_SVG_TEXT,
            renderer=render_gate_figure,
        ),
    )


def verify_existing(output_dir: Path) -> None:
    """Verify canonical evidence, count contracts, and existing SVG assets."""

    for spec in figure_specs(output_dir):
        source = _verify_source_and_counts(spec)
        verify_editable_svg(
            output_dir / spec.output_name,
            source=source,
            required_text=spec.required_svg_text,
        )
        print(f"[VERIFIED] {spec.name}: {output_dir / spec.output_name}")


def regenerate(output_dir: Path, *, verify_repeatability: bool) -> None:
    """Stage, verify, and promote the two canonical SVGs as one small batch."""

    output_dir.mkdir(parents=True, exist_ok=True)
    specs = figure_specs(output_dir)
    canonical_sources = {spec.name: _verify_source_and_counts(spec) for spec in specs}

    with TemporaryDirectory(prefix=".complementarity-figures-", dir=output_dir) as temporary:
        staging_dir = Path(temporary)
        staged_outputs: dict[str, Path] = {}
        for spec in specs:
            staged_output = spec.renderer(spec.source_path, staging_dir / spec.output_name)
            staged_outputs[spec.name] = staged_output

        if verify_repeatability:
            repeat_dir = staging_dir / "repeatability"
            repeat_dir.mkdir()
            for spec in specs:
                repeated_output = spec.renderer(spec.source_path, repeat_dir / spec.output_name)
                if sha256_file(staged_outputs[spec.name]) != sha256_file(repeated_output):
                    raise RuntimeError(
                        f"{spec.name.capitalize()} SVG is not byte-repeatable across two renders."
                    )
                print(f"[REPEATABLE] {spec.name}: {sha256_file(staged_outputs[spec.name])}")

        for spec in specs:
            staged_output = staged_outputs[spec.name]
            verify_editable_svg(
                staged_output,
                source=canonical_sources[spec.name],
                required_text=spec.required_svg_text,
            )

        for spec in specs:
            final_output = output_dir / spec.output_name
            staged_outputs[spec.name].replace(final_output)
            print(f"[WROTE] {spec.name}: {final_output}")


def _verify_source_and_counts(spec: FigureSpec) -> CanonicalSource:
    """Run evidence checksum validation plus the figure's population guard."""

    source = verify_canonical_source(spec.source_path, spec.source_relative_path)
    if spec.name == "recovery rate":
        load_counts(source.path)
    elif spec.name == "gate competence":
        load_routing(source.path)
    else:  # Defensive guard for future additions to the two-figure contract.
        raise RuntimeError(f"No count contract is registered for {spec.name!r}.")
    return source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Target directory; defaults to the canonical manuscript-figure directory.",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate canonical inputs and existing SVG assets without writing files.",
    )
    actions.add_argument(
        "--verify-repeatability",
        action="store_true",
        help="Render each SVG twice, require byte-identical output, then promote the batch.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.verify_only:
        verify_existing(args.output_dir)
        return
    regenerate(args.output_dir, verify_repeatability=args.verify_repeatability)


if __name__ == "__main__":
    main()
