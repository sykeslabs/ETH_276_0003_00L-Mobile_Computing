"""Five implementations of the same FP32 matrix multiplication on one Pi."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time

import numpy as np
from threadpoolctl import threadpool_limits
from cpu_worker import cpu_benchmark
from gpu_worker import gpu_benchmark


def progress(message):
    print(json.dumps({"event": "progress", "message": message}), flush=True)


def health():
    path = Path('/sys/class/thermal/thermal_zone0/temp')
    command = subprocess.run(['vcgencmd', 'get_throttled'], capture_output=True, text=True, timeout=5)
    return {'temperature_c': int(path.read_text()) / 1000,
            'throttling': command.stdout.strip()}


def run_suite(n=512, repetitions=3, trials=1):
    if not 1 <= n <= 4096 or repetitions < 1 or trials < 1:
        raise ValueError('Positive configuration required, with n <= 4096')
    folder = Path(__file__).resolve().parent
    progress(f"Preparing identical {n} × {n} FP32 inputs and the validation reference")
    rng = np.random.default_rng(42)
    a = rng.uniform(-1, 1, (n, n)).astype(np.float32)
    b = rng.uniform(-1, 1, (n, n)).astype(np.float32)
    digest = hashlib.sha256(a.tobytes() + b.tobytes()).hexdigest()
    with threadpool_limits(limits=4, user_api='blas'):
        reference = a.astype(np.float64) @ b.astype(np.float64)
    results = []
    with tempfile.TemporaryDirectory(prefix='pi-tiled-cpu-') as directory:
        temp = Path(directory)
        binary = temp / 'cpu_tiled_matmul'
        flags = ['-O3', '-march=native', '-std=c++17', '-fopenmp', '-ffp-contract=fast']
        progress('Compiling tiled C++ CPU worker')
        subprocess.run(['g++', *flags, str(folder/'cpu_tiled_matmul.cpp'), '-o', str(binary)],
                       check=True, capture_output=True, text=True, timeout=120)
        compiler = subprocess.check_output(['g++', '--version'], text=True).splitlines()[0]
        a.tofile(temp/'a.bin'); b.tofile(temp/'b.bin')
        for kind, label in [('one', 'CPU tiled C++ / 1 thread'), ('four', 'CPU tiled C++ / 4 threads'),
                            ('blas', 'CPU NumPy/BLAS / 4 threads'), ('gpu', 'GPU tiled Vulkan'), ('gpu_untiled', 'GPU untiled Vulkan')]:
            # Bring each implementation to a similar starting temperature where possible.
            wait_started = time.monotonic()
            before = health()
            if before['temperature_c'] > 65:
                progress(f"Cooling before {label}: {before['temperature_c']:.1f} °C (up to 10 s)")
            next_notice = wait_started + 10
            while before['temperature_c'] > 65 and time.monotonic()-wait_started < 10:
                time.sleep(min(2, max(0, 10 - (time.monotonic() - wait_started))))
                before = health()
                if time.monotonic() >= next_notice:
                    progress(f"Cooling: {before['temperature_c']:.1f} °C; {time.monotonic()-wait_started:.0f} s elapsed")
                    next_notice += 10
            cooldown = time.monotonic() - wait_started
            timing_description = (f"1 timed trial of {repetitions} matrix multiplications" if trials == 1
                                  else f"{trials} timed trials of {repetitions} matrix multiplications each")
            progress(f"Starting {label}: 1 warm-up, then {timing_description}")
            if kind in ('one', 'four'):
                threads = 1 if kind == 'one' else 4
                measured = subprocess.run([str(binary), str(n), str(repetitions), str(trials), str(threads), directory],
                                          check=True, capture_output=True, text=True, timeout=600,
                                          env={**os.environ, 'OMP_PROC_BIND':'true', 'OMP_PLACES':'cores'})
                data = json.loads(measured.stdout)
                c = np.fromfile(temp/'c.bin', dtype=np.float32).reshape(n, n)
                with threadpool_limits(limits=4, user_api='blas'):
                    error = float(np.linalg.norm(c-reference)/np.linalg.norm(reference))
                if not np.isfinite(error) or error > 1e-4:
                    raise RuntimeError(f'{label}: incorrect result ({error})')
                if data['actual_threads'] != threads:
                    raise RuntimeError(f'{label}: wrong OpenMP worker count')
                result = dict(processor='CPU', target='pi', host=platform.node(),
                    hardware=Path('/proc/device-tree/model').read_text().strip('\0'),
                    runtime=f'C++ / OpenMP / 16×16 tiled / {threads} threads',
                    n=n, dtype='float32', seed=42, repetitions=repetitions, warmup=1,
                    boundary='resident compute', requested_threads=threads, actual_threads=data['actual_threads'],
                    compiler=compiler, compiler_flags=flags, input_sha256=digest,
                    source_sha256=hashlib.sha256((folder/'cpu_tiled_matmul.cpp').read_bytes()).hexdigest(),
                    trial_s=data['trial_s'], median_ms=float(np.median(data['trial_s'])*1000/repetitions),
                    relative_error=error, validated=True)
            elif kind == 'blas':
                result = cpu_benchmark(n, repetitions, trials, threads=4)
                pools = [p for p in result['threadpools'] if p.get('user_api') == 'blas']
                if not pools or any(p['num_threads'] != 4 for p in pools):
                    raise RuntimeError('BLAS did not report four threads')
                if not np.isfinite(result['relative_error']):
                    raise RuntimeError('Non-finite BLAS validation error')
                result['target'] = 'pi'
            else:
                result = gpu_benchmark(n, repetitions, trials, variant="untiled" if kind == "gpu_untiled" else "tiled")
            result.update(implementation=label, health_before=before, health_after=health(),
                          cooldown_seconds=round(cooldown, 2))
            if result['input_sha256'] != digest or not result['validated']:
                raise RuntimeError('Input or validation mismatch')
            results.append(result)
            progress(f"Finished {label}: {result['median_ms']:.3f} ms; validation passed")
    progress("All five Pi implementations completed")
    return {'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'host':platform.node(), 'n':n, 'repetitions':repetitions, 'trials':trials,
            'timing':'Sequential completed matrix multiplications, prepared resident buffers; host wall time',
            'results':results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=512)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--trials', type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(run_suite(args.n, args.repetitions, args.trials)))
