"""Check pySerial and discover VLC ports without opening connections."""

def check_serial_environment(show=True):
    import glob
    def display(value):
        if show:
            _display(value)
    from IPython.display import display as _display, HTML
    from html import escape

    try:
        import serial
    except ImportError as exc:
        raise ImportError(
            "pySerial is missing. Run %pip install pyserial in this kernel, then restart it."
        ) from exc

    if not hasattr(serial, "Serial"):
        raise ImportError(
            "The imported serial module is not pySerial. Check for a local serial.py file "
            "or serial folder, or run %pip uninstall -y serial followed by %pip install --force-reinstall pyserial, then restart the kernel."
        )
    version = escape(str(getattr(serial, "__version__", "Unknown")))
    display(HTML(
        '<div class="alert alert-block alert-success">'
        f'Python serial check passed. pySerial {version} is available.<br>'
        'Continue with serial-port detection to check the connected boards.</div>'
    ))
    local_matches = glob.glob("serial*")
    if local_matches:
        display(HTML('<p>Local files to check for naming conflicts: '
                     + escape(", ".join(local_matches)) + '</p>'))

    # --- Auto-detect for serial ports (Windows / macOS / Linux) ---
    # Requires: pip install pyserial
    from serial.tools import list_ports
    import platform, re
    from IPython.display import display as _display, HTML
    from html import escape

    KNOWN_VIDS = {
        0x2341, 0x2A03,  # Arduino
        0x1A86,          # WCH CH340
        0x10C4,          # Silicon Labs CP210x
        0x0403,          # FTDI
        0x239A,          # Adafruit
        0x16C0,          # PJRC / Teensy
        0x2E8A,          # Raspberry Pi (RP2040)
    }

    # macOS exposes fake ports we should ignore
    SKIP_SUBSTR = {"bluetooth", "incoming", "debug-console", "debug"}

    def _com_number(dev):
        m = re.match(r"^COM(\d+)$", (dev or ""), re.IGNORECASE)
        return int(m.group(1)) if m else -1

    def _is_candidate(p):
        dev  = (p.device or "").lower()
        desc = (p.description or "").lower()
        manu = (p.manufacturer or "").lower()
        vid  = getattr(p, "vid", None)

        if any(s in dev for s in SKIP_SUBSTR) or any(s in desc for s in SKIP_SUBSTR):
            return False

        if vid in KNOWN_VIDS:
            return True

        # common hints even without a known VID
        hints = ("arduino","usbserial","usb modem","usbmodem","ch340","cp210","ftdi","teensy","sparkfun","seeed")
        if any(h in desc or h in manu for h in hints):
            return True

        # any real USB device with VID/PID
        if (getattr(p, "vid", None) is not None) and (getattr(p, "pid", None) is not None):
            return True

        return False

    def _score(p):
        dev  = (p.device or "").lower()
        desc = (p.description or "").lower()
        manu = (p.manufacturer or "").lower()
        vid  = getattr(p, "vid", None)
        s = 0.0

        if vid in KNOWN_VIDS: s += 10
        if "arduino" in desc or "arduino" in manu: s += 6
        if any(k in desc for k in ("usbmodem","usbserial","ch340","cp210","ftdi")): s += 4

        # macOS: prefer call-out ports (/dev/cu.*) and usbmodem
        if platform.system() == "Darwin":
            if "/cu."  in dev: s += 2
            if "usbmodem" in dev: s += 2

        # Windows: slightly prefer higher COM numbers (often most recent)
        s += max(_com_number(p.device), 0) * 0.01
        return s

    ports = list(list_ports.comports())
    PORT_A = PORT_B = None
    port_report = []

    if not ports:
        port_report.append("No serial ports found. Plug in your device and re-run this cell.")
    else:
        ranked = sorted(ports, key=_score, reverse=True)

        port_report.append("Detected serial ports:")
        for i, p in enumerate(ranked, 1):
            vid = f"{getattr(p,'vid',None):04X}" if getattr(p,'vid',None) is not None else "----"
            pid = f"{getattr(p,'pid',None):04X}" if getattr(p,'pid',None) is not None else "----"
            port_report.append(f"{i:2d}. {p.device:>24}  {p.description:35.35}  VID:PID={vid}:{pid}  Mfr={p.manufacturer or '-'}")

        # filter to real candidates (skip Bluetooth/debug)
        cands = [p for p in ranked if _is_candidate(p)]

        PORT_A = cands[0].device if len(cands) >= 1 else None
        PORT_B = cands[1].device if len(cands) >= 2 else None

        port_report.append("\nSelected:")
        port_report.append(f"  PORT_A = {PORT_A!r}")
        port_report.append(f"  PORT_B = {PORT_B!r}  # None if no second suitable device found")
    # Display directly below this cell, bypassing the serial log capture.
    display(HTML("<pre>" + escape("\n".join(port_report)) + "</pre>"))
    return {"serial": serial, "PORT_A": PORT_A, "PORT_B": PORT_B,
            "report": "\n".join(port_report), "local_matches": local_matches}
