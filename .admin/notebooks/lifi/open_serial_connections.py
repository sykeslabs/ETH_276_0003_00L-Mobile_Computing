"""Serial setup executed in the notebook namespace to preserve live callbacks."""
# BIDIRECTIONAL SETUP — run this cell after each restart

import sys, time, threading, re, platform
import serial

# Stop the previous listeners before replacing their globals or closing ports.
_previous_stop = globals().get("stop_event")
if _previous_stop is not None:
    _previous_stop.set()
_previous_threads = list(globals().get("threads", []))
for _label, _thread in _previous_threads:
    if _thread is not threading.current_thread():
        _thread.join(timeout=3.0)
if any(t.is_alive() for _, t in _previous_threads):
    raise RuntimeError("A previous serial listener is still stopping. Wait and rerun this cell; "
                       "restart the kernel if it remains active.")


BAUD   = 115200
BRIDGE = False
START_RETRIES  = 1
REOPEN_RETRIES = 1
RETRY_DELAY_S  = 1.0
MAX_LINE_BYTES = 8192

# ---- helpers ----
def _valid_port(p): return isinstance(p, str) and p.strip() != ""

def _darwin_alternates(port):
    """On macOS, try the sibling device (/cu.<x> <-> /tty.<x>)."""
    if platform.system() != "Darwin" or not _valid_port(port):
        return []
    if "/cu." in port:
        return [port.replace("/cu.", "/tty.", 1)]
    if "/tty." in port:
        return [port.replace("/tty.", "/cu.", 1)]
    return []

def _try_open_once(port, baud, timeout=0.05, verbose_label=None):
    """Try to open 'port', then (on macOS) its sibling. Return (ser, used_port)."""
    tried = []
    for candidate in [port] + _darwin_alternates(port):
        if not _valid_port(candidate):
            continue
        try:
            s = serial.Serial(candidate, baud, timeout=timeout)
            time.sleep(0.15)
            try:
                s.reset_input_buffer(); s.reset_output_buffer()
            except Exception:
                pass
            if verbose_label:
                print(f"[{verbose_label}] opened on {candidate}")
            return s, candidate
        except Exception as e:
            tried.append((candidate, str(e)))
    # verbose diagnostics
    if verbose_label and tried:
        why = "; ".join([f"{c}: {msg}" for c, msg in tried])
        print(f"[{verbose_label}] open failed ({why})", file=sys.stderr)
    return None, port

def close_if_open(ser):
    if ser is None or not getattr(ser, "is_open", False):
        return
    try:
        ser.close()
    except (OSError, serial.SerialException, TypeError) as exc:
        # A disconnected or previously raced handle can be partly closed.
        print(f"[WARN] Previous serial handle could not close cleanly: {exc}. "
              "Restart the kernel if reopening fails.", file=sys.stderr)

# ---- read ports from earlier autodetect (or user) ----
PORT_A = globals().get("PORT_A")
PORT_B = globals().get("PORT_B")

if not _valid_port(PORT_A):
    print("[WARN] PORT_A is not set. Define it or run the autodetect cell.", file=sys.stderr)
if not _valid_port(PORT_B):
    print("[INFO] Only one device expected; PORT_B not set.", file=sys.stderr)

# Close both original handles and replacements created by reconnecting listeners.
_previous_handles = [globals().get("serA"), globals().get("serB")]
for _name in ("serA_ref", "serB_ref"):
    _ref = globals().get(_name)
    if _ref:
        _previous_handles.append(_ref[0])
_closed_ids = set()
for _handle in _previous_handles:
    if _handle is not None and id(_handle) not in _closed_ids:
        close_if_open(_handle)
        _closed_ids.add(id(_handle))

# ---- initial open with macOS fallback ----
serA, PORT_A = _try_open_once(PORT_A, BAUD, timeout=0.05, verbose_label="PORT_A") if _valid_port(PORT_A) else (None, PORT_A)
serB, PORT_B = _try_open_once(PORT_B, BAUD, timeout=0.05, verbose_label="PORT_B") if _valid_port(PORT_B) else (None, PORT_B)

if _valid_port(PORT_A) and not (serA and serA.is_open):
    print(f"[{PORT_A}] not available; will retry once.", file=sys.stderr)
if _valid_port(PORT_B) and not (serB and serB.is_open):
    print(f"[{PORT_B}] not available; will retry once.", file=sys.stderr)

stop_event = threading.Event()
serA_ref = [serA]; serB_ref = [serB]

def pump(name, src_ref, dst_ref, start_retries=1, reopen_retries=1, retry_delay=1.0,
         stop_event=stop_event):
    """Read lines from src_ref[0]; bridge bytes to dst_ref[0] if BRIDGE."""
    if not _valid_port(name):
        print(f"[{name or 'UNKNOWN'}] invalid port; listener not started.", file=sys.stderr)
        return

    buf = bytearray()
    start_left  = start_retries if (src_ref[0] is None or not getattr(src_ref[0], "is_open", False)) else 0
    reopen_left = reopen_retries

    def open_once(label):
        ser, used = _try_open_once(label, BAUD, timeout=0.05)  # tries sibling on macOS
        if ser:
            src_ref[0] = ser
            # Update 'name' to the actually used device for future logs
            return used
        return None

    # initial ensure-open with bounded retries
    current_label = name
    while not stop_event.is_set():
        s = src_ref[0]
        if s is None or not getattr(s, "is_open", False):
            if start_left > 0:
                time.sleep(retry_delay)
                used = open_once(current_label)
                if used:
                    current_label = used
                    break
                start_left -= 1
                continue
            print(f"[{current_label}] unavailable after {START_RETRIES+1} attempts. Stopping listener.", file=sys.stderr)
            return
        break

    while not stop_event.is_set():
        try:
            b = src_ref[0].read(1)
            if not b:
                continue

            if BRIDGE and dst_ref[0] and getattr(dst_ref[0], "is_open", False):
                try: dst_ref[0].write(b)
                except serial.SerialException: pass

            if b == b'\n':
                line = buf.decode('utf-8', errors='replace').rstrip('\r')

                # >>> Hook: forward complete line to notebook callback if defined
                cb = globals().get("on_serial_line")
                if callable(cb):
                    try:
                        cb(current_label, line)
                    except Exception as e:
                        print(f"[{current_label} hook warn] {e}", file=sys.stderr)
                # <<< end hook

                print(f"[{current_label}] {line}")
                buf.clear()
            else:
                buf.extend(b)
                if len(buf) > MAX_LINE_BYTES:
                    line = buf.decode('utf-8', errors='replace')[:MAX_LINE_BYTES] + "…"
                    print(f"[{current_label} warn] oversized line truncated: {line}", file=sys.stderr)
                    buf.clear()

        except serial.SerialException as e:
            print(f"[{current_label} warn] {e}.", file=sys.stderr)
            close_if_open(src_ref[0]); src_ref[0] = None
            if reopen_left > 0:
                time.sleep(retry_delay)
                used = open_once(current_label)
                if used:
                    current_label = used
                    reopen_left = reopen_retries
                    continue
                reopen_left -= 1
                continue
            print(f"[{current_label}] could not reopen (max {reopen_retries} tries). Stopping listener.", file=sys.stderr)
            return

        except AttributeError as e:
            if 'hEvent' in str(e):  # Windows overlapped I/O glitch
                close_if_open(src_ref[0]); src_ref[0] = None
                if reopen_left > 0:
                    time.sleep(retry_delay)
                    used = open_once(current_label)
                    if used:
                        current_label = used
                        reopen_left -= 1
                        continue
                    reopen_left -= 1
                    continue
                print(f"[{current_label}] hEvent glitch and reopen failed. Stopping listener.", file=sys.stderr)
                return
            print(f"[{current_label} pump error] {e}", file=sys.stderr); return

        except Exception as e:
            msg = str(e)
            if ('byref' in msg) or ('ctypes' in msg) or ('OSError' in msg):
                close_if_open(src_ref[0]); src_ref[0] = None
                if reopen_left > 0:
                    time.sleep(retry_delay)
                    used = open_once(current_label)
                    if used:
                        current_label = used
                        reopen_left -= 1
                        continue
                    reopen_left -= 1
                    continue
                print(f"[{current_label}] handle glitch and reopen failed. Stopping listener.", file=sys.stderr)
                return
            print(f"[{current_label} pump error] {e}", file=sys.stderr); return

# start listeners (only for ports that exist)
threads = []
if _valid_port(PORT_A):
    tA = threading.Thread(target=pump, args=(PORT_A, serA_ref, serB_ref, START_RETRIES, REOPEN_RETRIES, RETRY_DELAY_S), daemon=True)
    tA.start(); threads.append(('A', tA))
if _valid_port(PORT_B):
    tB = threading.Thread(target=pump, args=(PORT_B, serB_ref, serA_ref, START_RETRIES, REOPEN_RETRIES, RETRY_DELAY_S), daemon=True)
    tB.start(); threads.append(('B', tB))

if not threads:
    print("[WARN] No valid ports configured. No listeners started.", file=sys.stderr)
else:
    print("Listening setup done. " + " ".join([f"{n}={t.is_alive()}" for n,t in threads]))


# --- sendA/sendB wrappers (robust; no dependency on _send signature) ---
import sys, time

def _write_serial(sref, label, cmd, *, newline=True, delay=0.1, encoding="utf-8"):
    if newline and not cmd.endswith('\n'):
        cmd += '\n'
    s = sref[0]
    if s and getattr(s, "is_open", False):
        s.write(cmd.encode(encoding, errors='replace'))
        if delay:
            time.sleep(delay)
    else:
        print(f"[{label}] not open; send skipped.", file=sys.stderr)

def sendA(cmd: str, *, newline=True, delay=0.1):
    label = PORT_A if ('PORT_A' in globals() and isinstance(PORT_A, str) and PORT_A.strip()) else "PORT_A"
    _write_serial(serA_ref, label, cmd, newline=newline, delay=delay)

def sendB(cmd: str, *, newline=True, delay=0.1):
    label = PORT_B if ('PORT_B' in globals() and isinstance(PORT_B, str) and PORT_B.strip()) else "PORT_B"
    _write_serial(serB_ref, label, cmd, newline=newline, delay=delay)
