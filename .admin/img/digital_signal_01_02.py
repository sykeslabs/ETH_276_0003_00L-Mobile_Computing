import numpy as np
import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def save_digital_signal(path, values, ylabel, ylim, yticks, sample_interval=1):
    n = len(values)
    t = np.arange(n) * sample_interval

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(1)
    ax.set_facecolor("white")

    ax.vlines(t, ymin=ylim[0], ymax=values, linewidth=2.5, alpha=0.55)
    ax.scatter(t, values, s=130, zorder=3)

    ax.set_xlabel("Time [s]", fontsize=24)
    ax.set_ylabel(ylabel, fontsize=24)
    ax.set_xlim(-0.5 * sample_interval, (n - 0.5) * sample_interval)
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks)
    ax.set_xticks(t)
    ax.set_xticklabels([f"{value:g}" for value in t])
    ax.tick_params(axis="both", labelsize=20)
    ax.grid(axis="y", color="#c7cdd1", linewidth=1.2, alpha=0.8)
    ax.grid(axis="x", visible=False)

    fig.savefig(
        path,
        format="png",
        transparent=False,
        facecolor=(1, 1, 1, 0),
        edgecolor="none",
        bbox_inches="tight",
    )
    plt.close(fig)


def main():
    rng = np.random.default_rng(seed=7)
    T = 1

    random_bits = rng.integers(0, 2, size=16)
    save_digital_signal(
        ".admin/img/digital_signal_01.png",
        random_bits,
        ylabel="Bit value s[n]",
        ylim=(-0.1, 1.2),
        yticks=[0, 1],
        sample_interval=T,
    )

    symbol_values = rng.integers(0, 256, size=16)
    save_digital_signal(
        ".admin/img/digital_signal_02.png",
        symbol_values,
        ylabel="Symbol value s[n]",
        ylim=(0, 275),
        yticks=[0, 64, 128, 192, 255],
        sample_interval=T,
    )


if __name__ == "__main__":
    main()
