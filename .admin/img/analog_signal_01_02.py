import io
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import Image, display
from ipywidgets import interact, FloatSlider

# Reset stale inline backend options from earlier runs. Matplotlib's PNG backend
# does not accept a `transparent` keyword in some versions.
%config InlineBackend.print_figure_kwargs = {'bbox_inches': 'tight'}

def display_transparent_plot(x, y):
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(1)
    ax.set_facecolor('white')
    ax.plot(x, y, linewidth=2)
    ax.set_xlabel('Time [s]', fontsize=24)
    ax.set_ylabel('Amplitude', fontsize=24)
    ax.tick_params(axis='both', labelsize=20)
    ax.grid(True)

    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format='png',
        transparent=False,
        facecolor=(1, 1, 1, 0),
        edgecolor='none',
        bbox_inches='tight',
    )
    plt.close(fig)
    display(Image(data=buffer.getvalue()))

# Generate a time array from 0 to 1 second, with 1000 samples
t = np.linspace(0, 1, 1000)

# Generate and plot a sine wave with frequency of 5 Hz
analog_signal = np.sin(2 * np.pi * 5 * t)
display_transparent_plot(t, analog_signal)

# Generate and plot an exponentially decaying analog signal
random_analog_signal = np.exp(-5 * t)
display_transparent_plot(t, random_analog_signal)