from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerificationResult:
    passed: bool
    reason: str


def verify_visual_change(
    before_text: str,
    after_text: str,
    expected: str,
):
    before = str(
        before_text or ""
    ).strip()

    after = str(
        after_text or ""
    ).strip()

    expected = str(
        expected or ""
    ).strip()

    if not before:
        return VerificationResult(
            False,
            "BEFORE_EVIDENCE_MISSING",
        )

    if not after:
        return VerificationResult(
            False,
            "AFTER_EVIDENCE_MISSING",
        )

    if not expected:
        return VerificationResult(
            False,
            "EXPECTED_STATE_MISSING",
        )

    if before == after:
        return VerificationResult(
            False,
            "NO_VISUAL_CHANGE_DETECTED",
        )

    if (
        expected.lower()
        not in after.lower()
    ):
        return VerificationResult(
            False,
            "EXPECTED_STATE_NOT_CONFIRMED",
        )

    return VerificationResult(
        True,
        "VISUAL_STATE_CONFIRMED",
    )
