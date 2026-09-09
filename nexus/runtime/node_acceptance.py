from __future__ import annotations

import json

from nexus.runtime.evidence_integrity import (
    extract_summary,
)


FAILURE_PHRASES = (
    "could you please specify",
    "please specify",
    "need clarification",
    "requires clarification",
    "cannot complete",
    "can't complete",
    "unable to complete",
    "no specific finding",
    "no finding",
    "nothing to verify",
    "no verification target",
    "task cannot be completed",
    "not produced any specific finding",
)


def evaluate_node_completion(
    role,
    objective,
    acceptance,
    result,
):
    text = str(
        result or ""
    )

    low = text.lower()

    for phrase in FAILURE_PHRASES:
        if phrase in low:
            return (
                False,
                "INCOMPLETE_OR_CLARIFICATION:"
                + phrase,
            )

    summary = extract_summary(
        text
    )

    criteria = list(
        acceptance or []
    )

    # A task with real acceptance criteria must not PASS with
    # zero successful tool evidence when its objective clearly
    # requires external/tool-backed evidence.
    objective_low = str(
        objective
    ).lower()

    evidence_required = any(
        token in objective_low
        for token in (
            "research",
            "web evidence",
            "website",
            "homepage",
            "verify",
            "verification",
            "independently",
            "authoritative",
        )
    )

    if (
        criteria
        and evidence_required
    ):
        if summary is None:
            return (
                False,
                "TOOL_EVIDENCE_SUMMARY_MISSING",
            )

        successful = int(
            summary.get(
                "successful",
                0,
            )
        )

        if successful < 1:
            return (
                False,
                "REQUIRED_TOOL_EVIDENCE_MISSING",
            )

    return (
        True,
        "NODE_COMPLETION_SUPPORTED",
    )
