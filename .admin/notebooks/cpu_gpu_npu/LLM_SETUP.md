# Qwen2 comparison on Raspberry Pi 5

The installation uses Qwen2-1.5B-Instruct on the Pi CPU, VideoCore VII Vulkan
backend, and Hailo-10H. The installed Vulkan runtime successfully offloads all
29 model layers to the GPU. The benchmark checks offload and generated output
before reporting a GPU result.

## Installed files and versions

The Pi working directory is `/home/cas/llm-comparison`.

| Item | Version or location |
|---|---|
| llama.cpp | `876c75b1f63d1567532fd4300fc5777549619d63` |
| HailoRT and Hailo GenAI Model Zoo | 5.1.1 |
| CPU/GPU model | `models/qwen2-1_5b-instruct-q4_0.gguf` |
| GGUF source | Qwen/Qwen2-1.5B-Instruct-GGUF, revision `c62434db644497c0ee545c690bb66a67eba6eb3f` |
| GGUF SHA-256 | `106c176ae807b164f16e2898e8f0267062e3c93c3c18c8267cf9e4ee90766beb` |
| NPU model | Hailo-Ollama `qwen2:1.5b` |
| HEF SHA-256 | `ab056548c60945cdf4fb30ca43fc7aeed2b9ffc751ad8d4c201dc4c4ab31e86a` |

Hailo stores the HEF in `/usr/share/hailo-ollama/models/blob/sha256_<hash>`.
Its manifest is `/usr/share/hailo-ollama/models/manifests/qwen2/1.5b/manifest.json`.
The runtime's Q4_0 metadata label does not make the HEF arithmetic identical to
GGUF Q4_0. Treat the CPU/NPU comparison as deployment-level performance.

## Setup commands

The existing Pi installation already has HailoRT 5.1.1, the Hailo kernel driver,
NumPy, Vulkan libraries, and a C++ compiler. Additional packages installed for
this experiment are `glslc`, `spirv-headers`, `libssl-dev`, and
`hailo-gen-ai-model-zoo` 5.1.1.

The [official Raspberry Pi instructions](https://www.raspberrypi.com/documentation/computers/ai.html#run-llms-on-raspberry-pi-5-ai-hat-2-only)
link the matching installer:

```sh
curl -fLO https://dev-public.hailo.ai/2025_12/Hailo10/hailo_gen_ai_model_zoo_5.1.1_arm64.deb
sudo apt install ./hailo_gen_ai_model_zoo_5.1.1_arm64.deb
```

The llama.cpp source is built with:

```sh
cd ~/llm-comparison/llama.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON -DLLAMA_BUILD_TESTS=ON
cmake --build build --target llama-server llama-cli llama-bench test-backend-ops -j 4
```

The GGUF comes from the [official Qwen repository](https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF).
The Hailo model is downloaded through `POST /api/pull` with
`{"model":"qwen2:1.5b","stream":false}` after starting `hailo-ollama`.
Model files are stored on the Pi and are not part of this Git repository.

## Run the prompt suite

The notebook uploads the worker and prompt list, then starts the experiment.
After those files have been uploaded, the equivalent Pi command is:

```sh
cd ~/llm-comparison
python3 -u llm_worker.py --repetitions 3 --gpu-repetitions 1 --max-tokens 64 --backends CPU GPU NPU
```

The worker starts and stops its own loopback-only servers. No background service
is required. It saves `llm-results.json` and runtime diagnostics in `logs/`.
It uses a four-thread CPU, explicitly requests the Broadcom GPU, and records
model hashes and the runtime revision. Loading and a separate warm-up request
are outside measured prompt requests. Cache reuse is disabled for llama.cpp;
independent Hailo conversations clear the context. Generated answers stop at
the model's end token or the common 64-token limit.

The reported token rate includes prompt processing and local HTTP overhead.
It is not a device-only decoding rate. Time to first text is measured at the
first nonempty streamed fragment. All responses remain available for inspecting
answer length and correctness. Sampling temperature zero reduces variability;
different quantization can still produce different answers.

Temperature and current throttling flags are sampled between requests.
Cooling pauses are outside the timers. Historical firmware flags are retained
in the JSON and distinguished from active flags. Sampling between requests
cannot rule out every brief event during a request.

The initial validation uses one GPU pass over the ten prompts and three CPU and NPU passes. Set `--gpu-repetitions 3` for a full GPU run.

Measured responses and validation notes are in [results](results/README.md). CPU thermal flags and an incorrect NPU warm-up answer remain visible in the notebook output.
