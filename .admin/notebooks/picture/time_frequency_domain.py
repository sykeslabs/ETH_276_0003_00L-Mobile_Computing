import os
import tempfile

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUTPUT = ".admin/notebooks/picture/time-frequency-domain.png"


COLORS = {
    "dark": "#27343d",
    "muted": "#52606d",
    "grid": "#c9d1d6",
    "panel": "#f8fafb",
    "red": "#d64545",
    "blue": "#1f78b4",
    "green": "#2f855a",
    "purple": "#7f4fb3",
    "orange": "#c47a1c",
}


def draw_panel(ax, xy, width, height, title):
    x, y = xy
    panel = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.015,rounding_size=0.035",
        linewidth=1.6,
        edgecolor=COLORS["dark"],
        facecolor=COLORS["panel"],
    )
    ax.add_patch(panel)

    for i in range(1, 5):
        gx = x + i * width / 5
        gy = y + i * height / 5
        ax.plot([gx, gx], [y, y + height], color=COLORS["grid"], linewidth=0.8)
        ax.plot([x, x + width], [gy, gy], color=COLORS["grid"], linewidth=0.8)

    ax.text(
        x + width / 2,
        y + height + 0.28,
        title,
        ha="center",
        va="bottom",
        fontsize=17,
        fontweight="bold",
        color=COLORS["dark"],
    )


def panel_coordinates(xy, width, height, x_values, y_values, y_min=-1.4, y_max=1.4):
    x0, y0 = xy
    px = x0 + width * (x_values - x_values.min()) / (x_values.max() - x_values.min())
    py = y0 + height * (y_values - y_min) / (y_max - y_min)
    return px, py


def draw_time_signal(ax, xy, width, height):
    t = np.linspace(0, 1, 800)
    signal = (
        0.8 * np.sin(2 * np.pi * 3 * t)
        + 0.45 * np.sin(2 * np.pi * 8 * t + 0.5)
        + 0.25 * np.sin(2 * np.pi * 14 * t + 1.2)
    )
    x, y = panel_coordinates(xy, width, height, t, signal, y_min=-1.6, y_max=1.6)
    ax.plot(x, y, color=COLORS["red"], linewidth=2.5)

    x0, y0 = xy
    arrow = FancyArrowPatch(
        (x0 + 0.4, y0 - 0.35),
        (x0 + width - 0.4, y0 - 0.35),
        arrowstyle="->",
        mutation_scale=14,
        linewidth=1.5,
        color=COLORS["dark"],
    )
    ax.add_patch(arrow)
    ax.text(
        x0 + width / 2,
        y0 - 0.68,
        "time",
        ha="center",
        va="top",
        fontsize=15,
        color=COLORS["dark"],
    )


def draw_frequency_spectrum(ax, xy, width, height):
    freqs = np.arange(1, 19)
    amplitudes = 0.08 + 0.04 * np.sin(freqs * 0.9)
    amplitudes[[2, 7, 13]] = [1.0, 0.56, 0.32]

    x0, y0 = xy
    bar_width = width / 28
    for freq, amp in zip(freqs, amplitudes):
        x = x0 + width * (freq - freqs.min()) / (freqs.max() - freqs.min())
        ax.add_patch(
            plt.Rectangle(
                (x - bar_width / 2, y0),
                bar_width,
                height * amp * 0.88,
                color=COLORS["blue"],
                alpha=0.95,
            )
        )

    for freq, amp in zip([3, 8, 14], [1.0, 0.56, 0.32]):
        x = x0 + width * (freq - freqs.min()) / (freqs.max() - freqs.min())
        ax.plot(
            [x, x],
            [y0, y0 + height * amp * 0.88],
            color="#0ea5d7",
            linewidth=3.2,
        )

    arrow = FancyArrowPatch(
        (x0 + 0.4, y0 - 0.35),
        (x0 + width - 0.4, y0 - 0.35),
        arrowstyle="->",
        mutation_scale=14,
        linewidth=1.5,
        color=COLORS["dark"],
    )
    ax.add_patch(arrow)
    ax.text(
        x0 + width / 2,
        y0 - 0.68,
        "frequency",
        ha="center",
        va="top",
        fontsize=15,
        color=COLORS["dark"],
    )


def draw_component_wave(ax, center, length, amplitude, cycles, color, label):
    cx, cy = center
    x = np.linspace(cx - length / 2, cx + length / 2, 600)
    phase = np.linspace(0, cycles * 2 * np.pi, x.size)
    y = cy + amplitude * np.sin(phase)
    ax.plot(x, y, color=color, linewidth=2.1)
    ax.text(
        cx + length / 2 + 0.18,
        cy,
        label,
        ha="left",
        va="center",
        fontsize=11,
        color=COLORS["muted"],
    )


def draw_transform_arrow(ax, start, end):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=18,
        linewidth=2.0,
        color=COLORS["dark"],
        connectionstyle="arc3,rad=0.0",
    )
    ax.add_patch(arrow)

def main():
    fig, ax = plt.subplots(figsize=(12.0, 5.8))
    fig.patch.set_alpha(0)
    ax.set_facecolor("white")
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 6.0)
    ax.axis("off")

    left_xy = (0.55, 1.45)
    right_xy = (8.75, 1.45)
    panel_w = 3.05
    panel_h = 2.5

    draw_panel(ax, left_xy, panel_w, panel_h, "Time domain")
    draw_time_signal(ax, left_xy, panel_w, panel_h)

    draw_panel(ax, right_xy, panel_w, panel_h, "Frequency domain")
    draw_frequency_spectrum(ax, right_xy, panel_w, panel_h)

    draw_component_wave(ax, (5.55, 4.55), 2.75, 0.16, 3, COLORS["green"], "low f")
    draw_component_wave(ax, (5.55, 3.85), 2.75, 0.13, 8, COLORS["purple"], "mid f")
    draw_component_wave(ax, (5.55, 3.20), 2.75, 0.10, 14, COLORS["orange"], "high f")

    draw_transform_arrow(ax, (3.85, 2.38), (4.85, 2.38))
    draw_transform_arrow(ax, (6.20, 2.38), (8.55, 2.38))
    ax.text(
        5.6,
        2.62,
        "frequency analysis",
        ha="center",
        va="bottom",
        fontsize=13,
        color=COLORS["dark"],
    )

    ax.text(
        5.15,
        5.55,
        "Waveform and frequency components describe the same signal",
        ha="center",
        va="center",
        fontsize=14,
        color=COLORS["dark"],
    )

    fig.savefig(
        OUTPUT,
        dpi=180,
        transparent=False,
        facecolor=(1, 1, 1, 0),
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.08,
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
