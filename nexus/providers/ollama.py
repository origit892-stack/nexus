import platform
import shutil
import subprocess
import time
from pathlib import Path

import httpx

from ..config import GLOBAL_CONFIG, save_yaml
from ..hardware import detect, select_profile


API = "http://127.0.0.1:11434"


def ollama_exists():
    return shutil.which("ollama") is not None


def api_alive():
    try:
        r = httpx.get(
            f"{API}/api/tags",
            timeout=2,
        )

        return r.status_code == 200

    except Exception:
        return False


def install_ollama():
    if ollama_exists():
        return

    print("Ollama is not installed.")

    answer = input(
        "Install Ollama automatically? [Y/n] "
    ).strip().lower()

    if answer not in {
        "",
        "y",
        "yes",
    }:
        raise RuntimeError(
            "OLLAMA_INSTALL_DECLINED"
        )

    if (
        platform.system() == "Darwin"
        and shutil.which("brew")
    ):
        subprocess.run(
            ["brew", "install", "ollama"],
            check=True,
        )

        return

    raise RuntimeError(
        "Automatic Ollama installation currently "
        "requires macOS + Homebrew."
    )


def ensure_server():
    if api_alive():
        return

    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(30):
        if api_alive():
            return

        time.sleep(0.5)

    raise RuntimeError(
        "OLLAMA_SERVER_START_FAILED"
    )


def list_models():
    r = httpx.get(
        f"{API}/api/tags",
        timeout=10,
    )

    r.raise_for_status()

    return [
        x.get("name", "")
        for x in r.json().get(
            "models",
            [],
        )
    ]


def choose_existing(installed, manifest):
    lower = {
        x.lower(): x
        for x in installed
    }

    for preferred in manifest.get(
        "preferred_existing_models",
        [],
    ):
        if preferred.lower() in lower:
            return lower[
                preferred.lower()
            ]

    qwen = [
        x
        for x in installed
        if "qwen" in x.lower()
    ]

    if not qwen:
        return None

    qwen.sort(
        key=lambda x: (
            "nexus" not in x.lower(),
            "bunker" not in x.lower(),
            "hermes" not in x.lower(),
            len(x),
        )
    )

    return qwen[0]


def pull_model(model):
    print(
        f"Qwen is not installed. "
        f"Recommended model: {model}"
    )

    answer = input(
        "Download it now? [Y/n] "
    ).strip().lower()

    if answer not in {
        "",
        "y",
        "yes",
    }:
        raise RuntimeError(
            "MODEL_DOWNLOAD_DECLINED"
        )

    subprocess.run(
        ["ollama", "pull", model],
        check=True,
    )


def create_profile(
    base_model,
    context_length,
):
    profile = "nexus-qwen"

    modelfile = (
        f"FROM {base_model}\n"
        f"PARAMETER num_ctx {context_length}\n"
        "PARAMETER temperature 0.10\n"
        "PARAMETER top_p 0.90\n"
        "PARAMETER repeat_penalty 1.05\n"
        "SYSTEM You are a precise autonomous agent. "
        "Use tools instead of guessing. "
        "Never fabricate execution evidence. "
        "A stub, mock, placeholder, simulation, "
        "or dry-run never satisfies a criterion "
        "requiring a real implementation.\n"
    )

    path = (
        Path.home()
        / ".nexus"
        / "NexusQwen.Modelfile"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        modelfile,
        encoding="utf-8",
    )

    subprocess.run(
        [
            "ollama",
            "create",
            profile,
            "-f",
            str(path),
        ],
        check=True,
    )

    return profile


def benchmark(model):
    start = time.time()

    r = httpx.post(
        f"{API}/api/chat",
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Reply exactly NEXUS_MODEL_PASS"
                    ),
                }
            ],
            "stream": False,
            "options": {
                "num_predict": 32,
            },
        },
        timeout=120,
    )

    elapsed = time.time() - start

    r.raise_for_status()

    data = r.json()

    return {
        "seconds": round(
            elapsed,
            2,
        ),
        "response": data.get(
            "message",
            {},
        ).get(
            "content",
            "",
        ),
    }


def bootstrap(
    current_cfg,
    manifest,
):
    install_ollama()
    ensure_server()

    hardware = detect()

    profile_name, profile = select_profile(
        hardware,
        manifest,
    )

    installed = list_models()

    existing = choose_existing(
        installed,
        manifest,
    )

    if existing:
        base_model = existing
        downloaded = False

    else:
        base_model = profile[
            "install_model"
        ]

        pull_model(
            base_model
        )

        downloaded = True

    installed = list_models()

    if any(
        x.split(":")[0]
        == "nexus-qwen"
        for x in installed
    ):
        nexus_model = "nexus-qwen"

    else:
        nexus_model = create_profile(
            base_model,
            profile[
                "context_length"
            ],
        )

    result = benchmark(
        nexus_model
    )

    cfg = dict(
        current_cfg
    )

    cfg["provider"] = "ollama"
    cfg["model"] = nexus_model
    cfg["base_url"] = (
        "http://127.0.0.1:11434/v1"
    )
    cfg["context_length"] = profile[
        "context_length"
    ]
    cfg["hardware_profile"] = (
        profile_name
    )

    cfg.setdefault(
        "agents",
        {},
    )["max_parallel"] = profile[
        "max_parallel_agents"
    ]

    save_yaml(
        GLOBAL_CONFIG,
        cfg,
    )

    return {
        "hardware": hardware,
        "profile_name": profile_name,
        "profile": profile,
        "base_model": base_model,
        "model": nexus_model,
        "downloaded": downloaded,
        "benchmark": result,
    }
