"""Sampling, aliasing, quantization, and encoding examples for notebook 01.4."""
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import Image, display
from ipywidgets import IntSlider, Image as WidgetImage, VBox


def _figure_image(fig):
    """Render and close the figure so Jupyter cannot display a second copy."""
    buffer = BytesIO()
    try:
        fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight',
                    transparent=False, facecolor='white', edgecolor='none')
    finally:
        plt.close(fig)
    return Image(data=buffer.getvalue())


def _show_interactive(make_figure, slider):
    image = WidgetImage(value=_figure_image(make_figure(slider.value)).data, format='png')

    def update(change):
        image.value = _figure_image(make_figure(change['new'])).data

    slider.observe(update, names='value')
    display(VBox([slider, image]))


def sample_signal(signal_function, t_start, t_end, sampling_frequency):
    T_s = 1 / sampling_frequency
    
    time_points = []
    sampled_values = []
    
    time_points = np.arange(t_start, t_end, T_s)
    for t in time_points:
        sampled_values.append(signal_function(t))
    return time_points, sampled_values


def make_sampling_figure(f_s):
    normalized_sine = lambda t: (np.sin(2 * np.pi * t) + 1) / 2
    time_points, sampled_values = sample_signal(normalized_sine, 0, 1.01, f_s)    
    fig = plt.figure(figsize=(10, 5))
    plt.plot(np.linspace(0, 1, 1000), normalized_sine(np.linspace(0, 1, 1000)), '-', label='Analog')
    plt.stem(time_points, sampled_values, 'r-', label=f'Sampled (f_s={f_s} Hz)', basefmt=" ")
    plt.xlabel('Time (s)')
    plt.legend(); 
    plt.grid();
    return fig


def make_adc_figure(f_s):
    
    # Analog signal: sum of 6 Hz and 20 Hz sinusoids
    t_cont = np.linspace(0, 1, 2000, endpoint=False)
    x_cont = np.sin(2 * np.pi * 6 * t_cont) + np.sin(2 * np.pi * 20 * t_cont)
    
    # Sampling
    Ts = 1 / f_s
    t_samp = np.arange(int(f_s)) / f_s
    x_samp = np.sin(2 * np.pi * 6 * t_samp) + np.sin(2 * np.pi * 20 * t_samp)
    
    # One-sided amplitude spectrum of the sampled signal.
    N = len(x_samp)
    X = np.fft.rfft(x_samp)
    freqs = np.fft.rfftfreq(N, d=Ts)
    amplitudes = np.abs(X) / N
    amplitudes[1:-1 if N % 2 == 0 else None] *= 2
    
    # Reconstruction via sinc interpolation
    # x_rec(t) = sum x[n] * sinc((t - nTs)/Ts)
    t_grid = t_cont
    sinc_matrix = np.sinc((t_grid[:, None] - t_samp[None, :]) / Ts)
    x_rec = sinc_matrix.dot(x_samp)
    
    # Plotting
    fig = plt.figure(figsize=(12, 6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2], hspace=0.3, wspace=0.3)
    
    # Top-left: analog + samples
    ax0 = fig.add_subplot(gs[0, 0])
    ax0.plot(t_cont, x_cont, 'b-', label='Analog')
    ax0.stem(t_samp, x_samp, 'r', markerfmt='ro', basefmt=" ", label='Samples')
    ax0.set_title(f'Sampling at {f_s} Hz')
    ax0.set_xlabel('Time (s)')
    ax0.set_ylabel('Amplitude')
    ax0.grid(True)
    ax0.legend()
    
    # Top-right: spectrum
    ax1 = fig.add_subplot(gs[0, 1])
    ax1.stem(freqs, amplitudes, 'g', markerfmt='go', basefmt=" ")
    ax1.set_title('Spectrum of sampled signal')
    ax1.set_xlabel('Frequency (Hz)')
    ax1.set_ylabel('One-sided amplitude')
    ax1.set_xlim(-1, f_s / 2 )
    ax1.grid(True)
    
    # Bottom: reconstructed signal + samples
    ax2 = fig.add_subplot(gs[1, :])
    ax2.plot(t_cont, x_rec, 'm-', label='Reconstructed')
    ax2.plot(t_cont, x_cont, 'b--', label='Original Analog', alpha=0.3)
    ax2.stem(t_samp, x_samp, 'r', markerfmt='ro', basefmt=" ", label='Samples')
    ax2.set_title('Reconstructed Signal from Samples')
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Amplitude')
    ax2.grid(True)
    ax2.legend()
    return fig


def uniform_quantizer(sampled_values, bits, V_fs=1):
    q = [] # quantized values
    delta = V_fs / (2 ** (bits) - 1)
    q = delta * np.round(sampled_values/ delta)
    return q


def make_quantization_figure(B):
    t = np.linspace(0, 1, 1000)
    sin = (np.sin(2*np.pi*t) + 1)/2
    sin_q = uniform_quantizer(sin, B, 1.0)
    lin = np.linspace(0, 1, len(t))
    lin_q = uniform_quantizer(lin, B, 1.0)

    fig, axs = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
    axs[0].plot(t, sin, 'b--', label='Analog')
    axs[0].step(t, sin_q, 'r', where='mid', label=f'Quantized ({B}-bit)')
    axs[0].set_title('Sine Signal')
    axs[0].set_xlabel('Time [s]')
    axs[0].legend()
    axs[0].grid(True)

    axs[1].plot(t, lin, 'b--', label='Analog')
    axs[1].step(t, lin_q, 'r', where='mid', label=f'Quantized ({B}-bit)')
    axs[1].set_title('Linear Signal')
    axs[1].set_xlabel('Time [s]')
    axs[1].legend()
    axs[1].grid(True)
    fig.tight_layout()
    return fig


def make_quantization_error_figure(B):
    t = np.linspace(0, 1, 1000)
    # Generate a half-shifted sine wave in [0,1]
    x = (np.sin(2 * np.pi * t) + 1) / 2
    xq = uniform_quantizer(x, B, V_fs=1.0)
    e = xq - x

    fig, axs = plt.subplots(1, 2, figsize=(12, 4), sharex=True)
    
    fig.suptitle(f"Quantization Step Size (Δ): {1/(2**B - 1):.4f} for {B}-bit quantization")
    # Left: Original vs Quantized
    axs[0].plot(t, x, 'b--', label='Original')
    axs[0].step(t, xq, 'r', where='mid', label=f'{B}-bit Quantized')
    axs[0].set_title('Original vs Quantized')
    axs[0].set_xlabel('Time [s]')
    axs[0].set_ylabel('Amplitude')
    axs[0].legend()
    axs[0].grid(True)
    
    # Right: Quantization Error
    axs[1].plot(t, e, 'm', label='Error')
    delta = 1 / (2**B - 1)
    axs[1].hlines([-delta / 2, delta / 2], 0, 1, colors='k', linestyles='--', label='±Δ/2')
    axs[1].set_title('Quantization Error')
    axs[1].set_xlabel('Time [s]')
    axs[1].set_ylabel('Error')
    axs[1].legend()
    axs[1].grid(True)
    axs[1].set_ylim(-0.55, 0.55)

    plt.tight_layout()
    return fig


def encode_fixed(q_values, bits, V_fs=1.0):
    L = 2**bits
    delta = V_fs / (L - 1)
    indices = np.round(q_values / delta).astype(int)
    return indices, [format(idx, f'0{bits}b') for idx in indices]


def show_sampling_comparison():
    """Compare sampling the same signal at 12 Hz and 100 Hz."""
    # Analog signal: equal-amplitude 6 Hz and 20 Hz sinusoids.
    t_cont = np.linspace(0, 1, 1000)
    x_cont = 0.5* np.sin(2 * np.pi * 20 * t_cont) + 0.5*np.sin(2 * np.pi * 6 * t_cont)  # adding a low frequency component for variety

    # two sampling rates to compare
    fs_values = [12, 100]  # Hz

    fig, axes = plt.subplots(2, 1, figsize=(8, 5), sharex=True)

    for ax, fs in zip(axes, fs_values):
        Ts = 1 / fs
        t_samp = np.arange(0, 1, Ts)
        x_samp =  0.5* np.sin(2 * np.pi * 20 * t_samp) + 0.5*np.sin(2 * np.pi * 6 * t_samp)
    
        ax.plot(t_cont, x_cont, 'b-', label='Analog signal (6 Hz + 20 Hz)')
        ax.stem(t_samp, x_samp, 'r', markerfmt='ro', basefmt=" ", 
                label=f'Sampled at {fs} Hz')
        ax.set_ylim(-1.2, 1.2)
        ax.set_ylabel('Amplitude')
        ax.set_title(f'Sampling at {fs} Hz')
        ax.grid(True)
        ax.legend()

    axes[-1].set_xlabel('Time (s)')
    plt.tight_layout()
    display(_figure_image(fig))

def show_encoding():
    """Display the fixed-length binary words for a quantized sine wave."""
    # Quantize a sine wave
    bits = 3
    t = np.linspace(0, 1, 16)
    x = (np.sin(2*np.pi*t) + 1) / 2  # normalized sine
    xq = uniform_quantizer(x, bits=bits, V_fs=1.0)

    # Encode
    indices, codes = encode_fixed(xq, bits=bits, V_fs=1.0)

    # Plot quantized signal with labels
    fig = plt.figure(figsize=(10,4))
    for ti, xi, code in zip(t, xq, codes):
        plt.text(ti, xi+0.05, code, ha='center', fontsize=9, rotation=90)

    plt.plot(t, x, 'b--', alpha=0.5, label="Original signal")
    plt.stem(t, xq, linefmt='r-', markerfmt='ro', basefmt=" ", label="Quantized + Encoded")
    plt.title("3-bit Fixed-Length Binary Encoding")
    plt.xlabel("Time [s]")
    plt.ylim(-0.1, 1.2)
    plt.ylabel("Amplitude / Code")
    plt.legend()
    plt.grid(True)
    display(_figure_image(fig))


def show_sampling():
    _show_interactive(make_sampling_figure, IntSlider(
        min=1, max=50, value=10, description='Sampling [Hz]',
        continuous_update=False,
    ))


def show_aliasing():
    _show_interactive(make_adc_figure, IntSlider(
        min=2, max=100, value=30, description='Sampling [Hz]',
        continuous_update=False,
    ))


def show_quantization():
    _show_interactive(make_quantization_figure, IntSlider(
        min=1, max=8, value=3, description='Bits',
        continuous_update=False,
    ))


def show_quantization_error():
    _show_interactive(make_quantization_error_figure, IntSlider(
        min=1, max=8, value=3, description='Bits',
        continuous_update=False,
    ))


