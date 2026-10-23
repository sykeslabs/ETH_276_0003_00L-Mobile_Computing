# VLC serial communication reference

This reference describes the USB serial commands and events used by the supplied ETH Zurich VLC devices. The computer sends commands to its connected board; the board handles communication over the optical link. Examples assume a serial connection at 115,200 baud.

## Commands

Each command starts with a single letter. Parameters, when required, appear in square brackets. End every command with a newline character (`\n`). Device addresses are hexadecimal: for example, `AB` and `CD`. Reserve `FF` for broadcast.

| Command | Purpose | Example | Response |
|---|---|---|---|
| `r` | Reset the device. | `r` | None specified. |
| `p` | Read the firmware version. | `p` | For example, `p[v1.0.1]`. |
| `a` | Read the device address. | `a` | For example, `a[AB]`. |
| `a[XX]` | Set the device address. | `a[AB]` | `a[AB]` |
| `c[group,parameter,value]` | Set a configuration parameter. | `c[1,1,16]` | The command is echoed if processed. |
| `m[message,destination]` | Submit a null-terminated message for transmission. | `m[hello\0,CD]` | `m[P,1,CD]` if accepted; `m[P,0,CD]` if dropped. |

Acceptance of a message does not confirm delivery. For unicast, inspect the acknowledgment (ACK) events. Broadcast messages are not acknowledged.

In the examples, `\0` represents a null byte and `\n` represents a newline. Python interprets these escapes in string and byte literals. For example, `b"m[hello\0,CD]\n"` includes the required null byte and command terminator. Use single-line payloads without commas or square brackets for the notebook experiments.

## Configuration parameters

Configuration commands have the form `c[group,parameter,value]`. The group selects the physical layer (PHY), medium access control (MAC), or logging settings.

| Group | Parameter | Meaning |
|---|---|---|
| PHY (`0`) | `0` | Preamble length. |
| PHY (`0`) | `1` | Forward error correction (FEC) threshold; disabled by default. |
| PHY (`0`) | `2` | Channel-busy threshold; default: `20`. |
| PHY (`0`) | `3` | Enable or disable light emission. The numeric ON/OFF mapping is not specified in this reference. |
| MAC (`1`) | `0` | Number of retransmissions. |
| MAC (`1`) | `1` | Distributed interframe space (DIFS). |
| MAC (`1`) | `2` | Minimum contention window (CWmin); use a power of two. |
| MAC (`1`) | `3` | Maximum contention window (CWmax); use a power of two. |
| MAC (`1`) | `4` | Request-to-send (RTS) threshold; disabled by default. |
| MAC (`1`) | `5` | Device MAC address. |
| Logging (`2`) | `0` | Logging level, from `0` (none) to `7` (most verbose, named “silly” in the firmware). |
| Logging (`2`) | `1` | Logger prefix character; disabled by default. |

For example, `c[1,0,5]` sets five retransmissions. `c[0,1,30]` sets the FEC threshold to 30, applying FEC to packets with payloads of at least 30 bytes. When enabling FEC, use a threshold of at least 10; FEC should not be applied to control frames.

## Message events

The board reports message activity using events that begin with `m[`. These distinguish an individual frame transmission from completion of the entire message operation.

| Event | Meaning |
|---|---|
| `m[T]` | The PHY completed a frame transmission. Reported for data and control frames, including retransmissions. |
| `m[D]` | Processing of the submitted message is complete, including any retransmissions. A new message can be submitted. This event alone does not confirm successful delivery. |
| `m[R,type,message]` | A frame was received. The type identifies data (`D`), ACK (`A`), RTS (`R`), or clear-to-send (`C`, CTS). The final field contains the message payload. |

Transmission and reception events are accompanied by statistics records in this format:

```text
s[mode,type,src->dest,size(txsize),seq,cw,cwsize,dispatch,time]
```

The `cw`, `cwsize`, and `dispatch` values are available for data-transmission events. Do not assume that every event supplies meaningful values for every field.

## Statistics fields

| Field | Meaning |
|---|---|
| `mode` | `R`: received; `T`: transmitted. |
| `type` | `D`: data; `A`: ACK; `R`: RTS; `C`: CTS. An appended `R` marks a retransmission. |
| `src` | Source address in hexadecimal. |
| `dest` | Destination address in hexadecimal. |
| `size` | Payload size in bytes. |
| `txsize` | Transmitted size in bytes, including payload and protocol overhead. |
| `seq` | Sequence number. |
| `cw` | Selected contention-window slot. |
| `cwsize` | Current contention-window size. |
| `dispatch` | Time at which the MAC dispatched the frame, in milliseconds. |
| `time` | Time at which the PHY received or transmitted the frame, in milliseconds. |

For round-trip measurements, pair a transmitted data frame with its received ACK using the sequence number. Use timestamps from the same transmitting device; timestamps from different boards are not necessarily synchronized.

## Setup and measurement notes

Opening a serial connection commonly resets the board. Configuration settings, including the address, are lost on reset and must be applied again after opening the port. Allow time for the firmware to start before sending commands.

If an address change is not confirmed, an earlier classroom workaround was to reset the board, then send the address command twice with five seconds between commands. Use this only when the normal setup fails, and check the echoed address.

The documented message-size limit is 200 characters. Use ASCII for these experiments so each payload character occupies one byte, and keep payloads below the limit. The notebook's 1-byte and 180-byte payloads leave room for the null terminator.

Point the LEDs toward each other. Keep alignment, distance, and ambient lighting consistent when comparing settings. Verbose logging can slow the device; the documented logging default is `0`. Check that the required statistics events are still available before collecting timings.

Only one program should open a given serial port at a time. Close Arduino Serial Monitor or other terminal software before running the notebook. A previous student team reported that a board was detected under Windows Subsystem for Linux (WSL), but reads failed. If that occurs, try the notebook in native Windows before assuming the board is faulty.

## Python example

Install `pyserial` in the active Python environment; the import name is `serial`. The example below configures one board as `AB` and sends to a second board addressed `CD`. Replace `COM4` with the local serial-port name. The receiver must already be configured and aligned with the transmitter.

The read loop handles empty reads caused by a timeout and collects complete lines. Interrupt it to stop; the context manager then closes the port. Run this example separately from the notebook's background serial listeners.

```python
import time
import serial

with serial.Serial("COM4", 115200, timeout=1) as connection:
    time.sleep(2)  # Allow the board to restart.

    commands = [
        b"a[AB]\n",                 # Set the local address.
        b"c[1,0,5]\n",              # Allow five retransmissions.
        b"c[0,1,30]\n",             # Set the FEC threshold.
        b"m[hello world!\0,CD]\n",  # Send to the other board.
    ]
    for command in commands:
        connection.write(command)
        time.sleep(0.1)

    buffer = bytearray()
    try:
        while True:
            byte = connection.read(1)
            if not byte:
                continue  # Read timed out; no data arrived.
            if byte == b"\n":
                print(buffer.decode("utf-8", errors="replace").rstrip("\r"))
                buffer.clear()
            else:
                buffer.extend(byte)
    except KeyboardInterrupt:
        print("Serial reading stopped.")
```

## Serial libraries

The notebook uses [Python with pySerial](https://github.com/pyserial/pyserial). Other options include [MATLAB serial communication](https://www.mathworks.com/help/matlab/serial-port-devices.html), [Java with jSSC](https://github.com/scream3r/java-simple-serial-connector), and [Node.js serialport](https://www.npmjs.com/package/serialport).
