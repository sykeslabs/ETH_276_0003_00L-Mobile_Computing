"""Audio plumbing for the acoustic communication notebooks (02.10 - 02.12).

Only two things live here:

* getting sound out of the speaker and back in through the microphone, and
* a substitute channel for laptops without a usable microphone,

so that every notebook runs the same way whether or not audio hardware is
available.  Nothing in this file decides a bit, finds a frame, or measures a
channel.  Those steps are written in the notebooks themselves, because they
are the point of the exercise.
"""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 48_000

try:  # The live path is optional.  Everything works without it.
    import sounddevice as _sd

    AUDIO_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the machine
    _sd = None
    AUDIO_AVAILABLE = False


# ----------------------------------------------------------------------------
# Test signals
# ----------------------------------------------------------------------------

def make_tone(frequency_hz, duration_s, amplitude=0.25, sample_rate=SAMPLE_RATE):
    """A single tone, faded in and out so the speaker does not click."""
    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    fade = np.minimum(
        1.0, np.minimum(np.arange(len(t)), len(t) - np.arange(len(t))) / (0.005 * sample_rate)
    )
    return amplitude * fade * np.sin(2 * np.pi * frequency_hz * t)


def make_sweep(start_hz, end_hz, duration_s, amplitude=0.25, sample_rate=SAMPLE_RATE):
    """A tone that slides smoothly from `start_hz` up to `end_hz`.

    The slide is exponential, so it spends the same amount of time on every
    octave.  That matches how hearing works and keeps the low notes, where a
    laptop speaker struggles most, from flashing past.
    """
    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    ratio = end_hz / start_hz
    phase = 2 * np.pi * start_hz * duration_s / np.log(ratio) * (ratio ** (t / duration_s) - 1)
    fade = np.minimum(
        1.0, np.minimum(np.arange(len(t)), len(t) - np.arange(len(t))) / (0.05 * sample_rate)
    )
    return amplitude * fade * np.sin(phase)


def sweep_frequency_at(seconds, start_hz, end_hz, duration_s):
    """Which frequency the sweep is playing at a given moment."""
    return start_hz * (end_hz / start_hz) ** (np.asarray(seconds) / duration_s)


# ----------------------------------------------------------------------------
# Substitute channel
# ----------------------------------------------------------------------------

def _speaker_and_microphone_response(frequencies_hz: np.ndarray) -> np.ndarray:
    """Magnitude response of a typical laptop speaker and microphone pair.

    Small speakers cannot move enough air to reproduce low frequencies, and the
    microphone rolls off at the top.  The bumps in between are enclosure and
    desk resonances.  The shape is representative, not a measurement of any
    particular machine.
    """
    f = np.maximum(frequencies_hz, 1.0)
    high_pass = f**2 / (f**2 + 420.0**2)          # speaker cannot push bass
    low_pass = 1.0 / (1.0 + (f / 9_000.0) ** 3)   # microphone rolls off
    resonance = (
        1.0
        + 0.45 * np.exp(-((f - 2_600.0) ** 2) / (2 * 700.0**2))
        - 0.55 * np.exp(-((f - 5_400.0) ** 2) / (2 * 600.0**2))
        + 0.20 * np.exp(-((f - 1_250.0) ** 2) / (2 * 400.0**2))
    )
    return high_pass * low_pass * np.clip(resonance, 0.05, None)


def _apply_response(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    spectrum = np.fft.rfft(samples)
    frequencies = np.fft.rfftfreq(len(samples), 1.0 / sample_rate)
    return np.fft.irfft(spectrum * _speaker_and_microphone_response(frequencies), n=len(samples))


def _room_noise(count: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    """Fan and street noise with a low-frequency tilt, plus mains hum."""
    white = rng.standard_normal(count)
    spectrum = np.fft.rfft(white)
    frequencies = np.fft.rfftfreq(count, 1.0 / sample_rate)
    tilt = 1.0 / np.sqrt(1.0 + (np.maximum(frequencies, 1.0) / 200.0))
    coloured = np.fft.irfft(spectrum * tilt, n=count)
    coloured *= 5.0e-4 / (np.std(coloured) + 1e-12)

    t = np.arange(count) / sample_rate
    hum = sum(3.0e-4 / k * np.sin(2 * np.pi * 50.0 * k * t + k) for k in (1, 2, 3))
    return coloured + hum


def simulate_laptop_channel(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    seed: int = 2026,
    muffled: bool = False,
) -> np.ndarray:
    """Play `samples` through a stand-in laptop speaker, room, and microphone.

    With `muffled=True` the stand-in speaker is covered, which is what a hand
    over a real speaker does: everything gets quieter and the high notes suffer
    most.
    """
    rng = np.random.default_rng(seed)
    shaped = _apply_response(np.asarray(samples, dtype=float), sample_rate)
    if muffled:
        spectrum = np.fft.rfft(shaped)
        frequencies = np.fft.rfftfreq(len(shaped), 1.0 / sample_rate)
        spectrum *= 0.50 / (1.0 + (frequencies / 1_500.0) ** 2)
        shaped = np.fft.irfft(spectrum, n=len(shaped))

    echo_delay = int(0.008 * sample_rate)          # one desk reflection
    delayed = np.zeros_like(shaped)
    delayed[echo_delay:] = shaped[:-echo_delay]
    shaped = shaped + 0.15 * delayed

    shaped *= 0.06                                  # distance and speaker level
    return shaped + _room_noise(len(shaped), sample_rate, rng)


# ----------------------------------------------------------------------------
# The one function the notebooks call
# ----------------------------------------------------------------------------

def play_and_record(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    lead_in_s: float = 0.3,
    tail_s: float = 0.4,
    seed: int = 2026,
    muffled: bool = False,
    force_offline: bool = False,
) -> tuple[np.ndarray, str]:
    """Play a waveform and record at the same time.

    Returns the recording and the mode that produced it, either ``"live"`` or
    ``"offline"``.  The recording always starts before playback, so the first
    fraction of a second is room sound.  Finding where the signal actually
    begins is left to the notebook.

    `muffled` only affects the substitute channel, where it stands in for a hand
    placed over the speaker.  On a real laptop you use your actual hand.
    """
    samples = np.asarray(samples, dtype=float).ravel()
    lead_in = np.zeros(int(lead_in_s * sample_rate))
    tail = np.zeros(int(tail_s * sample_rate))
    playback = np.concatenate([lead_in, samples, tail])

    if AUDIO_AVAILABLE and not force_offline:
        try:
            recording = _sd.playrec(
                playback.reshape(-1, 1), samplerate=sample_rate, channels=1, blocking=True
            )
            return np.asarray(recording, dtype=float).ravel(), "live"
        except Exception as error:  # pragma: no cover - depends on the machine
            print(f"Live audio did not start ({error}). Using the substitute channel.")

    return simulate_laptop_channel(playback, sample_rate, seed=seed, muffled=muffled), "offline"


def describe_mode(mode: str) -> None:
    """Print one honest line about where the numbers below came from."""
    if mode == "live":
        print("Mode: LIVE. The plots below are your own speaker, room, and microphone.")
    else:
        print(
            "Mode: OFFLINE. Live audio was disabled or unavailable, so a substitute "
            "signal produced this recording.\n"
            "      The exercise is unchanged, but label your answers as offline."
        )


def _speech_like_demo(duration_s: float, sample_rate: int, seed: int) -> np.ndarray:
    """Return a deterministic speech-like signal for the non-hardware path.

    This is not intelligible speech and is never presented as a person.  It
    merely has changing pitch, syllable-sized envelopes, harmonics, and room
    noise so that the notebook can contrast a voice-like spectrum with two
    pure modem tones when a microphone is unavailable.
    """

    count = int(round(duration_s * sample_rate))
    t = np.arange(count) / sample_rate
    pitch = 145.0 + 30.0 * np.sin(2 * np.pi * 0.8 * t)
    phase = 2 * np.pi * np.cumsum(pitch) / sample_rate
    voiced = sum(np.sin(harmonic * phase) / harmonic for harmonic in range(1, 10))
    syllables = (
        np.exp(-((t - 0.55) / 0.20) ** 2)
        + 0.9 * np.exp(-((t - 1.30) / 0.24) ** 2)
        + 0.8 * np.exp(-((t - 2.15) / 0.22) ** 2)
    )
    rng = np.random.default_rng(seed)
    breath = 0.05 * rng.standard_normal(count) * syllables
    return 0.12 * voiced * syllables + breath + _room_noise(count, sample_rate, rng)


def capture_microphone(
    duration_s: float,
    sample_rate: int = SAMPLE_RATE,
    *,
    kind: str = "room",
    seed: int = 2026,
    force_offline: bool = False,
) -> tuple[np.ndarray, str]:
    """Record the microphone, or return a clearly labeled substitute signal.

    ``kind`` is used only by the substitute path.  ``"room"`` returns quiet
    background noise and ``"voice"`` returns a non-intelligible speech-like
    demonstration.  Students choose the live path explicitly in the notebook,
    so validation never activates a microphone unexpectedly.
    """

    if duration_s <= 0:
        raise ValueError("duration_s must be positive.")
    if kind not in {"room", "voice"}:
        raise ValueError("kind must be 'room' or 'voice'.")

    count = int(round(duration_s * sample_rate))
    if AUDIO_AVAILABLE and not force_offline:
        try:
            print(f"Recording for {duration_s:.1f} s ...", flush=True)
            recording = _sd.rec(
                count,
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocking=True,
            )
            print("Recording complete.", flush=True)
            return np.asarray(recording, dtype=float).ravel(), "live"
        except Exception as error:  # pragma: no cover - depends on the machine
            print(f"Live recording did not start ({error}). Using a substitute signal.")

    rng = np.random.default_rng(seed)
    if kind == "voice":
        return _speech_like_demo(duration_s, sample_rate, seed), "offline"
    return _room_noise(count, sample_rate, rng), "offline"


# Public names for the two pieces the acoustic module reuses.
room_noise = _room_noise
apply_response = _apply_response
