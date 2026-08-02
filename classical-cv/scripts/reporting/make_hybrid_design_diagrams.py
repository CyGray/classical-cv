"""Generate publication-quality UML diagrams for the Hybrid Cascade Model Design document.

Uses classic academic monochrome styling (black borders, white fills, high-contrast black text).

Creates:
  1. docs/figures/fig_hybrid_system_flow.png (UML Activity Diagram for system workflow)
  2. docs/figures/fig_hybrid_gate_flow.png (UML Decision Flowchart for Escalation Gate)
  3. docs/figures/fig_hybrid_hardware_diagram.png (Deployment Diagram for Raspberry Pi 5 + NPU)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path

OUT_DIR = Path("docs/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def add_uml_initial_state(ax, x, y, label="Start"):
    """Draw UML initial state: solid filled black circle."""
    circle = patches.Circle((x, y), 0.28, facecolor="#000000", edgecolor="#000000", zorder=5)
    ax.add_patch(circle)
    ax.text(x, y - 0.52, label, ha="center", va="top", fontsize=12, fontweight="bold", color="#000000")


def add_uml_final_state(ax, x, y, label):
    """Draw UML final state: bullseye (outer black ring with solid inner black circle)."""
    outer = patches.Circle((x, y), 0.35, facecolor="#FFFFFF", edgecolor="#000000", lw=2.5, zorder=5)
    inner = patches.Circle((x, y), 0.20, facecolor="#000000", edgecolor="#000000", zorder=6)
    ax.add_patch(outer)
    ax.add_patch(inner)
    ax.text(x, y - 0.58, label, ha="center", va="top", fontsize=11.5, fontweight="bold", color="#000000", linespacing=1.2)


def add_uml_action(ax, x, y, width, height, title, text):
    """Draw UML action state: rounded rectangle with white background and black border."""
    rect = patches.FancyBboxPatch(
        (x - width / 2, y - height / 2), width, height,
        boxstyle="round,pad=0.18,rounding_size=0.25",
        facecolor="#FFFFFF", edgecolor="#000000", lw=2.0, zorder=4
    )
    ax.add_patch(rect)
    if text:
        ax.text(x, y + height * 0.18, title, ha="center", va="center", fontsize=12, fontweight="bold", color="#000000", zorder=5)
        ax.text(x, y - height * 0.20, text, ha="center", va="center", fontsize=10.5, color="#000000", linespacing=1.25, zorder=5)
    else:
        ax.text(x, y, title, ha="center", va="center", fontsize=12, fontweight="bold", color="#000000", zorder=5)


def add_uml_decision(ax, x, y, size_x, size_y, text):
    """Draw UML decision node: white diamond with black border."""
    pts = np.array([
        [x, y + size_y / 2],
        [x + size_x / 2, y],
        [x, y - size_y / 2],
        [x - size_x / 2, y]
    ])
    poly = patches.Polygon(pts, facecolor="#FFFFFF", edgecolor="#000000", lw=2.0, zorder=4)
    ax.add_patch(poly)
    ax.text(x, y, text, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#000000", linespacing=1.25, zorder=5)


def draw_arrow(ax, x1, y1, x2, y2, label="", style="->", rad=0.0, lw=1.8, label_pos=0.5):
    """Draw UML control flow arrow with black text box."""
    arrow = dict(arrowstyle=style, lw=lw, color="#000000", mutation_scale=16)
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=arrow, zorder=3)
    if label:
        lx = x1 + (x2 - x1) * label_pos
        ly = y1 + (y2 - y1) * label_pos
        ax.text(lx, ly + 0.18, label, ha="center", va="bottom", fontsize=10,
                fontweight="bold", color="#000000",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFFFFF", edgecolor="#000000", lw=1.0, alpha=0.95), zorder=6)


def draw_system_flow():
    fig, ax = plt.subplots(figsize=(15, 8.5), dpi=300)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    # Header / Title
    ax.text(7.5, 8.0, "UML Activity Diagram: LS-Face Hybrid Cascade Workflow",
            ha="center", va="center", fontsize=15, fontweight="bold", color="#000000")

    # 1. Initial State
    add_uml_initial_state(ax, 1.0, 5.8, label="Input Frame")

    # 2. YuNet Action
    add_uml_action(ax, 3.2, 5.8, 2.7, 1.4, "YuNet Detector", "• Face Bounding Box\n• 5 Facial Landmarks")

    # 3. Stage 1 LBPH Action
    add_uml_action(ax, 6.4, 5.8, 2.8, 1.4, "Stage 1: LBPH Fast Path", "• LBP Histogram Match\n• Distance & Margin Score")

    # 4. Escalation Gate Decision Diamond
    add_uml_decision(ax, 10.2, 5.8, 2.7, 1.6, "Escalation Gate\nEvaluate Rules")

    # Branch A: Fast Path Clear -> LBPH Decision Diamond
    add_uml_decision(ax, 13.5, 5.8, 2.2, 1.4, "LBPH Score\nCheck")

    # LBPH Terminals
    add_uml_final_state(ax, 13.5, 7.6, "Confident Accept\n(LBPH Fast Path)")
    add_uml_final_state(ax, 13.5, 3.8, "Confident Reject\n(Unknown Person)")

    # Branch B: Escalate -> Stage 2 SFace Action
    add_uml_action(ax, 10.2, 2.6, 2.8, 1.4, "Stage 2: SFace Deep Path", "• Landmark Alignment\n• 128-d Deep Embedding")

    # SFace Verification Decision Diamond
    add_uml_decision(ax, 10.2, 0.9, 2.7, 1.1, "SFace Match Check\ncosine >= 0.363 & L2 <= 1.018")

    # SFace Terminals
    add_uml_final_state(ax, 6.8, 0.9, "Deep Accept\n(Verified Identity)")
    add_uml_final_state(ax, 13.5, 0.9, "Deep Reject\n(Unverified Identity)")

    # Control Flows
    draw_arrow(ax, 1.3, 5.8, 1.85, 5.8)
    draw_arrow(ax, 4.55, 5.8, 5.0, 5.8)
    draw_arrow(ax, 7.8, 5.8, 8.85, 5.8)

    # Gate -> LBPH Check [Clear Quality & High Confidence]
    draw_arrow(ax, 11.55, 5.8, 12.4, 5.8, label="[No Rules Triggered]", label_pos=0.5)

    # LBPH Check -> Accept / Reject
    draw_arrow(ax, 13.5, 6.5, 13.5, 7.15, label="[dist <= tau_accept]")
    draw_arrow(ax, 13.5, 5.1, 13.5, 4.45, label="[dist >= tau_reject]")

    # Gate -> SFace [Quality Fail / Ambiguous / Low Margin]
    draw_arrow(ax, 10.2, 5.0, 10.2, 3.3, label="[Any Rule Triggered]")

    # SFace -> SFace Decision
    draw_arrow(ax, 10.2, 1.9, 10.2, 1.45)

    # SFace Decision -> Deep Accept / Deep Reject
    draw_arrow(ax, 8.85, 0.9, 7.4, 0.9, label="[Pass]")
    draw_arrow(ax, 11.55, 0.9, 12.9, 0.9, label="[Fail]")

    plt.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_system_flow.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def draw_gate_flow():
    fig, ax = plt.subplots(figsize=(13, 8.5), dpi=300)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    ax.text(6.5, 8.0, "UML Decision Diagram: Escalation Gate Evaluation Logic",
            ha="center", va="center", fontsize=15, fontweight="bold", color="#000000")

    add_uml_initial_state(ax, 1.2, 6.8, label="LBPH Score")

    # Rule Decisions
    add_uml_decision(ax, 3.8, 6.8, 3.0, 1.4, "Rule 1:\nQuality Fail?")
    add_uml_decision(ax, 3.8, 4.6, 3.0, 1.4, "Rule 2:\nAmbiguous Band?")
    add_uml_decision(ax, 3.8, 2.4, 3.0, 1.4, "Rule 3:\nThin Margin?")

    # Outcome Nodes
    add_uml_action(ax, 10.0, 4.6, 3.0, 1.4, "Escalate to SFace", "Trigger Stage 2 Deep Path\n(SFace Neural Recognizer)")
    add_uml_decision(ax, 3.8, 0.8, 2.4, 1.0, "LBPH Score")

    add_uml_final_state(ax, 8.2, 0.8, "Confident Accept\n(LBPH Fast Path)")
    add_uml_final_state(ax, 11.6, 0.8, "Confident Reject\n(Unknown Person)")

    # Connectors
    draw_arrow(ax, 1.5, 6.8, 2.3, 6.8)

    # Rule 1
    draw_arrow(ax, 5.3, 6.8, 10.0, 5.3, label="[YES: Blur, Noise, Pose, Light]", label_pos=0.45)
    draw_arrow(ax, 3.8, 6.1, 3.8, 5.3, label="[NO]")

    # Rule 2
    draw_arrow(ax, 5.3, 4.6, 8.5, 4.6, label="[YES: tau_accept < d < tau_reject]")
    draw_arrow(ax, 3.8, 3.9, 3.8, 3.1, label="[NO]")

    # Rule 3
    draw_arrow(ax, 5.3, 2.4, 10.0, 3.9, label="[YES: margin < margin_min]", label_pos=0.45)
    draw_arrow(ax, 3.8, 1.7, 3.8, 1.3, label="[NO: Clear & Confident]")

    # Fast Path Accept / Reject
    draw_arrow(ax, 5.0, 0.8, 7.5, 0.8, label="[dist <= tau_accept]")
    draw_arrow(ax, 3.8, 0.3, 11.6, 0.3, label="[dist >= tau_reject]", rad=-0.2)

    plt.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_gate_flow.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def draw_hardware_diagram():
    fig, ax = plt.subplots(figsize=(11, 6.0), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.0)
    ax.axis("off")

    ax.text(5.5, 5.6, "UML Deployment Diagram: Edge Hardware Architecture",
            ha="center", va="center", fontsize=15, fontweight="bold", color="#000000")

    rect = patches.FancyBboxPatch((0.4, 0.4), 10.2, 4.8, boxstyle="round,pad=0.3",
                                 facecolor="#FFFFFF", edgecolor="#000000", lw=2.2)
    ax.add_patch(rect)
    ax.text(0.8, 4.8, "Node: Raspberry Pi 5 Single Board Computer", fontsize=12, fontweight="bold", color="#000000")

    ax.text(3.0, 2.5, "Component: Host CPU\n(ARM Cortex-A76)\n\n• Video Stream Capture\n• YuNet Preprocessing\n• Stage 1 LBPH Fast Path\n• Escalation Gate & Probes\n• Decision Controller",
            ha="center", va="center", fontsize=10.5, bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFFFFF", edgecolor="#000000", lw=2.0), linespacing=1.35)

    ax.text(8.0, 2.5, "Component: NPU Accelerator\n(Hailo-8L / Coral TPU)\n\n• YuNet Face Detector\n• SFace Deep Embedding\n• Neural Network Execution\n• Low-Latency Inference",
            ha="center", va="center", fontsize=10.5, bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFFFFF", edgecolor="#000000", lw=2.0), linespacing=1.35)

    arrow_bi = dict(arrowstyle="<->", lw=2.2, color="#000000", mutation_scale=16)
    ax.annotate("", xy=(6.2, 2.5), xytext=(4.8, 2.5), arrowprops=arrow_bi)
    ax.text(5.5, 2.85, "PCIe / USB 3.0\n(ONNX Runtime)", ha="center", fontsize=10, fontweight="bold", color="#000000")

    plt.tight_layout()
    fig.savefig(OUT_DIR / "fig_hybrid_hardware_diagram.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    draw_system_flow()
    draw_gate_flow()
    draw_hardware_diagram()
    print("Successfully generated academic monochrome UML diagrams in docs/figures/")
