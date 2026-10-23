"""Console controls for bounded VLC round-trip measurements."""
import threading
import time
import ipywidgets as w


class PerformanceTest:
    ACK_WAIT_S = 10
    def __init__(self, console):
        self.console = console
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.active = False
        self.pending = {}
        self.samples = []
        self.results = []
        self.board = None
        layout = lambda: w.Layout(width='100%', min_width='0', margin='0')
        self.transmitter = w.Dropdown(options=list(console.boards), description='Sender:', layout=layout())
        self.payload = w.BoundedIntText(value=1, min=1, max=180, description='Bytes/packet:', layout=layout())
        self.packets = w.BoundedIntText(value=10, min=1, max=1000, description='Packets:', layout=layout())
        self.interval = w.BoundedFloatText(value=3, min=.1, max=60, step=.1, description='Interval (s):', layout=layout())
        self.fields = [self.transmitter, self.payload, self.packets, self.interval]
        for field in self.fields:
            field.style.description_width = '110px'
        fields = w.GridBox(self.fields, layout=w.Layout(width='100%', grid_template_columns='repeat(2, minmax(0, 1fr))', grid_gap='6px'))
        self.start_button = w.Button(description='Start test', layout=layout())
        self.stop_button = w.Button(description='Stop test', disabled=True, layout=layout())
        self.start_button.on_click(lambda _: self.start())
        self.stop_button.on_click(lambda _: self.stop.set())
        buttons = w.GridBox([self.start_button, self.stop_button], layout=w.Layout(width='100%', grid_template_columns='repeat(2, minmax(0, 1fr))', grid_gap='9px', margin='8px 0 0'))
        self.widget = w.VBox([w.HTML('<div style="color:#f2f0e5;font:bold 10px Arial;letter-spacing:1.2px;margin-bottom:8px">PERFORMANCE TEST</div>'), fields, buttons], layout=w.Layout(width='100%', margin='10px 0 0'))
        self.widget.add_class('vlc-control-panel')

    def note(self, message):
        self.console.write(f'{time.strftime("%H:%M:%S")}  {message}\n')

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            board = self.console.boards[self.transmitter.value]
            if not board.connection or not board.connection.is_open or board.stop.is_set():
                self.note('Test not started: sender is not connected.')
                return
            if any(b.worker and b.worker.is_alive() for b in self.console.boards.values()):
                self.note('Test not started: wait for the current console action to finish.')
                return
            dest = board.destination.value.strip().upper()
            import re
            if not re.fullmatch('[0-9A-F]{2}', dest) or dest in ('FF', board.local.value.strip().upper()):
                self.note('Test not started: choose a different unicast destination in Send to.')
                return
            self.board = board
            self.config = dict(sender=board.label, destination=dest, payload_bytes=self.payload.value,
                               packet_count=self.packets.value, interval_s=self.interval.value)
            self.pending = {}
            self.samples = []
            self.stop.clear()
            self.start_button.disabled = True
            self.stop_button.disabled = False
            for field in self.fields: field.disabled = True
            for b in self.console.boards.values():
                b.repeat_stop.set()
                for control in [*b.actions, b.led_switch, b.local, b.destination, b.retries, b.fec, b.message]: control.disabled = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def on_line(self, board, line):
        with self.lock:
            if not self.active or board is not self.board or time.monotonic() >= self.deadline:
                return
            if not line.startswith('s[') or not line.endswith(']'): return
            fields = line[2:-1].split(',')
            if len(fields) < 9: return
            try:
                seq = fields[4]
                if fields[:2] == ['T', 'D']:
                    self.pending[seq] = float(fields[7])
                elif fields[:2] == ['R', 'A'] and seq in self.pending:
                    dispatched = self.pending.pop(seq)
                    rtt = float(fields[8]) - dispatched
                    if rtt < 0: return
                    self.samples.append(dict(sequence=seq, dispatch_ms=dispatched, rtt_ms=rtt))
                    self.note(f'ACK {board.label} seq={seq}  rtt_ms={rtt:.3f}  (#{len(self.samples)})')
            except ValueError:
                self.note('Timing event ignored: invalid firmware timestamp.')

    def run(self):
        started = None
        error = None
        sent = 0
        try:
            for b in self.console.boards.values():
                if b.repeat_thread: b.repeat_thread.join(timeout=2)
                if b.repeat_thread and b.repeat_thread.is_alive():
                    raise RuntimeError('Repeated broadcast is still stopping.')
            # Let the last broadcast/ACK exchange settle before collecting events.
            if self.stop.wait(2): return
            with self.lock:
                started = time.monotonic()
                self.deadline = float('inf')
                self.active = True
            self.note(f"Test started: Arduino {self.board.label} -> {self.config['destination']}, {self.config['payload_bytes']} bytes, {self.config['packet_count']} packets, interval {self.config['interval_s']:g} s.")
            command = 'm[' + 'X' * self.config['payload_bytes'] + '\0,' + self.config['destination'] + ']'
            for index in range(self.config['packet_count']):
                if index and self.stop.wait(self.config['interval_s']): break
                if self.stop.is_set(): break
                if self.board.stop.is_set(): raise RuntimeError('Sender disconnected.')
                self.board.send(command, delay=0)
                sent += 1
                self.note(f'Packet {sent}/{self.config["packet_count"]} submitted.')
            self.deadline = time.monotonic() + self.ACK_WAIT_S
            while not self.stop.is_set() and time.monotonic() < self.deadline:
                if self.board.stop.is_set(): raise RuntimeError('Sender disconnected.')
                with self.lock:
                    if len(self.samples) >= sent: break
                self.stop.wait(.05)
        except Exception as exc:
            error = str(exc)
            self.note(f'Test interrupted: {exc}')
        finally:
            with self.lock:
                self.active = False
                if started is not None:
                    elapsed = max(.000001, time.monotonic() - started)
                    count = len(self.samples)
                    result = dict(self.config, elapsed_s=elapsed, submitted_packets=sent, acknowledgments=count,
                                  packets_per_s=count/elapsed, payload_bits_per_s=count*self.config['payload_bytes']*8/elapsed,
                                  samples=list(self.samples), stopped=self.stop.is_set(), error=error)
                    self.results.append(result)
                    self.console.namespace['vlc_performance_results'] = self.results
                    mean = sum(s['rtt_ms'] for s in self.samples)/count if count else None
                    timing = f'{mean:.1f} ms' if mean is not None else 'no matched ACKs'
                    self.note(f'Test finished: {sent} packets submitted, {count} matched ACKs in {elapsed:.1f} s; mean RTT {timing}; {result["packets_per_s"]:.2f} packets/s; {result["payload_bits_per_s"]:.1f} payload bit/s.')
                else:
                    self.note('Test cancelled before measurement.')
                for field in self.fields: field.disabled = False
                self.start_button.disabled = False
                self.stop_button.disabled = True
                for b in self.console.boards.values():
                    for control in [b.local, b.destination, b.retries, b.fec, b.message]: control.disabled = False
                    b.update_status(b.last_status)

    def close(self):
        self.stop.set()
        if self.thread: self.thread.join(timeout=4)
        if self.thread and self.thread.is_alive(): raise RuntimeError('Performance test is still stopping.')
