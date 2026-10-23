"""Run the same prompt suite on Pi CPU, Vulkan GPU and Hailo NPU.

Models and runtimes must already be installed in ~/llm-comparison.
Only servers started by this worker are stopped. No CPU fallback is reported
as GPU inference. All client timings are measured on the Pi over loopback.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import statistics
import subprocess
import time
import urllib.error
import urllib.request

SYSTEM = "You are a helpful assistant."
MODEL = "qwen2:1.5b"
GGUF = "qwen2-1_5b-instruct-q4_0.gguf"


def progress(message):
    print(message, flush=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_text(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    return (result.stdout or result.stderr).strip()


def sensors():
    raw = command_text(["vcgencmd", "get_throttled"])
    flags = int(raw.split("=")[-1], 16) if "=" in raw else None
    return {"temperature_c": float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000,
            "throttling_flags": flags,
            "current_flags": flags & 15 if flags is not None else None}


def wait_for_cooling(limit=72, timeout=240):
    deadline = time.monotonic() + timeout
    while True:
        state = sensors()
        if state["temperature_c"] <= limit and state["current_flags"] == 0:
            return state
        if time.monotonic() > deadline:
            raise RuntimeError(f"Pi did not cool sufficiently for benchmarking: {state}")
        progress(f"Cooling: {state['temperature_c']:.1f} C; waiting before timing.")
        time.sleep(10)


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fetch(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


@contextmanager
def server(backend, root, log_path):
    port = available_port()
    environment = dict(os.environ)
    environment["OMP_NUM_THREADS"] = "4"
    if backend == "NPU":
        environment["HAILO_MONITOR"] = "1"
        # Version 5.1.1 uses XDG configuration rather than OLLAMA_HOST.
        config = root / "config" / "hailo-ollama"
        config.mkdir(parents=True, exist_ok=True)
        (config / "hailo-ollama.json").write_text(json.dumps({
            "server": {"host": "127.0.0.1", "port": port},
            "library": {"host": "dev-public.hailo.ai", "port": 443},
            "main_poll_time_ms": 200}))
        environment["XDG_CONFIG_HOME"] = str(config.parent)
        args = ["hailo-ollama"]
        health = "/api/version"
    else:
        environment["VK_DRIVER_FILES"] = "/usr/share/vulkan/icd.d/broadcom_icd.json"
        args = [str(root / "llama.cpp/build/bin/llama-server"),
                "-m", str(root / "models" / GGUF), "--host", "127.0.0.1",
                "--port", str(port), "-c", "2048", "-t", "4", "-tb", "4",
                "-np", "1", "-b", "128", "-ub", "128",
                "-lv", "5",
                "-ngl", "99" if backend == "GPU" else "0",
                "--device", "Vulkan0" if backend == "GPU" else "none"]
        health = "/health"
    with open(log_path, "w") as log:
        process = subprocess.Popen(args, stdout=log, stderr=log, env=environment)
        try:
            start = time.perf_counter()
            url = f"http://127.0.0.1:{port}"
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{backend} server exited ({process.returncode}). "
                                       + log_path.read_text(errors="replace")[-3500:])
                try:
                    fetch(url + health)
                    break
                except (OSError, ValueError):
                    if time.perf_counter() - start > 180:
                        raise RuntimeError(f"{backend} server startup timed out; see {log_path}")
                    time.sleep(0.5)
            if backend == "GPU":
                evidence = log_path.read_text(errors="replace")
                offload = re.search(r"offloaded (\d+)/(\d+) layers", evidence)
                if "Vulkan0" not in evidence or offload is None or int(offload[1]) == 0:
                    raise RuntimeError("GPU offload was not confirmed in the server log")
            yield url, time.perf_counter() - start
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def request(backend, url, prompt, max_tokens, timeout=300):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    if backend == "NPU":
        path = "/api/chat"
        payload = {"model": MODEL, "messages": messages, "stream": True,
                   "options": {"temperature": 0, "seed": 42, "num_predict": max_tokens,
                               "frequency_penalty": 1.0}}
    else:
        # Explicit ChatML matches the installed Hailo Qwen2 manifest exactly.
        formatted = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n"
                            for m in messages) + "<|im_start|>assistant\n"
        path = "/completion"
        payload = {"prompt": formatted, "stream": True, "n_predict": max_tokens,
                   "temperature": 0, "seed": 42, "repeat_penalty": 1.0,
                   "frequency_penalty": 0, "presence_penalty": 0,
                   "cache_prompt": False, "stop": ["<|im_end|>", "<|endoftext|>"]}
    req = urllib.request.Request(url + path, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    start = time.perf_counter()
    first = None
    pieces = []
    final = None
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for raw in response:
            if time.perf_counter() - start > timeout:
                raise TimeoutError(f"Generation exceeded the {timeout}-second request limit")
            line = raw.decode().strip()
            if not line or line == "data: [DONE]":
                continue
            if backend != "NPU" and not line.startswith("data: "):
                # SSE comments/keepalives can arrive during slow GPU prefill.
                continue
            if line.startswith("data: "):
                line = line[6:]
            event = json.loads(line)
            if "error" in event:
                raise RuntimeError(str(event["error"]))
            content = event.get("message", {}).get("content", "") if backend == "NPU" else event.get("content", "")
            if content:
                if first is None:
                    first = time.perf_counter()
                pieces.append(content)
            if event.get("done") or event.get("stop"):
                final = event
    end = time.perf_counter()
    if first is None or final is None:
        raise RuntimeError("Incomplete response or no generated text")
    tokens = final.get("eval_count") if backend == "NPU" else final.get("tokens_predicted")
    if not isinstance(tokens, int) or tokens <= 0:
        raise RuntimeError("Runtime did not report a positive output token count")
    return {"text": "".join(pieces), "output_tokens": tokens,
            "time_to_first_text_s": first - start, "total_s": end - start,
            "tokens_per_s_including_prompt": tokens / (end - start),
            "runtime_final": final}


def run(root, prompts, repetitions=1, max_tokens=64, backends=("CPU", "GPU", "NPU"), gpu_repetitions=1):
    root = Path(root).expanduser().resolve()
    (root / "logs").mkdir(parents=True, exist_ok=True)
    gguf = root / "models" / GGUF
    manifest = json.loads(Path("/usr/share/hailo-ollama/models/manifests/qwen2/1.5b/manifest.json").read_text())
    hef = Path("/usr/share/hailo-ollama/models/blob") / ("sha256_" + manifest["hef_h10h"])
    result = {"model": "Qwen2-1.5B-Instruct", "repetitions": repetitions,
              "gpu_repetitions": gpu_repetitions,
              "max_output_tokens": max_tokens, "system_prompt": SYSTEM,
              "prompts": prompts, "host": socket.gethostname(),
              "llama_revision": command_text(["git", "-C", str(root / "llama.cpp"), "rev-parse", "HEAD"]),
              "gguf_sha256": sha256(gguf), "hef_sha256": sha256(hef),
              "hailo_version": command_text(["dpkg-query", "-W", "-f=${Version}", "hailo-gen-ai-model-zoo"]),
              "backends": [], "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for backend in backends:
        backend_repetitions = gpu_repetitions if backend == "GPU" else repetitions
        row = {"processor": backend, "status": "unavailable", "runs": [],
               "repetitions": backend_repetitions,
               "log": str(root / "logs" / f"llm-{backend.lower()}.log")}
        result["backends"].append(row)
        progress(f"Starting {backend}: {len(prompts)} prompts × {backend_repetitions} repetitions.")
        try:
            row["sensors_before"] = wait_for_cooling()
            with server(backend, root, Path(row["log"])) as (url, startup_s):
                row["server_startup_s"] = startup_s
                # Keep answer correctness separate from successful execution.
                warmup = request(backend, url, "What is 2 + 2? Return only the number.", 16)
                row["warmup"] = warmup
                row["warmup_answer_correct"] = bool(re.fullmatch(r"\s*4[.!]?\s*", warmup["text"]))
                if not row["warmup_answer_correct"]:
                    progress(f"{backend}: warm-up answer was {warmup['text']!r}; expected 4. "
                             "The failed answer check will remain visible with the measurements.")
                for repetition in range(backend_repetitions):
                    for item in prompts:
                        wait_for_cooling(limit=75)
                        progress(f"{backend}: repetition {repetition + 1}/{backend_repetitions}, {item['id']}")
                        print(f"\n{backend} | Prompt: {item['prompt']}", flush=True)
                        response = request(backend, url, item["prompt"], max_tokens)
                        print(f"Response: {response['text']}\n"
                              f"Response time: {response['total_s']:.3f} s | "
                              f"Output tokens: {response['output_tokens']}\n", flush=True)
                        row["runs"].append({"prompt_id": item["id"], "repetition": repetition + 1,
                                            **response, "sensors_after": sensors()})
                row["status"] = "completed"
                row["median_first_text_s"] = statistics.median(r["time_to_first_text_s"] for r in row["runs"])
                row["median_total_s"] = statistics.median(r["total_s"] for r in row["runs"])
                row["aggregate_tokens_per_s"] = sum(r["output_tokens"] for r in row["runs"]) / sum(r["total_s"] for r in row["runs"])
                row["current_throttling_observed"] = any(r["sensors_after"]["current_flags"] != 0 for r in row["runs"])
        except Exception as exc:
            row["status"] = "incomplete" if row["runs"] else "unavailable"
            row["error"] = str(exc)
            progress(f"{backend}: {row['status']}: {str(exc)[-400:]}")
        (root / "llm-results.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="~/llm-comparison")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--gpu-repetitions", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--backends", nargs="+", choices=["CPU", "GPU", "NPU"], default=["CPU", "GPU", "NPU"])
    args = parser.parse_args()
    if args.repetitions < 1 or args.gpu_repetitions < 1 or not 1 <= args.max_tokens <= 256:
        parser.error("Use positive repetitions and 1 to 256 output tokens")
    prompts = json.loads(Path(__file__).with_name("llm_prompts.json").read_text())
    output = run(args.root, prompts, args.repetitions, args.max_tokens, args.backends, args.gpu_repetitions)
    print("LLM_RESULT_JSON=" + json.dumps(output), flush=True)
