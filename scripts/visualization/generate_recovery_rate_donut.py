"""Create the manuscript SVG for SFace recovery of LBPH errors.

The figure is deliberately compact: each slice has a close, directly connected
category-and-percentage label on its nearest side, while the centre names the
conditional denominator. It derives every displayed count from the canonical
LSDB-DL41 complementarity probe record.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from scripts.visualization.manuscript_svg import (
    configure_matplotlib,
    export_matplotlib_svg,
)
from scripts.visualization.complementarity_contract import (
    RECOVERY_SOURCE_RELATIVE,
    canonical_source_path,
    canonical_svg_metadata,
    verify_canonical_source,
    verify_editable_svg,
)

configure_matplotlib()

import matplotlib.pyplot as plt


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = canonical_source_path(RECOVERY_SOURCE_RELATIVE)
DEFAULT_OUTPUT = (
    WORKSPACE_ROOT
    / "docs"
    / "manuscript"
    / "figures"
    / "fig_recovery_rate_donut.svg"
)

# Print-safe, high-contrast fills. Labels remain neutral text on white, with
# short colored connectors that retain the slice mapping in grayscale.
RECOVERED = "#007A78"
NOT_RECOVERED = "#C74E12"
TEXT = "#1B2326"
MUTED = "#4D575B"
REQUIRED_SVG_TEXT = (
    "Not recovered",
    "Recovered",
    "LBPH errors",
    "1,589",
    "81.6%",
    "18.4%",
)


@dataclass(frozen=True)
class RecoveryCounts:
    transformed_probes: int
    lbph_errors: int
    recovered: int
    not_recovered: int

    @property
    def recovery_percent(self) -> float:
        return 100 * self.recovered / self.lbph_errors

    @property
    def not_recovered_percent(self) -> float:
        return 100 * self.not_recovered / self.lbph_errors


def parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def load_counts(source: Path) -> RecoveryCounts:
    with source.open(newline="", encoding="utf-8") as handle:
        transformed = [
            row
            for row in csv.DictReader(handle)
            if row["modification"].strip().lower() != "clean"
        ]

    lbph_errors = [row for row in transformed if not parse_bool(row["cv_correct"])]
    recovered = sum(parse_bool(row["dl_correct"]) for row in lbph_errors)
    counts = RecoveryCounts(
        transformed_probes=len(transformed),
        lbph_errors=len(lbph_errors),
        recovered=recovered,
        not_recovered=len(lbph_errors) - recovered,
    )

    # These identifiers protect the artwork from silently being regenerated
    # against a different population without a deliberate provenance update.
    expected = (2296, 1589, 1296, 293)
    observed = (
        counts.transformed_probes,
        counts.lbph_errors,
        counts.recovered,
        counts.not_recovered,
    )
    if observed != expected:
        raise ValueError(
            "Unexpected LSDB-DL41 recovery counts; expected "
            f"{expected}, observed {observed}."
        )
    return counts


def build_figure(counts: RecoveryCounts) -> plt.Figure:
    """Return a compact one-column recovery figure for a Springer manuscript."""

    # The axes fill a content-matched landscape canvas so Word receives a
    # tightly cropped object, not a padded square around the outside labels.
    figure = plt.figure(figsize=(3.75, 2.27), facecolor="white")
    axis = figure.add_axes((0.0, 0.0, 1.0, 1.0))

    axis.pie(
        (counts.recovered, counts.not_recovered),
        colors=(RECOVERED, NOT_RECOVERED),
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.34, "edgecolor": "white", "linewidth": 2.4},
    )
    axis.set(aspect="equal")
    axis.set_axis_off()
    axis.set_xlim(-1.74, 1.74)
    axis.set_ylim(-1.055, 1.055)

    # Close external labels preserve a readable type size without requiring the
    # reader to scan a separate legend. Each connector lands on its own slice.
    axis.plot(
        (-0.86, -1.06),
        (0.50, 0.50),
        color=NOT_RECOVERED,
        linewidth=2.0,
        solid_capstyle="round",
        clip_on=False,
    )
    axis.text(
        -1.13,
        0.59,
        "Not recovered",
        ha="right",
        va="center",
        fontsize=10.8,
        fontweight="bold",
        color=TEXT,
    )
    axis.text(
        -1.13,
        0.39,
        f"{counts.not_recovered_percent:.1f}%",
        ha="right",
        va="center",
        fontsize=13.0,
        fontweight="bold",
        color=TEXT,
    )
    axis.plot(
        (0.90, 1.10),
        (-0.40, -0.40),
        color=RECOVERED,
        linewidth=2.0,
        solid_capstyle="round",
        clip_on=False,
    )
    axis.text(
        1.17,
        -0.31,
        "Recovered",
        ha="left",
        va="center",
        fontsize=10.8,
        fontweight="bold",
        color=TEXT,
    )
    axis.text(
        1.17,
        -0.51,
        f"{counts.recovery_percent:.1f}%",
        ha="left",
        va="center",
        fontsize=13.0,
        fontweight="bold",
        color=TEXT,
    )
    axis.text(
        0,
        0.105,
        f"{counts.lbph_errors:,}",
        ha="center",
        va="center",
        fontsize=18.0,
        fontweight="bold",
        color=TEXT,
    )
    axis.text(
        0,
        -0.105,
        "LBPH errors",
        ha="center",
        va="center",
        fontsize=10.6,
        color=MUTED,
    )
    return figure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def render_figure(source: Path = DEFAULT_INPUT, output: Path = DEFAULT_OUTPUT) -> Path:
    """Render the recovery figure from its one verified canonical source."""

    canonical_source = verify_canonical_source(source, RECOVERY_SOURCE_RELATIVE)
    counts = load_counts(canonical_source.path)
    figure = build_figure(counts)
    try:
        output = export_matplotlib_svg(
            figure,
            output,
            metadata=canonical_svg_metadata(
                canonical_source,
                title="SFace recovery of LBPH errors",
                description=(
                    f"Among {counts.lbph_errors:,} LBPH errors from "
                    f"{counts.transformed_probes:,} transformed held-out LSDB probes, "
                    f"SFace recovered {counts.recovered:,} "
                    f"({counts.recovery_percent:.2f}%) and did not recover "
                    f"{counts.not_recovered:,} ({counts.not_recovered_percent:.2f}%)."
                ),
            ),
        )
    finally:
        plt.close(figure)
    verify_editable_svg(
        output,
        source=canonical_source,
        required_text=REQUIRED_SVG_TEXT,
    )
    return output


def main() -> None:
    args = parse_args()
    print(render_figure(args.input, args.output))


if __name__ == "__main__":
    main()
