# Raspberry Pi setup for Comparing Processor Architectures

This guide covers the Raspberry Pi 5, its built-in VideoCore VII GPU, and the
AI HAT+ 2 with Hailo-10H used in [notebook 05.xx](../../../02_Notebooks/05_Mobile_AI/05.xx_Comparing_Processor_Architectures.ipynb).
It includes the installation and troubleshooting steps from 30 September 2026.
Commands labelled “Pi” run in a Pi terminal or an SSH session. Commands labelled
“notebook computer” run on the computer hosting VS Code.

## 1. Install the operating system on an SD card

Use Raspberry Pi OS 64-bit based on Debian Trixie. The Raspberry Pi image includes
the repositories and hardware support used by the Hailo packages [\[01\]](#ref-01),
[\[04\]](#ref-04).

On the notebook computer, open Raspberry Pi Imager and select Raspberry Pi 5,
Raspberry Pi OS 64-bit, and the SD card in the USB reader. Writing the image erases
the selected card, so check its capacity and device name before starting.
Configure the hostname as `raspberrypi`, create the account `cas`, set a password,
and enable SSH. Set the locale, keyboard layout, and time zone during configuration.
Finish writing and verification, eject the card, insert it in the Pi, connect
Ethernet to the router, and boot.

The Pi's network installer previously remained at “Downloading installer:
0/0 MB at 0 KB/s”. The USB SD card reader provides a practical installation path
without depending on that boot-time download. Reimaging is unnecessary once the
installed operating system works.

On the Pi, verify:

```sh
cat /etc/os-release
uname -m
```

The target is Trixie and `aarch64`.

## 2. Establish Ethernet and internet access

On the Pi:

```sh
ip -br address show eth0
ip -4 route
nmcli device status
nmcli connection show
```

The working Ethernet configuration observed on 30 September was
`192.168.88.238/24`, with default gateway `192.168.88.1`. These are local lab
addresses, not values that should be copied onto a different network.
DHCP supplies the address, route, and DNS configuration.

Earlier, `eth0` had `172.31.250.1/24`. That address was on a different subnet from
the router. An interface showing `UP` confirms its administrative state; it does
not establish usable routing or internet access.

If the Ethernet connection still has the old static configuration, run the
following from the Pi's keyboard and monitor. Activating a changed connection
can interrupt SSH. Substitute the connection name shown by `nmcli` if different:

```sh
sudo nmcli connection modify "Wired connection 1" \
  ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.dns "" \
  ipv4.ignore-auto-dns no ipv4.never-default no connection.autoconnect yes
sudo nmcli connection up "Wired connection 1"
```

These NetworkManager profile settings persist after reboot. A DHCP address can
change; a router DHCP reservation can keep the same address if needed. Obtain
the Ethernet MAC address with `cat /sys/class/net/eth0/address`. Ethernet and
Wi-Fi have different MAC addresses [\[03\]](#ref-03).

Check routing, DNS, and HTTPS separately:

```sh
ip -4 route
ping -c 3 192.168.88.1
getent hosts deb.debian.org
curl -I --connect-timeout 10 --max-time 20 https://deb.debian.org
```

Use the actual gateway from `ip -4 route` for the ping. A failed ping alone does
not establish that internet access is unavailable, because ICMP can be filtered.

## 3. Fix hostname resolution and enable SSH

On the Pi:

```sh
sudo hostnamectl set-hostname raspberrypi
sudo apt update
sudo apt install avahi-daemon openssh-server
sudo systemctl enable --now avahi-daemon ssh
```

The hostname must also resolve locally. Open `/etc/hosts` with `sudo nano /etc/hosts`
and ensure these entries exist, preserving the other entries:

```text
127.0.0.1 localhost
127.0.1.1 raspberrypi
```

This fixes the local `unable to resolve host raspberrypi` warning. Avahi provides
the separate `raspberrypi.local` name for other machines on the LAN [\[02\]](#ref-02).

The current Pi's `/etc/hosts` says it is managed by cloud-init. If that comment is
present, prevent cloud-init from replacing the chosen hostname and hosts entries
on subsequent boots. Create `/etc/cloud/cloud.cfg.d/99-local-hostname.cfg` with:

```yaml
preserve_hostname: true
manage_etc_hosts: false
```

Check on the Pi:

```sh
hostname
getent hosts raspberrypi
systemctl is-active avahi-daemon ssh
```

Then, on the notebook computer:

```sh
ping -c 3 raspberrypi.local
ssh cas@raspberrypi.local
```

If the `.local` name fails but the IP address works, check Avahi and that both
machines are on the same LAN. Guest-network isolation, VPNs, and multicast
filtering can prevent discovery. The router's client list or the Pi's local
`ip -br address` output can establish its current IP address.

### An SSH host key changed after reimaging

A newly written OS image normally has new SSH host keys. Paramiko correctly
rejects a changed key with `BadHostKeyException`.
On the Pi's keyboard and monitor, obtain the new fingerprint:

```sh
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

After comparing that fingerprint with the key presented by SSH, remove the old
entry on the notebook computer and reconnect:

```sh
ssh-keygen -R raspberrypi.local
ssh cas@raspberrypi.local
```

If an IP address was also used for SSH, remove its stale entry separately after
the same verification. The notebook uses the system's verified `known_hosts`
file; changing the code to ignore mismatched keys is unnecessary.

## 4. Resolve locale warnings

The earlier warnings about `LC_CTYPE` and `LC_ALL` indicate an unavailable locale.
On the Pi:

```sh
locale
locale -a
sudo dpkg-reconfigure locales
```

Select `en_US.UTF-8 UTF-8` and choose `en_US.UTF-8` as the default, or use another
UTF-8 locale consistently. Then:

```sh
sudo update-locale LANG=en_US.UTF-8
```

Log out and reconnect before running `locale` again. The working Pi now reports
`LANG=en_US.UTF-8` and an unset `LC_ALL`. A permanent `LC_ALL` override is not
needed. If only SSH sessions show the warning, inspect locale variables forwarded
by the notebook computer. A macOS client can forward an unsupported
`LC_CTYPE=UTF-8`; use a generated locale or disable that forwarding for this host.

## 5. Update the Pi and install CPU/GPU tools

On the Pi, with internet access established:

```sh
sudo apt update
sudo apt full-upgrade
sudo apt install python3-numpy python3-threadpoolctl libopenblas0-pthread \
  build-essential cmake git curl ca-certificates \
  libvulkan-dev vulkan-tools glslang-tools glslc spirv-headers libssl-dev
```

Threaded OpenBLAS matters: the earlier reference BLAS installation did not expose
a controllable thread pool. Installing `libopenblas0-pthread` enabled a verified
four-thread NumPy baseline. Check it with:

```sh
python3 - <<'PY'
import numpy as np
from threadpoolctl import threadpool_info, threadpool_limits
with threadpool_limits(limits=4, user_api="blas"):
    a = np.ones((16, 16), dtype=np.float32)
    a @ a
    print(threadpool_info())
PY
```

Check GPU access:

```sh
vulkaninfo --summary
```

Look for the Broadcom `V3D 7.1.10.2` device and V3DV driver. `llvmpipe` is CPU
software rendering and must not be labelled a hardware GPU result. No external
GPU is required for the notebook's Vulkan matrix experiment [\[05\]](#ref-05).

The Pi-only matrix comparison needs `g++` with OpenMP support (`-fopenmp`),
NumPy, threadpoolctl, Vulkan development libraries, and `glslangValidator`.
It runs tiled C++ with one and four CPU threads, four-thread BLAS, and Vulkan. Building llama.cpp additionally required `glslc`,
`spirv-headers`, and the TLS development library. These missing build dependencies
were resolved during this setup.

## 6. Install and verify the AI HAT+ 2

Shut down the Pi, disconnect power, and attach the AI HAT+ 2 according to its
assembly guide, including the PCIe ribbon cable. Provide cooling compatible with
the HAT. Reconnect power and boot [\[06\]](#ref-06).

On the Pi:

```sh
sudo apt install dkms hailo-h10-all python3-h10-hailort hailo-models
sudo reboot
```

The AI HAT+ 2 uses `hailo-h10-all`. The older `hailo-all` package targets Hailo-8
devices and cannot coexist with this stack. HailoRT, the driver, and compiled
models must have compatible versions [\[04\]](#ref-04).

After reconnecting:

```sh
lspci -nn
hailortcli fw-control identify
python3 -c 'import hailo_platform; print(hailo_platform.__version__)'
ls /dev/hailo*
ls /usr/share/hailo-models/resnet_v1_50_h10.hef
```

The observed PCI device is `Hailo-10H AI Processor [1e60:45c4]`, at
`0001:01:00.0`. Inspect that address with:

```sh
sudo lspci -s 0001:01:00.0 -vv
```

`0b40` in the original `lspci` output is a device class, not a slot address.
Using `-s 0b40` therefore fails. `LnkSta` reports the negotiated PCIe link;
`LnkCap` reports capability. Automatic Gen 3 setup for AI HAT+ 2 follows the
official configuration; the manual AI Kit procedure should not be copied
indiscriminately [\[04\]](#ref-04).

PCIe detection can succeed before HailoRT is installed. “NPU runtime unavailable”
at that stage means software setup is incomplete; it does not by itself indicate
a defective HAT.

## 7. Prepare the notebook computer

Open notebook 05.xx in VS Code and select the intended Python kernel. Install
these packages in that kernel environment if missing:

```python
%pip install -q numpy pandas matplotlib paramiko threadpoolctl ipywidgets
```

This command belongs in a notebook cell, not a Pi shell. The Pi workers use the
Pi's system Python and its `apt` packages. The section 3.1 helper installs
Paramiko quietly if needed and then connects with the local SSH key.

Keep `.admin/notebooks/cpu_gpu_npu` in the checkout. It contains the inventory
script, benchmark workers, animations, and image assets. Run section 3.1 to
confirm SSH, CPU, GPU, NPU, runtime, and throttling status.

## 8. Install Qwen2 for the LLM experiment

The experiment uses Qwen2-1.5B-Instruct. CPU and GPU share one Q4_0 GGUF file;
the NPU needs Hailo's compatible HEF model. A GGUF file cannot be passed directly
to the Hailo runtime [\[07\]](#ref-07), [\[08\]](#ref-08).

### CPU and Vulkan runtime

On the Pi, start from a new working directory or reuse the installation already
created there:

```sh
mkdir -p ~/llm-comparison/models ~/llm-comparison/logs
cd ~/llm-comparison
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
git checkout 876c75b1f63d1567532fd4300fc5777549619d63
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON -DLLAMA_BUILD_TESTS=ON
cmake --build build --target llama-server llama-cli llama-bench test-backend-ops -j 4
```

The checkout command establishes the revision used for this experiment. If the
directory already exists, inspect it before changing revisions. Compilation
takes time and can heat the Pi; benchmark after it finishes and the Pi cools.

Download the official Qwen file [\[07\]](#ref-07):

```sh
cd ~/llm-comparison
curl -fL --retry 3 \
  https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF/resolve/c62434db644497c0ee545c690bb66a67eba6eb3f/qwen2-1_5b-instruct-q4_0.gguf \
  -o models/qwen2-1_5b-instruct-q4_0.gguf
sha256sum models/qwen2-1_5b-instruct-q4_0.gguf
```

Expected SHA-256:
`106c176ae807b164f16e2898e8f0267062e3c93c3c18c8267cf9e4ee90766beb`.

The installed Vulkan build successfully offloads all 29 model layers on this Pi.
The worker checks offload and generated output on each run. Failed startup or
generation is reported with its diagnostic.

### Hailo runtime and model

The Pi currently uses HailoRT 5.1.1, so install the matching GenAI package linked
by Raspberry Pi [\[04\]](#ref-04):

```sh
cd ~/llm-comparison
curl -fLO https://dev-public.hailo.ai/2025_12/Hailo10/hailo_gen_ai_model_zoo_5.1.1_arm64.deb
sudo apt install ./hailo_gen_ai_model_zoo_5.1.1_arm64.deb
```

For a temporary local server, create `~/llm-comparison/config/hailo-ollama/hailo-ollama.json`
with the following contents:

```json
{
  "server": {"host": "127.0.0.1", "port": 8000},
  "library": {"host": "dev-public.hailo.ai", "port": 443},
  "main_poll_time_ms": 200
}
```

Create the parent directory first with
`mkdir -p ~/llm-comparison/config/hailo-ollama`. Start the server in one Pi terminal:

```sh
XDG_CONFIG_HOME="$HOME/llm-comparison/config" hailo-ollama
```

Version 5.1.1 uses this configuration file. Newer Hailo documentation also
describes `OLLAMA_HOST`, which is not the configuration method used here.

In a second Pi terminal:

```sh
curl -s http://127.0.0.1:8000/hailo/v1/list
curl --fail --silent --show-error http://127.0.0.1:8000/api/pull \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2:1.5b","stream":false}'
curl -s http://127.0.0.1:8000/api/tags
```

The model download is about 1.6 GB. The server stores it under
`/usr/share/hailo-ollama/models/blob/`. Verify generation:

```sh
curl --fail --silent --show-error http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2:1.5b","messages":[{"role":"user","content":"What is the capital of France?"}],"stream":true,"options":{"temperature":0,"num_predict":32}}'
```

Stop the temporary server with Ctrl+C before running the notebook benchmark.
The benchmark starts and stops its own local servers, uses the same prompts on
each available processor, and retains generated answers and timing records.
Hailo 5.1.1 rejects a zero `frequency_penalty`; its neutral multiplicative value
is `1.0`, unlike the additive penalty convention used by llama.cpp.

No separate browser interface or Docker installation is needed for the notebook.
Installation details, hashes, and the standalone worker command are also recorded
in [the implementation notes](LLM_SETUP.md).

## 9. Check temperature and preserve a working installation

On the Pi:

```sh
vcgencmd measure_temp
vcgencmd get_throttled
```

Compilation raised the Pi into its thermal-limit range during this setup.
The LLM worker waits for cooling and records current flags during the experiment.
`0x0` means no flags. Higher historical bits can remain set after the active
condition has ended, so a nonzero value does not always mean current throttling.
The recorded JSON keeps both the raw value and the current low four bits.

After the notebook hardware checks and experiments work, shut down cleanly with
`sudo poweroff`. An SD card backup can then preserve the configured installation.
Keep benchmark results separately from an image of the operating system. A restored
image retains its hostname and SSH keys, which matters if multiple copies run on
the same network.

## References

- <a id="ref-01"></a>\[01\] Raspberry Pi. [Getting started](https://www.raspberrypi.com/documentation/computers/getting-started.html). OS installation and boot media. Accessed 30 September 2026.
- <a id="ref-02"></a>\[02\] Raspberry Pi. [Remote access](https://www.raspberrypi.com/documentation/computers/remote-access.html). SSH and local hostname discovery. Accessed 30 September 2026.
- <a id="ref-03"></a>\[03\] Raspberry Pi. [Configuration](https://www.raspberrypi.com/documentation/computers/configuration.html). Network and system configuration. Accessed 30 September 2026.
- <a id="ref-04"></a>\[04\] Raspberry Pi. [AI software](https://www.raspberrypi.com/documentation/computers/ai.html). Hailo-10H drivers and LLM setup. Accessed 30 September 2026.
- <a id="ref-05"></a>\[05\] Mesa. [V3D and V3DV](https://docs.mesa3d.org/drivers/v3d.html). Driver documentation. Accessed 30 September 2026.
- <a id="ref-06"></a>\[06\] Raspberry Pi. [AI HATs](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html). Hardware assembly and compatibility. Accessed 30 September 2026.
- <a id="ref-07"></a>\[07\] Qwen Team. [Qwen2-1.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF). Official model repository, revision `c62434db644497c0ee545c690bb66a67eba6eb3f`. Accessed 30 September 2026.
- <a id="ref-08"></a>\[08\] Hailo. [Hailo Model Zoo GenAI](https://github.com/hailo-ai/hailo_model_zoo_genai/tree/v5.1.1). Runtime source and model manifests, version 5.1.1. Accessed 30 September 2026.
- <a id="ref-09"></a>\[09\] ggml-org. [llama.cpp build instructions](https://github.com/ggml-org/llama.cpp/blob/876c75b1f63d1567532fd4300fc5777549619d63/docs/build.md). CPU and Vulkan build, pinned revision. Accessed 30 September 2026.

## Password-free notebook connections

The notebook now uses SSH key authentication for its dashboard and benchmarks.
Authorize the notebook host's public SSH key in `~/.ssh/authorized_keys` for
`cas` on the Pi. Keep the private key on the notebook host. The Pi's `.ssh`
directory should have permissions `700`, and `authorized_keys` permissions `600`.
Existing authorized keys should be preserved. Verify the setup from the notebook
host with:

```sh
ssh -o BatchMode=yes cas@raspberrypi.local hostname
```

Paramiko looks for the default local SSH keys and keys available through the SSH
agent. Unlock a passphrase-protected key in the agent before running the notebook.
The fan switch uses the separately installed fan-only helper described below.

## Password-free fan switch

The configured Pi has a root-owned helper at
`/usr/local/libexec/mobilecomputing-pi-fan`, installed from `pi_fan_worker.py`.
Its directory and file are owned by root and are not writable by `cas`.
The helper uses Python isolated mode and accepts only the fixed fan protocol
on standard input. It keeps automatic thermal control enabled.

`/etc/sudoers.d/mobilecomputing-pi-fan` contains this rule, validated with `visudo`:

```sudoers
cas ALL=(root) NOPASSWD: /usr/local/libexec/mobilecomputing-pi-fan ""
```

The empty argument string restricts access to running the helper without
command-line arguments. The notebook invokes it with `sudo -n`, so the switch
never requests a password. Other administrator commands retain their existing
authentication policy. Helper updates require installation as root; changing the
repository copy alone does not update the installed helper.

## Matched ResNet-50 classification (section 4.3)

Installed and verified on 1 October 2026 with HailoRT 5.1.1 and
`hailo-models` 1.0.0-2. The CPU and GPU use a separate LiteRT environment;
its system-site access preserves the installed Hailo Python bindings.
On the Pi:

```sh
sudo apt install python3-venv python3-pil unzip
mkdir -p ~/neural-comparison/models
python3 -m venv --system-site-packages ~/neural-comparison/venv
~/neural-comparison/venv/bin/pip install ai-edge-litert==2.2.0 \
  backports.strenum==1.2.8 flatbuffers==25.12.19 ml_dtypes==0.6.0 protobuf==7.36.2
cd ~/neural-comparison/models
curl --fail --location --output resnet_v1_50.zip \
  https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/Classification/resnet_v1_50/pretrained/2025-01-15/resnet_v1_50.zip
unzip -j resnet_v1_50.zip '*.tflite'
curl --fail --location --output dog.jpg \
  https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg
curl --fail --location --output imagenet_classes.txt \
  https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt
```

The model archive SHA256 is
`33eaf6896f9fb4876375d53eb12e32a90a12055d86c541f76361817d3aa8d5ad`.
The worker verifies exact hashes for the extracted TFLite model, photograph,
labels, and installed `/usr/share/hailo-models/resnet_v1_50_h10.hef` before
measuring. A changed artifact stops the run for review. The verified environment
used NumPy 2.2.4, Pillow 11.1.0, and Mesa 26.2.2.

The helper enables the experimental V3D WebGPU path and explicitly selects
`/usr/share/vulkan/icd.d/broadcom_icd.json`. It requires full GPU acceleration
and measured V3D engine activity; software fallback is rejected. CPU/GPU run
FP32; the NPU runs the compiled quantized model. Each receives the same RGB
input, with equivalent channel-mean subtraction. The notebook cell uploads the
worker, runs all three processors, and saves the results on the notebook computer.

Sources: [Hailo ResNet-50 configuration](https://github.com/hailo-ai/hailo_model_zoo/blob/master/hailo_model_zoo/cfg/networks/resnet_v1_50.yaml),
[LiteRT Python API](https://developers.google.com/edge/litert/next/python), and
[Raspberry Pi LiteRT GPU setup](https://www.raspberrypi.com/news/get-started-with-litert-on-raspberry-pi/).

The ResNet-50 CPU comparison includes one LiteRT thread pinned to one core and four LiteRT threads allowed across four cores. CPU affinity is restored before GPU/NPU execution. Both CPU outputs and the GPU output are checked against the one-core reference.
