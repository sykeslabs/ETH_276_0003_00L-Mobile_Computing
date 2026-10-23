"""Interactive serial and optical-link controls for the LiFi notebook."""
from html import escape
from pathlib import Path
import re
import runpy
import sys
from collections import deque
import threading
import time

import ipywidgets as w
from IPython.display import display
serial = None

VintageLog = runpy.run_path(str(Path(__file__).with_name('vintage_log.py')))['VintageLog']
STYLE = '''<style>
.vlc-control-console,.vlc-control-console .widget-html-content,
.cell-output-ipywidget-background:has(.vlc-control-console){background:transparent!important;}
.vlc-control-case{box-sizing:border-box;padding:16px;border:7px solid #6d7868;border-radius:12px;
background:linear-gradient(115deg,#354134,#1c2b21 45%,#283728);box-shadow:inset 0 0 0 2px #162218,0 4px 6px #0005;}
.vlc-control-panel{box-sizing:border-box;padding:10px;border:1px solid #607457;border-radius:4px;background:transparent;}
.vlc-control-panel .widget-label{color:#f2f0e5!important;font:700 10px 'Arial Narrow','Helvetica Neue',Arial,sans-serif!important;letter-spacing:1.2px;text-transform:uppercase;text-shadow:0 1px 1px #000;padding:2px 5px;box-sizing:border-box;}
.vlc-control-panel input{background:#101e16!important;color:#c3e6a1!important;border:1px solid #6d7868!important;font:12px 'Courier New',monospace!important;}
/* Sculpted graphite keycaps with dark skirts and coloured legends. */
.vlc-control-panel button,.vlc-general-controls button{position:relative;background:linear-gradient(175deg,#606767,#4b5253 68%,#414849)!important;color:#eee9df!important;border:1px solid #161b1c!important;border-top:2px solid #7b8281!important;border-left:3px solid #343b3c!important;border-right:3px solid #292f30!important;border-bottom:6px solid #242a2b!important;border-radius:5px!important;height:36px;font:700 10px 'Arial Narrow','Helvetica Neue',Arial,sans-serif!important;letter-spacing:.5px;text-transform:uppercase;box-shadow:inset 0 1px 2px #ffffff30,inset 0 -2px 3px #0003,0 2px 0 #0b1010,0 3px 4px #0008;text-shadow:0 1px 1px #0005;transition:transform 70ms,box-shadow 70ms;}
.vlc-action-row button:nth-child(1){color:#e1b845!important;}
.vlc-action-row button:nth-child(2){color:#63c1c1!important;}
.vlc-action-row button:nth-child(3){color:#79b6e0!important;}
.vlc-action-row button:nth-child(4){color:#eb8981!important;}
.vlc-control-panel button.vlc-clear-key{background:linear-gradient(175deg,#484e4f,#353b3d 75%)!important;color:#dbdcd7!important;border-top-color:#636b6c!important;}
.vlc-control-panel button:active:not(:disabled){transform:translateY(2px);box-shadow:inset 0 1px 3px #0005,0 1px 0 #0b1010;}
.vlc-control-panel button:focus,.vlc-control-panel button:focus-visible{outline:none!important;}
.vlc-control-panel button.vlc-led-switch{position:relative;width:42px!important;height:43px!important;min-width:42px;padding:26px 0 0!important;margin:0!important;background:#253028!important;border:1px solid #87917d!important;border-radius:3px!important;font:9px 'Courier New',monospace!important;color:#c4d0b0!important;letter-spacing:0;line-height:14px;box-shadow:none;text-shadow:none;}
.vlc-control-panel button.vlc-led-switch:after{content:'';position:absolute;top:3px;left:15px;width:10px;height:24px;border-radius:5px;background:#0b130e;box-shadow:inset 0 1px 3px #000;}
.vlc-control-panel button.vlc-led-switch:before{content:'';position:absolute;top:15px;left:12px;z-index:1;width:16px;height:11px;border-radius:3px;background:linear-gradient(#eef0df,#909e93 48%,#d5dbca 55%,#697970);border:1px solid #afb6a1;box-shadow:0 2px 2px #080d08;transition:top .2s ease,box-shadow .2s ease;}
.vlc-control-panel button.vlc-led-switch.mod-active:before{top:3px;box-shadow:0 0 4px #dfca7c80;}
.vlc-control-panel button.vlc-led-switch.mod-active{color:#ffdea2!important;}
.vlc-control-panel button.vlc-led-switch:active:not(:disabled){transform:none;box-shadow:none;}
@media(prefers-reduced-motion:reduce){.vlc-control-panel button.vlc-led-switch:before{transition:none;}}
.vlc-action-row{gap:9px;}
.vlc-control-panel .widget-text{box-sizing:border-box;}
.vlc-control-panel .widget-text input{min-width:0;box-sizing:border-box;}
.vlc-control-panel input[type=number]{appearance:textfield;-moz-appearance:textfield;}
.vlc-control-panel input[type=number]::-webkit-inner-spin-button,
.vlc-control-panel input[type=number]::-webkit-outer-spin-button{-webkit-appearance:none;margin:0;}
.vlc-control-panel button:disabled{opacity:.45;}
.vlc-control-panel .vlc-vintage-log> .widget-html-content>div{padding:0!important;}
</style>'''


def address(text, broadcast=False):
    text = text.strip().upper()
    if not re.fullmatch(r'[0-9A-F]{2}', text) or (text == 'FF' and not broadcast):
        raise ValueError('Use a two-digit hexadecimal address from 00 to FE.')
    return text


class Board:
    def __init__(self, console, label, port):
        self.console, self.label = console, label
        self.connection = None
        self.reader = None
        self.stop = threading.Event()
        self.repeat_stop = threading.Event()
        self.repeat_thread = None
        self.worker = None
        self.jobs = deque()
        self.job_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.closed = False
        self.log = VintageLog(f'Arduino {label} · serial log', framed=False, height=240)
        self.log.widget.layout.margin = '14px 0 0'
        self.port = w.Text(value=port or '', description='USB port:', layout=w.Layout(width='100%'))
        self.last_status = None
        self.led_enabled = True
        self.led_switch = w.ToggleButton(value=True, description='ON', tooltip='LED light emission', layout=w.Layout(width='42px',height='43px',flex='0 0 42px',margin='0'))
        self.led_switch.add_class('vlc-led-switch')
        self.led_switch.observe(self.led_changed, names='value')
        self.blink = w.Button(description='Blink LED')
        self.clear = w.Button(description='Clear log', layout=w.Layout(width='110px', margin='12px 0 0'))
        self.clear.add_class('vlc-clear-key')
        self.local = w.Text(value='AB' if label=='A' else 'CD',description='Address:',layout=w.Layout(width='48%',min_width='0',margin='0'))
        self.destination = w.Text(value='CD' if label=='A' else 'AB',description='Send to:',layout=w.Layout(width='48%',min_width='0',margin='0'))
        self.retries = w.BoundedIntText(value=3,min=0,max=255,description='Retries:',layout=w.Layout(width='48%',min_width='0',margin='0'))
        self.fec = w.BoundedIntText(value=30,min=10,max=200,description='FEC:',layout=w.Layout(width='48%',min_width='0',margin='0'))
        self.message = w.Text(value='Hello from AB' if label == 'A' else 'Hello from CD',description='Message:',layout=w.Layout(width='100%',min_width='0',margin='6px 0'))
        self.unicast = w.Button(description='Send unicast')
        self.broadcast = w.Button(description='Send broadcast')
        self.repeat = w.Button(description='Repeat broadcast')
        self.actions=[self.blink,self.unicast,self.broadcast,self.repeat]
        for button in self.actions:
            button.layout=w.Layout(width='100%',min_width='0',margin='0')
        action_row=w.GridBox(self.actions,layout=w.Layout(width='100%',margin='4px 0 0',grid_template_columns='repeat(2, minmax(0, 1fr))',grid_gap='9px'))
        action_row.add_class('vlc-action-row')
        row=lambda children:w.HBox(children,layout=w.Layout(width='100%',flex_flow='row wrap',justify_content='space-between'))
        self.widget=w.VBox([
                           row([self.local,self.destination]),row([self.retries,self.fec]),
                           self.message,w.HBox([w.HTML('<span style="color:#f2f0e5;font:bold 10px Arial;letter-spacing:1.2px">LED</span>'),self.led_switch],layout=w.Layout(align_items='center',justify_content='space-between',width='100%',margin='4px 0 8px')),action_row,
                           self.log.widget,row([self.clear])],layout=w.Layout(width='100%',min_width='0'))
        self.widget.add_class('vlc-control-panel')
        self.blink.on_click(lambda _: self.launch(self.blink_led))
        self.unicast.on_click(lambda _: self.launch(lambda:self.send_message(False)))
        self.broadcast.on_click(lambda _: self.launch(lambda:self.send_message(True)))
        self.repeat.on_click(lambda _: self.toggle_repeat())
        self.clear.on_click(lambda _: self.log.clear())
        self.update_status('Disconnected')
        for field in (self.local,self.retries,self.fec):
            field.continuous_update=False
            field.observe(lambda change:self.launch(self.apply_settings), names='value')
        self.destination.continuous_update=False
        self.destination.observe(lambda change:self.check_destination(), names='value')
        self.port.continuous_update=False
        self.port.observe(lambda change:self.launch(self.open_connection), names='value')

    def note(self, text):
        self.log.write(f'{time.strftime("%H:%M:%S")}  {text}\n')

    def update_status(self, text):
        live=self.connection is not None and self.connection.is_open and not self.stop.is_set()
        if text != self.last_status:
            self.note(text)
            self.last_status = text
        self.port.disabled=live
        for button in [*self.actions,self.led_switch]:button.disabled=not live

    def launch(self, action):
        def run():
            while True:
                with self.job_lock:
                    if self.closed or not self.jobs:
                        self.jobs.clear()
                        self.worker=None
                        return
                    job=self.jobs.popleft()
                try:job()
                except Exception as exc:self.note(f'Error: {exc}')
        with self.job_lock:
            if self.closed:return
            self.jobs.append(action)
            if self.worker is None or not self.worker.is_alive():
                self.worker=threading.Thread(target=run,daemon=True)
                self.worker.start()

    def check_destination(self):
        try:
            dest=address(self.destination.value)
            if dest==address(self.local.value):raise ValueError('Destination must differ from the local address.')
            self.note(f'Destination set to {dest}.')
        except ValueError as exc:self.note(f'Error: {exc}')

    def open_connection(self):
        if self.connection is not None:
            self.disconnect()
        port=self.port.value.strip()
        if not port:raise ValueError('No port selected. Connect the board and rerun the console, or enter its USB port.')
        self.update_status('Opening connection...')
        try:
            self.connection=serial.Serial(port,115200,timeout=.05,write_timeout=1)
            self.stop.clear()
            self.stop.wait(2)  # Opening an Uno commonly resets the firmware.
            if self.closed:return
            self.reader=threading.Thread(target=self.listen,daemon=True)
            self.reader.start()
            self.console.namespace['PORT_'+self.label]=port
            self.update_status(f'Connected: {port} at 115200 baud.')
            self.apply_settings()
            self.set_led(self.led_enabled)
        except Exception:
            self.disconnect()
            raise

    def listen(self):
        buffer=bytearray()
        try:
            while not self.stop.is_set():
                byte=self.connection.read(1)
                if not byte:continue
                if byte==b'\n':
                    line=buffer.decode('utf-8',errors='replace').rstrip('\r');buffer.clear()
                    self.note('RX '+line)
                    self.console.performance.on_line(self, line)
                    callback=self.console.namespace.get('on_serial_line')
                    if callable(callback):
                        try:callback(self.port.value,line)
                        except Exception as exc:self.note(f'Callback error: {exc}')
                    # Later notebook log displays retain their existing serial output.
                    if sys.stdout is not self.console:
                        print(f'[{self.port.value}] {line}')
                else:
                    buffer.extend(byte)
                    if len(buffer)>8192:
                        self.note('Oversized serial line discarded.');buffer.clear()
        except Exception as exc:
            if not self.stop.is_set():self.note(f'Connection lost: {exc}')
            self.stop.set();self.repeat_stop.set()
            self.update_status('Connection lost. Rerun the console to reconnect.')

    def send(self, command, newline=True, delay=.1, **kwargs):
        if self.connection is None or not self.connection.is_open or self.stop.is_set():
            raise RuntimeError(f'Arduino {self.label} is not connected.')
        if newline and not command.endswith('\n'):command+='\n'
        with self.write_lock:self.connection.write(command.encode('utf-8'))
        self.note('TX '+command.rstrip('\n').replace('\0',r'\0'))
        if delay:self.stop.wait(delay)

    def apply_settings(self):
        local=address(self.local.value)
        for other in self.console.boards.values():
            if other is not self and other.connection and other.local.value.strip().upper()==local:
                raise ValueError('The two boards need different optical addresses.')
        for cmd in [f'a[{local}]',f'c[1,0,{self.retries.value}]',f'c[0,1,{self.fec.value}]']:
            self.send(cmd)
        self.note('Settings sent. Check the echoed commands in the log.')

    def led_changed(self, change):
        enabled = bool(change['new'])
        self.led_switch.description = 'ON' if enabled else 'OFF'
        self.launch(lambda: self.set_led(enabled))

    def set_led(self, enabled):
        # Installed boards: 1 enables light, 0 disables it (verified by user observation).
        # Change emission only; the serial receive loop remains running.
        self.send(f'c[0,3,{1 if enabled else 0}]', delay=0)
        self.led_enabled = enabled
        self.note(f'LED {"ON" if enabled else "OFF"} requested.')

    def blink_led(self):
        previous = self.led_enabled
        try:
            for _ in range(3):
                if self.stop.is_set(): break
                self.send('c[0,3,1]', delay=0)
                if self.stop.wait(.3): break
                self.send('c[0,3,0]', delay=0)
                if self.stop.wait(.3): break
        finally:
            if not self.stop.is_set(): self.set_led(previous)
        self.note('Blink test finished.')

    def message_command(self, broadcast):
        text=self.message.value
        if not text or len(text.encode('ascii'))>180:raise ValueError('Enter 1 to 180 ASCII characters.')
        if any(c in text for c in ',[]\0\r\n'):raise ValueError('Avoid commas, brackets, null bytes, and newlines.')
        dest='FF' if broadcast else address(self.destination.value)
        if not broadcast and dest==address(self.local.value):raise ValueError('The destination must differ from this board’s address.')
        return f'm[{text}\0,{dest}]'

    def send_message(self, broadcast):
        self.send(self.message_command(broadcast))

    def toggle_repeat(self):
        if self.repeat_thread and self.repeat_thread.is_alive():
            self.repeat_stop.set();self.repeat_thread.join(timeout=2)
            self.repeat.description='Repeat broadcast'
            self.note('Repeated broadcast stopped.')
            return
        try:command=self.message_command(True)
        except Exception as exc:self.note(f'Error: {exc}');return
        self.repeat_stop.clear();self.repeat.description='Stop broadcast'
        def run():
            try:
                while not self.repeat_stop.is_set() and not self.stop.is_set():
                    self.send(command,delay=0)
                    if self.repeat_stop.wait(2):break
            except Exception as exc:self.note(f'Broadcast stopped: {exc}')
            finally:self.repeat.description='Repeat broadcast'
        self.repeat_thread=threading.Thread(target=run,daemon=True);self.repeat_thread.start()

    def disconnect(self):
        self.stop.set();self.repeat_stop.set()
        for thread in (self.reader,self.repeat_thread):
            if thread and thread is not threading.current_thread():thread.join(timeout=3)
        if any(t and t.is_alive() for t in (self.reader,self.repeat_thread)):
            raise RuntimeError('Serial activity is still stopping; retry closing the connection.')
        with self.write_lock:
            if self.connection is not None:self.connection.close()
            self.connection=None
        self.repeat.description='Repeat broadcast'
        self.update_status('Disconnected')

    def close(self):
        self.closed=True;self.stop.set();self.repeat_stop.set()
        worker=self.worker
        if worker and worker is not threading.current_thread():worker.join(timeout=4)
        if worker and worker.is_alive():raise RuntimeError('A console action is still stopping.')
        self.disconnect()
        for button in [self.clear,self.led_switch,*self.actions]:button.disabled=True


class Console:
    def __init__(self, namespace):
        self.namespace=namespace
        self.boards={}
        self.general_log=VintageLog("General log", framed=False, height=120, show_title=False)
        self.original_stdout=getattr(sys.stdout,'_vlc_original_stdout',sys.stdout)
        self._vlc_original_stdout=self.original_stdout
        for label in ('A','B'):
            port=namespace.get('PORT_'+label)
            if port:self.boards[label]=Board(self,label,port)
        if not self.boards:self.boards['A']=Board(self,'A',None)
        for index, board in enumerate(self.boards.values()):
            board.widget.layout = w.Layout(flex='1 1 0%', min_width='0',
                margin='0 16px 0 0' if len(self.boards)==2 and index==0 else '0')
        badge=w.HTML(f'''<div style="display:flex;justify-content:flex-start;padding:0">
<span style="padding:5px 8px;border:1px solid #9da89d;border-radius:3px;background:repeating-linear-gradient(0deg,#ffffff09 0px,#ffffff09 1px,#00000008 1px,#00000008 2px),linear-gradient(115deg,#ede8d3,#c6c8b7 45%,#e1dfca 65%,#a7b0a3);box-shadow:1px 2px 3px #0008"><img alt="Lovefield" src="data:image/png;base64,{self.general_log.badge}" style="display:block;width:96px;height:auto"></span></div>''')
        panels=w.HBox([b.widget for b in self.boards.values()],layout=w.Layout(width='100%',gap='1%',align_items='stretch'))
        self.general_log.widget.layout = w.Layout(flex='1 1 0%', min_width='0')
        badge.layout = w.Layout(width='116px', height='auto', flex='0 0 auto', margin='0')
        label=w.HTML('<div style="color:#f2f0e5;font:700 10px Arial,sans-serif;letter-spacing:1.2px;text-transform:uppercase;padding:6px 0">General log</div>')
        self.clear_general=w.Button(description='Clear log',layout=w.Layout(width='110px'))
        self.clear_general.add_class('vlc-clear-key')
        self.clear_general.on_click(lambda _:self.general_log.clear())
        general_controls=w.VBox([label,self.clear_general])
        general_controls.add_class('vlc-general-controls')
        sidebar=w.VBox([general_controls,badge],layout=w.Layout(width='116px',flex='0 0 116px',margin='0 16px 0 0',justify_content='space-between'))
        footer=w.HBox([sidebar,self.general_log.widget],layout=w.Layout(width='100%',align_items='stretch',margin='10px 0 0'))
        footer.add_class('vlc-control-panel')
        self.performance=runpy.run_path(str(Path(__file__).with_name('performance_test.py')))['PerformanceTest'](self)
        case=w.VBox([panels,self.performance.widget,footer],layout=w.Layout(width='100%'))
        case.add_class('vlc-control-case')
        self.widget=w.VBox([w.HTML(STYLE),case],layout=w.Layout(width='100%',padding='16px 4px 12px'))
        self.widget.add_class('vlc-control-console')

    def send(self,label,command,**kwargs):
        if label not in self.boards:
            self.write(f'[{label}] No Arduino configured; send skipped.\n');return
        self.boards[label].send(command,**kwargs)

    def write(self,text):
        return self.general_log.write(text)

    def flush(self):pass

    def clear(self):
        self.general_log.clear()
        for board in self.boards.values():board.log.clear()

    def stop_capture(self):
        if sys.stdout is self:sys.stdout=self.original_stdout

    def close(self):
        self.performance.close()
        self.stop_capture()
        for board in self.boards.values():board.close()


def show_console(namespace):
    global serial
    previous=namespace.get('vlc_console')
    if previous is not None:previous.close()
    # Retire listeners from the former standalone setup, if it ran this session.
    event=namespace.get('stop_event')
    if event:event.set()
    threads=namespace.get('threads',[])
    for _,thread in threads:thread.join(timeout=3)
    if any(t.is_alive() for _,t in threads):raise RuntimeError('Old serial listeners are still stopping. Restart the kernel.')
    handles=[namespace.get('serA'),namespace.get('serB')]
    for name in ('serA_ref','serB_ref'):
        ref=namespace.get(name)
        if ref:handles.append(ref[0])
    for handle in {id(h):h for h in handles if h is not None}.values():
        if getattr(handle,'is_open',False):handle.close()
    namespace.pop('on_serial_line',None)  # A previous performance callback may send data.
    check = runpy.run_path(str(Path(__file__).with_name('check_serial_environment.py')))['check_serial_environment']
    detected = check(show=False)
    serial = detected['serial']
    namespace.update({key: detected[key] for key in ('serial', 'PORT_A', 'PORT_B')})
    console=Console(namespace)
    console.write(f"Python serial check passed. pySerial {getattr(serial, '__version__', 'Unknown')} is available.\n")
    console.write(detected['report'] + '\n')
    if detected['local_matches']:
        console.write('Local files to check for naming conflicts: ' + ', '.join(detected['local_matches']) + '\n')
    namespace.update(vlc_console=console,sendA=lambda command,**kw:console.send('A',command,**kw),
                     sendB=lambda command,**kw:console.send('B',command,**kw),
                     clear_log=console.clear,stop_capture=console.stop_capture)
    display(console.widget)
    sys.stdout=console
    for board in console.boards.values():
        if board.port.value.strip():board.launch(board.open_connection)
    return console
