from __future__ import annotations

import subprocess

from nexus.runtime.readiness import (
    RuntimeReadiness,
)


VISION_CANDIDATES = (
    "qwen3-vl",
    "qwen2.5vl",
    "qwen2.5-vl",
)


def missing_required(
    readiness: RuntimeReadiness,
):
    return [
        item.name
        for item in readiness.requirements
        if (
            item.required
            and not item.passed
        )
    ]


def remediation_text(
    readiness,
):
    missing = missing_required(
        readiness
    )

    if not missing:
        return (
            "NEXUS_READY=PASS"
        )

    lines = [
        "NEXUS_READY=NO",
        "MISSING_REQUIREMENTS="
        + ",".join(
            missing
        ),
    ]

    if (
        "vision_model"
        in missing
    ):
        lines.extend(
            [
                (
                    "RECOMMENDED_VISION_MODEL="
                    "qwen3-vl"
                ),
                (
                    "INSTALL_COMMAND="
                    "ollama pull qwen3-vl"
                ),
            ]
        )

    return "\n".join(
        lines
    )


def install_vision_model():
    errors = []

    for model in (
        VISION_CANDIDATES
    ):
        result = subprocess.run(
            [
                "ollama",
                "pull",
                model,
            ],
            text=True,
        )

        if result.returncode == 0:
            return model

        errors.append(
            model
        )

    raise RuntimeError(
        "VISION_MODEL_INSTALL_FAILED="
        + ",".join(
            errors
        )
    )
