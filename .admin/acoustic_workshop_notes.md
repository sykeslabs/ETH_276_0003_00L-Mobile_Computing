# Acoustic workshop (02.10 - 02.13) - instructor notes

Not for students. The answers to the graded artifact are here.

## What the four notebooks are

One narrative spine: `.admin/acoustic_workshop/assets/secret_message.wav` is
introduced in 02.10 and each notebook advances it one step. A student cannot
reach 02.13 without having actually done 02.11 and 02.12.

| Notebook | Teaches | Payoff on the secret file |
|---|---|---|
| 02.10 | ASCII, ASK/FSK/PSK, symbol rate | listen, see the five-part envelope |
| 02.11 | room noise, SNR, non-coherent detection | FFT a window, find the eight tones |
| 02.12 | chirps, correlation, searching for the symbol rate | solve it completely |
| 02.13 | phone-to-phone link, distance and reverberation | decode it again from measurements |

02.12 is where the secret actually falls. 02.13 repeats the decode with the
student's own three numbers pasted in, so a student who skipped 02.12 has
nothing to paste.

## The frame

```
[ silence ][ up-chirp 0.5 s ][ gap 0.1 s ][ payload, 8-FSK ][ gap 0.1 s ][ down-chirp 0.25 s ][ silence ]
```

**There is no header.** This was a deliberate change from an earlier draft that
carried a 7-byte header on a slow 2-FSK carrier. The two chirps bracket the
payload, so the receiver needs no length field; everything else - tones,
spacing, symbol duration - is measured. The sender id is the first two
characters of the payload as ASCII digits (`"07HELLO"`), fixed width so a
message containing punctuation cannot break the parse.

Payload defaults, and what the phone page transmits:

```
base      937.50 Hz      (20 bins of a 1024-point FFT at 48 kHz)
spacing   187.50 Hz      (4 bins) -> top tone 2250.00 Hz
symbol    40 ms          -> 75 bit/s
tones     8              -> 3 bits per symbol, Gray coded
```

Tone spacing is a whole number of FFT bins so every tone lands dead centre in a
bin. ggwave does the same. 16-FSK was tested and rejected: a 16-FSK symbol is
an ASCII nibble, English nibbles are badly non-uniform, and a typical message
exercises only 9 to 13 of the 16 tones, so students see gaps in the FFT ladder
with no way to know what is missing. 8-FSK covers 8 of 8 on any real message.

PSK was raised and rejected: at 1 kHz a wavelength is 34 cm, phone and laptop
crystals drift tens of ppm, and every reflection arrives with its own phase.

## The secret message

Regenerate with `python tools/make_secret.py`. Deterministic, and it self-tests
by solving itself the way a student must (find_burst, spectrum, find_peaks,
search_symbol_ms) and raises SystemExit if it is not solvable.

```
message         "WELL DONE. THE AIR WAS THE ONLY NETWORK YOU NEEDED."   (51 chars)
sender id       12
base            1125.000 Hz     (24 bins)
spacing          234.375 Hz     (5 bins) -> top tone 2765.625 Hz
symbol          35 ms           -> 85.7 bit/s
up-chirp at      1.500 s
down-chirp at    7.170 s
duration         8.62 s
```

Those parameters are not the notebook defaults and **not what the phone page
transmits**, so a student cannot shortcut the exercise by pointing a phone at
the file. Measuring is the only way in.

Expected student measurements from 02.12, using the chirp-derived window:

```
tones     1114.3 .. 2771.4 Hz   (true 1125.0 .. 2765.6)
base      1114.3 Hz  ->  about 1% low
spacing   236.7 Hz   ->  spread 11.1 Hz across the seven gaps
symbol    35.00 ms   ->  exact; the search resolves to 0.25 ms
```

A 1% frequency error still decodes cleanly. That is worth pointing out: FSK
tolerates a sloppy frequency measurement and no timing error at all.

## What is given and what is discovered

**Given** (documented in 02.12, as a real protocol publishes its frame format):
the frame layout, the chirp band and durations, the Gray tone mapping, ASCII
most-significant-bit-first, and that the sender id is the first two characters.

**Discovered by measurement**: where the payload starts and ends, the eight
tone frequencies, and the symbol duration.

Deliberately *not* included: channel coding, compression, collision handling,
and any per-tone gain normalisation. A failing link is answered by moving
closer or slowing down - which is the Wi-Fi MCS lesson.

## The symbol-duration search

`ac.search_symbol_ms` scores each candidate by **printable ASCII fraction x
whole-symbol fit**. The printable score alone is not enough: it reads 100% at
both the true duration and at exactly twice it, because reading every other
symbol of English still yields printable bytes. The fit term - how nearly the
chirp-to-chirp gap divides into whole symbols - kills the alias (0.19 at the
double). Exactly one candidate scores above 0.9. 02.12 makes students look at
both curves.

## Tolerances

The receiver is forgiving enough that a careful measurement always works, and
unforgiving enough that a guess does not.

- tone base and spacing: about +/- 2%, comfortably wider than the error a
  chirp-derived window produces
- symbol duration: the search steps 0.25 ms and the fit term is sharp
- start offset: the chirps find it to within a millisecond down to about
  -20 dB SNR

## What actually breaks the link

RT60 and DRR are independent, and the notebooks now say so explicitly. A sweep
over 4/8-FSK, three spacings and three symbol rates found that **DRR dominates
and modulation barely matters**: at +10 dB (desk) and +6 dB (office) every
configuration decoded 100%; at -3 dB (hall, 8 m) every configuration decoded
0%. That is why 02.13 sweeps distance rather than symbol rate, and why the
physical activity is "walk backwards until it breaks".

Symbol length does buy back reverberation, but only within a band, and a single
seed is noisy enough to hide the trend. Averaged over three seeds, 8-FSK at 18
dB SNR:

```
RT60 0.25 s      20ms  30  40  60  80  100  120  150  200
  DRR +0 dB       0/3  1/3 2/3 2/3 3/3 3/3  3/3  3/3  3/3
  DRR -6 dB       0/3  0/3 1/3 1/3 3/3 3/3  3/3  3/3  3/3
  DRR -9 dB       0/3  0/3 0/3 0/3 3/3 3/3  3/3  3/3  3/3
RT60 0.60 s
  DRR -6 dB       0/3  0/3 0/3 0/3 1/3 0/3  1/3  3/3  2/3
```

At RT60 0.6 s the recovery point is past 150 ms, which is off the end of a
usable slider, so **02.13 uses RT60 = 0.25 s and seed 5**. With those, both
sliders are monotone in one realisation: the link decodes out to 4 m and fails
from 5 m; parked at 6 m it fails at 20-60 ms and recovers from 80 ms up. If you
change the seed, re-check both - the notebook says so to the students too.

## The phone page

`audio_link.html` is a single static file. It transmits and receives, needs no
server, no install and no pairing, and touches the network only to load.

- Host it anywhere static over **https** (GitLab Pages is fine). The mic needs
  a secure context; `file://` transmits but cannot receive.
- Three modes - Tone, Bits, Message - matching notebooks 02.10, 02.11, 02.12,
  so nothing is a black box before its notebook.
- Hardcoded to the defaults above, so it cannot read the secret.
- Verified against `.admin/acoustic_workshop/acoustic.py` both directions: frames agree to 2.6e-08,
  Python decodes the page's WAV clean and through a 0.4 s room, the page
  decodes Python's frame clean, through a room, and at 44.1 kHz. Re-run with
  `node tools/check_link_js.mjs` then `python tools/check_link.py`.
- The "Download last as WAV" button is a plain `<a download>`. It works from a
  real static host; it is inert inside the Claude artifact viewer, which never
  grants pages download permission.

## Running the class

- Every notebook cell runs offline. `USE_LIVE_AUDIO = False` is the default.
- The air is the only network. No Wi-Fi, no server, no certificate between
  devices. That was deliberate: lecture-hall networks commonly isolate clients
  from each other, which is what made the trAACer approach unusable here.
- The room is a shared medium and pairs will collide. There is no MAC layer by
  design. Tell them to take turns; the sender id lets a student see whose
  transmission they caught.
- Marks come from the exercise questions plus one point for recovering the
  secret message. A failed live link still earns full marks if the student
  reports what the receiver said and what they changed.

## Interactive figures

Every parameter-dependent figure is a `make_*_figure` function driven by an
ipywidgets slider, using the `display(fig, display_id=True)` / `handle.update`
pattern from `01.2_Converting_Analog_Signals_to_Time_Series.ipynb`. The
`ac.plot_*` helpers therefore **return** their figure instead of calling
`plt.show()`. Assign the result: a bare `ac.plot_spectrum(x, rate)` as the last
line of a cell draws twice.

## Checking everything still works

```bash
python tools/make_secret.py      # regenerate and self-test the secret file
python tools/build_notebooks.py  # regenerate all four notebooks
python tools/check_notebooks.py  # execute them
python tools/check_widgets.py    # drive every slider through its full range
node   tools/check_link_js.mjs   # the phone page's DSP, in Node
python tools/check_link.py       # cross-check page against acoustic.py
```

`check_notebooks.py` only ever draws the first figure of an interactive cell,
because observers do not fire during a plain execute. `check_widgets.py` is
what catches a `make_*_figure` that breaks at one end of its slider.

## Relationship to trAACer

`trAACer` (Kasimir's thesis code, `eth/audio-kasimir/acoustic-signals`) is not
used. Its browser receiver needs phone-to-laptop reachability on the same LAN,
which a lecture-hall network is likely to break for everyone at once. A static
page removes the problem entirely: with no server, client isolation is
irrelevant. `css.py`, `psk.py` and the OFDM modules there are worth
cherry-picking if the workshop is ever extended.
