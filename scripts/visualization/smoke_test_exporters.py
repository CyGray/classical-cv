"""Verify the shared Matplotlib and Graphviz SVG export path without artifacts."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.visualization.manuscript_svg import (
    configure_matplotlib,
    export_matplotlib_svg,
    make_graphviz_digraph,
    render_graphviz_svg,
)


def main() -> None:
    configure_matplotlib()
    import matplotlib.pyplot as plt

    with TemporaryDirectory(prefix="lsface-svg-export-") as temporary_directory:
        output_directory = Path(temporary_directory)

        figure, axis = plt.subplots(figsize=(4.5, 2.6))
        axis.plot([0, 1, 2], [0.70, 0.84, 0.91], marker="o")
        axis.set(xlabel="Experiment", ylabel="Accuracy", title="Matplotlib SVG smoke test")
        chart_path = export_matplotlib_svg(figure, output_directory / "chart.svg")
        plt.close(figure)

        diagram = make_graphviz_digraph("export_flow", rankdir="LR")
        diagram.node("data", "Recorded data", shape="box", style="rounded")
        diagram.node("asset", "Manuscript SVG", shape="box", style="rounded")
        diagram.edge("data", "asset", label="export")
        diagram_path = render_graphviz_svg(diagram, output_directory / "diagram.svg")

        print(f"[OK] Matplotlib SVG: {chart_path.name}")
        print(f"[OK] Graphviz SVG: {diagram_path.name}")


if __name__ == "__main__":
    main()
