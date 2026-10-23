from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


sampling_rate = 1000  # Hz
sampling_interval = 1.0 / sampling_rate
sample_count = 1000
t = np.linspace(0.0, sample_count * sampling_interval, sample_count, endpoint=False)

f1 = 50  # Hz
f2 = 120  # Hz

harmonic_1 = 0.7 * np.sin(2.0 * np.pi * f1 * t)
harmonic_2 = np.sin(2.0 * np.pi * f2 * t)
signal = harmonic_1 + harmonic_2

fft_magnitude = np.abs(np.fft.fft(signal))
frequencies = np.fft.fftfreq(sample_count, sampling_interval)

fig, (ax_time, ax_freq) = plt.subplots(1, 2, figsize=(10, 4))

ax_time.plot(t, harmonic_1, label=r"$0.7\sin(2\pi\,50t)$", color="#b8c0cc", alpha=0.9)
ax_time.plot(t, harmonic_2, label=r"$\sin(2\pi\,120t)$", color="#79c7d3", alpha=0.9)
ax_time.plot(t, signal, label="sum", color="white", linewidth=1.8)
ax_time.set(xlabel="Time [s]", ylabel="Amplitude", xlim=(0, 0.2))
ax_time.set_facecolor((0.2, 0.2, 0.3))
ax_time.legend(fancybox=True, framealpha=1, loc="upper right", facecolor=(0.6, 0.61, 0.8))

ax_freq.plot(
    frequencies[: sample_count // 2],
    fft_magnitude[: sample_count // 2],
    label="Signal in Frequency Domain",
    color="white",
)
ax_freq.set(xlabel="Frequency [Hz]", ylabel="Magnitude", xlim=(0, 150))
ax_freq.set_facecolor((0.2, 0.2, 0.3))
ax_freq.legend(fancybox=True, framealpha=1, loc="upper left", facecolor=(0.6, 0.61, 0.8))

fig.tight_layout()
output_path = Path(__file__).with_suffix(".png")
fig.savefig(output_path, dpi=160, bbox_inches="tight")
plt.close(fig)
