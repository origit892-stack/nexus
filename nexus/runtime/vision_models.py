from __future__ import annotations

import json
import urllib.request


VISION_HINTS = (
    "vl",
    "vision",
    "llava",
    "minicpm-v",
    "moondream",
    "gemma3",
)


def ollama_models(
    base_url="http://127.0.0.1:11434",
):
    with urllib.request.urlopen(
        base_url.rstrip("/")
        + "/api/tags",
        timeout=10,
    ) as response:
        data = json.loads(
            response.read().decode(
                "utf-8"
            )
        )

    return [
        str(
            item.get(
                "name",
                ""
            )
        )
        for item in data.get(
            "models",
            []
        )
        if item.get(
            "name"
        )
    ]


def select_vision_model(
    models,
):
    lowered = [
        (
            model,
            model.lower(),
        )
        for model in models
    ]

    preferred = (
        "qwen3-vl",
        "qwen2.5vl",
        "qwen2.5-vl",
        "qwen-vl",
        "gemma3",
        "llava",
        "minicpm-v",
        "moondream",
    )

    for prefix in preferred:
        for original, low in lowered:
            if prefix in low:
                return original

    for original, low in lowered:
        if any(
            hint in low
            for hint in VISION_HINTS
        ):
            return original

    return None
