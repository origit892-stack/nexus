from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedEvidence:
    kind: str
    subject: str
    verified: bool
    positive: bool
    detail: str
    raw: Any = None


def verified_absence(
    *,
    subject: str,
    scope: str,
    raw: Any = None,
):
    return NormalizedEvidence(
        kind="verified_absence",
        subject=subject,
        verified=True,
        positive=False,
        detail=(
            f"{subject} was not found "
            f"after searching verified scope: "
            f"{scope}"
        ),
        raw=raw,
    )


def verified_presence(
    *,
    subject: str,
    detail: str,
    raw: Any = None,
):
    return NormalizedEvidence(
        kind="verified_presence",
        subject=subject,
        verified=True,
        positive=True,
        detail=detail,
        raw=raw,
    )


def is_completion_evidence(
    evidence: Any,
) -> bool:
    if isinstance(
        evidence,
        NormalizedEvidence,
    ):
        return evidence.verified

    if isinstance(
        evidence,
        dict,
    ):
        return bool(
            evidence.get(
                "verified",
                False,
            )
        )

    return False
