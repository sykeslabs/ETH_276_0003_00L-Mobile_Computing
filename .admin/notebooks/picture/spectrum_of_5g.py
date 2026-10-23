import matplotlib.pyplot as plt


# Define spectrum ranges (in GHz) and example bands
bands = {
    "Low-band (<1 GHz)": (0.41, 1.0),
    "Mid-band (1–6 GHz)": (1.0, 6.0),
    "Upper mid-band (6–7.125 GHz)": (6.0, 7.125),
    "High-band / mmWave (24–71 GHz)": (24.25, 71.0),
}

# Example frequencies (GHz) with labels
examples = {
    0.6: "600 MHz",
    0.7: "700 MHz",
    2.5: "2.5 GHz",
    3.5: "3.5 GHz",
    4.8: "4.8 GHz",
    26: "26 GHz",
    28: "28 GHz",
    39: "39 GHz",
    47: "47 GHz",
}

# Increase DPI (dots per inch) for higher resolution output

fig, ax = plt.subplots(figsize=(14, 4), dpi=200)  # larger figure, higher DPI

# Shade FR1 (0.41–7.125 GHz) and FR2 (24.25–71 GHz)
ax.axvspan(0.41, 7.125, color="lightblue", alpha=0.2)
ax.axvspan(24.25, 71.0, color="lightgreen", alpha=0.2)

# Plot spectrum bands with original legend
for i, (label, (start, end)) in enumerate(bands.items()):
    ax.plot([start, end], [i, i], linewidth=14, solid_capstyle="butt", label=label)

# Plot example frequencies
for freq, name in examples.items():
    if freq < 1.0:
        y = 0
    elif 1.0 <= freq < 6.0:
        y = 1
    elif 6.0 <= freq < 7.125:
        y = 2
    else:
        y = 3
    ax.plot(freq, y, 'ko', markersize=4)
    ax.text(freq, y + 0.25, name, ha='center', va='bottom', fontsize=9, rotation=45)

# Formatting
ax.set_xscale("log")
ax.set_xlim(0.4, 80)
ax.set_ylim(-1, len(bands))
ax.set_xlabel("Frequency")
ax.set_yticks([])
ax.set_title("5G Spectrum Ranges with Example Bands and FR1/FR2 Shading")

# Custom GHz tick formatter
def ghz_formatter(x, pos):
    return f"{x:.0f} GHz" if x >= 1 else f"{x:.2f} GHz"

ax.xaxis.set_major_formatter(FuncFormatter(ghz_formatter))

# Log-spaced ticks
ticks = [0.5, 0.6, 0.7, 1, 2, 3, 4, 5, 6, 7, 10, 20, 30, 40, 50, 60, 70]
ax.set_xticks(ticks)

# Rotate x-axis labels
plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

ax.legend(loc="upper left")
plt.show()


