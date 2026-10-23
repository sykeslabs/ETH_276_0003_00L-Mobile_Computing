"""Draw pi5-inside.png for 05.08: the cores, caches, GPU and memory of a Raspberry Pi 5 (numbers from lscpu)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

CPU, GPU, CACHE, MEMORY = "#2463a6", "#a55016", "#7a8b9c", "#536273"


def box(ax, x, y, w, h, text, color, size=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03", facecolor=color, edgecolor="white", lw=1.5))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="white", fontsize=size, linespacing=1.5)


fig, ax = plt.subplots(figsize=(12, 5.2))
ax.set(xlim=(0, 14), ylim=(0, 7.2))
ax.axis("off")
ax.add_patch(Rectangle((0.1, 2.15), 13.8, 4.95, fill=False, ec="#9aa8b5", lw=2))
ax.text(0.35, 6.65, "BCM2712 chip", fontsize=14)
for i in range(4):
    box(ax, 0.4 + 2.35 * i, 4.45, 2.1, 1.85, f"Core {i + 1}\nCortex-A76\nvector unit", CPU)
    box(ax, 0.4 + 2.35 * i, 3.75, 2.1, 0.5, "L1 64 + 64 KB", CACHE, 9)
    box(ax, 0.4 + 2.35 * i, 3.1, 2.1, 0.5, "L2 512 KB", CACHE, 9)
box(ax, 0.4, 2.45, 9.15, 0.5, "L3 2 MB, shared by the four cores", CACHE, 10)
box(ax, 9.85, 2.45, 3.75, 3.85, "VideoCore VII GPU\ngraphics and video", GPU)
box(ax, 0.4, 0.55, 13.2, 0.95, "8 GB LPDDR4X memory, shared by CPU and GPU", MEMORY, 12)
for x in (4.9, 11.7):
    ax.annotate("", xy=(x, 1.5), xytext=(x, 2.4), arrowprops={"arrowstyle": "<->", "color": "#536273", "lw": 2})
ax.text(5.1, 1.75, "17 GB/s", fontsize=12, color="#333333")
fig.tight_layout()
output = Path(__file__).with_name("pi5-inside.png")
fig.savefig(output, dpi=160, bbox_inches="tight", facecolor="white")
print(output)
