from __future__ import annotations

import json
import time
import urllib.request


OLLAMA = "http://127.0.0.1:11434"


def post(
    path,
    payload,
    timeout=600,
):
    body = json.dumps(
        payload
    ).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA + path,
        data=body,
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    started = time.time()

    with urllib.request.urlopen(
        req,
        timeout=timeout,
    ) as response:
        raw = response.read()

    wall = time.time() - started

    data = json.loads(
        raw.decode("utf-8")
    )

    data["_wall_seconds"] = wall

    return data


def unload(
    model,
):
    return post(
        "/api/generate",
        {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": 0,
        },
    )


def chat(
    model,
    messages,
    *,
    num_predict=64,
    keep_alive="30m",
    tools=None,
):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0,
            "num_predict": int(
                num_predict
            ),
        },
    }

    if tools:
        payload["tools"] = tools

    return post(
        "/api/chat",
        payload,
    )


def metrics(
    result,
):
    billion = 1_000_000_000

    eval_count = int(
        result.get(
            "eval_count",
            0,
        )
        or 0
    )

    eval_duration = int(
        result.get(
            "eval_duration",
            0,
        )
        or 0
    )

    prompt_count = int(
        result.get(
            "prompt_eval_count",
            0,
        )
        or 0
    )

    prompt_duration = int(
        result.get(
            "prompt_eval_duration",
            0,
        )
        or 0
    )

    load_duration = int(
        result.get(
            "load_duration",
            0,
        )
        or 0
    )

    total_duration = int(
        result.get(
            "total_duration",
            0,
        )
        or 0
    )

    generation_tps = (
        eval_count
        / (
            eval_duration
            / billion
        )
        if eval_duration
        else 0.0
    )

    prompt_tps = (
        prompt_count
        / (
            prompt_duration
            / billion
        )
        if prompt_duration
        else 0.0
    )

    return {
        "wall_seconds": round(
            float(
                result.get(
                    "_wall_seconds",
                    0,
                )
            ),
            4,
        ),
        "total_seconds": round(
            total_duration / billion,
            4,
        ),
        "load_seconds": round(
            load_duration / billion,
            4,
        ),
        "prompt_eval_seconds": round(
            prompt_duration / billion,
            4,
        ),
        "prompt_tokens": prompt_count,
        "prompt_tokens_per_second": round(
            prompt_tps,
            2,
        ),
        "generation_seconds": round(
            eval_duration / billion,
            4,
        ),
        "generation_tokens": eval_count,
        "generation_tokens_per_second": round(
            generation_tps,
            2,
        ),
    }
