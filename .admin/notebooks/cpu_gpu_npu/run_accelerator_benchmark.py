"""Upload a self-contained accelerator worker and run it on the Raspberry Pi."""
from html import escape
import json
from pathlib import Path
import posixpath
import shlex


def run_benchmark(kind, hostname='raspberrypi.local', username='cas', pi_python='python3'):
    import paramiko
    from IPython.display import HTML, display

    if kind not in ('gpu', 'npu'):
        raise ValueError('Choose gpu or npu')
    names = ['gpu_worker.py', 'gpu_matmul.cpp', 'matmul.comp'] if kind == 'gpu' else ['npu_worker.py']
    folder = Path(__file__).resolve().parent
    sources = {name: (folder/name).read_bytes() for name in names}
    account = f'{username}@{hostname}'
    client = paramiko.SSHClient()
    remote_dir = None
    sftp = None
    try:
        client.load_system_host_keys()
        client.connect(hostname=hostname, username=username,
                       timeout=8, auth_timeout=15, banner_timeout=8)
        def remote(command, timeout=600):
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            stdin.close()
            output, error = stdout.read().decode(), stderr.read().decode()
            status = stdout.channel.recv_exit_status()
            stdout.close(); stderr.close()
            if status:
                raise RuntimeError(error.strip() or output.strip() or 'Remote command failed')
            return output
        remote_dir = remote('mktemp -d /tmp/notebook-accelerator-XXXXXXXX').strip()
        if not remote_dir.startswith('/tmp/notebook-accelerator-') or '\n' in remote_dir:
            raise RuntimeError('Unexpected remote working directory')
        sftp = client.open_sftp()
        for name, data in sources.items():
            with sftp.file(posixpath.join(remote_dir, name), 'wb') as f:
                f.write(data)
        print(f'Running {kind.upper()} benchmark on the Pi; compilation and setup are outside timing...', flush=True)
        worker = posixpath.join(remote_dir, names[0])
        result = json.loads(remote(shlex.quote(pi_python)+' '+shlex.quote(worker)))
        rate = 1000/result['median_ms']
        if kind == 'gpu':
            headers = ['Processor', 'Device', 'Matrix', 'Median time per matrix multiplication (ms)', 'Matrix multiplications/s', 'Relative error']
            values = ['GPU', result['device_metadata']['device'], f"{result['n']} × {result['n']}",
                      f"{result['median_ms']:.3f}", f'{rate:.2f}', f"{result['relative_error']:.2e}"]
        else:
            headers = ['Processor', 'Model', 'Input', 'Median ms/inference', 'Inferences/s', 'Output checks']
            values = ['NPU', result['model'], '224 × 224 × 3, UINT8', f"{result['median_ms']:.3f}",
                      f'{rate:.2f}', 'Passed; model accuracy not assessed']
        head = ''.join(f'<th style="font-weight:normal;text-align:left">{escape(h)}</th>' for h in headers)
        body = ''.join(f'<td style="text-align:left">{escape(str(v))}</td>' for v in values)
        display(HTML(f'<table><thead><tr>{head}</tr></thead><tbody><tr>{body}</tr></tbody></table>'))
        return result
    finally:
        if sftp is not None:
            # Remove only the files created by this invocation.
            for name in names:
                try:
                    sftp.remove(posixpath.join(remote_dir, name))
                except OSError:
                    pass
            try:
                sftp.rmdir(remote_dir)
            except OSError:
                pass
            sftp.close()
        client.close()
