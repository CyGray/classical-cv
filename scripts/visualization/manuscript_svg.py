"""SVG-first export helpers for manuscript charts and diagrams.

Use Matplotlib for data-driven charts and Graphviz for structural diagrams.
Both helpers intentionally reject raster extensions so a manuscript asset
cannot silently fall back to PNG or JPEG output.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from matplotlib.figure import Figure


MANUSCRIPT_FORMAT = "svg"
DEFAULT_FONT_FAMILY = "Arial"
_WINDOWS_GRAPHVIZ_BIN_DIRS = (
    Path(r"C:\Program Files\Graphviz\bin"),
    Path(r"C:\Program Files (x86)\Graphviz\bin"),
)


def configure_matplotlib() -> None:
    """Configure Matplotlib for non-interactive, editable SVG output.

    Call this before importing ``matplotlib.pyplot`` in a report or figure
    script. Text remains text in the SVG so that manuscript copyediting and
    accessibility tooling can inspect it.
    """

    import matplotlib

    if "matplotlib.pyplot" not in sys.modules:
        matplotlib.use("Agg")

    matplotlib.rcParams.update(
        {
            "font.family": [DEFAULT_FONT_FAMILY, "DejaVu Sans"],
            "axes.unicode_minus": False,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "savefig.transparent": False,
            # Matplotlib otherwise salts clip-path IDs per render, which makes
            # unchanged SVG artwork differ byte-for-byte across runs.
            "svg.hashsalt": "lsface-manuscript-svg-v1",
            "svg.fonttype": "none",
        }
    )


def export_matplotlib_svg(
    figure: "Figure",
    output: str | Path,
    *,
    metadata: Mapping[str, str] | None = None,
    bbox_pad_inches: float = 0.02,
) -> Path:
    """Write one Matplotlib figure as a manuscript-ready SVG.

    ``output`` may omit its suffix; supplying a non-SVG suffix is an error so
    callers must make an intentional exception to the workspace convention.
    ``bbox_pad_inches`` permits a figure with boundary-adjacent labels to
    reserve a small, explicit SVG bleed without changing the global default.
    """

    if bbox_pad_inches < 0:
        raise ValueError("bbox_pad_inches must be non-negative.")
    output_path = _svg_path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    svg_metadata: dict[str, str] = {
        "Creator": "LS-Face manuscript SVG exporter",
    }
    if metadata:
        svg_metadata.update(metadata)
    figure.savefig(
        output_path,
        format=MANUSCRIPT_FORMAT,
        bbox_inches="tight",
        pad_inches=bbox_pad_inches,
        metadata=svg_metadata,
    )
    _assert_svg(output_path)
    return output_path


def ensure_graphviz_on_path() -> None:
    """Make a standard Graphviz installation available to this Python process.

    The Graphviz Python package is only a wrapper; it needs the system ``dot``
    executable. Windows terminals opened before installation may not yet have
    the updated user PATH, so the conventional installer locations are also
    checked here.
    """

    if shutil.which("dot"):
        return

    configured = os.environ.get("GRAPHVIZ_DOT")
    candidates: list[Path] = []
    if configured:
        configured_path = Path(configured)
        candidates.append(
            configured_path.parent
            if configured_path.name.lower().startswith("dot")
            else configured_path
        )
    candidates.extend(_WINDOWS_GRAPHVIZ_BIN_DIRS)

    executable = "dot.exe" if os.name == "nt" else "dot"
    for directory in candidates:
        if (directory / executable).is_file():
            os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
            return

    raise RuntimeError(
        "Graphviz's 'dot' executable was not found. Install Graphviz and add "
        "its bin directory to PATH (or set GRAPHVIZ_DOT)."
    )


def make_graphviz_digraph(
    name: str,
    *,
    engine: str = "dot",
    rankdir: str = "TB",
    graph_attr: Mapping[str, str] | None = None,
    node_attr: Mapping[str, str] | None = None,
    edge_attr: Mapping[str, str] | None = None,
) -> Any:
    """Create a Graphviz directed diagram with the workspace SVG defaults."""

    ensure_graphviz_on_path()
    from graphviz import Digraph

    resolved_graph_attr = {
        "bgcolor": "white",
        "fontname": DEFAULT_FONT_FAMILY,
        "rankdir": rankdir,
        "pad": "0.08",
        "nodesep": "0.35",
        "ranksep": "0.45",
    }
    resolved_node_attr = {
        "color": "black",
        "fontname": DEFAULT_FONT_FAMILY,
        "fontsize": "11",
    }
    resolved_edge_attr = {
        "color": "black",
        "fontname": DEFAULT_FONT_FAMILY,
        "fontsize": "10",
    }
    if graph_attr:
        resolved_graph_attr.update(graph_attr)
    if node_attr:
        resolved_node_attr.update(node_attr)
    if edge_attr:
        resolved_edge_attr.update(edge_attr)

    return Digraph(
        name=name,
        engine=engine,
        format=MANUSCRIPT_FORMAT,
        graph_attr=resolved_graph_attr,
        node_attr=resolved_node_attr,
        edge_attr=resolved_edge_attr,
    )


def render_graphviz_svg(diagram: Any, output: str | Path) -> Path:
    """Render a Graphviz graph as SVG and remove its intermediate DOT source."""

    ensure_graphviz_on_path()
    output_path = _svg_path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    diagram.render(
        filename=output_path.stem,
        directory=str(output_path.parent),
        format=MANUSCRIPT_FORMAT,
        cleanup=True,
    )
    _assert_svg(output_path)
    return output_path


def _svg_path(output: str | Path) -> Path:
    output_path = Path(output)
    if not output_path.suffix:
        return output_path.with_suffix(".svg")
    if output_path.suffix.lower() != ".svg":
        raise ValueError(
            f"Manuscript visual exports must be SVG, not '{output_path.suffix}'."
        )
    return output_path


def _assert_svg(output_path: Path) -> None:
    if not output_path.is_file():
        raise RuntimeError(f"SVG export was not created: {output_path}")
    contents = output_path.read_text(encoding="utf-8", errors="ignore")[:4096]
    if "<svg" not in contents:
        raise RuntimeError(f"Export is not a valid SVG document: {output_path}")
