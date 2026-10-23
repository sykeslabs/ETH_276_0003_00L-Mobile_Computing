"""Run and present all five matrix implementations on the Raspberry Pi."""
from datetime import datetime
from html import escape
import json
from pathlib import Path
import shlex
import socket


def comparison_html(suite):
    results = suite['results']
    if len(results) != 5 or len({(r['host'], r['n'], r['dtype'], r['input_sha256'], r['boundary'],
                                 r['repetitions'], len(r['trial_s'])) for r in results}) != 1:
        raise ValueError('Five matching Pi measurements are required')
    expected = {'CPU tiled C++ / 1 thread', 'CPU tiled C++ / 4 threads', 'CPU NumPy/BLAS / 4 threads', 'GPU tiled Vulkan', 'GPU untiled Vulkan'}
    if {r['implementation'] for r in results} != expected:
        raise ValueError('All five distinct implementations are required')
    baseline = next(r['median_ms'] for r in results if r['implementation'] == 'CPU tiled C++ / 1 thread')
    time_heading = ('Average' if suite['trials'] == 1 else 'Median') + ' time per matrix multiplication (ms)'
    headers = ['Pi implementation', time_heading,
               'Matrix multiplications/s', 'Speedup over one CPU thread', 'Temperature before / after (°C)']
    rows = []
    for r in results:
        if not r['validated'] or not 0 < r['median_ms'] < float('inf'):
            raise ValueError('Validated positive measurements required')
        values = [r['implementation'], f"{r['median_ms']:.3f}", f"{1000/r['median_ms']:.2f}",
                  f"{baseline/r['median_ms']:.2f}×",
                  f"{r['health_before']['temperature_c']:.1f} / {r['health_after']['temperature_c']:.1f}"]
        name, separator, threads = values[0].rpartition(' / ')
        label = (escape(name) + '<br>' + escape(threads)
                 if separator and threads in ('1 thread', '4 threads') else escape(values[0]))
        rows.append('<tr><td>'+label+'</td>'+''.join(f'<td>{escape(v)}</td>' for v in values[1:])+'</tr>')
    head = ''.join(f'<th style="font-weight:normal;text-align:left">{escape(h)}</th>' for h in headers)
    return '<table><thead><tr>'+head+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>'


def run_comparison(hostname='raspberrypi.local', username='cas', pi_python='python3',
                   n=512, repetitions=3, trials=1, show=True, on_progress=None):
    import paramiko
    names = ['matrix_comparison_worker.py', 'cpu_tiled_matmul.cpp', 'cpu_worker.py',
             'gpu_worker.py', 'gpu_matmul.cpp', 'matmul.comp', 'matmul_untiled.comp']
    folder = Path(__file__).resolve().parent
    def report(message):
        print(f"{datetime.now():%H:%M:%S}  {message}", flush=True)
        if on_progress is not None:
            on_progress(message)

    client = paramiko.SSHClient()
    directory = None
    sftp = None
    try:
        client.load_system_host_keys()
        client.connect(hostname=hostname, username=username, timeout=8, auth_timeout=15, banner_timeout=8)
        def remote(command, timeout=1800, progress=False):
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            stdin.close()
            try:
                if progress:
                    chunks = []
                    for line in stdout:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            chunks.append(line)
                            continue
                        if record.get('event') == 'progress':
                            report(record['message'])
                        else:
                            chunks.append(line)
                    output = ''.join(chunks)
                else:
                    output = stdout.read().decode()
                error = stderr.read().decode()
                if stdout.channel.recv_exit_status():
                    raise RuntimeError(error.strip() or output.strip() or 'Pi benchmark failed')
                return output
            finally:
                stdout.close(); stderr.close()
        directory = remote('mktemp -d /tmp/notebook-matrix-XXXXXXXX').strip()
        if not directory.startswith('/tmp/notebook-matrix-') or '\n' in directory:
            raise RuntimeError('Unexpected temporary directory')
        sftp = client.open_sftp()
        for name in names:
            sftp.put(str(folder/name), directory+'/'+name)
        report('Running five Pi implementations; preparation is outside timing')
        suite = json.loads(remote(shlex.join([pi_python, '-B', directory+'/matrix_comparison_worker.py',
                                             '--n', str(n), '--repetitions', str(repetitions), '--trials', str(trials)]), progress=True))
        html = comparison_html(suite)
        results_dir = folder/'results'
        results_dir.mkdir(exist_ok=True)
        stamp = suite['timestamp_utc'].replace(':','-').replace('+','_')
        output = results_dir/f'matrix-five-implementations-{stamp}.json'
        output.write_text(json.dumps(suite, indent=2)+'\n')
        suite['saved_path'] = str(output)
        if show:
            from IPython.display import HTML, display
            display(HTML(html))
        return suite
    except socket.gaierror as exc:
        message = (f"Cannot resolve Raspberry Pi hostname '{hostname}'. "
                   "Connect the Pi to the same network and check its hostname, "
                   "or set hostname to the Pi's IP address in this cell. "
                   "No matrix benchmarks were run.")
        report(message)
        return {'status': 'unavailable', 'results': [], 'error': str(exc),
                'hostname': hostname}
    except Exception as exc:
        report(f"Matrix comparison stopped: {exc}")
        raise
    finally:
        if sftp is not None:
            for name in names:
                try:sftp.remove(directory+'/'+name)
                except OSError:pass
            try:sftp.rmdir(directory)
            except OSError:pass
            sftp.close()
        client.close()
