from __future__ import annotations

from nexus.runtime.completion_evidence import (
    evaluate_completion_evidence,
    infer_evidence_requirements,
)


def test_non_mutating_question_needs_no_external_evidence():
    requirements = (
        infer_evidence_requirements(
            task=(
                "Explain how this function works."
            )
        )
    )

    assert (
        requirements
        .required_names()
        == ()
    )

    decision = (
        evaluate_completion_evidence(
            requirements=requirements,
            evidence=None,
        )
    )

    assert decision.complete
    assert (
        decision.status
        == "COMPLETE"
    )


def test_roblox_world_change_requires_studio():
    requirements = (
        infer_evidence_requirements(
            task=(
                "Move the Roblox MeshParts "
                "into a straight line in Studio."
            )
        )
    )

    assert requirements.artifact
    assert requirements.integration
    assert requirements.studio

    decision = (
        evaluate_completion_evidence(
            requirements=requirements,
            evidence={
                "artifact":
                    "PASS",
            },
        )
    )

    assert not decision.complete
    assert (
        decision.status
        == "VERIFICATION_PENDING"
    )

    assert "studio" in decision.missing


def test_gameplay_change_requires_runtime():
    requirements = (
        infer_evidence_requirements(
            task=(
                "Implement Roblox sprint stamina "
                "and verify gameplay in a playtest."
            )
        )
    )

    assert requirements.studio
    assert requirements.runtime

    decision = (
        evaluate_completion_evidence(
            requirements=requirements,
            evidence={
                "artifact":
                    "PASS",

                "integration":
                    "PASS",

                "studio":
                    "PASS",
            },
        )
    )

    assert not decision.complete
    assert "runtime" in decision.missing


def test_visual_change_requires_visual_evidence():
    requirements = (
        infer_evidence_requirements(
            task=(
                "Rework the Roblox bunker lighting "
                "and visually verify the result."
            )
        )
    )

    assert requirements.visual

    decision = (
        evaluate_completion_evidence(
            requirements=requirements,
            evidence={
                "artifact":
                    "PASS",

                "integration":
                    "PASS",

                "studio":
                    "PASS",
            },
        )
    )

    assert not decision.complete
    assert "visual" in decision.missing


def test_complete_roblox_evidence_passes():
    requirements = (
        infer_evidence_requirements(
            task=(
                "Implement Roblox stamina gameplay "
                "with tests and runtime verification."
            )
        )
    )

    evidence = {
        "artifact":
            "PASS",

        "tests":
            "PASS",

        "integration":
            "PASS",

        "studio":
            "PASS",

        "runtime":
            "PASS",
    }

    decision = (
        evaluate_completion_evidence(
            requirements=requirements,
            evidence=evidence,
        )
    )

    assert decision.complete
    assert (
        decision.status
        == "COMPLETE"
    )

    assert not decision.missing
