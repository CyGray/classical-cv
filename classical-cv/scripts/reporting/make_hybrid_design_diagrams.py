"""Generate Graphviz-backed SVG diagrams for the Hybrid Cascade design.

The diagrams are illustrative system-design assets, not experimental result
figures. They deliberately avoid embedding operating-threshold values, whose
runtime source of truth is ``src/hybrid/thresholds.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CLASSICAL_CV_ROOT = SCRIPT_PATH.parents[2]
WORKSPACE_ROOT = CLASSICAL_CV_ROOT.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.visualization.manuscript_svg import (  # noqa: E402
    make_graphviz_digraph,
    render_graphviz_svg,
)


OUT_DIR = CLASSICAL_CV_ROOT / "docs" / "figures"


def _terminal(diagram, identifier: str, label: str, *, accepted: bool) -> None:
    diagram.node(
        identifier,
        label,
        shape="doublecircle",
        style="filled",
        fillcolor="white" if accepted else "#f2f2f2",
    )


def draw_system_flow() -> Path:
    """Render the hybrid two-stage recognition flow as an SVG activity diagram."""

    diagram = make_graphviz_digraph(
        "hybrid_system_flow",
        graph_attr={
            "label": "LS-Face Hybrid Cascade Workflow",
            "labelloc": "t",
            "fontsize": "20",
            "splines": "polyline",
        },
        node_attr={"shape": "box", "style": "rounded", "margin": "0.15,0.08"},
    )
    diagram.node("input", "Input frame", shape="circle", style="filled", fillcolor="black", fontcolor="white")
    diagram.node("yunet", "YuNet detector\nface box + landmarks")
    diagram.node("lbph", "Stage 1: LBPH fast path\ndistance + margin")
    diagram.node("gate", "Escalation gate\nevaluate quality and confidence", shape="diamond")
    diagram.node("lbph_check", "LBPH score check", shape="diamond")
    diagram.node("sface", "Stage 2: SFace deep path\nalignment + embedding")
    diagram.node("sface_check", "SFace match check", shape="diamond")
    _terminal(diagram, "fast_accept", "Confident accept\nLBPH fast path", accepted=True)
    _terminal(diagram, "fast_reject", "Confident reject\nunknown person", accepted=False)
    _terminal(diagram, "deep_accept", "Deep accept\nverified identity", accepted=True)
    _terminal(diagram, "deep_reject", "Deep reject\nunverified identity", accepted=False)

    diagram.edge("input", "yunet")
    diagram.edge("yunet", "lbph")
    diagram.edge("lbph", "gate")
    diagram.edge("gate", "lbph_check", label="No rules triggered")
    diagram.edge("lbph_check", "fast_accept", label="distance <= tau_accept")
    diagram.edge("lbph_check", "fast_reject", label="distance >= tau_reject")
    diagram.edge("gate", "sface", label="Any rule triggered")
    diagram.edge("sface", "sface_check")
    diagram.edge("sface_check", "deep_accept", label="Pass")
    diagram.edge("sface_check", "deep_reject", label="Fail")

    return render_graphviz_svg(diagram, OUT_DIR / "fig_hybrid_system_flow.svg")


def draw_gate_flow() -> Path:
    """Render the escalation-gate decision sequence as an SVG flowchart."""

    diagram = make_graphviz_digraph(
        "hybrid_gate_flow",
        graph_attr={
            "label": "Escalation Gate Evaluation Logic",
            "labelloc": "t",
            "fontsize": "20",
            "splines": "polyline",
        },
        node_attr={"shape": "box", "style": "rounded", "margin": "0.15,0.08"},
    )
    diagram.node("score_in", "LBPH score", shape="circle", style="filled", fillcolor="black", fontcolor="white")
    diagram.node("quality", "Rule 1:\nquality fail?", shape="diamond")
    diagram.node("band", "Rule 2:\nambiguous band?", shape="diamond")
    diagram.node("margin", "Rule 3:\nthin margin?", shape="diamond")
    diagram.node("score_out", "LBPH score check", shape="diamond")
    diagram.node("escalate", "Escalate to SFace\nStage 2 deep path")
    _terminal(diagram, "accept", "Confident accept\nLBPH fast path", accepted=True)
    _terminal(diagram, "reject", "Confident reject\nunknown person", accepted=False)

    diagram.edge("score_in", "quality")
    diagram.edge("quality", "escalate", label="Yes")
    diagram.edge("quality", "band", label="No")
    diagram.edge("band", "escalate", label="Yes")
    diagram.edge("band", "margin", label="No")
    diagram.edge("margin", "escalate", label="Yes")
    diagram.edge("margin", "score_out", label="No: clear and confident")
    diagram.edge("score_out", "accept", label="distance <= tau_accept")
    diagram.edge("score_out", "reject", label="distance >= tau_reject")

    return render_graphviz_svg(diagram, OUT_DIR / "fig_hybrid_gate_flow.svg")


def draw_hardware_diagram() -> Path:
    """Render the edge deployment diagram as an SVG component diagram."""

    diagram = make_graphviz_digraph(
        "hybrid_hardware_diagram",
        rankdir="LR",
        graph_attr={
            "label": "Edge Hardware Architecture",
            "labelloc": "t",
            "fontsize": "20",
        },
        node_attr={"shape": "box", "style": "rounded", "margin": "0.18,0.12"},
    )
    with diagram.subgraph(name="cluster_raspberry_pi") as raspberry_pi:
        raspberry_pi.attr(
            label="Node: Raspberry Pi 5 single-board computer",
            color="black",
            fontname="Arial",
            style="rounded",
        )
        raspberry_pi.node(
            "host_cpu",
            "Host CPU (ARM Cortex-A76)\n\nvideo capture\nYuNet preprocessing\nStage 1 LBPH fast path\nescalation gate + probes\ndecision controller",
        )
        raspberry_pi.node(
            "npu",
            "NPU accelerator\n\nYuNet face detection\nSFace deep embedding\nneural-network execution\nlow-latency inference",
        )

    diagram.edge("host_cpu", "npu", dir="both", label="PCIe / USB 3.0\nONNX Runtime")
    return render_graphviz_svg(diagram, OUT_DIR / "fig_hybrid_hardware_diagram.svg")


def main() -> None:
    for output in (draw_system_flow(), draw_gate_flow(), draw_hardware_diagram()):
        print(f"[OK] {output}")


if __name__ == "__main__":
    main()
