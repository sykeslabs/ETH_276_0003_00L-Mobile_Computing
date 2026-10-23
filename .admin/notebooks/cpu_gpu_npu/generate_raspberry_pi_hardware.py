"""Generate the Raspberry Pi hardware overview for notebook 05.xx."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

COLORS = {"CPU": "#2463a6", "GPU": "#a55016", "NPU": "#087f72"}
plt.rcParams.update({"font.size": 11})

def box(ax, x, y, w, h, label, color, fontsize=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.025",
                              facecolor=color, edgecolor="white", linewidth=1.5))
    ax.text(x+w/2, y+h/2, label, ha="center", va="center", color="white", fontsize=fontsize)

def arrow(ax, start, end, color="#536273"):
    ax.annotate("", xy=end, xytext=start,
                arrowprops={"arrowstyle": "->", "color": color, "lw": 1.7})

def topology_figure():
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.set(xlim=(0, 14), ylim=(0, 6))
    ax.axis("off")
    ax.add_patch(Rectangle((.1, .2), 7.1, 5.6, fill=False, ec="#9aa8b5", lw=2))
    ax.add_patch(Rectangle((9.3, .2), 4.5, 5.6, fill=False, ec="#9aa8b5", lw=2))
    ax.text(.4, 5.35, "Raspberry Pi 5", weight="normal", fontsize=14)
    ax.text(9.6, 5.35, "AI HAT+ 2", weight="normal", fontsize=14)
    box(ax, .5, 3.1, 2.7, 1.25, "CPU", COLORS["CPU"])
    box(ax, 3.8, 3.1, 2.9, 1.25, "VideoCore VII GPU", COLORS["GPU"], 10)
    box(ax, .5, .8, 6.2, 1.2, "Shared system DRAM", "#536273")
    for x in [1.85, 5.25]:
        arrow(ax, (x, 3.1), (x, 2))
        arrow(ax, (x+.3, 2), (x+.3, 3.1))
    box(ax, 9.7, 3.1, 3.7, 1.25, "Hailo-10H NPU", COLORS["NPU"])
    box(ax, 9.7, .8, 3.7, 1.2, "8 GB HAT memory", "#536273")
    arrow(ax, (11.2, 3.1), (11.2, 2))
    arrow(ax, (11.8, 2), (11.8, 3.1))
    arrow(ax, (7.2, 3.6), (9.3, 3.6))
    arrow(ax, (9.3, 2.8), (7.2, 2.8))
    ax.text(8.25, 4.1, "PCIe ×1", ha="center", weight="normal")
    ax.text(8.25, 1.4, "inputs →\n← outputs", ha="center", fontsize=10)
    fig.tight_layout()
    return fig

if __name__ == "__main__":
    output = Path(__file__).resolve().parent / "img" / "raspberry-pi-hardware.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    figure = topology_figure()
    figure.savefig(output, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(output)
