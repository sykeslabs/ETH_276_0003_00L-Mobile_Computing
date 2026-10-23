"""Notebook entry point for the remote Qwen2 prompt experiment."""
from html import escape
import json
from pathlib import Path
import shlex
import socket


def show_results(result):
    from IPython.display import HTML, display
    headers = ["Processor", "Status", "Responses", "Median first text (s)",
               "Median response (s)", "Tokens/s incl. prompt", "Warm-up answer", "Thermal flags"]
    rows = []
    for row in result["backends"]:
        complete = row["status"] == "completed"
        values = [row["processor"], row["status"], len(row["runs"]),
                  f"{row['median_first_text_s']:.3f}" if complete else "Unavailable",
                  f"{row['median_total_s']:.3f}" if complete else "Unavailable",
                  f"{row['aggregate_tokens_per_s']:.2f}" if complete else "Unavailable",
                  ("Correct" if row["warmup_answer_correct"] else "Incorrect; inspect answers") if complete else "Unavailable",
                  ("Observed" if row["current_throttling_observed"] else "None during sampled checks") if complete else "Unavailable"]
        rows.append("<tr>" + "".join(f"<td>{escape(str(x))}</td>" for x in values) + "</tr>")
    head = "".join(f'<th style="font-weight:normal">{escape(h)}</th>' for h in headers)
    display(HTML(f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"))
    for row in result["backends"]:
        if row.get("error"):
            display(HTML(f"<details><summary>{escape(row['processor'])}: diagnostic</summary>"
                         f"<pre>{escape(row['error'])}</pre></details>"))
    for row in result["backends"]:
        if row.get("validation_note"):
            display(HTML(f"<p>{escape(row['processor'])}: {escape(row['validation_note'])}</p>"))


def prompt_responses_html(result):
    blocks = []
    if result.get("system_prompt"):
        blocks.append('<p>Shared system prompt</p><div style="white-space:pre-wrap">'
                      + escape(result["system_prompt"]) + '</div>')
    for index, prompt in enumerate(result["prompts"], 1):
        rows = []
        for backend in result["backends"]:
            run = next((r for r in backend["runs"]
                        if r["prompt_id"] == prompt["id"] and r["repetition"] == 1), None)
            if run is None:
                values = [backend["processor"], "Unavailable", "Unavailable",
                          "No measured response in repetition 1."]
            else:
                values = [backend["processor"], f"{run['total_s']:.3f}",
                          str(run["output_tokens"]), run["text"]]
            rows.append('<tr>' + ''.join(
                '<td style="vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere">'
                + escape(str(value)) + '</td>' for value in values) + '</tr>')
        blocks.append(f'<details open><summary>Prompt {index}: {escape(prompt["task"])}</summary>'
                      '<p style="white-space:pre-wrap">' + escape(prompt["prompt"]) + '</p>'
                      '<table style="width:100%;table-layout:fixed"><thead><tr>'
                      '<th style="font-weight:normal;width:12%">Processor</th>'
                      '<th style="font-weight:normal;width:14%">Response time (s)</th>'
                      '<th style="font-weight:normal;width:12%">Output tokens</th>'
                      '<th style="font-weight:normal">Response</th></tr></thead><tbody>'
                      + ''.join(rows) + '</tbody></table></details>')
    return '\n'.join(blocks)


def run_benchmarks(hostname="raspberrypi.local", username="cas", repetitions=1, max_tokens=64,
                   backends=("CPU", "GPU", "NPU"), gpu_repetitions=1):
    import paramiko
    if repetitions < 1 or gpu_repetitions < 1 or not 1 <= max_tokens <= 256 or not set(backends) <= {"CPU", "GPU", "NPU"}:
        raise ValueError("Check repetitions, max_tokens (1 to 256), and backend names")
    folder = Path(__file__).resolve().parent
    client = paramiko.SSHClient()
    try:
        client.load_system_host_keys()
        client.connect(hostname, username=username, timeout=10,
                       auth_timeout=15, banner_timeout=10)
        with client.open_sftp() as sftp:
            home = sftp.normalize(".")
            remote = home + "/llm-comparison"
            for name in ("llm_worker.py", "llm_prompts.json"):
                sftp.put(str(folder / name), remote + "/" + name)
        command = shlex.join(["python3", "-u", remote + "/llm_worker.py", "--root", remote,
                              "--repetitions", str(repetitions), "--max-tokens", str(max_tokens),
                              "--gpu-repetitions", str(gpu_repetitions),
                              "--backends", *backends])
        stdin, stdout, stderr = client.exec_command(command, timeout=7200)
        stdin.close()
        result = None
        try:
            for line in stdout:
                if line.startswith("LLM_RESULT_JSON="):
                    result = json.loads(line.split("=", 1)[1])
                else:
                    print(line, end="", flush=True)
            error = stderr.read().decode()
            status = stdout.channel.recv_exit_status()
            if status or result is None:
                raise RuntimeError(error[-3000:] or "No benchmark result returned")
        finally:
            stdout.close()
            stderr.close()
        show_results(result)
        return result
    except socket.gaierror as exc:
        print(f"Cannot resolve Raspberry Pi hostname '{hostname}'. "
              "Connect the Pi to the same network and check its hostname, "
              "or set hostname to the Pi's IP address in this cell. "
              "No Qwen2 benchmarks were run.", flush=True)
        return {'status': 'unavailable', 'backends': [], 'error': str(exc),
                'hostname': hostname}
    finally:
        client.close()
