import os
import tempfile

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUTPUT = ".admin/notebooks/picture/ADC_Pipeline.png"


def add_box(ax, xy, width, height, title, subtitle, facecolor):
    x, y = xy
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=1.6,
        edgecolor="#2f3b45",
        facecolor=facecolor,
    )
    ax.add_patch(box)
    ax.text(
        x + width / 2,
        y + height * 0.62,
        title,
        ha="center",
        va="center",
        fontsize=15,
        fontweight="bold",
        color="#1f2933",
    )
    ax.text(
        x + width / 2,
        y + height * 0.33,
        subtitle,
        ha="center",
        va="center",
        fontsize=10.5,
        color="#3f4d5a",
    )


def add_arrow(ax, start, end, label=None):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=16,
        linewidth=1.8,
        color="#2f3b45",
        shrinkA=3,
        shrinkB=3,
    )
    ax.add_patch(arrow)
    if label:
        ax.text(
            (start[0] + end[0]) / 2,
            start[1] + 0.58,
            label,
            ha="center",
            va="bottom",
            fontsize=10,
            color="#52606d",
        )


def add_wave(ax, x0, x1, y, amp=0.18, cycles=2.2, color="#1f78b4"):
    x = np.linspace(x0, x1, 350)
    phase = np.linspace(0, cycles * 2 * np.pi, x.size)
    ax.plot(x, y + amp * np.sin(phase), color=color, linewidth=2.6)


def add_sampled_wave(ax, x0, x1, y):
    x = np.linspace(x0, x1, 9)
    phase = np.linspace(0, 2.2 * 2 * np.pi, x.size)
    values = y + 0.18 * np.sin(phase)
    ax.vlines(x, y - 0.26, values, color="#1f78b4", linewidth=1.5, alpha=0.55)
    ax.scatter(x, values, s=48, color="#1f78b4", zorder=3)


def add_quantized_signal(ax, x0, x1, y):
    x = np.linspace(x0, x1, 10)
    phase = np.linspace(0, 2.2 * 2 * np.pi, x.size)
    raw = 0.18 * np.sin(phase)
    levels = np.round(raw / 0.12) * 0.12
    ax.step(x, y + levels, where="post", color="#b7791f", linewidth=2.6)
    ax.scatter(x, y + levels, s=34, color="#b7791f", zorder=3)
    for level in [-0.24, -0.12, 0, 0.12, 0.24]:
        ax.hlines(y + level, x0, x1, color="#d8c7a0", linewidth=0.8, alpha=0.7)


def add_bits(ax, x0, x1, y, color="#2f855a"):
    xs = np.linspace(x0, x1, 8)
    bits = np.array([1, 0, 1, 0, 1, 1, 0, 1])
    ax.vlines(xs, y, y + bits * 0.45, color=color, linewidth=2.2)
    ax.scatter(xs, y + bits * 0.45, s=48, color=color, zorder=3)
    ax.text((x0 + x1) / 2, y + 0.72, "1  0  1  0  1  1  0  1", ha="center", fontsize=11, color="#1f2933")


def main():
    fig, ax = plt.subplots(figsize=(15.8, 4.2))
    fig.patch.set_alpha(0)
    ax.set_facecolor("white")
    ax.set_xlim(0, 15.8)
    ax.set_ylim(0.65, 4.15)
    ax.axis("off")

    analog_color = "#e8f1f8"
    process_color = "#fff4d6"
    digital_color = "#eaf6ea"

    boxes = [
        ((0.55, 2.55), 1.8, 0.95, "Analog", "$x(t)$", analog_color),
        ((3.0, 2.55), 1.75, 0.95, "Sampling", "$x[n]=x(nT_s)$", process_color),
        ((5.4, 2.55), 1.95, 0.95, "Quantization", "$x_Q[n]=Q(x[n])$", process_color),
        ((8.1, 2.55), 1.65, 0.95, "Encoding", "$b_k$", process_color),
        ((11.25, 2.3), 3.45, 1.45, "Digital Bits", "$b_k \\in \\{0,1\\}$", digital_color),
    ]
    for args in boxes:
        add_box(ax, *args)

    add_arrow(ax, (2.35, 3.03), (3.0, 3.03), "sample")
    add_arrow(ax, (4.75, 3.03), (5.4, 3.03), "map to levels")
    add_arrow(ax, (7.35, 3.03), (8.1, 3.03), "assign bits")
    add_arrow(ax, (9.75, 3.03), (11.25, 3.03), "serialize")

    add_wave(ax, 0.72, 2.15, 1.55)
    ax.text(1.43, 1.05, "continuous-valued signal", ha="center", fontsize=11, color="#52606d")

    add_sampled_wave(ax, 3.1, 4.62, 1.52)
    ax.text(3.86, 1.05, "samples in time", ha="center", fontsize=11, color="#52606d")

    add_quantized_signal(ax, 5.55, 7.18, 1.52)
    ax.text(6.36, 1.05, "finite amplitude levels", ha="center", fontsize=11, color="#52606d")

    add_bits(ax, 8.2, 9.62, 1.28)
    ax.text(8.91, 1.05, "encoded bit sequence", ha="center", fontsize=11, color="#52606d")

    add_bits(ax, 11.85, 14.25, 1.24)
    ax.text(13.05, 1.05, "digital representation", ha="center", fontsize=11, color="#52606d")

    ax.text(
        7.65,
        3.98,
        "Analog-to-Digital Conversion Pipeline",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        color="#1f2933",
    )

    fig.savefig(
        OUTPUT,
        format="png",
        dpi=180,
        transparent=False,
        facecolor=(1, 1, 1, 0),
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.15,
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
