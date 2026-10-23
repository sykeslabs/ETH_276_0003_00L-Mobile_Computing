"""Measure sequential Hailo-10H ResNet-50 inference, independently of matrix timings."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import hailo_platform as hailo


def npu_benchmark(hef_path='/usr/share/hailo-models/resnet_v1_50_h10.hef', repetitions=100, trials=5):
    os.environ.setdefault('HAILO_MONITOR', '1')
    hef = Path(hef_path)
    if not hef.is_file():
        raise FileNotFoundError(f'{hef} is missing. Install the hailo-models package on the Pi.')
    rng = np.random.default_rng(42)
    with hailo.VDevice() as device:
        model = device.create_infer_model(str(hef))
        model.set_batch_size(1)
        model.input().set_format_type(hailo.FormatType.UINT8)
        model.output().set_format_type(hailo.FormatType.FLOAT32)
        input_shape = tuple(model.input().shape)
        output_shape = tuple(model.output().shape)
        if input_shape != (224, 224, 3) or np.prod(output_shape) != 1000:
            raise ValueError('This experiment requires the supplied ResNet-50 classification model.')
        inputs = rng.integers(0, 256, input_shape, dtype=np.uint8)
        outputs = np.empty(output_shape, dtype=np.float32)
        with model.configure() as configured:
            bindings = configured.create_bindings()
            bindings.input().set_buffer(inputs)
            bindings.output().set_buffer(outputs)
            def infer():
                configured.run([bindings], timeout=10000)
            def check_output():
                if not np.all(np.isfinite(outputs)) or np.any(outputs < -1e-6):
                    raise RuntimeError('Invalid classification output')
                # Quantized probabilities need not sum to one after dequantization.
                if np.any(outputs > 1.01) or not float(outputs.sum()) > 0:
                    raise RuntimeError('Invalid probability range or empty output')
            for _ in range(5):
                infer()
            check_output()
            expected = outputs.copy()
            elapsed = []
            for _ in range(trials):
                start = time.perf_counter_ns()
                for _ in range(repetitions):
                    infer()
                elapsed.append((time.perf_counter_ns()-start)/1e9)
                check_output()
                if not np.allclose(outputs, expected, atol=1e-6, rtol=1e-5):
                    raise RuntimeError('Repeated fixed-input inference produced inconsistent outputs')
            # Check input sensitivity separately from the timed workload.
            alternative = np.zeros(input_shape, dtype=np.uint8)
            bindings.input().set_buffer(alternative)
            infer()
            check_output()
            changed = not np.allclose(outputs, expected, atol=1e-6, rtol=1e-5)
            if not changed:
                raise RuntimeError('Output did not change for the second test input')
    median_ms = float(np.median(elapsed)*1000/repetitions)
    return dict(processor='NPU', target='pi', hardware='Hailo-10H', host=platform.node(),
                timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                runtime=f'HailoRT {hailo.__version__}', python=platform.python_version(),
                os=platform.platform(), model='ResNet-50', model_path=str(hef),
                model_sha256=hashlib.sha256(hef.read_bytes()).hexdigest(),
                input_sha256=hashlib.sha256(inputs.tobytes()).hexdigest(),
                input_shape=input_shape, output_shape=output_shape,
                input_dtype='uint8', output_dtype='float32 (runtime dequantization)',
                precision='Compiled quantized HEF; UINT8 input, dequantized FLOAT32 output',
                workload='ResNet-50 on fixed seeded synthetic input; batch size 1',
                boundary='host-to-host request', timing_details='Synchronous HailoRT call including input/output transfers and format conversion; model load and allocation excluded',
                batch_size=1, seed=42, warmup=5, repetitions=repetitions, trial_s=elapsed,
                median_ms=median_ms, inferences_per_s=1000/median_ms,
                output_checks_passed=True, accuracy_validated=False, output_sum=float(expected.sum()),
                validation_details='Finite nonnegative nonempty probability output, repeatability, changed output for a second input; no labeled-data accuracy assessment',
                system_power_W=None)


if __name__ == '__main__':
    print(json.dumps(npu_benchmark()))
