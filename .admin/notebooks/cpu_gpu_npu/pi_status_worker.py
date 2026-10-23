"""Read-only Pi telemetry; standard library only, no root privileges required."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None


def npu_monitor():
    if not shutil.which("hailortcli"):
        return {"percent": None, "detail": "HailoRT is not installed"}
    process = subprocess.Popen(["hailortcli", "monitor"], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    try:
        output, _ = process.communicate(timeout=1.2)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "\n", output)
    # Parse the device table, not model FPS or process CPU utilization.
    matches = re.findall(r"^\s*(\S+)\s+(\d+(?:\.\d+)?)\s+(HAILO\S*)\s*$", output, re.M | re.I)
    if matches:
        device, value, architecture = matches[-1]
        return {"percent": float(value), "detail": f"Hailo monitor: {device}, {architecture}"}
    return {"percent": None,
            "detail": "No Hailo utilization sample. The application must support HAILO_MONITOR=1."}


def collect():
    sample = {"wall_time": time.time(), "monotonic": time.monotonic(),
              "hostname": read("/etc/hostname"), "gpu_clients": {}, "npu_clients": []}
    stat = read("/proc/stat").splitlines()[0].split()[1:9]
    sample["cpu_ticks"] = [int(v) for v in stat]  # Exclude guest ticks counted in user/nice.
    sample["cpu_count"] = os.cpu_count()
    temperature = read("/sys/class/thermal/thermal_zone0/temp")
    sample["temperature_c"] = float(temperature) / 1000 if temperature else None
    usage = shutil.disk_usage("/")
    sample["storage"] = {"total": usage.total, "used": usage.used, "free": usage.free}
    memory = dict(re.findall(r"^(\w+):\s+(\d+)", read("/proc/meminfo"), re.M))
    sample["memory"] = {key: int(memory[key]) * 1024 for key in ("MemTotal", "MemAvailable")}
    sample["fans"] = []
    for hwmon in Path("/sys/class/hwmon").glob("hwmon*"):
        for rpm_file in hwmon.glob("fan*_input"):
            rpm = read(rpm_file)
            pwm = read(hwmon / "pwm1")
            sample["fans"].append({"name": read(hwmon / "name"),
                                   "rpm": int(rpm) if rpm is not None else None,
                                   "pwm": int(pwm) if pwm is not None else None})
    sample["process_visibility_limited"] = False
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                sample["process_visibility_limited"] = True
                continue
            npu_open = False
            for fd in (proc / "fd").iterdir():
                try:
                    target = os.readlink(fd)
                    if target.startswith("/dev/hailo"):
                        npu_open = True
                    if not target.startswith("/dev/dri/"):
                        continue
                    info = read(proc / "fdinfo" / fd.name) or ""
                    if not re.search(r"drm-driver:\s*v3d\b", info):
                        continue
                    client = re.search(r"drm-client-id:\s*(\d+)", info)
                    if client:
                        engines = re.findall(r"drm-engine-([\w-]+):\s*(\d+)\s+ns", info)
                        # A DRM client can have duplicate FDs; count its counters once.
                        sample["gpu_clients"][client[1]] = {k: int(v) for k, v in engines}
                except OSError:
                    continue
            if npu_open:
                sample["npu_clients"].append({"pid": int(proc.name), "name": read(proc / "comm")})
        except (OSError, ProcessLookupError):
            continue
    sample["npu"] = npu_monitor()
    if shutil.which("vcgencmd"):
        sample["throttling"] = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                                               text=True, timeout=3).stdout.strip()
    return sample


if __name__ == "__main__":
    print(json.dumps(collect()))
