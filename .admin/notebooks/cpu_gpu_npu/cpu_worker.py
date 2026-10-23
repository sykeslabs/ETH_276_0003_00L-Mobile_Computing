import contextlib, datetime, hashlib, io, json, platform, time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits, threadpool_info

def cpu_benchmark(n=512, repetitions=100, trials=5, threads=4):
    rng = np.random.default_rng(42)
    A = rng.uniform(-1, 1, (n, n)).astype(np.float32)
    B = rng.uniform(-1, 1, (n, n)).astype(np.float32)
    C = np.empty_like(A)
    def sensor(name):
        p = Path(name)
        return p.read_text().strip() if p.exists() else None
    temperature_path = "/sys/class/thermal/thermal_zone0/temp"
    temp_before = sensor(temperature_path)
    with threadpool_limits(limits=threads, user_api="blas"):
        pools = threadpool_info()
        for _ in range(1):
            np.matmul(A, B, out=C)
        elapsed = []
        for _ in range(trials):
            start = time.perf_counter_ns()
            for _ in range(repetitions):
                np.matmul(A, B, out=C)
            elapsed.append((time.perf_counter_ns()-start)/1e9)
        temp_after = sensor(temperature_path)
        reference = A.astype(np.float64) @ B.astype(np.float64)
    error = float(np.linalg.norm(C-reference)/np.linalg.norm(reference))
    if error > 1e-4:
        raise RuntimeError(f"Numerical validation failed: relative error {error}")
    model_path = Path("/proc/device-tree/model")
    board = model_path.read_text().strip("\x00") if model_path.exists() else platform.machine()
    config = io.StringIO()
    with contextlib.redirect_stdout(config): np.show_config()
    return dict(processor="CPU", hardware=board, host=platform.node(),
        timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        runtime=f"NumPy {np.__version__}", python=platform.python_version(), os=platform.platform(),
        dtype="float32", n=n, seed=42, repetitions=repetitions, warmup=1,
        requested_threads=threads, threadpools=pools, numpy_config=config.getvalue(),
        boundary="resident compute", workload="C=A@B; fixed A,B; output buffer reused",
        input_sha256=hashlib.sha256(A.tobytes()+B.tobytes()).hexdigest(),
        trial_s=elapsed, median_ms=float(np.median(elapsed)*1000/repetitions),
        relative_error=error, validated=True, system_power_W=None,
        temperature_mC_before=temp_before, temperature_mC_after=temp_after)

if __name__ == "__main__":
    print(json.dumps(cpu_benchmark()))
