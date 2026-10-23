"""Interactive Fourier-series examples for notebook 01.2, section 2.3."""

from io import BytesIO
from IPython.display import HTML, Image, display
from ipywidgets import FloatSlider, HBox, Layout, VBox, HTML as WidgetHTML
import matplotlib.pyplot as plt
import numpy as np


def exercise_figure_image(fig):
    buffer = BytesIO()
    fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    return Image(data=buffer.getvalue())


exercise_slider_block_layout = Layout(margin='0 auto', width='fit-content')
exercise_slider_row_layout = Layout(margin='0', justify_content='center')
exercise_widget_style = HTML('<style>.transparent-widget-controls { background: transparent !important; }</style>')

HARMONIC_COUNT = 7
exercise_t = np.linspace(0, 1, 1000, endpoint=False)


def rectangle_target(t):
    return np.where((t >= 0.2) & (t < 0.8), 1.0, 0.0)


def triangle_target(t):
    return np.piecewise(
        t,
        [t < 0.15, (t >= 0.15) & (t < 0.5), (t >= 0.5) & (t < 0.85), t >= 0.85],
        [0.0, lambda u: (u - 0.15) / 0.35, lambda u: (0.85 - u) / 0.35, 0.0],
    )


def trapezoid_target(t):
    return np.piecewise(
        t,
        [t < 0.1, (t >= 0.1) & (t < 0.3), (t >= 0.3) & (t < 0.7), (t >= 0.7) & (t < 0.9), t >= 0.9],
        [0.0, lambda u: (u - 0.1) / 0.2, 1.0, lambda u: (0.9 - u) / 0.2, 0.0],
    )


def initial_harmonics(target):
    # Convert the first seven complex Fourier coefficients to sine amplitude/phase form.
    coefficients = np.fft.fft(target) / target.size
    amplitudes = 2.0 * np.abs(coefficients[1:HARMONIC_COUNT + 1])
    phases = np.rad2deg(np.angle(coefficients[1:HARMONIC_COUNT + 1]) + np.pi / 2)
    phases = (phases + 180.0) % 360.0 - 180.0
    return float(coefficients[0].real), amplitudes, phases


def harmonic_exercise(title, target_function, error_parameter, error_harmonic, error_delta):
    target = target_function(exercise_t)
    dc_offset, default_amplitudes, default_phases = initial_harmonics(target)
    controls = []
    rows = []

    for m in range(1, HARMONIC_COUNT + 1):
        frequency_value = float(m)
        amplitude_value = round(float(default_amplitudes[m - 1]), 2)
        phase_value = round(float(default_phases[m - 1]), 1)
        if m == error_harmonic:
            if error_parameter == 'frequency':
                frequency_value += error_delta
            elif error_parameter == 'amplitude':
                amplitude_value += error_delta
            elif error_parameter == 'phase':
                phase_value += error_delta

        frequency = FloatSlider(
            value=frequency_value, min=0.5, max=12.0, step=0.1,
            description=f'f{m} [Hz]', continuous_update=False,
        )
        amplitude = FloatSlider(
            value=amplitude_value, min=0.0, max=1.5, step=0.01,
            description=f'A{m}', continuous_update=False,
        )
        phase = FloatSlider(
            value=phase_value, min=-180.0, max=180.0, step=0.1,
            description=f'phi{m} [deg]', continuous_update=False,
        )
        controls.append((frequency, amplitude, phase))
        rows.append(HBox([frequency, amplitude, phase], layout=exercise_slider_row_layout))

    control_box = VBox(rows, layout=exercise_slider_block_layout)
    control_box.add_class('transparent-widget-controls')

    def current_exercise_image():
        harmonic_sum = np.full_like(exercise_t, dc_offset)
        harmonic_components = []
        for frequency, amplitude, phase in controls:
            component = amplitude.value * np.sin(
                2 * np.pi * frequency.value * exercise_t + np.deg2rad(phase.value)
            )
            harmonic_components.append(component)
            harmonic_sum += component

        fig, ax = plt.subplots(figsize=(11, 3.5), facecolor='none')
        ax.set_facecolor('white')
        for index, component in enumerate(harmonic_components):
            ax.plot(
                exercise_t, component, color='#c7c7c7', linewidth=1.0, alpha=0.75,
                label='individual harmonics' if index == 0 else None,
            )
        ax.plot(exercise_t, target, '--', color='#202124', linewidth=2.4, label='target')
        ax.plot(exercise_t, harmonic_sum, color='#d64545', linewidth=2.0, label='DC + sum of 7 harmonics')
        ax.set(title=title, xlabel='Time [s]', ylabel='Amplitude', xlim=(0, 1), ylim=(-0.4, 1.4))
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        fig.tight_layout()
        return exercise_figure_image(fig)

    def reference_equations():
        equations = []
        for m, (amplitude, phase) in enumerate(zip(default_amplitudes, default_phases), start=1):
            equations.append(
                f'<i>s</i><sub>{m}</sub>(<i>t</i>) = {amplitude:.2f} sin('
                f'2&pi; &middot; {float(m):.1f} <i>t</i> '
                f'{phase:+.1f}&deg;)'
            )
        equation_grid = ''.join(
            f'<div style="padding: 2px 14px 2px 0;">{equation}</div>'
            for equation in equations
        )
        return (
            '<b>Reference equations (best seven-harmonic values):</b>'
            '<div style="display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); '
            'gap: 2px 24px; margin: 6px 0 12px 0;">'
            + equation_grid + '</div>'
        )

    display(WidgetHTML(value=f'<h4>{title}</h4>'))
    equation_display = WidgetHTML(value=reference_equations())
    display(equation_display)
    display(control_box)
    image_handle = display(current_exercise_image(), display_id=True)

    def update_exercise(change=None):
        image_handle.update(current_exercise_image())

    for harmonic_controls in controls:
        for widget in harmonic_controls:
            widget.observe(update_exercise, names='value')


def show_harmonic_examples():
    """Display the three examples with sliders and reference equations."""
    display(exercise_widget_style)
    harmonic_exercise('Example 1 — Rectangle', rectangle_target, 'frequency', 4, 0.5)
    harmonic_exercise('Example 2 — Triangle', triangle_target, 'amplitude', 2, 0.20)
    harmonic_exercise('Example 3 — Trapezoid', trapezoid_target, 'phase', 3, -60.0)
