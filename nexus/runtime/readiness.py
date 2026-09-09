from __future__ import annotations

import json
import shutil
import urllib.request
from dataclasses import dataclass, asdict

from nexus.runtime.vision_models import (
    ollama_models,
    select_vision_model,
)


@dataclass
class RequirementStatus:
    name: str
    required: bool
    passed: bool
    detail: str


@dataclass
class RuntimeReadiness:
    ready: bool
    requirements: list[RequirementStatus]

    def as_dict(self):
        return {
            "ready": self.ready,
            "requirements": [
                asdict(x)
                for x in self.requirements
            ],
        }


def ollama_available():
    if shutil.which(
        "ollama"
    ) is None:
        return False

    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags",
            timeout=5,
        ) as response:
            return (
                response.status
                == 200
            )

    except Exception:
        return False


def text_model_available(
    configured_model,
):
    if not configured_model:
        return False

    try:
        names = {
            str(x)
            for x in ollama_models()
        }

    except Exception:
        return False

    configured = str(
        configured_model
    )

    base = configured.split(
        ":",
        1,
    )[0]

    return any(
        (
            name == configured
            or name.split(
                ":",
                1,
            )[0] == base
        )
        for name in names
    )


def runtime_readiness(
    configured_text_model,
):
    requirements = []

    ollama_ok = (
        ollama_available()
    )

    requirements.append(
        RequirementStatus(
            name="ollama",
            required=True,
            passed=ollama_ok,
            detail=(
                "available"
                if ollama_ok
                else "missing_or_unreachable"
            ),
        )
    )

    text_ok = (
        ollama_ok
        and text_model_available(
            configured_text_model
        )
    )

    requirements.append(
        RequirementStatus(
            name="text_model",
            required=True,
            passed=text_ok,
            detail=(
                str(
                    configured_text_model
                )
                if text_ok
                else "missing"
            ),
        )
    )

    vision_model = None

    if ollama_ok:
        try:
            vision_model = (
                select_vision_model(
                    ollama_models()
                )
            )
        except Exception:
            vision_model = None

    vision_ok = bool(
        vision_model
    )

    requirements.append(
        RequirementStatus(
            name="vision_model",
            required=False,
            passed=vision_ok,
            detail=(
                str(
                    vision_model
                )
                if vision_ok
                else "missing"
            ),
        )
    )

    ready = all(
        item.passed
        for item in requirements
        if item.required
    )

    return RuntimeReadiness(
        ready=ready,
        requirements=requirements,
    )


def readiness_lines(
    readiness,
):
    lines = []

    for item in (
        readiness.requirements
    ):
        key = (
            item.name.upper()
        )

        lines.append(
            f"{key}="
            + (
                "PASS"
                if item.passed
                else "FAIL"
            )
        )

        lines.append(
            f"{key}_DETAIL="
            f"{item.detail}"
        )

    lines.append(
        "NEXUS_RUNTIME_REQUIREMENTS="
        + (
            "PASS"
            if readiness.ready
            else "FAIL"
        )
    )

    lines.append(
        "NEXUS_READY="
        + (
            "PASS"
            if readiness.ready
            else "NO"
        )
    )

    return lines
