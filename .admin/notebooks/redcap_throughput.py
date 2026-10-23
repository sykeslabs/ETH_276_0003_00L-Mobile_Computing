"""Interactive throughput model for Notebook 03.9; run in the notebook namespace."""

import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as widgets
from IPython.display import display, Image
from io import BytesIO


def show_figure(fig):
    """Display one PNG and close the figure to prevent duplicate notebook output."""
    try:
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=140, bbox_inches="tight")
        display(Image(data=buffer.getvalue()))
    finally:
        plt.close(fig)


def payload_rate(bandwidth_mhz, eta, streams, overhead, resource_share):
    """Illustrative payload throughput in bit/s; bandwidth input is MHz."""
    return np.asarray(bandwidth_mhz) * 1e6 * eta * streams * (1 - overhead) * resource_share


def plot_throughput(bandwidth_mhz=20, eta=1.0, streams=1,
                    overhead=0.0, resource_share=1.0):
    sweep = np.linspace(5, 20, 200)
    rate = float(payload_rate(bandwidth_mhz, eta, streams, overhead, resource_share))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sweep, payload_rate(sweep, eta, streams, overhead, resource_share) / 1e6)
    ax.scatter([bandwidth_mhz], [rate / 1e6], color="tab:red", zorder=3)
    ax.set(xlabel="Bandwidth (MHz)", ylabel="Throughput (Mbit/s)")
    ax.grid(alpha=0.3)
    show_figure(fig)


a_controls = {
    "bandwidth_mhz": widgets.SelectionSlider(options=[5, 10, 15, 20], value=20, description="B (MHz)"),
    "eta": widgets.FloatSlider(value=1, min=0.25, max=5.5, step=0.25, description="eta (bit/s/Hz)", style={"description_width": "initial"}),
    "streams": widgets.Dropdown(options=[1, 2], value=1, description="Streams"),
    "overhead": widgets.FloatSlider(value=0, min=0, max=1, step=0.05, description="Overhead"),
    "resource_share": widgets.FloatSlider(value=1, min=0, max=1, step=0.1, description="Share q"),
}
a_output = widgets.interactive_output(plot_throughput, a_controls)
display(widgets.VBox(list(a_controls.values()) + [a_output]))
