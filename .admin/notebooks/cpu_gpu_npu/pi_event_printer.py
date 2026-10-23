"""Fixed-size paper log, printed by a background thread without JavaScript."""
from collections import deque
from datetime import datetime
from html import escape
import queue
import threading


def render_paper(lines):
    body = ''.join(f'<div class="pi-event-line">{escape(line) or "&nbsp;"}</div>' for line in lines[-10:])
    return ('<style>.pi-event-paper{height:194px;box-sizing:border-box;}'
            '.pi-event-window{height:140px;overflow:hidden;}'
            '.pi-event-text{max-height:140px;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end;}'
            '.pi-event-line{flex:0 0 auto;min-height:14px;white-space:pre-wrap;overflow-wrap:anywhere;font:9px/14px "Courier New",monospace;}'
            '</style><div class="pi-printer-paper pi-event-paper">'
            '<div class="pi-printer-title">EQUIPMENT / EVENT LOG</div>'
            '<div class="pi-event-window" role="log" aria-label="Pi event log"><div class="pi-event-text">' + body + '</div></div></div>')


class EventPrinter:
    def __init__(self, rows=(), character_interval=0.022):
        import ipywidgets as widgets
        self.widget = widgets.HTML(render_paper([]), layout=widgets.Layout(margin='0', overflow='visible'))
        self.history = deque(maxlen=500)
        self.lines = deque(maxlen=10)
        self.pending = queue.Queue()
        self.stopped = threading.Event()
        self.character_interval = character_interval
        for component, value in rows:
            self.write(f'{component:<12} {value}', timestamp=False)
        self.thread = threading.Thread(target=self._print, name='pi-event-printer', daemon=True)
        self.thread.start()

    def write(self, message, timestamp=True):
        if self.stopped.is_set():
            return
        stamp = datetime.now().strftime('%H:%M:%S')
        line = f'{stamp}  {message}' if timestamp else message
        self.history.append(line)
        self.pending.put(line)

    def _print(self):
        while not self.stopped.is_set():
            try:
                message = self.pending.get(timeout=0.2)
            except queue.Empty:
                continue
            for line in [message]:
                self.lines.append('')
                self.widget.value = render_paper(list(self.lines))
                for i in range(1, len(line) + 1):
                    if self.stopped.wait(self.character_interval):
                        return
                    self.lines[-1] = line[:i]
                    self.widget.value = render_paper(list(self.lines))
            self.pending.task_done()

    def close(self):
        self.stopped.set()
