import platform
import subprocess
import psutil


def _sysctl(name):
    try:
        r = subprocess.run(
            ["sysctl", "-n", name],
            text=True,
            capture_output=True,
            timeout=5,
        )

        if r.returncode == 0:
            return r.stdout.strip()

    except Exception:
        pass

    return ""


def detect():
    system = platform.system()
    machine = platform.machine()

    memory_gb = round(
        psutil.virtual_memory().total / (1024 ** 3),
        1,
    )

    chip = ""

    if system == "Darwin":
        chip = _sysctl(
            "machdep.cpu.brand_string"
        )

        if not chip:
            try:
                r = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    text=True,
                    capture_output=True,
                    timeout=15,
                )

                for line in r.stdout.splitlines():
                    if "Chip:" in line:
                        chip = line.split(
                            "Chip:",
                            1,
                        )[1].strip()
                        break

            except Exception:
                pass

    return {
        "system": system,
        "machine": machine,
        "chip": chip or machine,
        "memory_gb": memory_gb,
    }


def select_profile(hardware, manifest):
    memory = hardware["memory_gb"]

    profiles = manifest[
        "hardware_profiles"
    ]

    for name in [
        "tiny",
        "small",
        "medium",
        "large",
        "huge",
    ]:
        profile = profiles[name]

        if memory <= profile["max_memory_gb"]:
            return name, profile

    return "huge", profiles["huge"]
