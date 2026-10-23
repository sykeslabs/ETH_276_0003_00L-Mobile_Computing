"""Draw processor-architecture.png for 05.08 (after Stefan Mangold's original): CPU, GPU and NPU side by side."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

COLORS = {"CPU": "#2463a6", "GPU": "#a55016", "NPU": "#087f72", "memory": "#536273"}
plt.rcParams.update({"font.size": 11})


def box(ax, x, y, w, h, label, color, size=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.025", facecolor=color, edgecolor="white", lw=1.5))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", color="white", fontsize=size)


def arrow(ax, start, end, color="#536273", lw=1.7):
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": color, "lw": lw})


fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
for ax in axes:
    ax.set(xlim=(0, 10), ylim=(-0.2, 8.8))
    ax.axis("off")

ax = axes[0]
box(ax, 0.5, 7.2, 9, 1.3, "CPU: a few strong cores", COLORS["CPU"])
for x in (0.6, 5.2):
    box(ax, x, 3.5, 4.2, 2.2, "core\nwith a vector unit", COLORS["CPU"])
    arrow(ax, (x + 2.1, 7.2), (x + 2.1, 5.7))
    arrow(ax, (x + 2.1, 3.5), (x + 2.1, 2.3))
box(ax, 0.5, 1.2, 9, 1.1, "caches and memory", COLORS["memory"])
ax.text(5, 0.2, "runs any program", ha="center")

ax = axes[1]
box(ax, 0.5, 7.2, 9, 1.3, "GPU: many simple units", COLORS["GPU"])
for i in range(6):
    for j in range(3):
        box(ax, 0.65 + i * 1.48, 3.45 + j * 0.9, 1.3, 0.75, "× +", COLORS["GPU"], 9)
arrow(ax, (5, 7.2), (5, 6.0))
arrow(ax, (5, 3.4), (5, 2.3))
box(ax, 0.5, 1.2, 9, 1.1, "shared memory of each group", COLORS["memory"])
ax.text(5, 0.2, "many equal pieces at once", ha="center")

ax = axes[2]
box(ax, 0.5, 7.2, 9, 1.3, "NPU: a grid of MAC units", COLORS["NPU"])
for i in range(4):
    for j in range(3):
        x, y = 1.6 + i * 2.0, 3.0 + j * 1.25
        box(ax, x, y, 1.3, 0.7, "× +", COLORS["NPU"], 9)
        if i < 3:
            arrow(ax, (x + 1.33, y + 0.35), (x + 1.97, y + 0.35), lw=1.2)
        if j > 0:
            arrow(ax, (x + 0.65, y - 0.03), (x + 0.65, y - 0.52), lw=1.2)
arrow(ax, (0.4, 5.85), (1.55, 5.85))
ax.text(0.35, 6.2, "A", fontsize=10)
arrow(ax, (2.25, 7.05), (2.25, 6.25))
ax.text(2.5, 6.45, "B", fontsize=10)
arrow(ax, (5, 2.95), (5, 2.3))
box(ax, 0.5, 1.2, 9, 1.1, "weights and buffers", COLORS["memory"])
ax.text(5, 0.2, "numbers passed from unit to unit", ha="center")

fig.tight_layout()
output = Path(__file__).with_name("processor-architecture.png")
fig.savefig(output, dpi=160, bbox_inches="tight", facecolor="white")
print(output)
