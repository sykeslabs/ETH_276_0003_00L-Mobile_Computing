"""Modem for the acoustic communication workshop (notebooks 02.10 - 02.13).

A transmission is bracketed by two chirps and carries nothing else:

    [ silence ][ up-chirp ][ gap ][ payload, M-FSK ][ gap ][ down-chirp ][ silence ]

There is no header.  A receiver listening to a live microphone has no idea when
a message begins or ends, so the two chirps supply exactly that and nothing
more.  The up-chirp sweeps low to high, the down-chirp sweeps high to low, so a
receiver that starts listening in the middle of a transmission can still tell
which end it found.  Everything else about the signal - the tone frequencies,
the symbol duration, the message length - is measurable from the recording
itself, which is the point of the workshop.

The payload is M-FSK: one tone at a time out of `TONE_COUNT`, carrying
log2(TONE_COUNT) bits per symbol.  Tone k sits at BASE + k * SPACING.  The
mapping is Gray coded, so the tones most likely to be confused differ in only
one bit.

Tone spacing is a whole number of FFT bins at 1024 points and 48 kHz
(48000 / 1024 = 46.875 Hz), so every tone lands dead centre in a bin and
neighbouring tones do not leak into each other.  ggwave does the same thing.

Text is ASCII, one byte per character, most significant bit first.

Only NumPy is needed.  Matplotlib is imported by the plotting helpers and
sounddevice only when the speaker or microphone is actually used.

Every `plot_*` helper *returns* its figure rather than showing it, so the same
call works both ways in a notebook:

    figure = ac.plot_spectrum(x, rate)          # drawn when the cell ends

    handle = display(figure, display_id=True)   # or redrawn under a slider
    plt.close(figure)
    ...
    handle.update(ac.plot_spectrum(y, rate))

Assign the result.  A bare `ac.plot_spectrum(x, rate)` as the last line of a
cell is drawn twice: once as the value of the cell and once by matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import wave

import numpy as np

SAMPLE_RATE = 48_000

# One bin of a 1024-point FFT at 48 kHz.  Tone spacing is a multiple of this.
BIN_HZ = SAMPLE_RATE / 1024          # 46.875 Hz

TONE_COUNT = 8                       # 8-FSK: three bits per symbol

LEAD_SILENCE_S = 0.30
CHIRP_START_HZ = 300.0
CHIRP_END_HZ = 3000.0
CHIRP_DURATION_S = 0.50              # the up-chirp that opens a transmission
END_CHIRP_DURATION_S = 0.25          # the down-chirp that closes it
GAP_S = 0.10
TAIL_SILENCE_S = 0.30

PAYLOAD_BASE_HZ = 20 * BIN_HZ        #  937.50 Hz
PAYLOAD_SPACING_HZ = 4 * BIN_HZ      #  187.50 Hz -> top tone at 2250.00 Hz
PAYLOAD_SYMBOL_MS = 40.0

AMPLITUDE = 0.45
SYMBOL_GUARD = 0.22   # fraction of a symbol ignored at each edge


# ---------------------------------------------------------------------------
# Gray mapping
# ---------------------------------------------------------------------------

def gray_table(tone_count: int) -> np.ndarray:
    """Bit value carried by each tone, lowest frequency first."""
    tones = np.arange(tone_count)
    return tones ^ (tones >> 1)


def _value_to_tone(tone_count: int) -> np.ndarray:
    """Inverse of `gray_table`: which tone carries each bit value."""
    lookup = np.empty(tone_count, dtype=int)
    lookup[gray_table(tone_count)] = np.arange(tone_count)
    return lookup


# ---------------------------------------------------------------------------
# Bits and bytes
# ---------------------------------------------------------------------------

def bytes_to_bits(data: bytes) -> np.ndarray:
    """Most significant bit first."""
    if not data:
        return np.empty(0, dtype=np.uint8)
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def bits_to_bytes(bits: np.ndarray) -> bytes:
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    if len(bits) % 8:
        raise ValueError("Bit count must be a multiple of 8.")
    if len(bits) == 0:
        return b""
    return np.packbits(bits).tobytes()


def text_to_bits(text: str) -> np.ndarray:
    return bytes_to_bits(text.encode("ascii"))


# ---------------------------------------------------------------------------
# Waveform pieces
# ---------------------------------------------------------------------------

def _fade(count: int, sample_rate: int, seconds: float = 0.004) -> np.ndarray:
    """Ramp the ends of a block so the speaker does not click."""
    edge = max(1, int(seconds * sample_rate))
    index = np.arange(count)
    return np.minimum(1.0, np.minimum(index + 1, count - index) / edge)


def make_chirp(
    sample_rate: int = SAMPLE_RATE,
    *,
    down: bool = False,
    duration_s: float | None = None,
) -> np.ndarray:
    """A known sweep that marks one end of a transmission.

    The sweep is linear in frequency, so it draws a straight diagonal line in a
    spectrogram: rising for the up-chirp that opens a transmission, falling for
    the down-chirp that closes it.  That makes both ends of a packet something
    you can see before you compute anything, and it means a receiver that
    starts listening halfway through can still tell which end it found.
    """
    if duration_s is None:
        duration_s = END_CHIRP_DURATION_S if down else CHIRP_DURATION_S
    count = int(round(duration_s * sample_rate))
    t = np.arange(count) / sample_rate
    f_from, f_to = (CHIRP_END_HZ, CHIRP_START_HZ) if down else (CHIRP_START_HZ, CHIRP_END_HZ)
    rate = (f_to - f_from) / duration_s
    phase = 2 * np.pi * (f_from * t + 0.5 * rate * t**2)
    return AMPLITUDE * _fade(count, sample_rate, 0.02) * np.sin(phase)


def modulate(
    bits: np.ndarray,
    tones_hz: np.ndarray,
    symbol_ms: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Turn bits into tones.  Two tones carry one bit each, four carry two."""
    tones_hz = np.asarray(tones_hz, dtype=float)
    tone_count = len(tones_hz)
    bits_per_symbol = int(round(np.log2(tone_count)))
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    if len(bits) % bits_per_symbol:
        raise ValueError(
            f"{tone_count}-FSK needs a multiple of {bits_per_symbol} bits."
        )

    values = bits.reshape(-1, bits_per_symbol)
    weights = 2 ** np.arange(bits_per_symbol - 1, -1, -1)
    symbol_values = values @ weights
    tone_index = _value_to_tone(tone_count)[symbol_values]

    per_symbol = _samples_per_symbol(symbol_ms, sample_rate)
    t = np.arange(per_symbol) / sample_rate
    bank = np.sin(2 * np.pi * np.outer(tones_hz, t)) * _fade(per_symbol, sample_rate)
    return AMPLITUDE * bank[tone_index].ravel()


def _samples_per_symbol(symbol_ms: float, sample_rate: int) -> int:
    return int(round(sample_rate * symbol_ms / 1000.0))


def payload_tones(
    base_hz: float = PAYLOAD_BASE_HZ,
    spacing_hz: float = PAYLOAD_SPACING_HZ,
    tone_count: int = TONE_COUNT,
) -> np.ndarray:
    """The M tones of the payload alphabet, lowest first."""
    return base_hz + spacing_hz * np.arange(tone_count)


# ---------------------------------------------------------------------------
# Transmitter
# ---------------------------------------------------------------------------

def bits_per_symbol(tone_count: int = TONE_COUNT) -> int:
    return int(round(np.log2(tone_count)))


@dataclass(slots=True)
class Transmission:
    """Everything about one outgoing packet."""

    text: str
    samples: np.ndarray
    sample_rate: int
    base_hz: float
    spacing_hz: float
    symbol_ms: float
    tone_count: int

    @property
    def duration_s(self) -> float:
        return len(self.samples) / self.sample_rate

    @property
    def tones_hz(self) -> np.ndarray:
        return payload_tones(self.base_hz, self.spacing_hz, self.tone_count)

    @property
    def bit_rate(self) -> float:
        return 1000.0 * bits_per_symbol(self.tone_count) / self.symbol_ms

    def describe(self) -> None:
        print(f"message    {self.text!r}")
        print(f"  {self.tone_count}-FSK, {bits_per_symbol(self.tone_count)} bits per symbol")
        print(f"  tones     {self.tones_hz[0]:.1f} .. {self.tones_hz[-1]:.1f} Hz"
              f", spacing {self.spacing_hz:.2f} Hz")
        print(f"  symbol    {self.symbol_ms:.1f} ms  ->  {self.bit_rate:.0f} bit/s")
        print(f"  duration  {self.duration_s:.2f} s")


def encode(
    text: str,
    *,
    base_hz: float = PAYLOAD_BASE_HZ,
    spacing_hz: float = PAYLOAD_SPACING_HZ,
    symbol_ms: float = PAYLOAD_SYMBOL_MS,
    tone_count: int = TONE_COUNT,
    sample_rate: int = SAMPLE_RATE,
    lead_s: float = LEAD_SILENCE_S,
    tail_s: float = TAIL_SILENCE_S,
) -> Transmission:
    """Build a complete transmission: up-chirp, payload, down-chirp."""
    bits = text_to_bits(text)

    per = bits_per_symbol(tone_count)
    if len(bits) % per:                       # 8-FSK does not divide a byte
        bits = np.concatenate([bits, np.zeros(per - len(bits) % per, np.uint8)])

    tones = payload_tones(base_hz, spacing_hz, tone_count)
    payload = modulate(bits, tones, symbol_ms, sample_rate)

    gap = np.zeros(int(round(GAP_S * sample_rate)))
    samples = np.concatenate([
        np.zeros(int(round(lead_s * sample_rate))),
        make_chirp(sample_rate),
        gap,
        payload,
        gap,
        make_chirp(sample_rate, down=True),
        np.zeros(int(round(tail_s * sample_rate))),
    ])
    return Transmission(
        text=text,
        samples=samples,
        sample_rate=sample_rate,
        base_hz=base_hz,
        spacing_hz=spacing_hz,
        symbol_ms=symbol_ms,
        tone_count=tone_count,
    )


# ---------------------------------------------------------------------------
# Receiver: finding the packet
# ---------------------------------------------------------------------------

def matched_filter(samples: np.ndarray, template: np.ndarray) -> np.ndarray:
    """How well `template` matches the recording at each possible offset.

    The result is normalised by the energy under the window, so a loud stretch
    of noise does not outscore a quiet copy of the template.  1.0 is a perfect
    match.  Index i is the offset at which the template would start.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    template = np.asarray(template, dtype=float).ravel()
    n_out = len(samples) - len(template) + 1
    if n_out < 1:
        raise ValueError("The recording is shorter than the template.")

    size = 1 << int(np.ceil(np.log2(len(samples) + len(template))))
    corr = np.fft.irfft(
        np.fft.rfft(samples, size) * np.fft.rfft(template[::-1], size), size
    )[len(template) - 1 : len(samples)]

    cumulative = np.concatenate([[0.0], np.cumsum(samples ** 2)])
    energy = cumulative[len(template):] - cumulative[:n_out]

    # A window holding almost no energy cannot be a match, but dividing by its
    # energy would say otherwise: in the silence at either end of a recording
    # the ratio is numerical noise over nothing, which scores arbitrarily high.
    # So refuse to normalise below a small fraction of a typical window.
    typical = len(template) * float(np.mean(samples ** 2))
    scale = np.sqrt(np.maximum(energy, 1e-3 * typical) * np.sum(template ** 2))
    return np.abs(corr) / scale


@dataclass(slots=True)
class Burst:
    """Where a packet sits in a recording, according to its two chirps."""

    start_sample: int          # first payload sample
    end_sample: int            # one past the last payload sample
    up_sample: int             # where the up-chirp begins
    down_sample: int           # where the down-chirp begins
    up_score: float
    down_score: float
    sample_rate: int
    up_correlation: np.ndarray = field(default_factory=lambda: np.empty(0))
    down_correlation: np.ndarray = field(default_factory=lambda: np.empty(0))

    @property
    def sample_count(self) -> int:
        return self.end_sample - self.start_sample

    @property
    def duration_s(self) -> float:
        return self.sample_count / self.sample_rate

    def symbol_count(self, symbol_ms: float) -> int:
        return self.sample_count // _samples_per_symbol(symbol_ms, self.sample_rate)

    def describe(self) -> None:
        print(f"up-chirp    at {self.up_sample / self.sample_rate:7.3f} s"
              f"   match {self.up_score:.2f}")
        print(f"down-chirp  at {self.down_sample / self.sample_rate:7.3f} s"
              f"   match {self.down_score:.2f}")
        print(f"payload     {self.start_sample / self.sample_rate:7.3f} s"
              f" .. {self.end_sample / self.sample_rate:.3f} s"
              f"   ({self.duration_s:.3f} s, {self.sample_count} samples)")


def find_burst(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    keep_correlation: bool = True,
) -> Burst:
    """Locate a packet by correlating for the up-chirp and the down-chirp.

    Nothing here needs to know anything about the payload.  The two sweeps are
    known signals, so they can be found even when they are far below the noise,
    and the payload is whatever lies between them.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    up, down = make_chirp(sample_rate), make_chirp(sample_rate, down=True)

    up_corr = matched_filter(samples, up)
    up_sample = int(np.argmax(up_corr))

    # Look for the closing sweep only after the opening one, so a reflection of
    # the up-chirp cannot be mistaken for the end of the packet.
    after = up_sample + len(up)
    down_corr = matched_filter(samples[after:], down)
    down_sample = after + int(np.argmax(down_corr))

    gap = int(round(GAP_S * sample_rate))
    return Burst(
        start_sample=up_sample + len(up) + gap,
        end_sample=down_sample - gap,
        up_sample=up_sample,
        down_sample=down_sample,
        up_score=float(up_corr[up_sample]),
        down_score=float(down_corr[down_sample - after]),
        sample_rate=sample_rate,
        up_correlation=up_corr if keep_correlation else np.empty(0),
        down_correlation=down_corr if keep_correlation else np.empty(0),
    )


# ---------------------------------------------------------------------------
# Receiver: reading the payload
# ---------------------------------------------------------------------------

def tone_energies(
    samples: np.ndarray,
    sample_rate: int,
    tones_hz: np.ndarray,
    start_sample: int,
    symbol_count: int,
    symbol_ms: float,
) -> np.ndarray:
    """Energy at each tone in each symbol interval, shape (symbols, tones).

    This is a non-coherent detector: it measures how much of each tone is
    present without needing to know the phase of the transmitter.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    tones_hz = np.asarray(tones_hz, dtype=float)
    per_symbol = _samples_per_symbol(symbol_ms, sample_rate)
    stop = start_sample + symbol_count * per_symbol
    if start_sample < 0 or stop > len(samples):
        raise ValueError(
            "The requested symbols fall outside the recording. Check the start "
            "offset, the symbol duration, and the length of the recording."
        )

    # Measure the middle of each symbol and ignore the edges.  A receiver whose
    # timing is slightly off then still lands inside the right symbol, and the
    # moments where one tone changes into the next are left out.
    guard = int(round(SYMBOL_GUARD * per_symbol))
    width = per_symbol - 2 * guard
    block = samples[start_sample:stop].reshape(symbol_count, per_symbol)
    block = block[:, guard : guard + width]
    t = np.arange(width) / sample_rate
    reference = np.exp(-2j * np.pi * np.outer(tones_hz, t))
    return np.abs(block @ reference.T) / width


def demodulate(energies: np.ndarray) -> np.ndarray:
    """Strongest tone in each symbol, translated back into bits.

    No threshold is needed.  Only one tone is transmitted at a time, so the
    decision is simply which of them carries the most energy.
    """
    tone_count = energies.shape[1]
    per = bits_per_symbol(tone_count)
    values = gray_table(tone_count)[np.argmax(energies, axis=1)]
    shifts = np.arange(per - 1, -1, -1)
    return ((values[:, None] >> shifts) & 1).astype(np.uint8).ravel()


def whole_symbol_fit(sample_count: int, symbol_ms: float, sample_rate: int) -> float:
    """How nearly the payload is a whole number of symbols long.

    The transmitter sent whole symbols and the two chirps bracket exactly those
    symbols, so the right symbol duration divides the payload evenly.  A wrong
    one leaves a fraction of a symbol over.  1.0 is an exact fit, 0.0 is half a
    symbol out.
    """
    per_symbol = _samples_per_symbol(symbol_ms, sample_rate)
    if per_symbol < 1:
        return 0.0
    count = sample_count / per_symbol
    return max(0.0, 1.0 - 2.0 * abs(count - round(count)))


def printable_fraction(data: bytes) -> float:
    """How much of `data` looks like readable text.  1.0 means all of it.

    This is the only check the receiver has.  There is no magic number and no
    checksum in the frame, so "does this decode to English" is what tells you
    the parameters were right.
    """
    if not data:
        return 0.0
    good = sum(1 for b in data if 32 <= b <= 126 or b in (9, 10, 13))
    return good / len(data)


def readable(text: str | bytes) -> str:
    """A decode made safe to put in a plot title or a table.

    Wrong parameters produce arbitrary bytes, and showing them is the point -
    that is how a student sees a guess fail.  But a control character wrecks the
    layout, and matplotlib reads a pair of dollar signs as mathematics and
    raises, so both are replaced by a dot.
    """
    if isinstance(text, bytes):
        text = text.decode("ascii", errors="replace")
    return "".join(c if 32 <= ord(c) < 127 and c != "$" else "." for c in text)


@dataclass(slots=True)
class Result:
    """What came out of the payload."""

    text: str
    data: bytes
    printable: float
    symbol_ms: float
    base_hz: float
    spacing_hz: float
    tone_count: int
    burst: Burst | None = None
    energies: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))
    tone_indices: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=int))

    @property
    def looks_right(self) -> bool:
        return self.printable > 0.95

    def describe(self) -> None:
        print(f"{self.tone_count}-FSK   base {self.base_hz:.1f} Hz"
              f"   spacing {self.spacing_hz:.2f} Hz"
              f"   symbol {self.symbol_ms:.2f} ms")
        print(f"{len(self.data)} bytes, {self.printable:6.1%} printable")
        print(f"message     {self.text!r}")


def decode(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    base_hz: float = PAYLOAD_BASE_HZ,
    spacing_hz: float = PAYLOAD_SPACING_HZ,
    symbol_ms: float = PAYLOAD_SYMBOL_MS,
    tone_count: int = TONE_COUNT,
    burst: Burst | None = None,
) -> Result:
    """Read a packet, given where it is and what its tones are.

    `burst` is reused if you already found it; otherwise the chirps are located
    first.  Everything else you have to supply, because nothing in the signal
    declares it.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    if burst is None:
        burst = find_burst(samples, sample_rate)

    tones = payload_tones(base_hz, spacing_hz, tone_count)
    count = burst.symbol_count(symbol_ms)
    if count * bits_per_symbol(tone_count) < 8:
        raise ValueError("The payload is too short to hold a single character.")

    energies = tone_energies(
        samples, sample_rate, tones, burst.start_sample, count, symbol_ms
    )
    bits = demodulate(energies)
    data = bits_to_bytes(bits[: len(bits) // 8 * 8])   # whole bytes only
    text = data.decode("ascii", errors="replace")

    return Result(
        text=text,
        data=data,
        printable=printable_fraction(data),
        symbol_ms=symbol_ms,
        base_hz=base_hz,
        spacing_hz=spacing_hz,
        tone_count=tone_count,
        burst=burst,
        energies=energies,
        tone_indices=np.argmax(energies, axis=1),
    )


@dataclass(slots=True)
class Search:
    """The result of sweeping the symbol duration.

    `printable` is the naive score: how much of the decode reads as text.  It
    has a second peak at twice the right duration, because reading every other
    symbol of ASCII still produces printable bytes.  `fit` is what settles it -
    see `whole_symbol_fit`.  `scores` is the product, and it has one peak.
    """

    candidates_ms: np.ndarray
    scores: np.ndarray
    printable: np.ndarray
    fit: np.ndarray
    best_ms: float
    best: Result

    def describe(self) -> None:
        print(f"best symbol duration {self.best_ms:.2f} ms"
              f"   (score {self.scores.max():.1%})")
        self.best.describe()


def search_symbol_ms(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    base_hz: float = PAYLOAD_BASE_HZ,
    spacing_hz: float = PAYLOAD_SPACING_HZ,
    tone_count: int = TONE_COUNT,
    burst: Burst | None = None,
    low_ms: float = 10.0,
    high_ms: float = 120.0,
    step_ms: float = 0.25,
) -> Search:
    """Try every symbol duration in a range and keep the one that reads as text.

    The two chirps say where the payload starts and stops, and an FFT says which
    tones it uses, but nothing says how long a symbol lasts.  So guess, decode,
    and score the guess by how much of the result looks like readable ASCII.
    The right answer stands well clear of every wrong one.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    if burst is None:
        burst = find_burst(samples, sample_rate)

    candidates = np.arange(low_ms, high_ms + 0.5 * step_ms, step_ms)
    printable = np.zeros(len(candidates))
    fit = np.zeros(len(candidates))
    best_result: Result | None = None
    best_score = -1.0

    for i, candidate in enumerate(candidates):
        try:
            result = decode(
                samples, sample_rate,
                base_hz=base_hz, spacing_hz=spacing_hz,
                symbol_ms=float(candidate), tone_count=tone_count, burst=burst,
            )
        except ValueError:
            continue
        printable[i] = result.printable
        fit[i] = whole_symbol_fit(burst.sample_count, float(candidate), sample_rate)
        if printable[i] * fit[i] > best_score:
            best_score, best_result = printable[i] * fit[i], result

    if best_result is None:
        raise ValueError("No candidate symbol duration produced a decodable payload.")
    return Search(candidates, printable * fit, printable, fit,
                  best_result.symbol_ms, best_result)


# ---------------------------------------------------------------------------
# Looking at signals
# ---------------------------------------------------------------------------

def spectrum(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    seconds: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Frequencies and magnitudes for a stretch of a recording.

    Pass `seconds=(start, stop)` to look at one part.  Taking the spectrum of a
    whole recording mixes the chirps in with the payload, and the tones you are
    looking for get lost in the average.  Take the spectrum of the payload
    alone - `find_burst` tells you where that is.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    if seconds is not None:
        first = max(0, int(round(seconds[0] * sample_rate)))
        last = min(len(samples), int(round(seconds[1] * sample_rate)))
        samples = samples[first:last]
    if len(samples) < 16:
        raise ValueError("That window is too short to take a spectrum of.")
    windowed = samples * np.hanning(len(samples))
    magnitude = np.abs(np.fft.rfft(windowed)) * 2.0 / len(samples)
    return np.fft.rfftfreq(len(samples), 1.0 / sample_rate), magnitude


def find_peaks(
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    *,
    count: int = 4,
    min_hz: float = 300.0,
    max_hz: float = 4000.0,
    min_separation_hz: float = 80.0,
) -> np.ndarray:
    """The strongest well-separated peaks in a spectrum, loudest first."""
    band = (frequencies >= min_hz) & (frequencies <= max_hz)
    candidates = np.argsort(magnitude[band])[::-1]
    frequencies, magnitude = frequencies[band], magnitude[band]
    chosen: list[int] = []
    for index in candidates:
        if all(
            abs(frequencies[index] - frequencies[other]) >= min_separation_hz
            for other in chosen
        ):
            chosen.append(int(index))
        if len(chosen) == count:
            break
    return frequencies[sorted(chosen)]


def plot_waveform(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    title: str = "Recording",
) -> "Figure":
    import matplotlib.pyplot as plt

    samples = np.asarray(samples, dtype=float).ravel()
    time = np.arange(len(samples)) / sample_rate
    figure, axis = plt.subplots(figsize=(11, 2.8))
    axis.plot(time, samples, linewidth=0.4)
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Amplitude")
    axis.set_title(title)
    axis.margins(x=0)
    figure.tight_layout()
    return figure


def plot_spectrum(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    seconds: tuple[float, float] | None = None,
    max_hz: float = 4000.0,
    mark_hz: np.ndarray | list[float] | None = None,
    title: str = "Spectrum",
) -> "Figure":
    import matplotlib.pyplot as plt

    frequencies, magnitude = spectrum(samples, sample_rate, seconds=seconds)
    band = frequencies <= max_hz
    figure, axis = plt.subplots(figsize=(11, 3.2))
    axis.plot(frequencies[band], magnitude[band], linewidth=0.8)
    for value in np.atleast_1d(mark_hz) if mark_hz is not None else []:
        axis.axvline(value, color="tab:red", linestyle="--", linewidth=0.9)
        axis.text(value, axis.get_ylim()[1], f" {value:.0f}", color="tab:red",
                  va="top", fontsize=8)
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel("Magnitude")
    axis.set_title(title)
    axis.margins(x=0)
    figure.tight_layout()
    return figure


def plot_spectrogram(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    window_ms: float = 20.0,
    max_hz: float = 4000.0,
    title: str = "Spectrogram",
    seconds: tuple[float, float] | None = None,
) -> "Figure":
    """Frequency against time.

    `window_ms` is the trade-off you cannot escape: a long window separates
    close frequencies but blurs the moment a tone changes, and a short window
    does the opposite.
    """
    import matplotlib.pyplot as plt

    samples = np.asarray(samples, dtype=float).ravel()
    offset = 0.0
    if seconds is not None:
        first = max(0, int(round(seconds[0] * sample_rate)))
        last = min(len(samples), int(round(seconds[1] * sample_rate)))
        samples, offset = samples[first:last], first / sample_rate

    size = max(64, int(round(window_ms / 1000.0 * sample_rate)))
    step = max(1, size // 4)
    starts = np.arange(0, max(1, len(samples) - size), step)
    if len(starts) < 2:
        raise ValueError("That recording is too short for this window length.")
    frames = np.stack([samples[s : s + size] for s in starts]) * np.hanning(size)
    magnitude = np.abs(np.fft.rfft(frames, axis=1))
    decibels = 20 * np.log10(magnitude.T + 1e-9)

    frequencies = np.fft.rfftfreq(size, 1.0 / sample_rate)
    band = frequencies <= max_hz
    figure, axis = plt.subplots(figsize=(11, 4.0))
    axis.imshow(
        decibels[band],
        origin="lower",
        aspect="auto",
        cmap="magma",
        vmin=decibels.max() - 60,
        vmax=decibels.max(),
        extent=(
            offset,
            offset + len(samples) / sample_rate,
            0.0,
            float(frequencies[band][-1]),
        ),
    )
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Frequency (Hz)")
    axis.set_title(f"{title}  (window {window_ms:.0f} ms)")
    figure.tight_layout()
    return figure


def plot_correlation(burst: "Burst", *, title: str = "Chirp correlation") -> "Figure":
    """Both matched filters on one axis: the sweep in, and the sweep out."""
    import matplotlib.pyplot as plt

    rate = burst.sample_rate
    figure, axis = plt.subplots(figsize=(11, 3.0))

    up = burst.up_correlation
    axis.plot(np.arange(len(up)) / rate, up, linewidth=0.7,
              label="up-chirp (start)", color="tab:blue")

    down = burst.down_correlation
    if len(down):
        offset = burst.down_sample - int(np.argmax(down))
        axis.plot((np.arange(len(down)) + offset) / rate, down, linewidth=0.7,
                  label="down-chirp (end)", color="tab:orange")

    for sample, colour in ((burst.up_sample, "tab:blue"),
                           (burst.down_sample, "tab:orange")):
        axis.axvline(sample / rate, color=colour, linestyle="--", linewidth=1.0)

    axis.axvspan(burst.start_sample / rate, burst.end_sample / rate,
                 color="tab:green", alpha=0.12, label="payload")
    axis.set_xlabel("Offset into the recording (s)")
    axis.set_ylabel("Match")
    axis.set_ylim(0, 1)
    axis.set_title(title)
    axis.legend(loc="upper right", fontsize=8)
    axis.margins(x=0)
    figure.tight_layout()
    return figure


def plot_search(search: "Search", *, title: str = "Which symbol duration reads as text?") -> "Figure":
    """The score curve from `search_symbol_ms`.  The right answer is a spike."""
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(11, 3.0))
    axis.plot(search.candidates_ms, 100 * search.printable, linewidth=0.8,
              color="tab:grey", alpha=0.7, label="printable ASCII")
    axis.plot(search.candidates_ms, 100 * search.scores, linewidth=1.1,
              color="tab:blue", label="printable x whole-symbol fit")
    axis.legend(loc="upper right", fontsize=8)
    axis.axvline(search.best_ms, color="tab:red", linestyle="--", linewidth=1.0)
    axis.text(search.best_ms, 100 * search.scores.max(), f"  {search.best_ms:.2f} ms",
              color="tab:red", va="top", fontsize=9)
    axis.set_xlabel("Assumed symbol duration (ms)")
    axis.set_ylabel("Score (%)")
    axis.set_ylim(0, 105)
    axis.set_title(title)
    axis.margins(x=0)
    figure.tight_layout()
    return figure


def plot_symbol_energies(
    energies: np.ndarray,
    tones_hz: np.ndarray,
    *,
    max_symbols: int = 60,
    title: str = "Energy at each tone, symbol by symbol",
) -> "Figure":
    """One line per tone.  A clean signal keeps them well apart."""
    import matplotlib.pyplot as plt

    energies = np.asarray(energies, dtype=float)
    shown = min(max_symbols, len(energies))
    figure, axis = plt.subplots(figsize=(11, 3.2))
    for column, frequency in enumerate(np.atleast_1d(tones_hz)):
        axis.plot(energies[:shown, column], marker="o", markersize=3,
                  linewidth=0.9, label=f"{frequency:.0f} Hz")
    axis.set_xlabel("Symbol number")
    axis.set_ylabel("Energy")
    axis.set_title(f"{title}  (first {shown})")
    axis.legend(loc="upper right", fontsize=8, ncol=len(np.atleast_1d(tones_hz)))
    figure.tight_layout()
    return figure


# ---------------------------------------------------------------------------
# Channel, files, and audio hardware
# ---------------------------------------------------------------------------

def simulate_channel(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    snr_db: float = 22.0,
    seed: int = 2026,
) -> np.ndarray:
    """A stand-in speaker, room, and microphone for laptops without audio."""
    from audio_channel import apply_response, room_noise

    rng = np.random.default_rng(seed)
    shaped = apply_response(np.asarray(samples, dtype=float).ravel(), sample_rate)
    noise = room_noise(len(shaped), sample_rate, rng)
    signal_power = float(np.mean(shaped**2))
    noise_power = float(np.mean(noise**2))
    if noise_power > 0 and signal_power > 0:
        wanted = signal_power / (10 ** (snr_db / 10.0))
        noise *= np.sqrt(wanted / noise_power)
    return shaped + noise


def add_noise(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    snr_db: float = 20.0,
    seed: int = 0,
) -> np.ndarray:
    """Add room-like noise at a chosen signal-to-noise ratio, in decibels.

    Same argument order as `add_reverberation` and `simulate_channel`: the
    recording, then its sample rate, then everything else by name.
    """
    from audio_channel import room_noise

    samples = np.asarray(samples, dtype=float).ravel()
    noise = room_noise(len(samples), sample_rate, np.random.default_rng(seed))
    signal_power = float(np.mean(samples**2))
    noise_power = float(np.mean(noise**2))
    if noise_power <= 0 or signal_power <= 0:
        return samples
    wanted = signal_power / (10 ** (snr_db / 10.0))
    return samples + noise * np.sqrt(wanted / noise_power)


def _convolve(samples: np.ndarray, response: np.ndarray) -> np.ndarray:
    """Convolution through the FFT.  Direct convolution is far too slow here:
    a room response is tens of thousands of taps long."""
    n = len(samples) + len(response) - 1
    size = 1 << int(np.ceil(np.log2(n)))
    return np.fft.irfft(
        np.fft.rfft(samples, size) * np.fft.rfft(response, size), size
    )[:n]


def add_reverberation(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    rt60_s: float = 0.40,
    drr_db: float = 6.0,
    seed: int = 1,
) -> np.ndarray:
    """Put the signal in a room with echoes.

    Two numbers describe a room, and they are independent:

    `rt60_s` is the reverberation time - how long the room takes to decay by
    60 dB.  A small office is around 0.3 s, a lecture hall 0.6 to 1.2 s.  It
    depends on the room, not on where you stand.

    `drr_db` is the direct-to-reverberant ratio - how much louder the sound
    that travels straight to the microphone is than everything that bounced.
    That one depends almost entirely on distance: close to the speaker it is
    strongly positive, and past the critical distance it goes negative and the
    room is louder than the source.  Roughly +10 dB across a table, 0 dB a few
    metres away, negative across a hall.

    Every symbol arrives on top of the fading echoes of the ones before it, so
    reverberation is what usually limits how fast an indoor acoustic link can
    run - the same mechanism as multipath in a radio channel.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    length = max(2, int(round(rt60_s * sample_rate)))
    rng = np.random.default_rng(seed)

    tail = rng.standard_normal(length) * np.exp(-6.9 * np.arange(length) / length)
    tail[0] = 0.0                                    # the direct sound is separate
    tail /= np.sqrt(float(tail @ tail))              # unit energy in the echoes

    response = tail.copy()
    response[0] = 10.0 ** (drr_db / 20.0)            # direct sound, set by the DRR
    response /= np.sqrt(float(response @ response))  # overall gain of 1
    return _convolve(samples, response)[: len(samples)]


def save_wav(path: str | Path, samples: np.ndarray, sample_rate: int) -> Path:
    """Write mono samples as 16-bit PCM."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    values = np.clip(np.asarray(samples, dtype=float).ravel(), -1.0, 1.0)
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(np.round(values * 32767.0).astype("<i2").tobytes())
    return destination


def load_wav(path: str | Path) -> tuple[np.ndarray, int]:
    """Load an uncompressed PCM WAV and return mono floating-point samples."""
    with wave.open(str(Path(path)), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
        if handle.getcomptype() != "NONE":
            raise ValueError("Only uncompressed PCM WAV files are supported.")

    if width == 1:
        values = (np.frombuffer(raw, dtype=np.uint8).astype(float) - 128.0) / 128.0
    elif width == 2:
        values = np.frombuffer(raw, dtype="<i2").astype(float) / 32768.0
    elif width == 4:
        values = np.frombuffer(raw, dtype="<i4").astype(float) / 2_147_483_648.0
    else:
        raise ValueError(f"Unsupported sample width: {width} bytes.")
    if channels > 1:
        values = values.reshape(-1, channels).mean(axis=1)
    return values, sample_rate


def record(
    seconds: float,
    sample_rate: int = SAMPLE_RATE,
    *,
    offline: bool = False,
    offline_signal: np.ndarray | None = None,
    seed: int = 2026,
) -> tuple[np.ndarray, str]:
    """Record the microphone.  Returns the samples and the mode used.

    Every notebook records through this one function, so the workshop can
    change how audio is captured without changing any of the exercises.  When
    a microphone is unavailable the substitute path returns either quiet room
    noise or, if `offline_signal` is given, that signal put through the
    stand-in channel, and says so.
    """
    if seconds <= 0:
        raise ValueError("seconds must be positive.")
    count = int(round(seconds * sample_rate))

    if not offline:
        try:
            import sounddevice as sd

            print(f"Recording for {seconds:.1f} s ...", flush=True)
            block = sd.rec(count, samplerate=sample_rate, channels=1,
                           dtype="float32", blocking=True)
            print("Recording complete.", flush=True)
            return np.asarray(block, dtype=float).ravel(), "live"
        except Exception as error:
            print(f"Live recording unavailable ({error}). Using the substitute channel.")

    if offline_signal is None:
        from audio_channel import room_noise

        return room_noise(count, sample_rate, np.random.default_rng(seed)), "offline"

    padded = np.concatenate(
        [
            np.zeros(int(round(0.4 * sample_rate))),
            np.asarray(offline_signal, dtype=float).ravel(),
        ]
    )
    if len(padded) < count:
        padded = np.concatenate([padded, np.zeros(count - len(padded))])
    return simulate_channel(padded[:count], sample_rate, seed=seed), "offline"


def play(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bool:
    """Play through the speaker.  Returns False if no audio device was usable."""
    try:
        import sounddevice as sd

        print("Playing ...", flush=True)
        sd.play(np.asarray(samples, dtype=np.float32).ravel(),
                samplerate=sample_rate, blocking=True)
        print("Playback complete.", flush=True)
        return True
    except Exception as error:
        print(f"Playback unavailable ({error}). Use the notebook audio player instead.")
        return False


def describe_mode(mode: str) -> None:
    """One honest line about where the numbers came from."""
    if mode == "live":
        print("Mode: LIVE - this is your own speaker, room, and microphone.")
    else:
        print(
            "Mode: OFFLINE - no microphone was used. A substitute channel produced\n"
            "      this signal. The exercise is unchanged; label your answer offline."
        )
