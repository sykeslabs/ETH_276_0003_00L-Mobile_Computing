# Qwen2 measurements, 30 September 2026

`qwen2-2026-09-30.json` contains measured responses and timings from the Pi.
CPU and NPU completed three passes over ten prompts. GPU completed one pass.
The GPU's last prompt exceeded the initial 180-second deadline. Its successful
retry used a fresh warmed GPU server and a 300-second deadline. The JSON marks
that response and retains the original diagnostic. The original partial result
is preserved as `qwen2-2026-09-30-original.json`.

| Processor | Responses | Median response, s | Tokens/s including prompt |
|---|---:|---:|---:|
| CPU | 30 | 2.355 | 8.48 |
| GPU | 10 | 61.403 | 0.27 |
| NPU | 30 | 1.673 | 7.08 |

The CPU run recorded active thermal flags. NPU warm-up returned `2` for `2 + 2`;
the failed answer check and all generated responses remain visible. Different
answers and lengths prevent treating response latency alone as a speed ratio.
The NPU uses a separately compiled quantized model. GPU logs confirmed all
29 layers were offloaded through Vulkan.

Telemetry UI checks overlapped portions of this exploratory run. These are
initial validation measurements, not a controlled performance study. Pause the
monitor for subsequent timing runs. The current worker defaults to one GPU pass
and uses a 300-second request deadline. The original CPU/NPU run predates the
addition of `HAILO_MONITOR=1` to the NPU server environment.


## Four Pi matrix implementations, 1 October 2026

Raw measurements: [matrix-four-implementations-2026-10-01T14-25-46.463372_00-00.json](matrix-four-implementations-2026-10-01T14-25-46.463372_00-00.json). All variants use identical seeded 512 × 512 FP32 inputs, five warm-ups, and five trials of 100 completed matrix multiplications.

CPU tiled C++ / 1 thread: 39.969 ms, 25.02 matrix multiplications/s.

CPU tiled C++ / 4 threads: 10.795 ms, 92.63 matrix multiplications/s.

CPU NumPy/BLAS / 4 threads: 3.729 ms, 268.19 matrix multiplications/s.

GPU tiled Vulkan: 97.025 ms, 10.31 matrix multiplications/s.

All numerical checks passed. The four-thread tiled C++ run ended at 81.5 °C with `throttled=0x80008`, including an active soft temperature limit. Later runs retained historical `0x80000` with no active low-bit flags at their sampling points. Treat the four-thread timing as potentially temperature-limited; samples before/after cannot reconstruct every clock change within a trial.


## Tiled and untiled GPU comparison, 1 October 2026

[matrix-five-implementations-2026-10-01T14-45-55.225277_00-00.json](matrix-five-implementations-2026-10-01T14-45-55.225277_00-00.json) records a fresh run of all five implementations: 512 × 512 FP32, five warm-ups, five trials of 100 multiplications. Both GPU shaders use the same 16 × 16 workgroups and host submit/wait code. All input hashes match and all full-output numerical checks passed.

CPU tiled C++ / 1 thread: 40.172 ms, 24.89 matrix multiplications/s.

CPU tiled C++ / 4 threads: 10.877 ms, 91.94 matrix multiplications/s.

CPU NumPy/BLAS / 4 threads: 3.832 ms, 260.98 matrix multiplications/s.

GPU tiled Vulkan: 96.664 ms, 10.35 matrix multiplications/s.

GPU untiled Vulkan: 121.039 ms, 8.26 matrix multiplications/s.

Untiled Vulkan was slower in this run: 121.039 ms versus 96.664 ms. Removing shared-memory tiles and barriers also changes data access and caching; this comparison does not isolate one hardware cost. Historical soft-temperature-limit flags were already present, so endpoint flags cannot rule out temperature limiting during a trial.

## Matched ResNet-50, 1 October 2026

`resnet50-comparison-2026-10-01T15-21-06.918767_00-00.json` records the same RGB photograph and ResNet-50 classification task on all three Pi processors: CPU 82.498 ms, GPU 393.143 ms, NPU 4.593 ms per inference. Each uses one warm-up and one trial of three inferences, batch size one. CPU/GPU share FP32 TFLite; NPU uses quantized HEF. All predicted Samoyed. CPU/GPU numerical checks passed; NPU score cosine similarity to CPU was 0.9941. GPU full acceleration and V3D engine activity were verified. These are exploratory request timings, not a dataset accuracy assessment or identical-precision hardware comparison.

## One-core CPU comparison

`resnet50-comparison-2026-10-01T15-26-34.070506_00-00.json` adds a CPU run pinned to one core: 220.635 ms, compared with 83.753 ms across four cores. GPU: 392.864 ms; NPU: 4.437 ms. One warm-up and three timed inferences per implementation. CPU outputs were identical; CPU/GPU tolerance checks passed. All four predicted Samoyed. CPU affinity lists are recorded in the result.
