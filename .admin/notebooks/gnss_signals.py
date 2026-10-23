"""Illustrative direct-sequence spread-spectrum signals, not a GPS receiver."""
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO
import re
from IPython.display import SVG, display


def _display_figure(fig):
    output = StringIO()
    fig.savefig(output, format='svg', bbox_inches='tight')
    plt.close(fig)
    svg = output.getvalue()
    # Preserve the viewBox while allowing the plot to fit the output column.
    svg = re.sub(r'<svg\b[^>]*>', lambda match: re.sub(
        r'\s(?:width|height)="[^"]*"', '', match.group(0)
    )[:-1] + ' width="100%" style="width:100%;max-width:100%;height:auto;display:block;">', svg, count=1)
    display(SVG(svg))


def show_transmitter(seed=0):
    # ----------------------------
    # Parameters for visualization
    # ----------------------------
    num_symbols = 6        # show about 5–6 bits
    samples_per_symbol = 1000
    samples_per_chip = 100
    fc = 100               # carrier frequency [Hz]
    fs = 10000             # sampling frequency [Hz]
    T_total = num_symbols * samples_per_symbol / fs
    t = np.arange(0, T_total, 1/fs)

    # Derived rates
    Rs = fs / samples_per_symbol   # symbol rate
    Rc = fs / samples_per_chip     # chip rate

    # (optional) reproducibility
    rng = np.random.RandomState(seed)

    # ----------------------------
    # Colors / styles
    # ----------------------------
    line_color = (1, 0, 1)           # magenta
    axes_facecolor = (0.2, 0.2, 0.3) # dark bluish background

    # ----------------------------
    # 1) Transmitter "step" message (+1 / -1)
    # ----------------------------
    msg_symbols = np.array([1 if i % 2 == 0 else -1 for i in range(num_symbols)])
    message = np.repeat(msg_symbols, samples_per_symbol)
    message = message[:len(t)]

    # ----------------------------
    # 2) PRN code (+1 / -1)
    # ----------------------------
    num_chips = int(T_total * Rc)
    prn_chips = rng.choice([1, -1], size=num_chips)
    prn = np.repeat(prn_chips, samples_per_chip)
    prn = prn[:len(t)]

    # ----------------------------
    # 3) Spread signal (message × PRN)
    # ----------------------------
    spread = message * prn

    # ----------------------------
    # 4) Carrier
    # ----------------------------
    carrier = np.cos(2*np.pi*fc*t)

    # ----------------------------
    # 5) Modulated signal: (spread) × (carrier)
    # ----------------------------
    tx = spread * carrier

    # ----------------------------
    # Plot: aligned
    # ----------------------------
    fig, axes = plt.subplots(
        5, 1, figsize=(11, 8), sharex=True,
        gridspec_kw={"hspace": 0.12}
    )

    def draw_symbol_edges(ax):
        for k in range(num_symbols + 1):
            ax.axvline(k * samples_per_symbol / fs, linestyle='--', color='gray', alpha=0.3)
        ax.grid(True, which='both', axis='y', alpha=0.3)
        ax.set_facecolor(axes_facecolor)

    # 1) Message
    axes[0].step(t, message, where='post', linewidth=1.2, color=line_color)
    axes[0].set_ylabel("Navigation Message\n(+1/−1)")
    draw_symbol_edges(axes[0])

    # 2) PRN
    axes[1].step(t, prn, where='post', linewidth=1.2, color=line_color)
    axes[1].set_ylabel("PRN\n(+1/−1)")
    draw_symbol_edges(axes[1])

    # 3) Spread (message × PRN)
    axes[2].step(t, spread, where='post', linewidth=1.2, color=line_color)
    axes[2].set_ylabel("Spread\n(message×PRN)")
    draw_symbol_edges(axes[2])

    # 4) Carrier
    axes[3].plot(t, carrier, linewidth=1.0, color=line_color)
    axes[3].set_ylabel("Carrier\ncos(2πf_ct)")
    draw_symbol_edges(axes[3])

    # 5) RF signal (spread × carrier)
    axes[4].plot(t, tx, linewidth=1.0, color=line_color)
    axes[4].set_ylabel("RF: spread×carrier")
    axes[4].set_xlabel("Time [s]")
    draw_symbol_edges(axes[4])

    #fig.suptitle("DSSS Transmitter Chain (6 slow bits, aligned view)", y=0.995)
    _display_figure(fig)

    return dict(time=t, message=message, spreading_code=prn, transmitted=tx)


def show_receiver(snr_db=0.0, code_phase_offset=12, carrier_phase=0.4, freq_offset_hz=0.0, seed=0):
    # ----------------------------
    # Parameters for visualization
    # ----------------------------
    num_symbols = 6        # show about 5–6 bits
    samples_per_symbol = 1000
    samples_per_chip = 100
    fc = 100               # carrier frequency [Hz]
    fs = 10000             # sampling frequency [Hz]
    T_total = num_symbols * samples_per_symbol / fs
    t = np.arange(0, T_total, 1/fs)

    # Derived rates
    Rs = fs / samples_per_symbol   # symbol rate
    Rc = fs / samples_per_chip     # chip rate

    # (optional) reproducibility
    rng = np.random.RandomState(seed)

    # ----------------------------
    # Colors / styles (display settings)
    # ----------------------------
    line_color = (1, 0, 1)           # common line color (magenta)
    axes_facecolor = (0.2, 0.2, 0.3) # common facecolor for all subplots

    # ----------------------------
    # 1) Transmitter "step" message (+1 / -1)
    # ----------------------------
    msg_symbols = np.array([1 if i % 2 == 0 else -1 for i in range(num_symbols)])
    message = np.repeat(msg_symbols, samples_per_symbol)
    message = message[:len(t)]

    # ----------------------------
    # 2) PRN code (+1 / -1)
    # ----------------------------
    num_chips = int(T_total * Rc)
    prn_chips = rng.choice([1, -1], size=num_chips)
    prn = np.repeat(prn_chips, samples_per_chip)
    prn = prn[:len(t)]

    # ----------------------------
    # 3) Spread signal (message × PRN)
    # ----------------------------
    spread = message * prn

    # ----------------------------
    # 4) Carrier
    # ----------------------------
    carrier = np.cos(2*np.pi*fc*t)

    # ----------------------------
    # 5) Modulated signal: (spread) × (carrier)
    # ----------------------------
    tx = spread * carrier

    # ==========================================================
    # RECEIVER SIDE: "combined received signal" + correlator
    # ==========================================================

    # --- Channel impairments / combination settings ---

    # Apply PRN code-phase offset at the transmitter path to simulate misalignment at the RX
    prn_rx = np.roll(prn, code_phase_offset)
    spread_rx = message * prn_rx

    # Apply carrier with channel phase/freq offset
    carrier_ch = np.cos(2*np.pi*(fc + freq_offset_hz)*t + carrier_phase)
    tx_offset = spread_rx * carrier_ch

    # Add AWGN
    def add_awgn(x, snr_db):
        sig_power = np.mean(x**2)
        snr_lin = 10**(snr_db/10)
        noise_power = sig_power / snr_lin
        noise = np.sqrt(noise_power) * rng.randn(*x.shape)
        return x + noise

    rx = add_awgn(tx_offset, snr_db)

    # --- Receiver: carrier wipeoff (assume known fc; unknown phase reduces amplitude) ---
    lo = np.cos(2*np.pi*fc*t)  # if freq_offset_hz != 0 or phase != 0 -> residual loss
    baseband = rx * lo         # coherent downconversion to (roughly) baseband

    # --- Code-phase search (0..samples_per_chip-1) using short window ---
    # We use a short window (e.g., 1 symbol) for the correlation metric
    win_len = samples_per_symbol  # integrate over one symbol worth of samples

    metrics = np.zeros(samples_per_chip)
    for tau in range(samples_per_chip):
        prn_hyp = np.roll(prn, tau)
        # Despread hypothesis over window
        y = baseband[:win_len] * prn_hyp[:win_len]
        metrics[tau] = np.abs(np.sum(y))  # magnitude correlation metric

    est_code_phase = int(np.argmax(metrics))

    # --- Despread with estimated code phase over full duration ---
    prn_aligned = np.roll(prn, est_code_phase)
    despread = baseband * prn_aligned

    # --- Symbol integrate-and-dump to recover message ---
    despread_reshaped = despread[:num_symbols*samples_per_symbol].reshape(num_symbols, samples_per_symbol)
    symbol_sums = np.sum(despread_reshaped, axis=1)
    msg_hat = np.sign(symbol_sums)
    # In case any zero (exactly), map to +1
    msg_hat[msg_hat == 0] = 1

    # --- BER (expect 0 with enough SNR and perfect carrier wipeoff) ---
    ber = np.mean(msg_hat != msg_symbols)

    # ----------------------------
    # Plot: received signal and correlator results
    # ----------------------------
    fig, axes = plt.subplots(
        2, 2, figsize=(10, 5.5), layout='constrained'
    )
    axes = axes.ravel()

    def beautify(ax):
        ax.grid(True, which='both', axis='y', alpha=0.3)
        ax.set_facecolor(axes_facecolor)

    # RX signal (after channel + noise)
    axes[0].plot(t, rx, linewidth=0.9, color=line_color)
    axes[0].set_ylabel("RX (RF)")
    beautify(axes[0])

    # Baseband after wipeoff
    axes[1].plot(t, baseband, linewidth=0.9, color=line_color)
    axes[1].set_ylabel("Baseband\n(wipeoff)")
    beautify(axes[1])

    # Code-phase correlation metric
    axes[2].plot(np.arange(samples_per_chip), metrics, linewidth=1.2, color=line_color)
    axes[2].set_xlabel("Code phase [samples]")
    axes[2].set_ylabel("|Corr| over 1 symbol")
    axes[2].set_title(f"Estimated code phase = {est_code_phase}  (true offset = {code_phase_offset})")
    beautify(axes[2])

    # Recovered message vs original (symbol-level)
    n = np.arange(num_symbols)
    axes[3].step(n, msg_symbols, where='mid', linewidth=3, color='white', label="Original message")
    axes[3].step(n, msg_hat, where='mid', linewidth=1.5, color=line_color, label="Recovered message")
    axes[3].set_xlabel("Symbol index")
    axes[3].set_ylabel("Bit (+1/−1)")
    axes[3].set_title(f"BER = {ber:.3f}", loc="right", fontsize=9)
    axes[3].legend(loc="lower left", bbox_to_anchor=(0, 1.02), borderaxespad=0, ncol=2, fontsize=8, fancybox=True, framealpha=1, facecolor=axes_facecolor, labelcolor="white")

    beautify(axes[3])

    _display_figure(fig)

    print(f"Spreading-code offset: {est_code_phase} samples (injected: {code_phase_offset})")
    print(f"Bit errors: {int(np.sum(msg_hat != msg_symbols))}/{num_symbols}; BER = {ber:.3f}")
    return dict(estimated_offset=est_code_phase, injected_offset=code_phase_offset, ber=float(ber), original=msg_symbols, recovered=msg_hat, metrics=metrics)


def show_code_correlation(offset_samples=137, snr_db=-15.0, seed=0):
    """Estimate a circular code delay with an ideal baseband matched filter."""
    length, sample_rate = 1023, 10000
    if not 0 <= offset_samples < length:
        raise ValueError('Offset must be an integer from 0 to 1022 samples.')
    if int(offset_samples) != offset_samples:
        raise ValueError('Offset must be an integer.')
    offset_samples = int(offset_samples)
    rng = np.random.default_rng(seed)
    code = rng.choice([-1.0, 1.0], size=length)
    delayed = np.roll(code, offset_samples)
    noise = rng.normal(0, np.sqrt(10 ** (-snr_db / 10)), length)
    received = delayed + noise

    def correlate(signal):
        return np.fft.ifft(np.fft.fft(signal) * np.conj(np.fft.fft(code))).real / length

    clean_correlation = correlate(delayed)
    noisy_correlation = correlate(received)
    estimate = int(np.argmax(np.abs(noisy_correlation)))
    fig, axes = plt.subplots(2, 2, figsize=(10, 5.5), layout='constrained')
    for ax in axes.ravel():
        ax.set_facecolor((.2, .2, .3))
        ax.grid(alpha=.2)
    snippet = np.arange(80)
    axes[0, 0].step(snippet, code[:80], color='white', label='Local code')
    axes[0, 0].step(snippet, delayed[:80], color='magenta', alpha=.8, label='Delayed code')
    axes[0, 0].set(title='First 80 samples of each code', xlabel='Sample index', ylabel='Amplitude')
    axes[0, 0].legend(facecolor=(.2,.2,.3), labelcolor='white', fontsize=8)
    axes[0, 1].plot(received, color='magenta', linewidth=.6)
    axes[0, 1].set(title=f'Received code with noise: SNR {snr_db:g} dB', xlabel='Sample index', ylabel='Amplitude')
    for ax, values, title in [(axes[1, 0], clean_correlation, 'Correlation without noise'),
                               (axes[1, 1], noisy_correlation, 'Correlation with noise')]:
        ax.plot(np.abs(values), color='magenta', linewidth=.8, zorder=3)
        ax.axvline(offset_samples, color='white', linestyle='--', zorder=1, label=f'Injected offset: {offset_samples}')
        ax.set(title=title, xlabel='Candidate offset (samples)', ylabel='|Correlation| / N')
        ax.legend(facecolor=(.2,.2,.3), labelcolor='white', fontsize=8)
    _display_figure(fig)
    print(f'Injected offset: {offset_samples} samples ({offset_samples/sample_rate*1000:.2f} ms)')
    print(f'Estimated offset: {estimate} samples ({estimate/sample_rate*1000:.2f} ms)')
    print(f'Noise power is {10**(-snr_db/10):.1f} times signal power (specified SNR).')
    return dict(injected_offset=offset_samples, estimated_offset=estimate,
                estimated_delay_s=estimate/sample_rate, clean_correlation=clean_correlation,
                noisy_correlation=noisy_correlation, snr_db=snr_db)
