"""Run the same CPU worker locally and over SSH, then display both outcomes."""
from html import escape
import json
from pathlib import Path
import shlex
import subprocess
import sys


def run_benchmarks(hostname="raspberrypi.local", username="cas", pi_python="python3"):
    from IPython.display import HTML, display

    worker = Path(__file__).with_name("cpu_worker.py")
    source = worker.read_text(encoding="utf-8")
    results, rows = [], []
    for target in ("local", "pi"):
        print(f"Running CPU benchmark: {target}...", flush=True)
        try:
            if target == "local":
                completed = subprocess.run(
                    [sys.executable, str(worker)], capture_output=True,
                    text=True, timeout=300,
                )
                if completed.returncode:
                    raise RuntimeError(completed.stderr.strip() or "Local worker failed")
                raw = completed.stdout
            else:
                import paramiko

                client = paramiko.SSHClient()
                try:
                    client.load_system_host_keys()
                    client.connect(hostname=hostname, username=username,
                                   timeout=8, auth_timeout=15, banner_timeout=8)
                    command = shlex.quote(pi_python) + " -c " + shlex.quote(source)
                    stdin, stdout, stderr = client.exec_command(command, timeout=300)
                    stdin.close()
                    raw, error = stdout.read().decode(), stderr.read().decode()
                    status = stdout.channel.recv_exit_status()
                    stdout.close(); stderr.close()
                    if status:
                        raise RuntimeError(error.strip() or raw.strip() or "Pi worker failed")
                finally:
                    client.close()
            result = json.loads(raw)
            if not result.get("validated"):
                raise RuntimeError("Worker did not validate the numerical result")
            result["target"] = target
            results.append(result)
            ms = result["median_ms"]
            rows.append([target, result["hardware"], result["dtype"],
                         f"{result['n']} × {result['n']}",
                         ", ".join(str(v) for v in sorted({p["num_threads"] for p in result["threadpools"] if p.get("user_api") == "blas"})) or "Not reported", f"{ms:.3f}",
                         f"{1000 / ms:.2f}", f"{result['relative_error']:.2e}", "Passed"])
        except Exception as exc:
            rows.append([target, hostname if target == "pi" else "Notebook host",
                         "", "", "", "", "", "", f"{type(exc).__name__}: {exc}"])

    headers = ["Target", "Hardware", "Precision", "Matrix size", "BLAS threads", "Median time per matrix multiplication (ms)",
               "Matrix multiplications/s", "Relative error", "Status"]
    head = ''.join(f'<th style="font-weight:normal;text-align:left">{escape(h)}</th>'
                   for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td style="text-align:left">{escape(str(v))}</td>'
                                   for v in row) + '</tr>' for row in rows)
    display(HTML(f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'))
    return results
