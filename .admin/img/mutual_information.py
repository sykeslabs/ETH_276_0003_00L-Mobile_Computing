from pathlib import Path
import math
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
from matplotlib_inline.backend_inline import set_matplotlib_formats

set_matplotlib_formats("svg")
plt.rcParams["savefig.transparent"] = True

def empirical_entropy(values):
    counts = Counter(values)
    total = len(values)
    return -sum((count / total) * math.log2(count / total)
                for count in counts.values())

def conditional_entropy(values):
    pairs = list(zip(values[:-1], values[1:]))
    previous_counts = Counter(previous for previous, current in pairs)
    pair_counts = Counter(pairs)
    total = len(pairs)
    result = 0.0
    for (previous, current), pair_count in pair_counts.items():
        p_pair = pair_count / total
        p_current_given_previous = pair_count / previous_counts[previous]
        result -= p_pair * math.log2(p_current_given_previous)
    return result

rng = np.random.default_rng(7)
# Stationary probabilities: P(000)=0.75, P(111)=0.25.
# Switch from 000 to 111 with probability 0.1, and back with 0.3.
markov_rng = np.random.default_rng(42)
state = "000" if markov_rng.random() < 0.75 else "111"
biased_source = []
for _ in range(10000):
    biased_source.append(state)
    switch_probability = 0.1 if state == "000" else 0.3
    if markov_rng.random() < switch_probability:
        state = "111" if state == "000" else "000"

sources = {
    "Independent source": ["111" if value else "000" for value in rng.integers(0, 2, size=10000)],
    "Alternating source": (["000", "111"] * 5000),
    "Biased, dependent source": biased_source,
}

names = []
symbol_entropies = []
conditional_entropies = []
for name, values in sources.items():
    h_symbol = empirical_entropy(values)
    h_conditional = conditional_entropy(values)
    names.append(name)
    symbol_entropies.append(h_symbol)
    conditional_entropies.append(h_conditional)
    print(f"{name}: H(X_n) = {h_symbol:.4f} bit, "
          f"H(X_n | X_(n-1)) = {h_conditional:.4f} bit")

positions = np.arange(len(names))
width = 0.34
fig, ax = plt.subplots(figsize=(12, 4.3))
fig.patch.set_facecolor("none")
fig.patch.set_alpha(0)
ax.set_facecolor("none")
ax.patch.set_alpha(0)
ax.bar(positions - width/2, symbol_entropies, width, label=r"$H(X_n)$")
ax.bar(positions + width/2, conditional_entropies, width,
       label=r"$H(X_n \mid X_{n-1})$")
ax.set_xticks(positions, names)
for position, values in zip(positions, sources.values()):
    pattern = " ".join(values[:8]) + "\n" + " ".join(values[8:16])
    ax.text(position, -0.15, pattern, transform=ax.get_xaxis_transform(),
            ha="center", va="top", fontsize=9, fontfamily="monospace", linespacing=1.6)
ax.set_ylabel("bit per source symbol")
ax.set_ylim(0, 1.1)
ax.legend(loc="upper right")
ax.grid(True, axis="y", alpha=0.3)
plt.tight_layout(rect=(0, 0.19, 1, 1))
fig.savefig(Path(__file__).with_suffix(".svg"), transparent=True,
            bbox_inches="tight", pad_inches=0.04)
plt.close(fig)
