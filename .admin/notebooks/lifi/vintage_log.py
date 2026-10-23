"""Vintage VLC log console, using the Lovefield badge from notebook 05.xx."""
import base64
from collections import deque
from html import escape
from pathlib import Path
import sys
import threading

import ipywidgets as widgets
from IPython.display import display


class VintageLog:
    def __init__(self, title='VLC Networking', max_lines=400, framed=True, height=300, show_title=True):
        self.lines = deque(maxlen=max_lines)
        self.partial = ''
        self.lock = threading.RLock()
        self.title = title
        self.framed = framed
        self.height = height
        self.show_title = show_title
        badge = Path(__file__).resolve().parent.parent / 'cpu_gpu_npu/img/lovefield-logo-transparent.png'
        self.badge = base64.b64encode(badge.read_bytes()).decode('ascii')
        self.widget = widgets.HTML(layout=widgets.Layout(width='100%'))
        self.widget.add_class('vlc-vintage-log')
        previous = sys.stdout
        # Re-running the cell replaces the console without nesting capture sinks.
        self.original_stdout = getattr(previous, '_vlc_original_stdout', previous)
        self._vlc_original_stdout = self.original_stdout
        self._render()

    def _screen(self, text):
        return f'''<div style="padding:7px;border:1px solid #687b73;border-radius:17px;background:linear-gradient(135deg,#87938d,#f0f3e9 18%,#87988f 36%,#d8dfd3 60%,#6d8078 83%,#cbd3c6);box-shadow:0 3px 5px #0009,inset 0 0 0 1px #edf0df,inset 0 0 0 3px #a4b0a0">
<div style="position:relative;overflow:hidden;border:2px solid #526455;border-radius:11px;background:#07150e;box-shadow:0 0 0 1px #e0e4d0,inset 0 0 20px #000">
<div role="log" aria-label="{escape(self.title)}" style="height:{self.height}px;overflow:auto;display:flex;flex-direction:column-reverse;padding:12px;box-sizing:border-box;scrollbar-color:#576d4b #0b1b12;background:radial-gradient(ellipse at 48% 40%,#203b25 0%,#102719 58%,#07150e 100%)">
<pre style="margin:0;flex-shrink:0;white-space:pre-wrap;overflow-wrap:anywhere;color:#c3e6a1;text-shadow:0 0 3px #a2dc7770,0 0 8px #6da84835;font:10px/1.4 'Courier New',monospace">{escape(text)}</pre>
</div>
<div aria-hidden="true" style="position:absolute;inset:0;pointer-events:none;border-radius:9px;background:repeating-linear-gradient(0deg,#0000 0px,#0000 2px,#00000025 2px,#00000025 3px),linear-gradient(125deg,#e4f6d810 0%,#ffffff03 32%,#0000 48%);box-shadow:inset 0 0 24px #0009,inset 0 2px 3px #dcecc022"></div>
</div></div>'''

    def _render(self):
        text = '\n'.join(list(self.lines) + ([self.partial] if self.partial else []))
        heading = (f'<div style="color:#f2f0e5;font:700 10px Arial,sans-serif;letter-spacing:1.2px;margin:0 0 7px;text-transform:uppercase">{escape(self.title)}</div>' if self.show_title else '')
        if not self.framed:
            self.widget.value = f'''<div style="padding:6px 0;background:transparent">
{heading}
{self._screen(text)}
</div>'''
            return
        screws = ''.join(f'<span style="position:absolute;{v}:3px;{h}:3px;width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 30% 25%,#d7d9bd,#586450 55%,#162017);box-shadow:1px 1px 2px #000"></span>' for v in ('top','bottom') for h in ('left','right'))
        self.widget.value = f'''<style>
.vlc-vintage-log, .vlc-vintage-log .widget-html-content,
.cell-output-ipywidget-background:has(.vlc-vintage-log),
.jp-OutputArea-output:has(.vlc-vintage-log),
.widget-subarea:has(.vlc-vintage-log) {{background:transparent!important;}}
</style><div style="padding:16px 4px 12px;background:transparent">
<div style="position:relative;padding:18px;border:8px solid #6d7868;border-radius:12px;background:linear-gradient(115deg,#354134,#1c2b21 45%,#283728);box-shadow:inset 0 0 0 2px #162218,0 4px 6px #0005;color:#b8cf9f;font-family:'Courier New',monospace">
{screws}
<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:14px">
<span style="font-size:13px;letter-spacing:2px;text-transform:uppercase">{escape(self.title)}</span>
<span style="padding:5px 8px;border:1px solid #9da89d;border-radius:3px;background:repeating-linear-gradient(0deg,#ffffff09 0px,#ffffff09 1px,#00000008 1px,#00000008 2px),linear-gradient(115deg,#ede8d3,#c6c8b7 45%,#e1dfca 65%,#a7b0a3);box-shadow:1px 2px 3px #0008,inset 0 0 0 1px #ffffff80"><img alt="Lovefield" src="data:image/png;base64,{self.badge}" style="display:block;width:96px;height:auto"></span>
</div>
{self._screen(text)}
</div></div>'''

    def write(self, text):
        if not text:
            return 0
        with self.lock:
            for char in text:
                if char == '\r':
                    self.partial = ''
                elif char == '\n':
                    self.lines.append(self.partial)
                    self.partial = ''
                else:
                    self.partial += char
            self._render()
        return len(text)

    def flush(self):
        pass

    def clear(self):
        with self.lock:
            self.lines.clear()
            self.partial = ''
            self._render()

    def stop_capture(self):
        if sys.stdout is self:
            sys.stdout = self.original_stdout


def show_log(title='VLC Networking'):
    console = VintageLog(title)
    display(console.widget)
    sys.stdout = console
    print(title + ':')
    return console
