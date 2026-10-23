"""Notebook fan switch using one short privileged command per click."""
import asyncio
from html import escape
import json
import time

FAN_STYLE = '''<style>
.pi-fan-field {padding:9px 10px!important;background:#0e1c13;border:1px solid #50664d;box-sizing:border-box;}
.pi-fan-field .widget-toggle-button {position:relative;width:42px!important;height:43px!important;
 padding-top:26px!important;margin:0!important;background:#253028!important;border:1px solid #87917d!important;
 font:9px 'Courier New',monospace!important;color:#c4d0b0!important;}
.pi-fan-field .widget-toggle-button:after {content:'';position:absolute;top:3px;left:15px;
 width:10px;height:24px;border-radius:5px;background:#0b130e;box-shadow:inset 0 1px 3px #000;}
.pi-fan-field .widget-toggle-button:before {content:'';position:absolute;top:15px;left:12px;z-index:1;
 width:16px;height:11px;border-radius:3px;background:linear-gradient(#eef0df,#909e93 48%,#d5dbca 55%,#697970);
 border:1px solid #afb6a1;box-shadow:0 2px 2px #080d08;transition:top .2s ease,box-shadow .2s ease;}
.pi-fan-field .widget-toggle-button.mod-active:before {top:3px;box-shadow:0 0 4px #dfca7c80;}
@media(prefers-reduced-motion:reduce){.pi-fan-field .widget-toggle-button:before {transition:none;}}
.pi-fan-field .widget-toggle-button.mod-active {color:#ffdea2!important;}
</style>'''


class FanControl:
    def __init__(self, client, on_event=None):
        import ipywidgets as widgets
        self.client = client
        self.on_event = on_event or (lambda message: None)
        self.reported_mode = None
        self.pending_mode = None
        self.pending_since = 0.0
        self.settle_until = 0.0
        self.closed = False
        self.updating = False
        self.task = None
        self.message_until = 0
        self.lock = asyncio.Lock()
        self.switch = widgets.ToggleButton(value=False, description='OFF',
                                           tooltip='Manual fan control; automatic cooling stays active',
                                           layout=widgets.Layout(width='42px',height='43px',flex='0 0 42px'))
        self.readout = widgets.HTML('<div class="pi-status-label">Fan (RPM)</div><div class="pi-status-value">Not reported</div>',
                                    layout=widgets.Layout(margin='0',flex='1',min_width='0'))
        self.message = widgets.HTML('', layout=widgets.Layout(margin='0',height='14px',min_height='14px',overflow='hidden'))
        row = widgets.HBox([self.readout, self.switch], layout=widgets.Layout(align_items='flex-start',justify_content='space-between'))
        self.widget = widgets.VBox([widgets.HTML(FAN_STYLE,layout=widgets.Layout(height='0',margin='0')),row,self.message],
                                   layout=widgets.Layout(width='auto',min_width='0',margin='0'))
        self.widget.add_class('pi-fan-field')
        self.widget.add_class('pi-readout-field')
        self.switch.observe(self._changed, names='value')

    def _send(self, mode):
        stdin, stdout, stderr = self.client.exec_command(
            'sudo -n -- /usr/local/libexec/mobilecomputing-pi-fan', timeout=12)
        try:
            stdin.write(json.dumps({'mode': mode}) + '\n')
            stdin.flush()
            stdin.channel.shutdown_write()
            output = stdout.read().decode()
            error = stderr.read().decode().strip()
            if stdout.channel.recv_exit_status():
                raise RuntimeError(error or 'Fan command failed')
            return json.loads(output)
        finally:
            stdin.close()
            stdout.close()
            stderr.close()

    def _message(self, text):
        self.message_until = time.monotonic() + 10
        self.message.value = (f'<div title="{escape(text, quote=True)}" '
                              'style="font:10px/14px Courier New;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                              f'{escape(text)}</div>') if text else ''

    def _show(self, result):
        self.updating = True
        try:
            self.switch.value = result['mode'] == 'ON'
            self.switch.description = 'ON' if self.switch.value else 'OFF'
        finally:
            self.updating = False
        if result.get('message'):
            self._message(result['message'])
        elif time.monotonic() >= self.message_until:
            self.message.value = ''

    def _log_stable_mode(self, mode):
        now = time.monotonic()
        if self.reported_mode is None:
            self.reported_mode = mode
        if now < self.settle_until or mode == self.reported_mode:
            self.pending_mode = None
            return
        if mode != self.pending_mode:
            self.pending_mode = mode
            self.pending_since = now
        elif now - self.pending_since >= 3.0:
            self.on_event(f"Fan {mode} (automatic control)")
            self.reported_mode = mode
            self.pending_mode = None

    def update_sample(self, fans):
        fan = fans[0] if fans else {}
        rpm = fan.get('rpm')
        value = f"{rpm:,}" if rpm is not None else 'Not reported'
        self.readout.value = '<div class="pi-status-label">Fan (RPM)</div>' + f'<div class="pi-status-value">{value}</div>'
        if not self.switch.disabled and fan.get("pwm") is not None:
            mode = 'ON' if fan['pwm'] > 0 else 'OFF'
            self._show({'mode': mode})
            self._log_stable_mode(mode)

    def _changed(self, change):
        if self.updating or self.closed:
            return
        self.switch.disabled = True
        self.task = asyncio.get_running_loop().create_task(self._set('ON' if change['new'] else 'OFF'))

    async def _set(self, mode):
        try:
            async with self.lock:
                self.message_until = 0
                self.message.value = ""
                result = await asyncio.to_thread(self._send, mode)
                self.reported_mode = result['mode']
                self.pending_mode = None
                self.settle_until = time.monotonic() + 3.0
                self._show(result)
                if result.get('message') or result['mode'] != mode:
                    detail = result.get('message') or 'automatic control'
                    self.on_event(f"Fan {mode} requested; remains {result['mode']} ({detail})")
                else:
                    self.on_event(f"Fan {mode} (manual switch)")
        except Exception as exc:
            self._message(str(exc))
            self.on_event(f"Fan {mode} request failed: {exc}")
        finally:
            self.switch.disabled = self.closed

    def close(self):
        self.closed = True
        if self.task:
            self.task.cancel()
        self.switch.disabled = True
