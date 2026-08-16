"""Generate a clean, professional vector diagram for Figure 1:
Final LS-Face Quality-First Selective-Computation Pipeline.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

def create_fig1_pipeline():
    fig, ax = plt.subplots(figsize=(10.5, 4.4), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5)
    ax.axis('off')

    # Color palette (LNCS compliant, clean professional)
    c_input = '#EBF2FA'
    c_det = '#D6E4F0'
    c_qual = '#FEF9E7'
    c_lbph = '#E8F8F5'
    c_sface = '#F4ECF7'
    c_exit = '#EAF2F8'
    c_fail = '#FDEDEC'
    c_border = '#2C3E50'

    # Box styling helper
    def draw_box(x, y, w, h, text, color, header=None, dashed=False):
        rect = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.06,rounding_size=0.12",
            facecolor=color, edgecolor=c_border,
            linewidth=1.2, linestyle='--' if dashed else '-',
            zorder=2
        )
        ax.add_patch(rect)
        if header:
            ax.text(x + w/2, y + h - 0.24, header, ha='center', va='center',
                    fontsize=8.5, fontweight='bold', color='#1A252F', zorder=3)
            ax.text(x + w/2, y + (h - 0.24)/2, text, ha='center', va='center',
                    fontsize=7.5, color='#2C3E50', zorder=3)
        else:
            ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                    fontsize=8, fontweight='bold', color='#1A252F', zorder=3)

    # 1. Input Image
    draw_box(0.2, 2.0, 1.2, 1.2, "Input\nFrame", c_input)

    # 2. YuNet Detection
    draw_box(1.8, 2.0, 1.5, 1.2, "Bounding Box\n& 5 Landmarks", c_det, "YuNet Detector")
    ax.annotate('', xy=(1.8, 2.6), xytext=(1.4, 2.6),
                arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=1.3), zorder=1)

    # Detection failure exit
    ax.annotate('', xy=(2.55, 0.9), xytext=(2.55, 2.0),
                arrowprops=dict(arrowstyle='->', color='#C0392B', lw=1.3), zorder=1)
    ax.text(2.6, 1.45, " No face", ha='left', va='center', fontsize=7.5, fontweight='bold', color='#C0392B', zorder=4)
    draw_box(1.8, 0.3, 1.5, 0.6, "Strict Failure\n(Detection Failed)", c_fail)

    # 3. Quality Diagnostics
    draw_box(3.8, 1.9, 1.8, 1.4, "5 Diagnostics:\nBlur, Luma, Noise,\nPose, Face Size", c_qual, "Quality Gate")
    ax.annotate('', xy=(3.8, 2.6), xytext=(3.3, 2.6),
                arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=1.3), zorder=1)

    # Early Bypass path (top curve)
    ax.annotate(
        '', xy=(7.7, 3.1), xytext=(4.7, 3.3),
        arrowprops=dict(arrowstyle='->', color='#C0392B', lw=1.4,
                        connectionstyle="arc3,rad=-0.22"),
        zorder=1
    )
    ax.text(6.2, 4.25, "Early Bypass (Quality Flagged)", ha='center', va='center',
            fontsize=7.5, fontweight='bold', color='#C0392B',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#FDEDEC', edgecolor='#C0392B', lw=0.8),
            zorder=4)

    # 4. Compact LBPH Fast Path
    draw_box(3.8, 0.2, 1.8, 1.3, "r=3, n=8, 6x6 Grid\n36 KiB Template\n(Tan-Triggs Norm.)", c_lbph, "Compact LBPH")
    ax.annotate('', xy=(4.7, 1.5), xytext=(4.7, 1.9),
                arrowprops=dict(arrowstyle='->', color='#27AE60', lw=1.3), zorder=1)
    ax.text(4.8, 1.7, " Passed", ha='left', va='center', fontsize=7.5, fontweight='bold', color='#27AE60', zorder=4)

    # 5. Fast Path Exit
    draw_box(6.2, 0.3, 1.5, 1.1, "Fast-Path Exit\n(~3.06 ms)", c_exit, "Confident LBPH")
    ax.annotate('', xy=(6.2, 0.85), xytext=(5.6, 0.85),
                arrowprops=dict(arrowstyle='->', color='#27AE60', lw=1.3), zorder=1)
    ax.text(5.9, 1.15, "d1 <= 52.37\nm >= 0.05", ha='center', va='center', fontsize=6.8,
            fontweight='bold', color='#27AE60',
            bbox=dict(boxstyle='round,pad=0.15', facecolor='white', edgecolor='none', alpha=0.85),
            zorder=4)

    # 6. SFace Recognizer
    draw_box(7.7, 1.8, 1.6, 1.6, "128-D Embedding\nAligned Crop\nL2 <= 1.0313", c_sface, "SFace Fallback")

    # Uncertain LBPH path
    ax.annotate(
        '', xy=(7.7, 2.1), xytext=(5.6, 0.4),
        arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=1.3,
                        connectionstyle="arc3,rad=-0.12"),
        zorder=1
    )
    ax.text(6.65, 1.65, "Uncertain LBPH", ha='center', va='center', fontsize=7,
            fontweight='bold', color='#2C3E50',
            bbox=dict(boxstyle='round,pad=0.15', facecolor='white', edgecolor='none', alpha=0.85),
            zorder=4)

    # 7. Final Output
    draw_box(9.7, 2.0, 1.1, 1.2, "Final Decision\n(Accept / Reject)", c_exit)
    ax.annotate('', xy=(9.7, 2.6), xytext=(9.3, 2.6),
                arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=1.3), zorder=1)

    plt.tight_layout()
    
    out_dir = Path("docs/manuscript/figures")
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / "fig1_final_architecture_pipeline.svg"
    png_path = out_dir / "fig1_final_architecture_pipeline.png"
    
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Generated Figure 1 -> {svg_path} and {png_path}")

if __name__ == "__main__":
    create_fig1_pipeline()
