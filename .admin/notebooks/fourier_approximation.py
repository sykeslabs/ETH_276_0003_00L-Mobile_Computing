"""Plots for notebook 01.3, with one displayed output per example."""
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import Image, display
from ipywidgets import FloatSlider, IntSlider, Image as WidgetImage, VBox


def figure_image(fig):
    """Render once and close the figure before Jupyter can display it again."""
    buffer = BytesIO()
    try:
        fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight',
                    transparent=False, facecolor='none', edgecolor='none')
    finally:
        plt.close(fig)
    return Image(data=buffer.getvalue())


def _show_interactive(plot, slider):
    """Update one image widget in place when the slider changes."""
    image = WidgetImage(value=plot(slider.value).data, format='png')

    def update(change):
        image.value = plot(change['new']).data

    slider.observe(update, names='value')
    display(VBox([slider, image]))


def rect(t, T):
    """Unit-height rectangular pulse, using the Fourier-series value 1/2 at its edges."""
    distance = np.abs(t)
    values = (distance < T / 2).astype(float)
    values[np.isclose(distance, T / 2, rtol=0, atol=1e-12)] = 0.5
    return values

def X_analytic(f, T):
    """Continuous Fourier transform T*sinc(fT), with f in hertz."""
    return T * np.sinc(f * T)

def plot_pulse_and_spectrum(T=0.5):
    t = np.linspace(-2, 2, 4001)
    f = np.linspace(-20, 20, 8001)
    fig, (ax_t, ax_f) = plt.subplots(1, 2, figsize=(14, 4.5), facecolor='none')

    ax_t.plot(t, rect(t, T), color='yellow', linewidth=2)
    ax_t.set(xlabel='Time [s]', ylabel='x(t)', title=f'Rectangular pulse: T={T:.2f} s', ylim=(-0.1, 1.15))

    ax_f.plot(f, np.abs(X_analytic(f, T)), color='orange', linewidth=2)
    ax_f.axvline(-1 / T, color='white', linestyle='--', linewidth=1, label=r'first zeros $\pm1/T$')
    ax_f.axvline(1 / T, color='white', linestyle='--', linewidth=1)
    ax_f.set(xlabel='Frequency [Hz]', ylabel='|X(f)|', title=f'Null-to-null main-lobe width: {2/T:.2f} Hz')
    ax_f.legend()

    for ax in (ax_t, ax_f):
        ax.set_facecolor((0.2, 0.2, 0.3))
        ax.grid(alpha=0.25)
    plt.tight_layout()
    return figure_image(fig)


def show_pulse_and_spectrum():
    _show_interactive(plot_pulse_and_spectrum, FloatSlider(
        value=0.5, min=0.05, max=2.0, step=0.05,
        description='T [s]', continuous_update=False,
    ))



def plot_approximation(M=10):
    Fs_approx = 200.0
    T_obs = 10.0
    N_approx = int(Fs_approx * T_obs)
    t_approx = (np.arange(N_approx) - N_approx // 2) / Fs_approx
    T_rect = 0.5
    x_rect = rect(t_approx, T_rect)
    X_rect = np.fft.rfft(x_rect)
    f_bins = np.fft.rfftfreq(N_approx, 1 / Fs_approx)
    delta_f = Fs_approx / N_approx
    X_limited = np.zeros_like(X_rect)
    X_limited[:M + 1] = X_rect[:M + 1]  # DC plus M harmonic pairs
    x_limited = np.fft.irfft(X_limited, n=N_approx)
    cutoff = M * delta_f

    fig, (ax_t, ax_f) = plt.subplots(1, 2, figsize=(14, 4.5), facecolor='none')
    ax_t.plot(t_approx, x_rect, color='magenta', linewidth=3, label='ideal rectangle')
    ax_t.plot(t_approx, x_limited, color='white', linewidth=2, label=f'{M} harmonics')
    ax_t.set(xlabel='Time [s]', ylabel='Amplitude', title=f'Band-limited reconstruction: cutoff {cutoff:.2f} Hz', xlim=(-1.0, 1.0), ylim=(-0.2, 1.2))
    ax_t.legend()

    magnitude = 2 * np.abs(X_limited) / N_approx
    magnitude[0] /= 2
    ax_f.stem(f_bins[:M + 1], magnitude[:M + 1], linefmt='w-', markerfmt='wo', basefmt=' ')
    ax_f.set(xlabel='Frequency [Hz]', ylabel='One-sided amplitude', title=rf'Retained DFT components ($\Delta f={delta_f:.2f}$ Hz)', xlim=(-0.05, max(1.0, cutoff * 1.15)))

    for ax in (ax_t, ax_f):
        ax.set_facecolor((0.2, 0.2, 0.3))
        ax.grid(alpha=0.25)
    plt.tight_layout()
    return figure_image(fig)


def show_approximation():
    _show_interactive(plot_approximation, IntSlider(
        value=10, min=1, max=100, step=1,
        description='Harmonics', continuous_update=False,
    ))


def show_zero_order_hold():
    samples = np.array([0.25, 1.0, 0.55, 0.85, 0.35, 0.70])
    T_s = 0.10
    t_0 = 0.23
    n = np.arange(samples.size)

    # ZOH spectrum: shifted rectangular pulses of duration T_s.
    f_zoh = np.linspace(-30, 30, 4001)
    pulse_spectrum = T_s * np.sinc(f_zoh * T_s) * np.exp(-1j * np.pi * f_zoh * T_s)
    sample_spectrum = np.sum(
        samples[:, None] * np.exp(-1j * 2 * np.pi * n[:, None] * T_s * f_zoh[None, :]),
        axis=0,
    )
    X_zoh = pulse_spectrum * sample_spectrum
    X_delayed = X_zoh * np.exp(-1j * 2 * np.pi * f_zoh * t_0)

    fig = plt.figure(figsize=(12, 7), facecolor='none')
    grid = fig.add_gridspec(2, 2, height_ratios=[1.05, 1])
    ax_time = fig.add_subplot(grid[0, :])
    ax_mag = fig.add_subplot(grid[1, 0])
    ax_phase = fig.add_subplot(grid[1, 1])

    edges = np.arange(samples.size + 1) * T_s
    held_values = np.r_[samples, samples[-1]]
    ax_time.step(edges, held_values, where='post', linewidth=2.4, label='Original row of rectangles')
    ax_time.step(edges + t_0, held_values, where='post', linewidth=2.4, linestyle='--', label=rf'Delayed by $t_0={t_0}$ s')
    ax_time.set(xlabel='Time [s]', ylabel='Amplitude', title='Zero-order-hold representation of a digital time series')
    ax_time.set_xlim(-0.03, edges[-1] + t_0 + 0.04)
    ax_time.grid(True, alpha=0.3)
    ax_time.legend()

    ax_mag.plot(f_zoh, np.abs(X_zoh), linewidth=2.2, label=r'$|X(f)|$')
    ax_mag.plot(f_zoh, np.abs(X_delayed), '--', linewidth=1.8, label=r'$|X_d(f)|$')
    ax_mag.set(xlabel='Frequency [Hz]', ylabel='Magnitude', title='Identical magnitude and bandwidth')
    ax_mag.grid(True, alpha=0.3)
    ax_mag.legend()

    phase_change = -2 * np.pi * f_zoh * t_0
    ax_phase.plot(f_zoh, phase_change, color='#7f4fb3', linewidth=2.2)
    ax_phase.set(xlabel='Frequency [Hz]', ylabel='Phase change [rad]', title=r'Only phase changes: $\Delta\phi(f)=-2\pi f t_0$')
    ax_phase.grid(True, alpha=0.3)

    plt.tight_layout()
    display(figure_image(fig))