"""Hardware inventory and compact results table for notebook section 3.1."""
from IPython.display import display

def connect_pi(raspberry_pi_conf, use_password=False, password=None):
    import getpass
    import paramiko
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    # Unknown or changed hosts are rejected; establish trust in a terminal first.
    if use_password and password is None:
        account = f"{raspberry_pi_conf['username']}@{raspberry_pi_conf['hostname']}"
        password = getpass.getpass(f"SSH password for {account}: ")
    try:
        client.connect(**raspberry_pi_conf, password=password,
                       timeout=8, auth_timeout=15, banner_timeout=8)
    except Exception:
        client.close()
        raise
    return client

def remote_text(client, command, timeout=30):
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    stdin.close()
    output, error = stdout.read().decode(), stderr.read().decode()
    status = stdout.channel.recv_exit_status()
    stdout.close()
    stderr.close()
    if status:
        raise RuntimeError(f"Remote exit {status}: {error or output}")
    return output

import re
from html import escape
from IPython.display import HTML

# Raw command results remain available for troubleshooting.

def inventory_summary(inventory):
    def value(key):
        item = inventory[key]
        return item['output'].strip() if item['error'] is None else ''

    model = value('model') or 'Board model unavailable'
    cpu = value('cpu')
    cores = re.search(r'^CPU\(s\):\s*(\d+)', cpu, re.M)
    name = re.search(r'^Model name:\s*(.+)', cpu, re.M)
    cpu_result = model
    if cores and name:
        cpu_result += f", {cores[1]} {name[1].strip()} cores"
    else:
        cpu_result += '; CPU details unavailable'

    vulkan = value('gpu')
    devices = re.split(r'GPU\d+:', vulkan)[1:]
    hardware = [d for d in devices if re.search(
        r'deviceType\s*=\s*PHYSICAL_DEVICE_TYPE_(INTEGRATED|DISCRETE)_GPU', d)]
    gpu_result = 'Hardware GPU not confirmed'
    if any('V3DV' in d for d in hardware):
        gpu_result = 'Hardware GPU detected through the V3DV Vulkan driver'
    elif hardware:
        gpu_result = 'Hardware GPU detected through Vulkan'
    elif 'llvmpipe' in vulkan:
        gpu_result = 'Only CPU software rendering detected (llvmpipe)'
    elif inventory['gpu']['error']:
        gpu_result = 'Vulkan check unavailable or failed'

    hailo_lines = [line for line in value('pcie').splitlines() if 'hailo' in line.lower()]
    npu_result = ('Hailo-10H detected on PCIe' if any('Hailo-10H' in line for line in hailo_lines)
                  else 'Hailo device detected on PCIe' if hailo_lines
                  else 'No Hailo device reported on PCIe')
    if inventory['pcie']['error']:
        npu_result = 'PCIe check unavailable or failed'
    runtime = ('Hailo runtime responded' if value('runtime')
               else 'Hailo runtime unavailable or identification failed')

    match = re.search(r'throttled=(0x[0-9a-fA-F]+)', value('throttling'))
    throttling = 'Throttling status unavailable'
    if match:
        flag = match[1]
        throttling = flag + (': no throttling flags reported' if int(flag, 16) == 0
                             else ': current or historical power/thermal flags reported')
    return [('CPU', cpu_result), ('GPU', gpu_result), ('NPU', npu_result),
            ('NPU runtime', runtime), ('Throttling', throttling)]


def run_checks(hostname="raspberrypi.local", username="cas", use_password=False, live_status=False, connected_client=None, show=True):
    import importlib.util
    if importlib.util.find_spec("paramiko") is None:
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "paramiko"], check=True)
    if live_status and importlib.util.find_spec("ipywidgets") is None:
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "ipywidgets"], check=True)
    raspberry_pi_conf = {"hostname": hostname, "username": username}
    pi_inventory = {}
    commands = {
        'model': "tr -d '\\000' < /proc/device-tree/model",
        'cpu': 'LC_ALL=C lscpu',
        'pcie': 'lspci -nn',
        'runtime': 'hailortcli fw-control identify',
        'gpu': 'vulkaninfo --summary',
        'throttling': 'vcgencmd get_throttled',
    }
    client = None
    try:
        client = connected_client if connected_client is not None else connect_pi(raspberry_pi_conf, use_password)
        address = client.get_transport().getpeername()[0]
        rows = [('Connection', f"{raspberry_pi_conf['hostname']} ({address}); SSH works")]
        for key, command in commands.items():
            try:
                pi_inventory[key] = {'output': remote_text(client, command), 'error': None}
            except Exception as exc:
                pi_inventory[key] = {'output': '', 'error': str(exc)}
        rows.extend(inventory_summary(pi_inventory))
    except Exception as exc:
        if client is not None:
            client.close()
            client = None
        rows = [('Connection', f'{type(exc).__name__}: {exc}'),
                ('Hardware checks', 'Not run because SSH connection failed')]
    table_rows = ''.join(
        f'<tr><td style="text-align:left">{escape(component)}</td>'
        f'<td style="text-align:left">{escape(result)}</td></tr>'
        for component, result in rows)
    if live_status:
        monitor = None
        import runpy
        from pathlib import Path
        module = runpy.run_path(str(Path(__file__).with_name("pi_status_widget.py")))
        if client is not None:
            try:
                monitor = module["PiStatusMonitor"](client, hostname, rows, show=show)
            except Exception:
                client.close()
                raise
        else:
            display(HTML(module["CONSOLE_STYLE"] + '<div class="pi-status-console">' +
                         '<div class="pi-console-case">' +
                         '<div>PI TELEMETRY / CONNECTION UNAVAILABLE</div>' +
                         module["render_cards"](module["unavailable_cards"]("SSH connection unavailable")) +
                         '<div class="pi-printer-row" style="display:flex;align-items:flex-start">' +
                         '<div class="pi-printer-column pi-inline-paper">' +
                         module["render_inventory_log"](rows) + '</div>' +
                         '<div class="pi-brand-badge">' + module["render_brand_badge"]() +
                         '</div></div></div><div style="height:160px"></div></div>'))
        return pi_inventory, monitor
    display(HTML('<table><thead><tr><th style="text-align:left;font-weight:normal">Component</th>'
                 '<th style="text-align:left;font-weight:normal">Result</th></tr></thead>'
                 f'<tbody>{table_rows}</tbody></table>'))
    if client is not None:
        client.close()
    return pi_inventory


if __name__ == "__main__":
    previous_login = globals().get("pi_login")
    previous_monitor = globals().get("pi_monitor")
    if previous_login is not None:
        previous_login.close()
    if previous_monitor is not None:
        previous_monitor.close()
    pi_login = None
    pi_inventory, pi_monitor = run_checks(use_password=False, live_status=True)
