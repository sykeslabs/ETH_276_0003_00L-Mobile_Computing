"""Matched ResNet-50 inference on the Pi CPU, VideoCore GPU, and Hailo NPU."""
from contextlib import contextmanager
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

# Restrict LiteRT to the Pi hardware Vulkan driver; never accept software rendering.
os.environ['V3D_WEBGPU_OVERRIDE'] = '1'
os.environ['VK_DRIVER_FILES'] = '/usr/share/vulkan/icd.d/broadcom_icd.json'
os.environ['VK_ICD_FILENAMES'] = os.environ['VK_DRIVER_FILES']
os.environ['HAILO_MONITOR'] = '1'

import numpy as np
from PIL import Image, ImageOps

EXPECTED = {
    'resnet_v1_50.tflite': '2625772f5e1324c1e2781856926a445b4fe6494b9e0bb0161a7d86df7f095d38',
    'resnet_v1_50_h10.hef': '1f6fecf62263f7bea9f76b1caff406ed899bc355dae92ab738f1aeaead49c857',
    'dog.jpg': 'f3f87bb8ab3c26c7ecfd3ac60421d7f32b0503d1d6c5baf8bac42ed93d86351a',
    'imagenet_classes.txt': '1f386e0d1cb6e28b9c2dac651c3dea6801e98ad1b41a14ce6bb1a093d72069f5',
}
MEAN = np.array([123.68, 116.78, 103.94], dtype=np.float32)


def progress(message):
    print(json.dumps({'event': 'progress', 'message': message}), flush=True)


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def health():
    return {'temperature_c': int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,
            'throttling': subprocess.check_output(['vcgencmd', 'get_throttled'], text=True).strip()}


def gpu_counters():
    clients = {}
    for path in Path('/proc/self/fdinfo').iterdir():
        try:
            info = path.read_text()
        except OSError:
            continue
        if not re.search(r'drm-driver:\s*v3d\b', info):
            continue
        client = re.search(r'drm-client-id:\s*(\d+)', info)
        if client:
            clients[client[1]] = dict((k, int(v)) for k, v in
                                     re.findall(r'drm-engine-([\w-]+):\s*(\d+)\s+ns', info))
    return {key: sum(c.get(key, 0) for c in clients.values()) for key in ('csd', 'tfu')}


def check_output(values):
    if values.shape != (1000,) or not np.all(np.isfinite(values)):
        raise RuntimeError('Expected 1,000 finite class scores')
    if np.any(values < -1e-6) or np.any(values > 1.01) or values.sum() <= 0:
        raise RuntimeError('Invalid class probabilities')


def measure(infer, repetitions):
    # Exactly one warm-up. Validation and counter reads remain outside timing.
    expected = infer()
    check_output(expected)
    counters_before = gpu_counters()
    start = time.perf_counter_ns()
    for _ in range(repetitions):
        output = infer()
    elapsed = (time.perf_counter_ns()-start)/1e9
    counters_after = gpu_counters()
    check_output(output)
    if not np.allclose(output, expected, rtol=1e-4, atol=1e-6):
        raise RuntimeError('Fixed-input output changed between warm-up and measurement')
    return output, elapsed, {k: counters_after[k]-counters_before[k] for k in counters_before}


@contextmanager
def cpu_affinity(threads):
    original = {}
    allowed = sorted(os.sched_getaffinity(0))
    selected = allowed[:threads]
    if len(selected) != threads:
        raise RuntimeError(f'Expected {threads} available CPU cores')
    try:
        for task in Path('/proc/self/task').iterdir():
            tid = int(task.name)
            try:
                original[tid] = os.sched_getaffinity(tid)
                os.sched_setaffinity(tid, selected)
            except ProcessLookupError:
                pass
        yield selected
    finally:
        for task in Path('/proc/self/task').iterdir():
            tid = int(task.name)
            try:
                os.sched_setaffinity(tid, original.get(tid, allowed))
            except ProcessLookupError:
                pass


def run_litert(kind, path, rgb, repetitions, threads=4):
    from ai_edge_litert.compiled_model import CompiledModel, HardwareAccelerator
    from ai_edge_litert.options import Options
    from ai_edge_litert.cpu_options import CpuOptions
    from ai_edge_litert.gpu_options import GpuOptions
    options = Options(hardware_accelerators=getattr(HardwareAccelerator, kind),
                      cpu_options=CpuOptions(num_threads=threads), gpu_options=GpuOptions(enforce_f32=True))
    model = CompiledModel.from_file(str(path), options=options)
    try:
        accelerated = model.is_fully_accelerated()
        if kind == 'GPU' and not accelerated:
            raise RuntimeError('LiteRT did not fully accelerate the GPU graph; refusing a fallback result')
        inputs, outputs = model.create_input_buffers(0), model.create_output_buffers(0)
        def infer():
            # HEF contains the same subtraction internally; include it here in the request.
            normalized = rgb.astype(np.float32) - MEAN
            inputs[0].write(normalized[None])
            model.run_by_index(0, inputs, outputs)
            return outputs[0].read(1000, np.float32).copy().reshape(-1)
        output, elapsed, counters = measure(infer, repetitions)
        if kind == 'GPU' and counters['csd'] + counters['tfu'] <= 0:
            raise RuntimeError('No hardware V3D work observed during GPU inference')
        return output, elapsed, {
            'runtime': f"LiteRT {importlib.metadata.version('ai-edge-litert')} / " + (f'CPU, {threads} thread' + ('s' if threads != 1 else '') if kind == 'CPU' else 'WebGPU / Vulkan'),
            'precision': 'FP32', 'requested_cpu_threads': threads,
            'gpu_fully_accelerated': accelerated if kind == 'GPU' else None,
            'gpu_engine_ns': counters if kind == 'GPU' else None,
            'gpu_enforce_f32': kind == 'GPU',
        }
    finally:
        model.close()


def run_hailo(path, rgb, repetitions):
    import hailo_platform as hailo
    with hailo.VDevice() as device:
        model = device.create_infer_model(str(path))
        model.set_batch_size(1)
        model.input().set_format_type(hailo.FormatType.UINT8)
        model.output().set_format_type(hailo.FormatType.FLOAT32)
        if tuple(model.input().shape) != (224, 224, 3) or np.prod(model.output().shape) != 1000:
            raise RuntimeError('Unexpected HEF input/output shape')
        input_buffer = np.empty_like(rgb)
        output_buffer = np.empty(model.output().shape, np.float32)
        with model.configure() as configured:
            bindings = configured.create_bindings()
            bindings.input().set_buffer(input_buffer)
            bindings.output().set_buffer(output_buffer)
            def infer():
                np.copyto(input_buffer, rgb)
                configured.run([bindings], timeout=10000)
                return output_buffer.copy().reshape(-1)
            output, elapsed, _ = measure(infer, repetitions)
    return output, elapsed, {'runtime': f'HailoRT {hailo.__version__}',
                             'precision': 'Quantized HEF', 'input_dtype': 'UINT8',
                             'output_dtype': 'FP32 (dequantized)'}


def run_comparison(repetitions=3):
    if repetitions < 1:
        raise ValueError('At least one inference is required')
    directory = Path.home()/'neural-comparison/models'
    paths = {name: directory/name for name in EXPECTED}
    paths['resnet_v1_50_h10.hef'] = Path('/usr/share/hailo-models/resnet_v1_50_h10.hef')
    for name, path in paths.items():
        if not path.is_file() or checksum(path) != EXPECTED[name]:
            raise RuntimeError(f'Missing or changed reference artifact: {path}. See the setup guide.')
    progress('Preparing one shared 224 × 224 RGB image for ResNet-50')
    with Image.open(paths['dog.jpg']) as image:
        rgb = np.asarray(ImageOps.fit(image.convert('RGB'), (224, 224), method=Image.Resampling.BILINEAR), dtype=np.uint8).copy()
    labels = paths['imagenet_classes.txt'].read_text().splitlines()
    if len(labels) != 1000:
        raise RuntimeError('Expected 1,000 ImageNet labels')
    digest = hashlib.sha256(rgb.tobytes()).hexdigest()
    results, vectors = [], {}
    for kind, threads, implementation in [('CPU', 1, 'CPU: 1 core'), ('CPU', 4, 'CPU: 4 cores'), ('GPU', 4, 'GPU'), ('NPU', 4, 'NPU')]:
        before = health()
        deadline = time.monotonic()+10
        if before['temperature_c'] > 65:
            progress(f"Cooling before {implementation}: {before['temperature_c']:.1f} °C (up to 10 s)")
        while before['temperature_c'] > 65 and time.monotonic() < deadline:
            time.sleep(min(2, max(0, deadline-time.monotonic())))
            before = health()
        progress(f'{implementation}: loading ResNet-50, then 1 warm-up and 1 timed trial of {repetitions} inferences')
        artifact = paths['resnet_v1_50_h10.hef' if kind == 'NPU' else 'resnet_v1_50.tflite']
        if kind == 'CPU':
            with cpu_affinity(threads) as cores:
                output, elapsed, details = run_litert(kind, artifact, rgb, repetitions, threads)
                details['cpu_affinity'] = cores
        else:
            output, elapsed, details = (run_hailo(artifact, rgb, repetitions) if kind == 'NPU'
                                        else run_litert(kind, artifact, rgb, repetitions))
        vectors[implementation] = output
        top5 = np.argsort(output)[-5:][::-1]
        results.append(dict(processor=kind, implementation=implementation, model='ResNet-50 v1', model_sha256=checksum(artifact),
            input_sha256=digest, input_shape=[224,224,3], batch_size=1, warmup=1, trials=1,
            repetitions=repetitions, trial_s=[elapsed], average_ms=elapsed*1000/repetitions,
            inferences_per_s=repetitions/elapsed, output_checks_passed=True,
            health_before=before, health_after=health(),
            top1=labels[int(top5[0])], top1_index=int(top5[0]),
            top5=[{'index':int(i), 'label':labels[int(i)], 'score':float(output[i])} for i in top5],
            output_scores=output.tolist(), **details))
        progress(f'{implementation} finished: {elapsed*1000/repetitions:.3f} ms/inference; top class {labels[int(top5[0])]}')
    reference = vectors['CPU: 1 core']
    for result in results:
        output = vectors[result['implementation']]
        result['agreement_with_cpu'] = {
            'top1_matches':int(output.argmax()) == int(reference.argmax()),
            'cosine_similarity':float(np.dot(reference,output)/(np.linalg.norm(reference)*np.linalg.norm(output))),
            'mean_absolute_error':float(np.abs(reference-output).mean()),
            'maximum_absolute_error':float(np.abs(reference-output).max()),
        }
    if any(not np.allclose(vectors[key], reference, rtol=1e-3, atol=1e-5)
           for key in ('CPU: 4 cores', 'GPU')):
        raise RuntimeError('FP32 CPU/GPU predictions differ beyond tolerance')
    return dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        host=platform.node(), python=platform.python_version(), pillow=importlib.metadata.version('Pillow'),
        model='Hailo Model Zoo ResNet-50 v1', repetitions=repetitions,
        warmup=1, trials=1, results=results, artifact_hashes=EXPECTED,
        preprocessing='Pillow RGB conversion and centered square crop/resize to 224×224, bilinear; channel means [123.68,116.78,103.94]',
        preprocessing_in_timer='Mean subtraction included on CPU/GPU; embedded in HEF on NPU. Image decoding/resizing excluded on all paths.',
        boundary='Host RGB input to completed host FP32 class-score vector, including input staging, execution, output transfer/dequantization and copy',
        precision_caveat='Same network task; CPU/GPU use identical FP32 TFLite file, NPU uses quantized compiled HEF. Arithmetic and weights are not bit-identical across formats.',
        validation='Shape, finite scores, probability range, repeatability, CPU/GPU numerical agreement; NPU output differences reported, not hidden. One image does not establish dataset accuracy.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repetitions', type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(run_comparison(args.repetitions)), flush=True)
