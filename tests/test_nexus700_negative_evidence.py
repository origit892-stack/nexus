from nexus.runtime.evidence_normalization import (
    is_completion_evidence,
    verified_absence,
)


def test_verified_absence_counts_as_evidence():
    evidence = verified_absence(
        subject="pyproject.toml",
        scope="/project",
    )

    assert evidence.verified
    assert not evidence.positive
    assert is_completion_evidence(
        evidence
    )
