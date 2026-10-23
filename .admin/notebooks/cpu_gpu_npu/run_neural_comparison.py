"""Run the matched ResNet-50 experiment and display a compact results table."""
from datetime import datetime
from html import escape
import json
from pathlib import Path
import shlex
import socket
import threading


def comparison_html(suite):
    results = suite['results']
    if len(results) != 4 or {r['implementation'] for r in results} != {'CPU: 1 core', 'CPU: 4 cores', 'GPU', 'NPU'}:
        raise ValueError('One-core CPU, four-core CPU, GPU, and NPU measurements are required')
    if len({(r['input_sha256'], r['model'], r['batch_size'], r['repetitions'], r['trials']) for r in results}) != 1:
        raise ValueError('All processors must use the same workload and input')
    headers = ['Processor', 'Runtime', 'Precision', 'Average inference time (ms)', 'Inferences/s', 'Top 3 classes (score)']
    rows = []
    for r in results:
        if not r['output_checks_passed'] or not 0 < r['average_ms'] < float('inf'):
            raise ValueError('Invalid inference result')
        values = [r['implementation'], r['runtime'], r['precision'], f"{r['average_ms']:.3f}",
                  f"{r['inferences_per_s']:.2f}"]
        predictions = '<br>'.join(f"{rank}. {escape(p['label'])} ({p['score']:.1%})"
                                  for rank, p in enumerate(r['top5'][:3], 1))
        rows.append('<tr>'+''.join(f'<td>{escape(v)}</td>' for v in values)+f'<td>{predictions}</td></tr>')
    return '<table><thead><tr>'+''.join(f'<th style="font-weight:normal;text-align:left">{h}</th>' for h in headers)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>'


def run_comparison(hostname='raspberrypi.local', username='cas', repetitions=3, show=True):
    import paramiko
    client = paramiko.SSHClient()
    folder = Path(__file__).resolve().parent
    sftp, directory = None, None
    def report(message):
        print(f'{datetime.now():%H:%M:%S}  {message}', flush=True)
    try:
        client.load_system_host_keys()
        client.connect(hostname=hostname, username=username, timeout=8, auth_timeout=15, banner_timeout=8)
        stdin, stdout, stderr = client.exec_command('mktemp -d /tmp/notebook-neural-XXXXXXXX',timeout=10)
        stdin.close()
        directory = stdout.read().decode().strip()
        if stdout.channel.recv_exit_status() or not directory.startswith('/tmp/notebook-neural-') or '\n' in directory:
            raise RuntimeError('Could not create temporary worker directory')
        stdout.close(); stderr.close()
        sftp = client.open_sftp()
        home = sftp.normalize('.')
        worker = directory+'/neural_comparison_worker.py'
        sftp.put(str(folder/'neural_comparison_worker.py'), worker)
        python = home+'/neural-comparison/venv/bin/python'
        report('Running matched ResNet-50 inference on CPU, GPU, and NPU')
        stdin, stdout, stderr = client.exec_command(shlex.join([python,'-u','-B',worker,'--repetitions',str(repetitions)]),timeout=600)
        stdin.close()
        diagnostics = []
        drain = threading.Thread(target=lambda: diagnostics.append(stderr.read().decode()), daemon=True)
        drain.start()
        suite = None
        try:
            for line in stdout:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    diagnostics.append(line)
                    continue
                if record.get('event') == 'progress':
                    report(record['message'])
                else:
                    suite = record
            status = stdout.channel.recv_exit_status()
            drain.join(timeout=10)
            if status or suite is None:
                raise RuntimeError('ResNet-50 comparison failed:\n'+''.join(diagnostics)[-6000:])
        finally:
            stdout.close(); stderr.close()
        html = comparison_html(suite)
        output_dir = folder/'results'
        output_dir.mkdir(exist_ok=True)
        stamp = suite['timestamp_utc'].replace(':','-').replace('+','_')
        result_path = output_dir/f'resnet50-comparison-{stamp}.json'
        suite['runtime_diagnostics'] = ''.join(diagnostics)
        result_path.write_text(json.dumps(suite,indent=2)+'\n')
        suite['saved_path'] = str(result_path)
        if show:
            from IPython.display import display, HTML
            display(HTML(html))
        return suite
    except socket.gaierror as exc:
        report(f"Cannot resolve Raspberry Pi hostname '{hostname}'. "
               "Connect the Pi to the same network and check its hostname, "
               "or set hostname to the Pi's IP address in this cell. "
               "No ResNet-50 benchmarks were run.")
        return {'status': 'unavailable', 'results': [], 'error': str(exc),
                'hostname': hostname}
    finally:
        if sftp is not None:
            try:sftp.remove(directory+'/neural_comparison_worker.py')
            except OSError:pass
            try:sftp.rmdir(directory)
            except OSError:pass
            sftp.close()
        client.close()
