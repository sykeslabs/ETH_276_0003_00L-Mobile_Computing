"""Interactive sinusoid controls and time/frequency plots for notebook 01.2."""

from io import BytesIO
from IPython.display import HTML, Image, display
from ipywidgets import Checkbox, FloatSlider, HBox, Layout, VBox
import numpy as np
import matplotlib.pyplot as plt


TRANSPARENT_WIDGET_STYLE = HTML("""
<style>
.jp-Cell-outputWrapper,
.jp-Cell-outputArea,
.jp-OutputArea,
.jp-OutputArea-child,
.jp-OutputArea-output,
.jp-RenderedWidget,
.output,
.output_area,
.output_subarea,
.output_wrapper,
.output_widget_view,
.cell-output,
.cell-output-ipywidget-background,
.widget-area,
.widget-subarea {
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
    border: none !important;
}

.transparent-widget-controls,
.transparent-widget-controls.widget-box,
.transparent-widget-controls.widget-hbox,
.transparent-widget-controls.widget-vbox,
.transparent-widget-controls .widget-box,
.transparent-widget-controls .widget-hbox,
.transparent-widget-controls .widget-vbox,
.transparent-widget-controls .widget-inline-hbox,
.transparent-widget-controls .widget-hslider,
.transparent-widget-controls .widget-slider,
.transparent-widget-controls .jupyter-widgets,
.transparent-widget-controls .p-Widget,
.transparent-widget-controls .lm-Widget {
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
    border: none !important;
}
</style>
""")


def make_time_frequency_figure(
    f1=3.0, a1=0.8, phi1_deg=0.0, hide1=False,
    f2=8.0, a2=0.45, phi2_deg=30.0, hide2=False,
    f3=14.0, a3=0.25, phi3_deg=70.0, hide3=False,
):
    duration = 1.0
    t = np.linspace(0, duration, 1000, endpoint=True)

    frequencies = np.array([f1, f2, f3])
    amplitudes = np.array([a1, a2, a3])
    phase_degrees = np.array([phi1_deg, phi2_deg, phi3_deg])
    phases = np.deg2rad(phase_degrees)
    hidden = np.array([hide1, hide2, hide3])
    colors = ["#2f855a", "#7f4fb3", "#c47a1c"]

    components = np.array([
        amplitude * np.sin(2 * np.pi * frequency * t + phase)
        for amplitude, frequency, phase in zip(amplitudes, frequencies, phases)
    ])
    x = components[~hidden].sum(axis=0)

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5), facecolor="none")
    fig.patch.set_alpha(0)
    for axis in ax:
        axis.set_facecolor("white")

    ax[0].plot(
        t,
        x,
        color="#d64545",
        linewidth=1,
        zorder=3,
        label="composite signal",
    )
    for i, (component, frequency, amplitude, phase, color, is_hidden) in enumerate(
        zip(components, frequencies, amplitudes, phase_degrees, colors, hidden),
        start=1,
    ):
        if is_hidden:
            continue
        ax[0].plot(
            t,
            component,
            color=color,
            alpha=0.45,
            linestyle="--",
            linewidth=0.8,
            label=f"s{i}: {frequency:.1f} Hz, A={amplitude:.2f}, phi={phase:.0f} deg",
        )
    ax[0].set_xlabel("Time [s]")
    ax[0].set_ylabel("Amplitude")
    ax[0].set_title("Time Domain: Composite Signal")
    ax[0].set_xlim(0, duration)
    ax[0].grid(True, axis="y", color="#c9d1d6", alpha=0.8)
    ax[0].legend(loc="upper right", fontsize=8)
    ax[0].set_ylim(-3.0, 3.0)

    visible_frequencies = frequencies[~hidden]
    visible_amplitudes = amplitudes[~hidden]
    ax[1].vlines(visible_frequencies, 0, visible_amplitudes, color="#1f78b4", linewidth=3.0)
    ax[1].scatter(visible_frequencies, visible_amplitudes, color="#1f78b4", s=46, zorder=3)
    ax[1].set_title("Source Frequency Components")
    ax[1].set_xlabel("Frequency [Hz]")
    ax[1].set_ylabel("Amplitude")
    ax[1].set_xlim(0, 30)
    ax[1].set_ylim(0, 1.25)
    ax[1].grid(True, axis="y", color="#c9d1d6", alpha=0.8)

    for frequency, amplitude in zip(visible_frequencies, visible_amplitudes):
        ax[1].annotate(
            f"{frequency:.1f} Hz",
            xy=(frequency, amplitude),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color="#27343d",
        )

    plt.tight_layout()
    return fig


def figure_image(fig):
    buffer = BytesIO()
    fig.savefig(
        buffer,
        format="png",
        dpi=120,
        bbox_inches="tight",
        transparent=False,
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    plt.close(fig)
    return Image(data=buffer.getvalue())


def show_time_frequency():
    """Display the interactive plots and return their sliders."""
    slider_block_layout = Layout(background="transparent", border="none", padding="0", margin="0 auto", width="fit-content")
    slider_row_layout = Layout(background="transparent", border="none", padding="0", margin="0", justify_content="center")
    slider_settings = {"continuous_update": False}
    controls = {
        "f1": FloatSlider(value=3.0, min=0.0, max=30.0, step=0.5, description="f1 [Hz]", **slider_settings),
        "a1": FloatSlider(value=0.8, min=0.0, max=1.0, step=0.05, description="A1", **slider_settings),
        "phi1_deg": FloatSlider(value=0.0, min=-180.0, max=180.0, step=5.0, description="phi1 [deg]", **slider_settings),
        "hide1": Checkbox(value=False, description="Hide", indent=False),
        "f2": FloatSlider(value=8.0, min=0.0, max=30.0, step=0.5, description="f2 [Hz]", **slider_settings),
        "a2": FloatSlider(value=0.45, min=0.0, max=1.0, step=0.05, description="A2", **slider_settings),
        "phi2_deg": FloatSlider(value=30.0, min=-180.0, max=180.0, step=5.0, description="phi2 [deg]", **slider_settings),
        "hide2": Checkbox(value=False, description="Hide", indent=False),
        "f3": FloatSlider(value=14.0, min=0.0, max=30.0, step=0.5, description="f3 [Hz]", **slider_settings),
        "a3": FloatSlider(value=0.25, min=0.0, max=1.0, step=0.05, description="A3", **slider_settings),
        "phi3_deg": FloatSlider(value=70.0, min=-180.0, max=180.0, step=5.0, description="phi3 [deg]", **slider_settings),
        "hide3": Checkbox(value=False, description="Hide", indent=False),
    }

    slider_row_1 = HBox([controls["f1"], controls["a1"], controls["phi1_deg"], controls["hide1"]], layout=slider_row_layout)
    slider_row_2 = HBox([controls["f2"], controls["a2"], controls["phi2_deg"], controls["hide2"]], layout=slider_row_layout)
    slider_row_3 = HBox([controls["f3"], controls["a3"], controls["phi3_deg"], controls["hide3"]], layout=slider_row_layout)
    for row in (slider_row_1, slider_row_2, slider_row_3):
        row.add_class("transparent-widget-controls")
    slider_rows = VBox([slider_row_1, slider_row_2, slider_row_3], layout=slider_block_layout)

    def current_image():
        values = {name: widget.value for name, widget in controls.items()}
        return figure_image(make_time_frequency_figure(**values))


    slider_rows.add_class("transparent-widget-controls")
    display(TRANSPARENT_WIDGET_STYLE)
    display(slider_rows)
    image_handle = display(current_image(), display_id=True)


    def update_plot(change=None):
        image_handle.update(current_image())


    for widget in controls.values():
        widget.observe(update_plot, names="value")
    return controls
