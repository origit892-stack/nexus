from __future__ import annotations

import re


INTERNAL_MARKERS = (
    "NEXUS_EVIDENCE_SUMMARY=",
    "NEXUS_TIMING_SUMMARY=",
    "NEXUS_EVIDENCE_INTEGRITY=",
    "NEXUS_NODE_COMPLETION=",
    "NODE_COMPLETION_REASON=",
)


def strip_internal_metadata(
    text,
):
    text = str(
        text or ""
    )

    cut = len(text)

    for marker in INTERNAL_MARKERS:
        pos = text.find(
            marker
        )

        if (
            pos >= 0
            and pos < cut
        ):
            cut = pos

    return text[
        :cut
    ].strip()


def compact_result(
    text,
    limit=1800,
):
    text = strip_internal_metadata(
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    ).strip()

    if len(text) <= limit:
        return text

    return (
        text[:limit]
        + "\n[HANDOFF_TRUNCATED]"
    )


def build_dependency_handoff(
    dependencies,
):
    if not dependencies:
        return ""

    blocks = []

    for item in dependencies:
        task_id = str(
            item.get(
                "task_id",
                "",
            )
        )

        role = str(
            item.get(
                "role",
                "",
            )
        )

        status = str(
            item.get(
                "status",
                "",
            )
        )

        result = compact_result(
            item.get(
                "result",
                "",
            )
        )

        blocks.append(
            f"TASK={task_id}\n"
            f"ROLE={role}\n"
            f"STATUS={status}\n"
            f"FINDING:\n{result}"
        )

    return (
        "\n\nDEPENDENCY HANDOFF\n"
        "These are predecessor outputs. "
        "Use them as claims to verify, not as "
        "independent evidence.\n\n"
        + "\n\n---\n\n".join(
            blocks
        )
    )
