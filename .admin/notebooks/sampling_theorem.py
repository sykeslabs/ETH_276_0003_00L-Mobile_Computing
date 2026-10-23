"""Shannon-Nyquist sampling theorem: step-by-step proof figures for notebook 01.8."""
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import Image, display
from ipywidgets import Dropdown, HBox, IntSlider, Image as WidgetImage, VBox

# Test signal shared with notebook 01.4, so the two notebooks describe the same example.
F_LOW = 6.0
F_HIGH = 20.0
F_MAX = F_HIGH
NYQUIST_RATE = 2 * F_MAX

_COPY_COLORS = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple']


def _figure_image(fig):
    """Render and close the figure so Jupyter cannot display a second copy."""
    buffer = BytesIO()
    try:
        fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight',
                    transparent=False, facecolor='white', edgecolor='none')
    finally:
        plt.close(fig)
    return Image(data=buffer.getvalue())


def _show_interactive(make_figure, **controls):
    """Render a figure that redraws whenever any of the named widgets changes."""
    def render():
        return _figure_image(
            make_figure(**{name: widget.value for name, widget in controls.items()})).data

    image = WidgetImage(value=render(), format='png')

    def update(change):
        image.value = render()

    for widget in controls.values():
        widget.observe(update, names='value')
    display(VBox([HBox(list(controls.values())), image]))


def test_signal(t):
    """The band-limited example signal used throughout the notebook."""
    t = np.asarray(t, dtype=float)
    return 0.5 * np.sin(2 * np.pi * F_LOW * t) + 0.5 * np.sin(2 * np.pi * F_HIGH * t)


SPECTRUM_SHAPES = ('two tones', 'trapezoid', 'brick wall')

_SHAPE_NOTES = {
    'two tones': 'the line locations of $x(t)$:\nnormalized to unit height',
    'trapezoid': 'a generic band-limited shape\nwith sloping edges',
    'brick wall': 'a band that stays full\nright up to $\\pm f_{max}$',
}


def _spikes(f, centres, half_width=0.25):
    """Narrow triangular spikes, so a line spectrum can reuse the same plotting code.

    The width is a drawing choice, but it must not change any verdict. The k=1 line
    closest to the passband edge sits f_s/2 - F_MAX above it, so a half width below
    0.5 Hz keeps every integer sampling rate on the slider judged by line position
    rather than by how thickly the line happens to be drawn.
    """
    out = np.zeros_like(f)
    for centre in centres:
        # A small flat top keeps every drawn line the same height whatever the grid
        # spacing; the support stays +-half_width, so no verdict changes.
        out = np.maximum(out, np.clip(
            (half_width - np.abs(f - centre)) / (0.5 * half_width), 0.0, 1.0))
    return out


def _band_shape(f, shape='trapezoid'):
    """A band-limited spectrum, exactly zero for |f| > F_MAX.

    The proof uses only the fact that X(f) vanishes outside the band, so the notebook
    offers several shapes and the argument has to hold for every one of them. The two
    smooth shapes stand in for the test signal's line spectrum in the replica figures,
    where overlapping spectral lines on their own would not be legible.
    """
    f = np.asarray(f, dtype=float)
    a = np.abs(f)
    if shape == 'two tones':
        return _spikes(f, (-F_HIGH, -F_LOW, F_LOW, F_HIGH))
    if shape == 'brick wall':
        return np.where(a <= F_MAX, 1.0, 0.0)
    flat = 0.7 * F_MAX
    return np.clip(np.where(a <= flat, 1.0, (F_MAX - a) / (F_MAX - flat)), 0.0, 1.0)


def show_spectrum_choices():
    """Show the three stand-ins for X(f) side by side, before they are copied."""
    f = np.linspace(-45, 45, 6000)
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), sharey=True)
    for ax, shape in zip(axes, SPECTRUM_SHAPES):
        values = _band_shape(f, shape)
        ax.axvspan(-F_MAX, F_MAX, color='tab:blue', alpha=0.07)
        ax.fill_between(f, 0, values, color='tab:blue', alpha=0.3)
        ax.plot(f, values, color='tab:blue', linewidth=1.8)
        for edge in (-F_MAX, F_MAX):
            ax.axvline(edge, color='tab:red', linestyle='--', linewidth=1)
        ax.set_xlim(-45, 45)
        ax.set_ylim(0, 1.3)
        ax.set_xlabel('Frequency (Hz)')
        ax.set_title(f'"{shape}"\n{_SHAPE_NOTES[shape]}', fontsize=10)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel('normalized $|X(f)|$')
    fig.suptitle('Three choices for $X(f)$. Every one is zero outside '
                 '$\\pm f_{max}=20$ Hz, which is the only property the proof uses.')
    fig.tight_layout()
    display(_figure_image(fig))


def sinc_reconstruct(t_eval, t_samples, x_samples, T_s):
    """Ideal band-limited interpolation: sum of sample-weighted, shifted sinc functions."""
    kernel = np.sinc((np.asarray(t_eval)[:, None] - np.asarray(t_samples)[None, :]) / T_s)
    return kernel @ np.asarray(x_samples)


def _relative_rms_error(f_s, t_view, margin=2.0):
    """Relative RMS error of sinc reconstruction of the test signal at sampling rate f_s.

    Samples are taken over an interval wider than the viewing window, so that truncating
    the infinite reconstruction sum does not dominate the error near the window edges.
    """
    T_s = 1.0 / f_s
    t_samples = np.arange(t_view[0] - margin, t_view[-1] + margin, T_s)
    x_samples = test_signal(t_samples)
    reconstructed = sinc_reconstruct(t_view, t_samples, x_samples, T_s)
    truth = test_signal(t_view)
    return float(np.sqrt(np.mean((reconstructed - truth) ** 2))
                 / np.sqrt(np.mean(truth ** 2)))


# --------------------------------------------------------------------------------------
# 8.2  Step 1: the signal x(t)
# --------------------------------------------------------------------------------------

def show_signal_and_spectrum():
    t = np.linspace(0, 0.5, 2000)
    fig, (ax_time, ax_freq) = plt.subplots(1, 2, figsize=(12, 4))

    ax_time.plot(t, test_signal(t), color='tab:blue')
    ax_time.set_title('Time domain: $x(t)$')
    ax_time.set_xlabel('Time (s)')
    ax_time.set_ylabel('Amplitude')
    ax_time.grid(alpha=0.3)

    lines = [(-F_HIGH, 0.25), (-F_LOW, 0.25), (F_LOW, 0.25), (F_HIGH, 0.25)]
    ax_freq.axvspan(-F_MAX, F_MAX, color='tab:blue', alpha=0.08)
    for frequency, amplitude in lines:
        ax_freq.stem([frequency], [amplitude], linefmt='tab:blue', markerfmt='o', basefmt=' ')
    for edge in (-F_MAX, F_MAX):
        ax_freq.axvline(edge, color='tab:red', linestyle='--', linewidth=1)
    ax_freq.text(0, 0.29, 'occupied band', ha='center', color='tab:blue', fontsize=9)
    ax_freq.text(F_MAX + 2, 0.20, '$X(f)=0$\nbeyond here', color='tab:red', fontsize=9)
    ax_freq.set_xlim(-45, 45)
    ax_freq.set_ylim(0, 0.34)
    ax_freq.set_title('Frequency domain: $|X(f)|$, two-sided')
    ax_freq.set_xlabel('Frequency (Hz)')
    ax_freq.set_ylabel('Magnitude')
    ax_freq.grid(alpha=0.3)

    fig.suptitle(f'$x(t)=0.5\\sin(2\\pi\\,6t)+0.5\\sin(2\\pi\\,20t)$, '
                 f'band-limited to $f_{{max}}={F_MAX:.0f}$ Hz')
    fig.tight_layout()
    display(_figure_image(fig))


# --------------------------------------------------------------------------------------
# 8.3  Step 2: the sampling function and its Fourier series
# --------------------------------------------------------------------------------------

def _make_impulse_train_figure(harmonics, f_s=20.0):
    T_s = 1.0 / f_s
    t = np.linspace(0, 0.3, 4000)

    partial_sum = np.ones_like(t) / T_s
    for k in range(1, harmonics + 1):
        partial_sum += (2.0 / T_s) * np.cos(2 * np.pi * k * f_s * t)

    fig, (ax_time, ax_coeff) = plt.subplots(2, 1, figsize=(11, 6))

    for spike in np.arange(0, 0.3 + T_s / 2, T_s):
        ax_time.axvline(spike, color='tab:red', linestyle=':', linewidth=1)
    ax_time.plot(t, partial_sum, color='tab:blue')
    ax_time.axhline(1 / T_s, color='grey', linestyle='--', linewidth=1)
    ax_time.text(0.302, 1 / T_s, '$1/T_s$', va='center', fontsize=9, color='grey')
    ax_time.set_xlim(0, 0.3)
    ax_time.set_xlabel('Time (s)')
    ax_time.set_ylabel('Amplitude')
    ax_time.set_title(f'Partial sum with $K={harmonics}$ harmonic pairs '
                      f'(peak value $={(2 * harmonics + 1) / T_s:.0f}$). '
                      f'Dotted lines mark the sampling instants $nT_s$.')
    ax_time.grid(alpha=0.3)

    k_values = np.arange(-harmonics, harmonics + 1)
    ax_coeff.stem(k_values * f_s, np.full(k_values.size, 1 / T_s),
                  linefmt='tab:green', markerfmt='o', basefmt=' ')
    ax_coeff.axhline(1 / T_s, color='grey', linestyle='--', linewidth=1)
    # The axis follows K, otherwise a small K is an unreadable cluster near zero. The
    # annotations keep the essential point visible: the harmonics never stop.
    limit = max(6, harmonics + 2) * f_s
    ax_coeff.set_xlim(-limit, limit)
    ax_coeff.set_ylim(0, 1.6 / T_s)
    for side in (-1, 1):
        ax_coeff.text(side * limit * 0.97, 1.28 / T_s, '$\\cdots$ forever',
                      ha=('left' if side < 0 else 'right'), color='grey', fontsize=9)
    ax_coeff.set_xlabel('Frequency (Hz)')
    ax_coeff.set_ylabel('$|c_k|$')
    ax_coeff.set_title('Fourier coefficients of $s(t)$: every harmonic $kf_s$ carries '
                       'the same weight $1/T_s$')
    ax_coeff.grid(alpha=0.3)

    fig.tight_layout()
    return fig


def show_impulse_train_series():
    _show_interactive(_make_impulse_train_figure,
                      harmonics=IntSlider(value=3, min=0, max=40, step=1,
                                          description='K:', continuous_update=False))


# --------------------------------------------------------------------------------------
# 8.4  Step 3: sampling is multiplication
# --------------------------------------------------------------------------------------

def show_multiplication(f_s=60.0):
    T_s = 1.0 / f_s
    t = np.linspace(0, 0.3, 3000)
    t_samples = np.arange(0, 0.3 + T_s / 2, T_s)

    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True)

    axes[0].plot(t, test_signal(t), color='tab:blue')
    axes[0].set_ylabel('$x(t)$')
    axes[0].set_title('The signal')
    axes[0].grid(alpha=0.3)

    axes[1].stem(t_samples, np.ones_like(t_samples),
                 linefmt='tab:red', markerfmt='^', basefmt=' ')
    axes[1].set_ylabel('$s(t)$')
    axes[1].set_ylim(0, 1.4)
    axes[1].set_title(f'The sampling function: unit spikes every $T_s={T_s * 1000:.1f}$ ms '
                      f'($f_s={f_s:.0f}$ Hz)')
    axes[1].grid(alpha=0.3)

    axes[2].plot(t, test_signal(t), color='tab:blue', alpha=0.25)
    axes[2].stem(t_samples, test_signal(t_samples),
                 linefmt='tab:red', markerfmt='o', basefmt=' ')
    axes[2].set_ylabel('$x_s(t)$')
    axes[2].set_xlabel('Time (s)')
    axes[2].set_title('Their product: each spike is now weighted by $x(nT_s)$')
    axes[2].grid(alpha=0.3)

    fig.tight_layout()
    display(_figure_image(fig))


def _make_replica_figure(copies, shape='two tones', f_s=50.0):
    T_s = 1.0 / f_s
    f = np.linspace(-170, 170, 9000)
    fig, ax = plt.subplots(figsize=(11, 4))

    scale = 1.0 / T_s
    ax.plot(f, scale * _band_shape(f, shape), color=_COPY_COLORS[0], linewidth=2,
            label='$k=0$ (the original $X(f)$)')
    ax.fill_between(f, 0, scale * _band_shape(f, shape), color=_COPY_COLORS[0], alpha=0.25)

    for index in range(1, copies + 1):
        color = _COPY_COLORS[index % len(_COPY_COLORS)]
        for k in (index, -index):
            shifted = scale * _band_shape(f - k * f_s, shape)
            ax.plot(f, shifted, color=color, linewidth=1.6)
            ax.fill_between(f, 0, shifted, color=color, alpha=0.20)
            ax.axvline(k * f_s, color=color, linestyle=':', linewidth=1)
        ax.plot([], [], color=color, linewidth=1.6, label=f'$k=\\pm{index}$')

    ax.set_xlim(-170, 170)
    ax.set_ylim(0, 1.3 * scale)
    ax.axhline(scale, color='grey', linestyle='--', linewidth=1)
    ax.text(-168, scale * 1.04, '$1/T_s$', color='grey', fontsize=9)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('normalized magnitude, scaled by $1/T_s$')
    ax.set_title(f'$X_s(f)$ built one term at a time.     $X(f)$ = "{shape}",     '
                 f'$f_s={f_s:.0f}$ Hz,     showing $k=-{copies}\\dots{copies}$')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def show_spectral_replicas():
    _show_interactive(
        _make_replica_figure,
        copies=IntSlider(value=0, min=0, max=3, step=1,
                         description='copies:', continuous_update=False),
        shape=Dropdown(options=SPECTRUM_SHAPES, value='two tones', description='X(f):'))


# --------------------------------------------------------------------------------------
# 8.5  Step 4: the no-overlap condition
# --------------------------------------------------------------------------------------

def _make_overlap_figure(f_s, shape='trapezoid'):
    """Show the spectral copies and, in the passband, what the ideal filter actually returns.

    Only k = -2..2 is drawn. For any f_s at or above f_max, no copy beyond k = +-1 can reach
    inside the passband, so nothing that matters to the argument is left out.

    The red marking is content from a copy other than k = 0 that falls inside the passband.
    That is the criterion that decides recoverability, and unlike 'two copies are nonzero at
    the same frequency' it is also correct for a line spectrum, whose lines interleave with
    their neighbours' lines rather than landing on top of them.
    """
    f_s = float(f_s)
    T_s = 1.0 / f_s
    f = np.linspace(-100, 100, 9000)
    k_values = list(range(-2, 3))
    scale = 1.0 / T_s
    copies = scale * np.array([_band_shape(f - k * f_s, shape) for k in k_values])
    total = copies.sum(axis=0)
    passband = np.abs(f) <= f_s / 2
    neighbours = np.array([row for row, k in zip(copies, k_values) if k != 0]).max(axis=0)
    intruding = passband & (neighbours > 1e-9)
    critical = abs(f_s - NYQUIST_RATE) < 1e-9
    clear = f_s > NYQUIST_RATE

    fig, (ax_copies, ax_band) = plt.subplots(2, 1, figsize=(11, 7.5))

    for row, k in zip(copies, k_values):
        color = _COPY_COLORS[abs(k) % len(_COPY_COLORS)]
        ax_copies.plot(f, row, color=color, linewidth=1.6)
        ax_copies.fill_between(f, 0, row, color=color, alpha=0.16)
    ax_copies.axvspan(-f_s / 2, f_s / 2, color='tab:purple', alpha=0.07)
    ax_copies.fill_between(f, 0, neighbours, where=intruding, color='red', alpha=0.6,
                           label='content from another copy, inside the passband')
    for edge in (F_MAX, -F_MAX):
        ax_copies.axvline(edge, color='k', linestyle='--', linewidth=1)
    for edge in (f_s / 2, -f_s / 2):
        ax_copies.axvline(edge, color='tab:purple', linestyle='-.', linewidth=1.2)
    # The axis is fixed across the whole slider range so that copy heights, which really
    # do grow as 1/T_s = f_s, can be compared from one sampling rate to the next.
    top = 1.3 * 70.0
    ax_copies.annotate('$\\pm f_{max}$', xy=(F_MAX, 1.20 * scale), fontsize=9, ha='left',
                       bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85))
    ax_copies.annotate('$\\pm f_s/2$', xy=(f_s / 2, 1.09 * scale), fontsize=9, ha='left',
                       color='tab:purple',
                       bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85))
    ax_copies.axhline(scale, color='grey', linestyle='--', linewidth=1)
    ax_copies.text(-98, scale * 1.03, f'$1/T_s={scale:.0f}$', color='grey', fontsize=9)
    ax_copies.set_xlim(-100, 100)
    ax_copies.set_ylim(0, top)
    ax_copies.set_xlabel('Frequency (Hz)')
    ax_copies.set_ylabel('normalized magnitude, scaled by $1/T_s$')
    ax_copies.legend(loc='upper left', fontsize=9)
    ax_copies.grid(alpha=0.3)

    if critical:
        verdict = ('CRITICAL: the copies touch at $\\pm f_{max}$ rather than overlapping. '
                   'Harmless for a smooth spectrum, fatal for a line at $f_{max}$: see Section 8.7')
        color = 'tab:orange'
    elif clear:
        verdict = 'CLEAR: the copies stay apart, so the original can be recovered'
        color = 'tab:green'
    else:
        verdict = 'OVERLAP: the copies collide, so the original cannot be recovered'
        color = 'tab:red'
    comparison = '>' if clear else ('=' if critical else '<')
    ax_copies.set_title(
        f'$f_s={f_s:.0f}$ Hz      $f_s-f_{{max}}={f_s - F_MAX:.0f}$ Hz '
        f'{comparison} $f_{{max}}={F_MAX:.0f}$ Hz      '
        f'$X(f)$ = "{shape}"      Nyquist rate $2f_{{max}}={NYQUIST_RATE:.0f}$ Hz'
        f'\n{verdict}',
        color=color, fontsize=10.5)

    # The reconstruction filter H(f) = T_s rect(f/f_s) contributes a gain of T_s, which
    # cancels the 1/T_s that sampling introduced. The passband comparison is therefore in
    # the units of the original X(f).
    wanted = _band_shape(f, shape)
    got = T_s * total
    peak_error = float(np.max(np.abs(got - wanted)[passband]))

    # The filter output is drawn first and thicker, so that when the two curves agree
    # exactly the dashed 'wanted' curve still reads on top of it.
    ax_band.plot(f[passband], got[passband], color='k', linewidth=3.2,
                 label='what the ideal lowpass filter returns, after its $T_s$ gain')
    ax_band.plot(f[passband], wanted[passband], color='tab:blue', linestyle='--',
                 linewidth=1.8, label='$X(f)$, what we want back')
    ax_band.fill_between(f[passband], wanted[passband], got[passband],
                         color='red', alpha=0.35, label='error introduced by sampling')
    ax_band.set_xlim(-f_s / 2 * 1.35, f_s / 2 * 1.35)
    ax_band.set_ylim(0, 1.35)
    ax_band.set_xlabel('Frequency (Hz)')
    ax_band.set_ylabel('normalized magnitude')
    ax_band.set_title(f'Zoomed into the passband $|f|<f_s/2={f_s / 2:.1f}$ Hz.     '
                      f'largest error $={peak_error:.3f}$',
                      color=('tab:green' if peak_error < 1e-6 else 'tab:red'), fontsize=11)
    ax_band.legend(loc='upper right', fontsize=9)
    ax_band.grid(alpha=0.3)

    fig.tight_layout()
    return fig


def show_overlap_condition():
    _show_interactive(
        _make_overlap_figure,
        f_s=IntSlider(value=34, min=20, max=70, step=1,
                      description='f_s (Hz):', continuous_update=False),
        shape=Dropdown(options=SPECTRUM_SHAPES, value='trapezoid', description='X(f):'))


# --------------------------------------------------------------------------------------
# 8.6  Step 5: recovery by sinc interpolation
# --------------------------------------------------------------------------------------

def _make_reconstruction_figure(f_s):
    f_s = float(f_s)
    T_s = 1.0 / f_s
    view = (0.0, 0.3)
    t_view = np.linspace(view[0], view[1], 1500)
    t_samples = np.arange(view[0] - 2.0, view[1] + 2.0, T_s)
    x_samples = test_signal(t_samples)
    reconstructed = sinc_reconstruct(t_view, t_samples, x_samples, T_s)
    error = _relative_rms_error(f_s, t_view)

    fig, ax = plt.subplots(figsize=(11, 5))

    visible = t_samples[(t_samples >= view[0] - T_s) & (t_samples <= view[1] + T_s)]
    if visible.size <= 40:
        for centre in visible:
            ax.plot(t_view, test_signal(centre) * np.sinc((t_view - centre) / T_s),
                    color='tab:orange', linewidth=0.8, alpha=0.45)
        ax.plot([], [], color='tab:orange', linewidth=0.8, alpha=0.7,
                label='individual shifted sinc functions')
    else:
        ax.plot([], [], ' ', label=f'{visible.size} sinc functions, not drawn individually')

    # The reconstruction is drawn first and thicker, so that where it matches the original
    # the dashed original still reads on top of it instead of vanishing underneath.
    ax.plot(t_view, reconstructed, color='tab:blue', linewidth=3.2,
            label='reconstruction $\\sum_n x[n]\\,$sinc')
    ax.plot(t_view, test_signal(t_view), color='0.25', linestyle='--', linewidth=1.6,
            label='original $x(t)$')
    ax.stem(visible, test_signal(visible), linefmt='tab:red', markerfmt='o', basefmt=' ',
            label='samples $x[n]$')

    ax.set_xlim(view)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude')
    if f_s > NYQUIST_RATE:
        status = 'above'
        title_color = 'tab:green'
    elif f_s < NYQUIST_RATE:
        status = 'below'
        title_color = 'tab:red'
    else:
        status = 'at'
        title_color = 'tab:orange'
    ax.set_title(f'$f_s={f_s:.0f}$ Hz, {status} the Nyquist rate of '
                 f'{NYQUIST_RATE:.0f} Hz.     relative RMS error $={error:.4f}$',
                 color=title_color)
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def show_sinc_reconstruction():
    _show_interactive(_make_reconstruction_figure,
                      f_s=IntSlider(value=30, min=25, max=120, step=1,
                                    description='f_s (Hz):', continuous_update=False))


# --------------------------------------------------------------------------------------
# 8.7  Why the inequality is strict
# --------------------------------------------------------------------------------------

def _make_critical_phase_figure(phase_degrees):
    phase = np.deg2rad(float(phase_degrees))
    f_s = NYQUIST_RATE
    T_s = 1.0 / f_s
    view = (0.0, 0.25)
    t_view = np.linspace(view[0], view[1], 2000)
    t_samples = np.arange(view[0] - 2.0, view[1] + 2.0, T_s)
    x_samples = np.sin(2 * np.pi * F_HIGH * t_samples + phase)
    reconstructed = sinc_reconstruct(t_view, t_samples, x_samples, T_s)

    recovered = float(np.max(np.abs(reconstructed)))
    predicted = float(abs(np.sin(phase)))
    visible = t_samples[(t_samples >= view[0]) & (t_samples <= view[1])]

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(t_view, reconstructed, color='tab:blue', linewidth=3.2, label='reconstruction')
    ax.plot(t_view, np.sin(2 * np.pi * F_HIGH * t_view + phase),
            color='0.25', linestyle='--', linewidth=1.6, label='original, amplitude 1')
    ax.stem(visible, np.sin(2 * np.pi * F_HIGH * visible + phase),
            linefmt='tab:red', markerfmt='o', basefmt=' ', label='samples')
    ax.axhline(0, color='k', linewidth=0.8)
    ax.set_ylim(-1.3, 1.3)
    ax.set_xlim(view)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude')
    ax.set_title(f'A {F_HIGH:.0f} Hz sine sampled at exactly '
                 f'$f_s=2f_{{max}}={f_s:.0f}$ Hz, phase $={phase_degrees}^\\circ$\n'
                 f'recovered amplitude $={recovered:.3f}$, '
                 f'predicted $|\\sin\\phi|={predicted:.3f}$',
                 color=('tab:red' if recovered < 0.5 else 'tab:orange'))
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def show_critical_phase():
    _show_interactive(_make_critical_phase_figure,
                      phase_degrees=IntSlider(value=0, min=0, max=180, step=5,
                                              description='phase (deg):',
                                              continuous_update=False))
