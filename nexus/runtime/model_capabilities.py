from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.request

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ModelCapability:
    provider: str
    model: str
    local: bool
    available: bool

    structured_output: bool = False
    tool_calling: bool = False
    reasoning: bool = False
    coding: bool = False

    context_hint: int | None = None
    path: str | None = None
    detail: str = ""

    def to_dict(self):
        return asdict(self)


def _ollama_tags(
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 2.0,
):
    try:
        with urllib.request.urlopen(
            base_url.rstrip("/")
            + "/api/tags",
            timeout=timeout,
        ) as response:
            payload = json.load(response)
    except Exception:
        return []

    result = []

    for item in payload.get(
        "models",
        [],
    ):
        name = (
            item.get("name")
            or item.get("model")
            or ""
        )

        if name:
            result.append(name)

    return result


def _infer(
    provider: str,
    name: str,
    *,
    path: str | None = None,
):
    lower = name.lower()

    reasoning = any(
        token in lower
        for token in (
            "deepseek",
            "reason",
            "gpt-oss",
            "qwen3",
        )
    )

    coding = any(
        token in lower
        for token in (
            "coder",
            "code",
            "devstral",
        )
    )

    structured = provider == "ollama"

    tools = (
        provider == "ollama"
        and any(
            token in lower
            for token in (
                "qwen",
                "llama",
                "mistral",
                "gpt-oss",
                "deepseek",
            )
        )
    )

    return ModelCapability(
        provider=provider,
        model=name,
        local=True,
        available=True,
        structured_output=structured,
        tool_calling=tools,
        reasoning=reasoning,
        coding=coding,
        path=path,
    )


def discover_models(
    nexus_home: Path | None = None,
):
    nexus_home = (
        nexus_home
        or Path.home() / ".nexus"
    )

    found = []

    for name in _ollama_tags():
        found.append(
            _infer(
                "ollama",
                name,
            )
        )

    model_root = (
        nexus_home
        / "models"
    )

    if model_root.is_dir():
        for child in model_root.iterdir():
            if not child.is_dir():
                continue

            config = child / "config.json"
            tokenizer = child / "tokenizer.json"

            if (
                config.is_file()
                and tokenizer.is_file()
            ):
                found.append(
                    _infer(
                        "mlx-local",
                        child.name,
                        path=str(child),
                    )
                )

    unique = {}

    for item in found:
        key = (
            item.provider,
            item.model,
        )

        unique[key] = item

    return list(
        unique.values()
    )


def select_model(
    models: Iterable[ModelCapability],
    *,
    require_structured: bool = False,
    require_tools: bool = False,
    prefer_reasoning: bool = False,
    prefer_coding: bool = False,
):
    candidates = [
        model
        for model in models
        if model.available
    ]

    if require_structured:
        candidates = [
            model
            for model in candidates
            if model.structured_output
        ]

    if require_tools:
        candidates = [
            model
            for model in candidates
            if model.tool_calling
        ]

    def score(model):
        value = 0

        if prefer_reasoning and model.reasoning:
            value += 8

        if prefer_coding and model.coding:
            value += 8

        if model.structured_output:
            value += 3

        if model.tool_calling:
            value += 3

        if model.provider == "mlx-local":
            value += 2

        return value

    candidates.sort(
        key=score,
        reverse=True,
    )

    return (
        candidates[0]
        if candidates
        else None
    )


def environment_capabilities():
    return {
        "platform": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "ollama": shutil.which("ollama"),
        "brew": shutil.which("brew"),
        "git": shutil.which("git"),
        "mlx_expected": (
            platform.system() == "Darwin"
            and platform.machine() in {
                "arm64",
                "aarch64",
            }
        ),
    }
