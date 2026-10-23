# CPU, GPU and NPU visualizations

The three animations are embedded in notebook 05.xx and run inside VS Code.
Each HTML file includes its styling, data, playback controls and calculations.
PNG snapshots provide a fallback for notebook viewers that cannot run iframe scripts.

The CPU view is a scalar teaching example, the GPU view illustrates a parallel tile,
and the NPU view illustrates a systolic array. These are not measured timings or exact
representations of the Pi's processor implementations.

Section 2 uses the static image `img/processor-architecture.png`.
Regenerate it from the repository root with:

```sh
python3 .admin/notebooks/cpu_gpu_npu/generate_processor_architecture.py
```

Section 3 uses the static image `img/raspberry-pi-hardware.png`.
Regenerate it from the repository root with:

```sh
python3 .admin/notebooks/cpu_gpu_npu/generate_raspberry_pi_hardware.py
```

Section 4.2 runs only on the Pi. `run_matrix_comparison.py` uploads the workers, runs all five implementations sequentially, verifies matching inputs and timing configuration, and displays a common table. `matrix_comparison_worker.py` coordinates tiled C++ with one/four OpenMP workers, four-thread NumPy/BLAS, and both tiled and untiled Vulkan. `cpu_tiled_matmul.cpp` uses 16 × 16 tiles, compiler vectorization, and native CPU instructions. `cpu_worker.py` supplies the optimized BLAS reference. Compilation, allocation, transfers, and validation are outside the timed region. Complete calls include OpenMP coordination or Vulkan submit/wait overhead.

Default configuration: n=512, one timed trial containing three matrix multiplications (repetitions=3, trials=1), after one warm-up. Relative error is validated and saved but omitted from the output tables. Each implementation checks every output against a float64 reference with relative error <=1e-4. Actual CPU/BLAS thread counts are checked. All five input hashes must match. Per-implementation temperature and throttling readings and raw trials are saved to `results/matrix-five-implementations-*.json`. Each variant has up to 10 seconds of cooldown before timing; the full run can take several minutes. The console remains running during experiments and creates no demo workload. Live progress streams from the Pi to the cell output only; preparation, cooldown, and implementation start/completion are identified. Monitoring overhead remains part of this exploratory run; closing the console manually avoids it. The previous local-host benchmark launcher is retained for compatibility but is no longer called by the notebook.

Section 4.3 uses `run_neural_comparison.py` and `neural_comparison_worker.py` for matched ResNet-50 classification on CPU, GPU, and NPU. CPU and GPU share the Hailo Model Zoo FP32 TFLite file; NPU uses the corresponding installed quantized HEF. All paths use the same cropped RGB photograph, batch size one, one warm-up, and one timed trial of three inferences. Timing includes normalization, staging, execution, output transfer/conversion, and output copy. Model loading, image decoding/cropping, and initial buffer allocation are excluded. GPU results require full LiteRT acceleration and increasing V3D hardware engine counters. Output vectors, top predictions, numerical agreement, artifact hashes, runtime diagnostics, and thermal readings are saved in `results/resnet50-comparison-*.json`. One image does not assess dataset accuracy. Installation instructions are in the setup guide. The previous standalone `npu_worker.py` remains available but is no longer called by the notebook.

`check_pi_hardware.py` implements the section 3.1 inventory, automatic SSH key login and results table. It quietly installs Paramiko only if missing in the
notebook kernel environment. Raw checks are returned as `pi_inventory`.

Section 4.4 uses `run_llm_benchmarks.py`, `llm_worker.py`, and `llm_prompts.json`.
The worker runs Qwen2-1.5B-Instruct through llama.cpp on CPU or Vulkan, and
Hailo-Ollama on NPU. Runtime startup failures are recorded as unavailable.
Prompt outputs and timings are kept separate from the matrix measurements.
See [LLM setup](LLM_SETUP.md) for the Pi installation and command-line entry point.

The complete [Raspberry Pi setup guide](raspberry_pi_setup.md) covers SD card installation, network and hostname fixes, SSH keys, locales, drivers, benchmark tools, and the LLM runtimes.

`show_processor_animation.py` handles embedding each animation from the short notebook calls.

`pi_status_widget.py` combines the section 3.1 inventory as a printer paper log with a live Apollo-style console. `pi_status_worker.py` collects telemetry over the existing SSH connection. CPU, GPU compute, and available NPU utilization appear as circular needle gauges. Missing utilization parks the needle at zero and is marked as no signal. Temperature, storage, memory, and fan RPM remain numeric readouts. The monitor updates automatically with a one-second target interval. Rerunning the cell replaces the connection; `pi_monitor.close()` stops monitoring.

`pi_fan_control.py` provides the single vintage ON / OFF switch inside the fan field. Each click runs the root-owned `/usr/local/libexec/mobilecomputing-pi-fan` helper once. No session lock or password prompt is used. Automatic thermal control remains enabled; OFF is declined at 65 °C or above. Feedback occupies a fixed-height line. The sudoers rule permits only this helper with no command-line arguments.

The fixed-height paper prints the inventory and timestamped events character by character. Ten visible lines scroll as new lines arrive. Warning lights print only when they turn ON; OFF transitions are silent. CPU, GPU, and NPU load trigger above 80%, temperature above 80 °C, and storage and memory at 75% usage or higher. Each warning remains lit for ten seconds after the last above-threshold sample; the paper logs each new ON event. Fan setting changes, manual requests, cooling overrides, and failures also print. Missing fan telemetry does not imply OFF. The latest 500 entries remain available in `pi_monitor.event_printer.history`. Printing runs independently of telemetry polling and stops when the dashboard closes.


Fan controls follow the kernel [pwm-fan interface](https://www.kernel.org/doc/html/latest/hwmon/pwm-fan.html). `pwm1_enable=2` does not mean automatic mode for this driver; the helper leaves that attribute unchanged.

Each fan click writes PWM once. The helper leaves automatic thermal control active and does not continuously override it; the switch follows the actual PWM setting.

Section 3.1 and the CPU, accelerator, and LLM benchmark launchers use SSH keys from the notebook host or its SSH agent. The dashboard connects automatically. The fan switch uses the installed root-owned helper with a narrowly scoped password-free sudo rule.

Telemetry runs in a dedicated background thread so synchronous benchmark cells do not freeze the gauges. GPU load is the V3D compute-engine counter for visible clients. NPU load remains unavailable unless Hailo publishes a utilization sample; an open device alone does not imply a load percentage.

Dashboard startup is synchronous: the section 3.1 cell performs key authentication and displays the widget before completing. Only telemetry polling runs in a background thread; startup does not rely on a scheduled login coroutine.

The ResNet-50 CPU comparison includes one LiteRT thread pinned to one core and four LiteRT threads allowed across four cores. CPU affinity is restored before GPU/NPU execution. Both CPU outputs and the GPU output are checked against the one-core reference.
