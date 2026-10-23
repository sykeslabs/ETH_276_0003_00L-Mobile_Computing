"""Build and measure a Vulkan matrix product on the Pi's Broadcom GPU."""
import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile

import numpy as np
from threadpoolctl import threadpool_limits


def gpu_benchmark(n=512, repetitions=100, trials=5, variant="tiled"):
    if variant not in ("tiled", "untiled"):
        raise ValueError("Choose tiled or untiled GPU shader")
    folder = Path(__file__).resolve().parent
    shader_name = "matmul.comp" if variant == "tiled" else "matmul_untiled.comp"
    rng = np.random.default_rng(42)
    a = rng.uniform(-1, 1, (n, n)).astype(np.float32)
    b = rng.uniform(-1, 1, (n, n)).astype(np.float32)
    with tempfile.TemporaryDirectory(prefix='pi-gpu-benchmark-') as temp:
        work = Path(temp)
        for command in [
            ['glslangValidator', '-V', str(folder/shader_name), '-o', str(work/'matmul.spv')],
            ['g++', '-O3', '-std=c++17', str(folder/'gpu_matmul.cpp'), '-lvulkan', '-o', str(work/'gpu_matmul')],
        ]:
            built = subprocess.run(command, capture_output=True, text=True, timeout=120)
            if built.returncode:
                raise RuntimeError(built.stderr or built.stdout)
        a.tofile(work/'a.bin'); b.tofile(work/'b.bin')
        def sensor():
            p = Path('/sys/class/thermal/thermal_zone0/temp')
            return p.read_text().strip() if p.exists() else None
        before = sensor()
        completed = subprocess.run([str(work/'gpu_matmul'), str(n), str(repetitions), str(trials), temp],
                                   capture_output=True, text=True, timeout=300)
        after = sensor()
        if completed.returncode:
            raise RuntimeError(completed.stderr or completed.stdout)
        measured = json.loads(completed.stdout)
        c = np.fromfile(work/'c.bin', dtype=np.float32).reshape(n, n)
    with threadpool_limits(limits=4, user_api='blas'):
        reference = a.astype(np.float64) @ b.astype(np.float64)
    error = float(np.linalg.norm(c-reference)/np.linalg.norm(reference))
    if not np.isfinite(error) or error > 1e-4:
        raise RuntimeError(f'GPU numerical validation failed: relative error {error}')
    board = Path('/proc/device-tree/model').read_text().strip('\x00')
    return dict(processor='GPU', target='pi', hardware=board+' / '+measured['device'],
                host=platform.node(), timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                runtime=f'Vulkan / {variant} FP32 compute shader / 16×16 workgroup', shader_variant=variant, python=platform.python_version(),
                os=platform.platform(), dtype='float32', n=n, seed=42, repetitions=repetitions, warmup=1,
                boundary='resident compute', timing_details='Host wall time: sequential queue submission and fence wait; prepared shared buffers',
                workload='C=A@B; fixed A,B; output buffer reused',
                input_sha256=hashlib.sha256(a.tobytes()+b.tobytes()).hexdigest(),
                shader_sha256=hashlib.sha256((folder/shader_name).read_bytes()).hexdigest(),
                trial_s=measured['trial_s'], median_ms=float(np.median(measured['trial_s'])*1000/repetitions),
                relative_error=error, validated=True, system_power_W=None,
                temperature_mC_before=before, temperature_mC_after=after,
                device_metadata={k:v for k,v in measured.items() if k!='trial_s'})


if __name__ == '__main__':
    print(json.dumps(gpu_benchmark()))
