"""Live notebook widget backed by a verified SSH connection."""
import asyncio
import base64
from datetime import datetime
from html import escape
import json
import math
from pathlib import Path
import shlex
import threading
import time

CONSOLE_STYLE = """<style>
.cell-output-ipywidget-background:has(.pi-status-console) {background:transparent!important;}
.pi-dashboard-host,.pi-status-console,.pi-status-console > .widget-html {background:transparent!important;}
.pi-status-console {padding:0;color:#c4d0b0;max-width:980px;overflow:visible!important;
 font-family:'Courier New',monospace;font-weight:normal;}
.pi-console-case {position:relative;padding:6px 12px 8px;border:8px solid #6d7868;border-radius:10px;
 background:linear-gradient(115deg,#354134,#1c2b21 45%,#283728);
 box-shadow:inset 0 0 0 2px #121d15,inset 0 3px 7px #0008,0 2px 0 #a2a48a,0 5px 8px #0005;}
.pi-console-case:before {content:'';position:absolute;inset:-5px;pointer-events:none;border-radius:6px;
 background:radial-gradient(circle at 3px 3px,#d0ceae 1px,#525e50 2px,#242e26 3px,transparent 4px),
 radial-gradient(circle at calc(100% - 3px) 3px,#d0ceae 1px,#525e50 2px,#242e26 3px,transparent 4px),
 radial-gradient(circle at 3px calc(100% - 3px),#d0ceae 1px,#525e50 2px,#242e26 3px,transparent 4px),
 radial-gradient(circle at calc(100% - 3px) calc(100% - 3px),#d0ceae 1px,#525e50 2px,#242e26 3px,transparent 4px);}
.pi-status-console .widget-html {min-height:0;overflow:visible;}
.pi-status-console .widget-html-content {background:transparent!important;width:100%;box-sizing:border-box;}
.pi-readout-row {display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;}
.pi-readout-field {min-height:82px!important;height:100%;padding:9px 10px!important;box-sizing:border-box;}
.pi-readout-field .pi-status-label {line-height:14px;margin-bottom:3px;}
.pi-readout-field .pi-status-value {font-size:18px;line-height:24px;}
.pi-readout-field .pi-status-detail {font-size:10px;line-height:14px;margin-top:3px;white-space:normal;}
@media(max-width:650px){.pi-readout-row {grid-template-columns:repeat(2,minmax(0,1fr));}}
.pi-console-status {font:10px/14px 'Courier New',monospace;}
.pi-status-console .widget-button,.pi-status-console .widget-toggle-button {
 background:#62695b!important;color:#f1eddc!important;border:1px solid #91957f!important;
 border-radius:2px!important;box-shadow:inset 0 -2px #353c33;font:11px 'Courier New',monospace!important;}
.pi-status-console .widget-label {font:11px 'Courier New',monospace;color:#c4d0b0!important;}
.pi-status-console select {background:#27372c!important;color:#d2dec0!important;
 border:1px solid #65755f!important;font:11px 'Courier New',monospace!important;}
.pi-status-console .widget-html-content {font-family:'Courier New',monospace;}
.pi-status-readouts {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;}
.pi-status-gauges {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-bottom:5px;}
.pi-status-gauge {text-align:center;position:relative;display:grid;grid-template-columns:minmax(0,1fr) 25px;column-gap:7px;align-items:start;}
.pi-status-gauge > .pi-load-lamp {position:relative;top:auto;right:auto;grid-column:2;grid-row:1;margin-top:6px;justify-self:center;}
.pi-load-lamp {position:absolute;top:9px;right:9px;width:21px;height:21px;box-sizing:border-box;border-radius:50%;
 border:1px solid #687b73;background:linear-gradient(135deg,#87938d,#f0f3e9 18%,#87988f 36%,#d8dfd3 60%,#6d8078 83%,#cbd3c6);
 box-shadow:0 1px 3px #000,inset 0 0 0 1px #edf0df;}
.pi-load-lamp:after {content:'';position:absolute;inset:3px;border-radius:50%;border:1px solid #58352b;
 background:radial-gradient(circle at 35% 30%,#70352d,#401811 65%,#240c09);box-shadow:inset 0 0 3px #000;}
.pi-load-lamp-on:after {background:radial-gradient(circle at 35% 30%,#ffbc83,#ee3821 42%,#a61c10 78%);
 box-shadow:0 0 9px #f33c24aa,inset 0 0 2px #ffe6aa;}
.pi-status-gauge svg {display:block;width:100%;height:auto;grid-column:1;grid-row:1;background:transparent!important;}
.pi-status-panel {position:relative;padding:5px 8px;min-height:62px;box-sizing:border-box;border:1px solid #50664d;
 background:repeating-linear-gradient(0deg,#0e1c1300,#0e1c1300 2px,#050a071a 2px,#050a071a 3px),#0e1c13;}
.pi-status-label {font-size:10px;line-height:12px;letter-spacing:1px;text-transform:uppercase;color:#a5b397;}
.pi-status-value {font-size:16px;line-height:21px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
 color:#c1efa6;text-shadow:0 0 4px #8ecb8033;font-weight:normal;}
.pi-status-detail {font-size:9px;line-height:11px;color:#94a88c;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pi-printer-row {gap:12px;padding-top:5px;height:58px;overflow:visible!important;}
.pi-printer-row > .pi-brand-badge {flex:0 0 98px;text-align:right;}
.pi-lovefield-label {display:inline-block;margin:5px 0 0;padding:4px 6px;
 background:repeating-linear-gradient(0deg,#ffffff09 0px,#ffffff09 1px,#00000008 1px,#00000008 2px),linear-gradient(115deg,#ede8d3,#c6c8b7 45%,#e1dfca 65%,#a7b0a3);
 border:1px solid #9da89d;border-radius:3px;box-shadow:1px 2px 3px #0008,inset 0 0 0 1px #ffffff80;}
.pi-lovefield-label img {display:block;width:82px;height:auto;}
.pi-inline-paper .pi-printer-paper {margin:0 0 18px;}
.pi-printer-column {flex:1 1 0;min-width:0;overflow:visible!important;}
@media(max-width:650px){.pi-printer-row{gap:6px;}.pi-printer-row > .pi-brand-badge{flex-basis:86px;}
 .pi-lovefield-label{padding:4px;}.pi-lovefield-label img{width:76px;}}
.pi-printer-slot {height:7px;margin:5px 0 0;background:#060b08;border-top:2px solid #65705e;
 border-bottom:1px solid #98a38a;border-radius:3px;box-shadow:inset 0 2px 3px #000;}
.pi-printer-paper {position:relative;margin:-16px 36px 18px;padding:12px 22px 18px;z-index:1;color:#34382e;
 background:repeating-linear-gradient(0deg,#ede9d700,#ede9d700 29px,#9a99891a 29px,#9a99891a 30px),#ede9d7;
 border-bottom:1px dashed #9b9a85;box-shadow:2px 3px 4px #0005;font:10px/13px 'Courier New',monospace;}
.pi-printer-paper:before,.pi-printer-paper:after {content:'';position:absolute;top:4px;bottom:4px;width:10px;
 background:radial-gradient(circle,#263029 2px,transparent 2.8px) center top/10px 15px repeat-y;}
.pi-printer-paper:before {left:3px;border-right:1px dashed #bbb8a3;}
.pi-printer-paper:after {right:3px;border-left:1px dashed #bbb8a3;}
.pi-printer-title {font-size:9px;letter-spacing:1px;border-bottom:1px dashed #969983;padding-bottom:3px;margin-bottom:3px;}
.pi-printer-paper table {width:100%;border-collapse:collapse;background:transparent!important;color:#34382e!important;
 font:10px/13px 'Courier New',monospace!important;}
.pi-printer-paper td,.pi-printer-paper th {background:transparent!important;color:#34382e!important;
 border:0!important;padding:1px 4px!important;text-align:left!important;font-weight:normal!important;}
.pi-printer-paper th {text-transform:uppercase;border-bottom:1px dotted #999b87!important;font-size:9px;}
.pi-printer-paper td:first-child {width:95px;white-space:nowrap;}
@media(max-width:650px){.pi-status-readouts {grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>"""


def render_gauge(title, value, detail, previous_value=None, warning_on=None):
    def percent(text):
        if text and text.endswith("%"):
            try:
                return min(100, max(0, float(text[:-1])))
            except ValueError:
                pass
        return None
    current = percent(value)
    previous = percent(previous_value)
    gauge_id = title.lower().replace(" ", "-")
    face_colors = ("#fff3bf", "#ecdc9a", "#b9a969") if current is not None else ("#aaa68a", "#8c8c71", "#555e4d")
    face_light = f'filter="url(#{gauge_id}-backlight)"' if current is not None else ""
    face_label = "LOAD %" if current is not None else "LOAD % · NO SIGNAL"
    parts = [f'''<defs>
      <linearGradient id="{gauge_id}-metal" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#87938d"/><stop offset=".18" stop-color="#f0f3e9"/>
        <stop offset=".36" stop-color="#87988f"/><stop offset=".60" stop-color="#d8dfd3"/>
        <stop offset=".83" stop-color="#6d8078"/><stop offset="1" stop-color="#cbd3c6"/>
      </linearGradient>
      <radialGradient id="{gauge_id}-face" cx=".46" cy=".38" r=".65">
        <stop offset="0" stop-color="{face_colors[0]}"/><stop offset=".75" stop-color="{face_colors[1]}"/>
        <stop offset="1" stop-color="{face_colors[2]}"/>
      </radialGradient>
      <filter id="{gauge_id}-backlight"><feDropShadow dx="0" dy="0" stdDeviation="2.3" flood-color="#ffe59a" flood-opacity=".6"/></filter>
      <filter id="{gauge_id}-shadow"><feDropShadow dx="1" dy="2" stdDeviation="1.2" flood-opacity=".3"/></filter>
      </defs>
      <rect x="4" y="6" width="232" height="119" rx="14" fill="url(#{gauge_id}-metal)" stroke="#687b73"/>
      <rect x="7" y="9" width="226" height="113" rx="12" fill="none" stroke="#edf0df" stroke-width="1.5"/>
      <rect x="11" y="13" width="218" height="105" rx="10" fill="none" stroke="#70867b" stroke-width="2"/>
      <rect x="14" y="16" width="212" height="99" rx="8" fill="url(#{gauge_id}-face)" stroke="#b7af86" stroke-width="2" {face_light}/>
      <path d="M 22 21 H 216" fill="none" stroke="#fffde4" stroke-opacity=".3" stroke-width="3"/>
      <g transform="translate(30 0)">
    ''']
    def dial_point(radius, degrees):
        radians = math.radians(degrees)
        return 90 + radius * math.sin(radians), 80 - radius * math.cos(radians)
    outer_start = dial_point(46, 36)
    outer_end = dial_point(46, 60)
    inner_end = dial_point(28, 60)
    inner_start = dial_point(28, 36)
    parts.append(f'<path d="M {outer_start[0]:.2f} {outer_start[1]:.2f} '
                 f'A 46 46 0 0 1 {outer_end[0]:.2f} {outer_end[1]:.2f} '
                 f'L {inner_end[0]:.2f} {inner_end[1]:.2f} '
                 f'A 28 28 0 0 0 {inner_start[0]:.2f} {inner_start[1]:.2f} Z" '
                 'fill="#be4739" fill-opacity=".22"/>')
    parts.append(f'<path d="M {outer_start[0]:.2f} {outer_start[1]:.2f} '
                 f'A 46 46 0 0 1 {outer_end[0]:.2f} {outer_end[1]:.2f}" '
                 'fill="none" stroke="#a52d27" stroke-width="2"/>')
    for tick in range(21):
        angle = math.radians(-60 + 120 * tick / 20)
        major = tick % 5 == 0
        inner = 30 if major else 35
        x1, y1 = 90 + inner * math.sin(angle), 80 - inner * math.cos(angle)
        x2, y2 = 90 + 41 * math.sin(angle), 80 - 41 * math.cos(angle)
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{'#a52d27' if tick >= 16 else '#263329'}" stroke-width="{2 if major else 1}"/>')
        if major:
            tx, ty = 90 + 58 * math.sin(angle), 80 - 58 * math.cos(angle) + 10.5
            parts.append(f'<text x="{tx:.2f}" y="{ty:.2f}" fill="{'#a52d27' if tick == 20 else '#263329'}" text-anchor="middle" font-size="8">{tick*5}</text>')
    parts.append(f'<text x="90" y="66" text-anchor="middle" fill="#263329" font-size="11">{escape(title.split()[0])}</text>')
    needle_value = current if current is not None else 0
    angle = -60 + 120 * needle_value / 100
    start_value = previous if previous is not None and current is not None else needle_value
    start = -60 + 120 * start_value / 100
    duration = 0.18 if needle_value > start_value else 2.5
    parts.append(f'<g class="pi-gauge-needle" transform="rotate({angle:.2f} 90 80)" filter="url(#{gauge_id}-shadow)">'
                 '<path d="M 89 34 L 88 76 L 86.5 94 Q 90 97 93.5 94 L 92 76 Z" fill="#b61922" stroke="#87131a" stroke-width=".6"/>'
                 f'<animateTransform attributeName="transform" type="rotate" from="{start:.2f} 90 80" to="{angle:.2f} 90 80" dur="{duration}s" calcMode="spline" keyTimes="0;1" keySplines="0.333333 0.666667 0.666667 1" fill="freeze"/></g>')
    parts.extend(['<circle cx="90" cy="80" r="6.5" fill="#b61922" stroke="#901821" stroke-width="1"/>',
                  '<path d="M 86 77 Q 90 74 94 78" fill="none" stroke="#d96357" stroke-opacity=".65"/>',
                  f'<text x="90" y="109" text-anchor="middle" fill="#4a513b" font-size="6.5" letter-spacing="1">{face_label}</text></g>'])
    if current is None:
        parts.append('<rect x="14" y="16" width="212" height="99" rx="8" fill="#101711" opacity=".22"/>')
    hot = (current is not None and current > 80) if warning_on is None else warning_on
    lamp_state = "on" if hot else "off"
    lamp_label = "Load warning on (10-second hold)" if hot else "Load alarm off" if current is not None else "Load alarm unavailable"
    lamp = (f'<span class="pi-load-lamp pi-load-lamp-{lamp_state}" role="img" '
            f'aria-label="{lamp_label}" title="{lamp_label}"></span>')
    return (f'<div class="pi-status-panel pi-status-gauge" title="{escape(detail, quote=True)}">'
            + lamp + f'<svg viewBox="0 0 240 132" role="img" aria-label="{escape(title + ": " + value, quote=True)}" '
            'style="font-family:Arial,sans-serif;font-weight:normal;">' + ''.join(parts) + '</svg></div>')


def readout_lamp(title, value, warning_on=None):
    try:
        reading = float(value.split()[0].rstrip("%"))
    except (ValueError, IndexError):
        reading = None
    threshold = 75 if title in ("Storage", "Memory") else 80
    triggered = reading is not None and (reading >= threshold if threshold == 75 else reading > threshold)
    hot = triggered if warning_on is None else warning_on
    state = "on" if hot else "off"
    condition = "75% usage or higher" if threshold == 75 else "above 80 °C"
    label = (f"{title} warning on (10-second hold)" if hot else
             f"{title} warning: {condition}" if reading is not None else f"{title} unavailable")
    return (f'<span class="pi-load-lamp pi-load-lamp-{state}" role="img" '
            f'aria-label="{label}" title="{label}"></span>')


def render_readout(title, value, detail, warning_on=None):
    return (f'<div class="pi-status-panel pi-readout-field" title="{escape(detail, quote=True)}">'
            + (readout_lamp(title, value, warning_on) if title in ("Temperature", "Storage", "Memory") else "")
            + f'<div class="pi-status-label">{escape(title)}</div>'
            f'<div class="pi-status-value">{escape(value)}</div>'
            f'<div class="pi-status-detail">{escape(detail)}</div></div>')


def render_cards(cards, previous_cards=(), warning_states=None):
    warning_states = warning_states or {}
    loads = {"CPU load", "GPU load", "NPU load"}
    old = {title: value for title, value, _ in previous_cards}
    gauges = '<div class="pi-status-gauges">' + ''.join(
        render_gauge(title, value, detail, old.get(title), warning_states.get(title)) for title, value, detail in cards if title in loads) + '</div>'
    count = sum(title not in loads for title, _, _ in cards)
    if not any(title in loads for title, _, _ in cards):
        gauges = ""
    return CONSOLE_STYLE + gauges + f'<div class="pi-status-readouts" style="grid-template-columns:repeat({max(1,count)},minmax(0,1fr))">' + "".join(
        f'<div class="pi-status-panel" title="{escape(detail, quote=True)}">'
        + (readout_lamp(title, value, warning_states.get(title)) if title in ("Temperature", "Storage", "Memory") else "")
        + f'<div class="pi-status-label">{escape(title)}</div>'
        f'<div class="pi-status-value" title="{escape(value, quote=True)}">{escape(value)}</div>'
        f'<div class="pi-status-detail">{escape(detail)}</div></div>'
        for title, value, detail in cards if title not in loads) + "</div>"


def unavailable_cards(detail="Waiting for the first reading"):
    return [(title, "Not reported", detail) for title in
            ("CPU load", "GPU load", "NPU load", "Temperature", "Storage", "Memory", "Fan (RPM)")]


def render_brand_badge():
    logo_path = Path(__file__).with_name("img") / "lovefield-logo-transparent.png"
    logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return ('<div class="pi-lovefield-label"><img src="data:image/png;base64,'
            + logo + '" alt="Lovefield" /></div>')


def render_inventory_log(rows, include_slot=True):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    delay = 0.3
    lines = []
    for component, value in rows:
        text = f"{component:<12} {value}"
        letters = ''.join(
            f'<span style="animation-delay:{delay + 0.2 + i * 0.022:.3f}s">{escape(char)}</span>'
            for i, char in enumerate(text))
        lines.append(f'<div class="pi-print-line" style="animation-delay:{delay:.3f}s">'
                     f'<div>{letters}</div></div>')
        delay += 0.35 + len(text) * 0.022
    return (('<div class="pi-printer-slot"></div>' if include_slot else '') +
            '<style>@keyframes pi-paper-feed{to{grid-template-rows:1fr}}'
            '@keyframes pi-print-letter{to{visibility:visible}}'
            '.pi-print-line{display:grid;grid-template-rows:0fr;animation:pi-paper-feed .2s ease-out forwards;}'
            '.pi-print-line>div{min-height:0;overflow:hidden;white-space:pre-wrap;font:11px/18px "Courier New",monospace;}'
            '.pi-print-line span{visibility:hidden;animation:pi-print-letter 0s forwards;}'
            '@media(prefers-reduced-motion:reduce){.pi-print-line{grid-template-rows:1fr;animation:none;}'
            '.pi-print-line span{visibility:visible;animation:none;}}</style>'
            '<div class="pi-printer-paper">'
            f'<div class="pi-printer-title">EQUIPMENT LOG / {stamp}</div>'
            + ''.join(lines) + '</div>')


def summarize(sample, previous=None):
    cards = []
    temperature = sample.get("temperature_c")
    cards.append(("Temperature", f"{temperature:.1f} °C" if temperature is not None else "Not reported", "Pi SoC"))
    disk = sample["storage"]
    cards.append(("Storage", f"{100*disk['used']/disk['total']:.1f}%",
                  f"{disk['free']/10**9:.1f} / {disk['total']/10**9:.1f} GByte free"))
    memory = sample["memory"]
    cards.append(("Memory", f"{100*(1-memory['MemAvailable']/memory['MemTotal']):.1f}%",
                  f"{memory['MemAvailable']/10**9:.1f} GByte available"))
    cpu = None
    engines = {}
    if previous and sample["monotonic"] > previous["monotonic"]:
        ticks = [a-b for a, b in zip(sample["cpu_ticks"], previous["cpu_ticks"])]
        if sum(ticks) > 0 and all(t >= 0 for t in ticks):
            cpu = 100 * (1 - (ticks[3] + ticks[4]) / sum(ticks))
        elapsed_ns = (sample["monotonic"] - previous["monotonic"]) * 1e9
        for client, values in sample["gpu_clients"].items():
            old = previous["gpu_clients"].get(client)
            if old is None:
                continue
            for engine, busy in values.items():
                if engine in old and busy >= old[engine]:
                    engines[engine] = engines.get(engine, 0) + 100 * (busy - old[engine]) / elapsed_ns
    cards.append(("CPU load", f"{cpu:.1f}%" if cpu is not None else "Sampling…",
                  f"Across {sample['cpu_count']} logical CPUs"))
    gpu_value = f"{min(100, engines['csd']):.1f}%" if "csd" in engines else "Sampling…" if sample["gpu_clients"] else "Not reported"
    gpu_detail = "Compute engine; visible V3D clients"
    if "render" in engines:
        gpu_detail += f"; render {min(100, engines['render']):.1f}%"
    cards.append(("GPU load", gpu_value, gpu_detail))
    npu = sample["npu"]
    npu_detail = npu["detail"]
    if sample["npu_clients"]:
        npu_detail += " Device open by " + ", ".join(p["name"] or str(p["pid"]) for p in sample["npu_clients"])
    cards.append(("NPU load", f"{npu['percent']:.1f}%" if npu["percent"] is not None else "Not reported", npu_detail))
    fans = sample["fans"]
    if fans and fans[0]["rpm"] is not None:
        fan = fans[0]
        label = f"{fan['rpm']:,}"
        detail = fan["name"] or "Fan tachometer"
        if fan["pwm"] is not None:
            detail += f"; PWM command {100*fan['pwm']/255:.0f}%"
    else:
        label, detail = "Not reported", "No readable fan tachometer"
    cards.append(("Fan (RPM)", label, detail))
    return cards


class PiStatusMonitor:
    def __init__(self, client, hostname, inventory_rows=(), show=True):
        import ipywidgets as widgets
        from IPython.display import display
        self.client = client
        self.hostname = hostname
        self.previous = None
        self.previous_cards = []
        self.needle_motion = {}
        self.latest = None
        self.closed = False
        self.interval = 1
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.source = Path(__file__).with_name("pi_status_worker.py").read_text()
        self.status = widgets.HTML("", layout=widgets.Layout(margin="0",display="none"))
        self.status.add_class("pi-console-status")
        initial = unavailable_cards()
        self.cards = widgets.HTML(render_cards([c for c in initial if c[0].endswith("load")]),layout=widgets.Layout(margin="0"))
        self.readouts = {title: widgets.HTML(render_readout(title, value, detail),
                         layout=widgets.Layout(width="auto",min_width="0",margin="0"))
                         for title, value, detail in initial if title in ("Temperature", "Storage", "Memory")}
        import runpy
        fan_module = runpy.run_path(str(Path(__file__).with_name("pi_fan_control.py")))
        printer_module = runpy.run_path(str(Path(__file__).with_name("pi_event_printer.py")))
        self.event_printer = printer_module["EventPrinter"](inventory_rows)
        self.warning_states = {}
        self.warning_hold_until = {}
        self.fan_control = fan_module["FanControl"](client, on_event=self.event_printer.write)
        readout_row = widgets.GridBox([*self.readouts.values(), self.fan_control.widget],
                                      layout=widgets.Layout(align_items="stretch",margin="0"))
        readout_row.add_class("pi-readout-row")
        self.paper_log = self.event_printer.widget
        badge = widgets.HTML(render_brand_badge(), layout=widgets.Layout(margin="0"))
        badge.add_class("pi-brand-badge")
        slot = widgets.HTML('<div class="pi-printer-slot"></div>',layout=widgets.Layout(margin="0",width="100%"))
        self.paper_log.add_class("pi-inline-paper")
        printer_column = widgets.VBox([slot, self.paper_log], layout=widgets.Layout(margin="0",gap="0",overflow="visible"))
        printer_column.add_class("pi-printer-column")
        printer_row = widgets.HBox([printer_column, badge], layout=widgets.Layout(margin="0",align_items="flex-start",height="58px",overflow="visible"))
        printer_row.add_class("pi-printer-row")
        self.enclosure = widgets.VBox([self.status, self.cards, readout_row, printer_row],layout=widgets.Layout(gap="2px",overflow="visible"))
        self.enclosure.add_class("pi-console-case")
        paper_clearance = widgets.Box(layout=widgets.Layout(height="160px",flex="0 0 160px"))
        self.widget = widgets.VBox([self.enclosure, paper_clearance],layout=widgets.Layout(gap="0",margin="14px 0 0 0",padding="0",overflow="visible"))
        self.widget.add_class("pi-status-console")
        if show:
            display(self.widget)
        self.thread = threading.Thread(target=self._poll, name="pi-status-monitor", daemon=True)
        self.thread.start()

    def _fetch(self):
        command = "python3 -c " + shlex.quote(self.source)
        stdin, stdout, stderr = self.client.exec_command(command, timeout=10)
        stdin.close()
        try:
            output, error = stdout.read().decode(), stderr.read().decode()
            if stdout.channel.recv_exit_status():
                raise RuntimeError(error.strip() or "Status request failed")
            return json.loads(output)
        finally:
            stdout.close()
            stderr.close()

    def _log_warning_changes(self, cards):
        now = time.monotonic()
        for title, value, _ in cards:
            if title not in ("CPU load", "GPU load", "NPU load", "Temperature", "Storage", "Memory"):
                continue
            available = value.endswith("%") or value.endswith("°C")
            reading = float(value.split()[0].rstrip("%")) if available else None
            above_threshold = available and (reading >= 75 if title in ("Storage", "Memory") else reading > 80)
            if above_threshold:
                self.warning_hold_until[title] = now + 10.0
            on = above_threshold or now < self.warning_hold_until.get(title, 0.0)
            previous = self.warning_states.get(title, False)
            self.warning_states[title] = on
            if on and not previous:
                name = title.replace(" load", "")
                detail = value if available else "no signal"
                self.event_printer.write(f"{name} warning light ON ({detail})")

    def _needle_starts(self, cards):
        """Continue from the visible needle position when a new sample arrives."""
        now = time.monotonic()
        starts = []
        for title, value, detail in cards:
            if not title.endswith("load"):
                continue
            if not value.endswith("%"):
                self.needle_motion.pop(title, None)
                continue
            target = min(100, max(0, float(value[:-1])))
            motion = self.needle_motion.get(title)
            position = 0.0
            if motion is not None:
                elapsed = min(1.0, max(0.0, (now - motion["time"]) / motion["duration"]))
                # Same quadratic ease-out as the SVG spline with linear x.
                eased = 1 - (1 - elapsed) ** 2
                position = motion["start"] + (motion["target"] - motion["start"]) * eased
            duration = 0.18 if target > position else 2.5
            self.needle_motion[title] = {"start": position, "target": target,
                                         "time": now, "duration": duration}
            starts.append((title, f"{position:.6f}%", detail))
        return starts

    async def update(self):
        await asyncio.to_thread(self._update_sync)

    def _update_sync(self):
        if self.closed or not self.lock.acquire(blocking=False):
            return
        try:
            sample = self._fetch()
            if self.closed:
                return
            cards = summarize(sample, self.previous)
            self.latest = sample
            self.previous = sample
            self._log_warning_changes(cards)
            self.cards.value = render_cards([c for c in cards if c[0].endswith("load")], self._needle_starts(cards), self.warning_states)
            for title, value, detail in cards:
                if title in self.readouts:
                    self.readouts[title].value = render_readout(title, value, detail, self.warning_states.get(title))
            self.fan_control.update_sample(sample["fans"])
            self.previous_cards = cards
            self.status.value = ""
            self.status.layout.display = "none"
        except Exception as exc:
            if not self.closed:
                self.status.layout.display = ""
                self.status.value = f"Status unavailable: {escape(str(exc))}. Last readings are stale. Rerun the cell to reconnect."
        finally:
            self.lock.release()

    def _poll(self):
        while not self.stop_event.is_set():
            start = time.monotonic()
            self._update_sync()
            self.stop_event.wait(max(0.1, self.interval - (time.monotonic() - start)))

    def close(self):
        self.closed = True
        self.stop_event.set()
        self.fan_control.close()
        self.event_printer.close()
        self.client.close()
        self.status.value = "Disconnected. Rerun the cell to reconnect."
