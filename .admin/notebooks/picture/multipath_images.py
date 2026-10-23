# Generate four images:
# 1) tx_impulse.png         - Transmitted impulse in time domain
# 2) rx_los_only.png        - LOS-only received in time domain
# 3) rx_multipath.png       - Multipath received in time domain
# 4) rx_freq_compare.png    - Frequency response |H(f)| comparison (LOS vs Multipath) in one chart

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# ---------------- Parameters (consistent across time & freq) ----------------
# Time axis (µs)
t_us = np.linspace(-0.5, 6.0, 2000)

# Impulse width for visualization (approx FWHM 0.08 µs)
sigma = 0.08 / 2.355  # µs

# LOS settings
los_amp = 1.0
los_delay = 0.6  # µs

# Multipath profile
num_taps = 8
tap_spacing = 0.3    # µs
tau_rms = 0.9        # µs
rng = np.random.default_rng(7)  # reproducible

# Frequency axis (± MHz span)
f_span_MHz = 20.0
num_f_points = 4096
f_Hz = np.linspace(-f_span_MHz*1e6, f_span_MHz*1e6, num_f_points)

# ---------------- Time-domain signals ----------------
# Transmitted impulse (Gaussian for visibility)
x_tx = np.exp(-0.5 * (t_us/sigma)**2)
x_tx /= np.max(x_tx)

# LOS-only received: scaled & delayed impulse
y_los = los_amp * np.exp(-0.5 * ((t_us - los_delay)/sigma)**2)

# Multipath received: sum of scaled/delayed impulses
del_us = np.arange(num_taps) * tap_spacing
pdp = np.exp(-del_us / tau_rms)
pdp = pdp / np.sum(pdp)

# Complex Gaussian taps scaled by sqrt(PDP); normalize total energy
cn = (rng.normal(size=num_taps) + 1j*rng.normal(size=num_taps)) / np.sqrt(2.0)
taps = cn * np.sqrt(pdp)
taps = taps / np.sqrt(np.sum(np.abs(taps)**2))

y_mp = np.zeros_like(t_us, dtype=float)
for k, hk in enumerate(taps):
    y_mp += np.abs(hk) * np.exp(-0.5 * ((t_us - del_us[k])/sigma)**2)

# ---------------- Save time-domain figures ----------------
plt.figure(figsize=(8,2.8))
plt.plot(t_us, x_tx, color="blue")
plt.title("Transmitted Impulse (baseband)")
plt.xlabel("Time (µs)")
plt.ylabel("Amplitude")
plt.grid(True)
plt.savefig(OUT_DIR / "tx_impulse.png", dpi=120, bbox_inches="tight")
plt.close()

plt.figure(figsize=(8,2.8))
plt.plot(t_us, y_los, color="black")
plt.title("Received (LOS-only) — scaled & delayed impulse")
plt.xlabel("Time (µs)")
plt.ylabel("Amplitude")
plt.grid(True)
plt.savefig(OUT_DIR / "rx_los_only.png", dpi=120, bbox_inches="tight")
plt.close()

plt.figure(figsize=(8,2.8))
plt.plot(t_us, y_mp, color="red")
plt.title("Received (Multipath) — superposition of delayed/scaled impulses")
plt.xlabel("Time (µs)")
plt.ylabel("Amplitude (|tap|)")
plt.grid(True)
plt.savefig(OUT_DIR / "rx_multipath.png", dpi=120, bbox_inches="tight")
plt.close()

# ---------------- Frequency-domain comparison (|H(f)|) ----------------
# Build LOS-only channel: one tap at los_delay with amplitude los_amp
# H_LOS(f) ~ los_amp * exp(-j 2π f τ_LOS)
tau_LOS_s = los_delay * 1e-6
H_los = los_amp * np.exp(-1j * 2 * np.pi * f_Hz * tau_LOS_s)

# Build multipath channel frequency response
# H_MP(f) = sum_k |h_k| * exp(-j 2π f τ_k), with τ_k in seconds
tau_k_s = del_us * 1e-6
H_mp = np.zeros_like(f_Hz, dtype=complex)
for hk, tauk in zip(np.abs(taps), tau_k_s):
    H_mp += hk * np.exp(-1j * 2 * np.pi * f_Hz * tauk)

# Magnitude (dB)
H_los_db = 20*np.log10(np.abs(H_los) + 1e-12)
H_mp_db  = 20*np.log10(np.abs(H_mp)  + 1e-12)

plt.figure(figsize=(9,3.2))
plt.plot(f_Hz/1e6, H_los_db, label="LOS-only", color="black")
plt.plot(f_Hz/1e6, H_mp_db,  label="Multipath", color="red")
plt.title("Frequency Response |H(f)| — LOS vs Multipath")
plt.xlabel("Frequency (MHz)")
plt.ylabel("Magnitude (dB)")
plt.grid(True)
plt.legend()
plt.savefig(OUT_DIR / "rx_freq_compare.png", dpi=130, bbox_inches="tight")
plt.close()
