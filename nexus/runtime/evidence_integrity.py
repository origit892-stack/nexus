from __future__ import annotations

import json
import re


SUMMARY_PREFIX = (
    "NEXUS_EVIDENCE_SUMMARY="
)


def extract_summary(
    result,
):
    text = str(
        result or ""
    )

    index = text.rfind(
        SUMMARY_PREFIX
    )

    if index < 0:
        return None

    raw = text[
        index
        + len(SUMMARY_PREFIX):
    ].strip()

    # Summary is one JSON object at the end.
    try:
        return json.loads(
            raw
        )

    except Exception:
        line = raw.splitlines()[0]

        try:
            return json.loads(
                line
            )

        except Exception:
            return None


def task_requires_independent_evidence(
    role,
    objective,
    acceptance,
):
    if role != "qa":
        return False

    text = (
        str(objective)
        + "\n"
        + "\n".join(
            str(x)
            for x in (
                acceptance
                or []
            )
        )
    ).lower()

    markers = (
        "independent",
        "independently",
        "verify",
        "verification",
        "confirm",
        "validate",
    )

    return any(
        marker in text
        for marker in markers
    )


def independent_evidence_passed(
    role,
    objective,
    acceptance,
    result,
):
    if not task_requires_independent_evidence(
        role,
        objective,
        acceptance,
    ):
        return (
            True,
            "NOT_REQUIRED",
        )

    summary = extract_summary(
        result
    )

    if summary is None:
        return (
            False,
            "EVIDENCE_SUMMARY_MISSING",
        )

    successful = [
        item
        for item in summary.get(
            "tools",
            []
        )
        if item.get(
            "success"
        )
    ]

    # acceptance_verify is not itself independent source evidence.
    source_tools = [
        item
        for item in successful
        if item.get(
            "tool"
        )
        not in {
            "acceptance_verify",
            "memory_search",
            "memory_add",
        }
    ]

    if not source_tools:
        return (
            False,
            "INDEPENDENT_SOURCE_EVIDENCE_MISSING",
        )

    return (
        True,
        "INDEPENDENT_SOURCE_EVIDENCE_PRESENT",
    )
