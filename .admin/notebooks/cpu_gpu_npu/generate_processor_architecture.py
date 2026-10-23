"""Generate the static processor architecture illustration for notebook 05.xx."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

COLORS = {"CPU": "#2463a6", "GPU": "#a55016", "NPU": "#087f72"}
plt.rcParams.update({"font.size": 11})

def box(ax, x, y, w, h, label, color, fontsize=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.025",
                              facecolor=color, edgecolor="white", linewidth=1.5))
    ax.text(x+w/2, y+h/2, label, ha="center", va="center", color="white", fontsize=fontsize)

def arrow(ax, start, end, color="#536273"):
    ax.annotate("", xy=end, xytext=start,
                arrowprops={"arrowstyle": "->", "color": color, "lw": 1.7})

def architecture_figure():
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax in axes:
        ax.set(xlim=(0, 10), ylim=(-.2, 8.8))
        ax.axis("off")
    ax = axes[0]
    box(ax, .5, 7.2, 9, 1.3, "CPU: Instructions and control", COLORS["CPU"])
    for x in [.6, 5.2]:
        box(ax, x, 3.5, 4.2, 2.2, "Core\nscalar + vector", COLORS["CPU"])
        arrow(ax, (x+2.1, 7.2), (x+2.1, 5.7))
    box(ax, .5, 1.2, 9, 1.1, "Cache / memory", "#536273")
    for x in [2.7, 7.3]: arrow(ax, (x, 3.5), (x, 2.3))
    ax.text(5, .2, "Flexible instruction execution", ha="center")
    ax = axes[1]
    box(ax, .5, 7.2, 9, 1.3, "GPU: Dispatch groups of work", COLORS["GPU"])
    for i in range(6):
        for j in range(3):
            box(ax, .65+i*1.48, 3.45+j*.9, 1.3, .75, "× +", COLORS["GPU"], 9)
    arrow(ax, (5, 7.2), (5, 6.0))
    box(ax, .5, 1.2, 9, 1.1, "Shared / device memory", "#536273")
    arrow(ax, (5, 3.4), (5, 2.3))
    ax.text(5, .2, "Many operations in parallel", ha="center")
    ax = axes[2]
    box(ax, .5, 7.2, 9, 1.3, "NPU: Compile a supported graph", COLORS["NPU"])
    for i, label in enumerate(["MatMul", "Add", "Activation"]):
        x = .3+i*3.3
        box(ax, x, 4, 2.8, 1.5, label, COLORS["NPU"], 10)
        if i < 2: arrow(ax, (x+2.8, 4.75), (x+3.3, 4.75))
    arrow(ax, (5, 7.2), (5, 5.5))
    box(ax, .5, 1.2, 9, 1.1, "Buffers / weights / memory", "#536273")
    arrow(ax, (5, 4), (5, 2.3))
    ax.text(5, .2, "Specialized graph execution", ha="center")
    fig.tight_layout()
    return fig

if __name__ == "__main__":
    output = Path(__file__).resolve().parent / "img" / "processor-architecture.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    figure = architecture_figure()
    figure.savefig(output, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(output)
