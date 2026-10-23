import os
import tempfile

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUTPUT = ".admin/notebooks/picture/analog_digital_transmission_chain.png"


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
        y + height * 0.34,
        subtitle,
        ha="center",
        va="center",
        fontsize=11,
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


def add_wave(ax, x0, x1, y, amp=0.13, cycles=8, color="#1f78b4"):
    x = np.linspace(x0, x1, 500)
    phase = np.linspace(0, cycles * 2 * np.pi, x.size)
    envelope = 0.75 + 0.25 * np.sin(np.linspace(0, 3 * np.pi, x.size))
    ax.plot(x, y + amp * envelope * np.sin(phase), color=color, linewidth=2.4)


def main():
    fig, ax = plt.subplots(figsize=(16, 5.8))
    fig.patch.set_alpha(0)
    ax.set_facecolor("white")
    ax.set_xlim(0, 16)
    ax.set_ylim(1.15, 5.35)
    ax.axis("off")

    tx_color = "#e8f1f8"
    digital_color = "#eaf6ea"
    carrier_color = "#fff4d6"
    rx_color = "#f3edf7"

    add_box(ax, (0.45, 3.4), 1.65, 1.05, "Analog", "sensor signal", tx_color)
    add_box(ax, (2.55, 3.4), 1.35, 1.05, "ADC", "samples\n+ levels", tx_color)
    add_box(ax, (4.45, 3.4), 1.85, 1.05, "Digital", "bits + processing", digital_color)
    add_box(ax, (6.95, 3.4), 1.65, 1.05, "Modulator", "map bits\nto wave", carrier_color)
    add_box(ax, (11.05, 3.4), 1.65, 1.05, "Receiver", "analog front end", rx_color)
    add_box(ax, (13.55, 3.4), 1.65, 1.05, "Digital", "processing", digital_color)

    add_arrow(ax, (2.1, 3.93), (2.55, 3.93), "convert")
    add_arrow(ax, (3.9, 3.93), (4.45, 3.93))
    add_arrow(ax, (6.3, 3.93), (6.95, 3.93), "prepare for transmission")
    add_arrow(ax, (8.6, 3.93), (11.05, 3.93), "analog carrier through the channel")
    add_arrow(ax, (12.7, 3.93), (13.55, 3.93), "recover data")

    add_wave(ax, 0.55, 1.9, 2.35, amp=0.22, cycles=3)
    ax.text(1.22, 1.9, "continuous-valued signal", ha="center", fontsize=11, color="#52606d")

    bit_x = np.linspace(4.6, 6.15, 8)
    bits = np.array([1, 0, 1, 1, 0, 0, 1, 0])
    ax.vlines(bit_x, 1.9, 1.9 + bits * 0.55, color="#2f855a", linewidth=2.2)
    ax.scatter(bit_x, 1.9 + bits * 0.55, s=48, color="#2f855a", zorder=3)
    ax.text(5.38, 1.43, "discrete symbols", ha="center", fontsize=11, color="#52606d")

    add_wave(ax, 7.55, 10.55, 2.25, amp=0.24, cycles=15, color="#b7791f")
    ax.text(
        9.05,
        1.63,
        "physical waveform through air, wire, or light",
        ha="center",
        fontsize=11,
        color="#52606d",
    )

    bit_x_rx = np.linspace(13.65, 15.0, 7)
    bits_rx = np.array([1, 0, 1, 1, 0, 1, 0])
    ax.vlines(bit_x_rx, 1.9, 1.9 + bits_rx * 0.55, color="#2f855a", linewidth=2.2)
    ax.scatter(bit_x_rx, 1.9 + bits_rx * 0.55, s=48, color="#2f855a", zorder=3)
    ax.text(14.33, 1.43, "decoded data", ha="center", fontsize=11, color="#52606d")

    ax.text(3.4, 5.08, "Transmitter side", ha="center", fontsize=16, fontweight="bold", color="#1f2933")
    ax.text(9.0, 5.08, "Analog transmission channel", ha="center", fontsize=16, fontweight="bold", color="#1f2933")
    ax.text(13.1, 5.08, "Receiver side", ha="center", fontsize=16, fontweight="bold", color="#1f2933")

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
