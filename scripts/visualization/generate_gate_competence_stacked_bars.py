"""Create a manuscript SVG that shows deployed gate routing as stacked bars.

The figure presents routing conditional on the thresholded LBPH outcome:
every scored LBPH failure is escalated to SFace, while a portion of scored
LBPH-correct probes remains on the inexpensive LBPH path.  Counts are read
from the canonical LSDB-DL41 complementarity summary rather than copied into
the artwork.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from scripts.visualization.manuscript_svg import (
    configure_matplotlib,
    export_matplotlib_svg,
)
from scripts.visualization.complementarity_contract import (
    GATE_SOURCE_RELATIVE,
    canonical_source_path,
    canonical_svg_metadata,
    verify_canonical_source,
    verify_editable_svg,
)

configure_matplotlib()

import matplotlib.pyplot as plt
from matplotlib.patches import Patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = canonical_source_path(GATE_SOURCE_RELATIVE)
DEFAULT_OUTPUT = (
    WORKSPACE_ROOT
    / "docs"
    / "manuscript"
    / "figures"
    / "fig_gate_competence_stacked_bars.svg"
)

# Routing action palette: neutral descriptive actions rather than evaluative judgments.
ESCALATED = "#007A78"
RETAINED = "#4D575B"
TEXT = "#1B2326"
MUTED = "#4D575B"
GRID = "#D9E0E2"
REQUIRED_SVG_TEXT = (
    "Escalated",
    "Retained at LBPH",
    "LBPH failures",
    "LBPH-correct",
    "100.0%",
    "40.9%",
    "59.1%",
    "Share within thresholded LBPH outcome (%)",
)


@dataclass(frozen=True)
class GateRouting:
    scored_probes: int
    excluded_no_signal: int
    lbph_failures: int
    lbph_correct: int
    escalated_failures: int
    escalated_correct: int
    retained_correct: int

    @property
    def failure_recall_percent(self) -> float:
        return 100 * self.escalated_failures / self.lbph_failures

    @property
    def correct_escalation_percent(self) -> float:
        return 100 * self.escalated_correct / self.lbph_correct

    @property
    def correct_retained_percent(self) -> float:
        return 100 * self.retained_correct / self.lbph_correct

    @property
    def escalation_precision_percent(self) -> float:
        return 100 * self.escalated_failures / (
            self.escalated_failures + self.escalated_correct
        )

    @property
    def escalated_total(self) -> int:
        return self.escalated_failures + self.escalated_correct


def load_routing(source: Path) -> GateRouting:
    payload = json.loads(source.read_text(encoding="utf-8"))
    gate = payload["complementarity_battery"]["gate"]["modified_only"]
    routing = gate["escalate_vs_lbph_wrong"]

    scored_probes = int(gate["probes"])
    failures = int(routing["lbph_wrong"])
    correct = scored_probes - failures
    escalated_total = int(routing["escalated"])
    escalated_failures = round(float(routing["tpr_recall_of_wrong"]) * failures)
    escalated_correct = escalated_total - escalated_failures
    result = GateRouting(
        scored_probes=scored_probes,
        excluded_no_signal=int(gate["excluded_no_signal"]),
        lbph_failures=failures,
        lbph_correct=correct,
        escalated_failures=escalated_failures,
        escalated_correct=escalated_correct,
        retained_correct=correct - escalated_correct,
    )

    # These checks prevent a silent scope or protocol shift from regenerating
    # an apparently polished figure with a different routing population.
    expected = (2060, 236, 1353, 707, 1353, 289, 418)
    observed = (
        result.scored_probes,
        result.excluded_no_signal,
        result.lbph_failures,
        result.lbph_correct,
        result.escalated_failures,
        result.escalated_correct,
        result.retained_correct,
    )
    if observed != expected:
        raise ValueError(
            "Unexpected LSDB-DL41 gate-routing counts; expected "
            f"{expected}, observed {observed}."
        )
    if abs(result.correct_escalation_percent / 100 - float(routing["fpr_on_right"])) > 1e-12:
        raise ValueError("Stored LBPH-correct escalation rate does not match counts.")
    if abs(result.escalation_precision_percent / 100 - float(routing["precision"])) > 1e-12:
        raise ValueError("Stored escalation precision does not match counts.")
    return result


def build_figure(routing: GateRouting) -> plt.Figure:
    """Return a compact conventional 100% stacked vertical bar figure."""

    # The wider, shorter canvas leaves a compact column on the right for the
    # outcome legend without taking space below the x-axis labels.
    figure, axis = plt.subplots(figsize=(4.85, 2.95), facecolor="white")
    figure.subplots_adjust(left=0.15, right=0.60, top=0.94, bottom=0.22)

    failure_x, correct_x = 0, 1
    width = 0.62
    bar_style = {"edgecolor": "white", "linewidth": 1.05, "zorder": 3}

    axis.bar(
        failure_x,
        routing.failure_recall_percent,
        width=width,
        color=ESCALATED,
        **bar_style,
    )
    axis.bar(
        correct_x,
        routing.correct_escalation_percent,
        width=width,
        color=ESCALATED,
        **bar_style,
    )
    axis.bar(
        correct_x,
        routing.correct_retained_percent,
        bottom=routing.correct_escalation_percent,
        width=width,
        color=RETAINED,
        **bar_style,
    )

    axis.text(
        failure_x,
        routing.failure_recall_percent / 2,
        f"{routing.failure_recall_percent:.1f}%",
        ha="center",
        va="center",
        fontsize=11.5,
        fontweight="bold",
        color="white",
        zorder=4,
    )
    axis.text(
        correct_x,
        routing.correct_escalation_percent / 2,
        f"{routing.correct_escalation_percent:.1f}%",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color="white",
        zorder=4,
    )
    axis.text(
        correct_x,
        routing.correct_escalation_percent + routing.correct_retained_percent / 2,
        f"{routing.correct_retained_percent:.1f}%",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color="white",
        zorder=4,
    )

    axis.set_xlim(-0.55, 1.55)
    axis.set_ylim(0, 100)
    axis.set_xticks(
        (failure_x, correct_x),
        (
            f"LBPH failures\n$n$ = {routing.lbph_failures:,}",
            f"LBPH-correct\n$n$ = {routing.lbph_correct:,}",
        ),
    )
    axis.set_yticks((0, 25, 50, 75, 100), ("0", "25", "50", "75", "100"))
    axis.set_ylabel(
        "Share within thresholded LBPH outcome (%)",
        fontsize=9.3,
        color=MUTED,
        labelpad=7,
    )
    # Nudge the rotated label down from the tight export's upper edge.
    axis.yaxis.label.set_y(0.44)
    axis.tick_params(axis="x", labelsize=9.3, colors=TEXT, length=4, width=0.9, pad=5)
    axis.tick_params(axis="y", labelsize=9.0, colors=MUTED, length=4, width=0.9, pad=4)
    axis.set_axisbelow(True)
    axis.grid(axis="both", color=GRID, linewidth=0.8, zorder=0)
    axis.spines["left"].set_color("#7C898E")
    axis.spines["left"].set_linewidth(0.95)
    axis.spines["bottom"].set_color("#7C898E")
    axis.spines["bottom"].set_linewidth(0.95)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)

    for label in axis.get_xticklabels():
        label.set_fontweight("bold")

    figure.legend(
        handles=(
            Patch(facecolor=ESCALATED, edgecolor="none", label="Escalated"),
            Patch(facecolor=RETAINED, edgecolor="none", label="Retained at LBPH"),
        ),
        loc="center left",
        bbox_to_anchor=(0.62, 0.56),
        ncol=1,
        frameon=False,
        fontsize=9.7,
        handlelength=1.25,
        handletextpad=0.5,
        labelspacing=0.7,
    )
    return figure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def render_figure(source: Path = DEFAULT_INPUT, output: Path = DEFAULT_OUTPUT) -> Path:
    """Render the gate figure from its one verified canonical source."""

    canonical_source = verify_canonical_source(source, GATE_SOURCE_RELATIVE)
    routing = load_routing(canonical_source.path)
    figure = build_figure(routing)
    try:
        output = export_matplotlib_svg(
            figure,
            output,
            # Preserve a small external bleed so Word cannot crop the rotated
            # y-axis title at the SVG boundary.
            bbox_pad_inches=0.06,
            metadata=canonical_svg_metadata(
                canonical_source,
                title="Deployed gate routing on held-out LSDB-DL41 probes",
                description=(
                    f"Among {routing.scored_probes:,} scored modified probes, the deployed gate escalated all "
                    f"{routing.lbph_failures:,} thresholded LBPH failures to SFace (100.0% recall). It escalated "
                    f"{routing.correct_escalation_percent:.2f}% of {routing.lbph_correct:,} thresholded LBPH-correct "
                    f"probes and retained {routing.correct_retained_percent:.2f}% on the LBPH path. Escalation precision "
                    f"was {routing.escalation_precision_percent:.2f}%; {routing.excluded_no_signal:,} modified probes "
                    "without the required gate signals were excluded from this routing analysis. Teal denotes escalated "
                    "probes and slate gray denotes probes retained on the LBPH path."
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
