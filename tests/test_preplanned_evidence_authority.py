from nexus.runtime.completion_evidence import (
    evaluate_completion_evidence,
    infer_evidence_requirements,
    preplanned_evidence_requirements,
)


def _task(evidence):
    return (
        "NEXUS MASTER PROMPT MILESTONE MODE\n"
        "CURRENT_MILESTONE=M1\n"
        "OBJECTIVE:\n"
        "Inspect BunkerGame architecture\n"
        "MILESTONE_RESTRICTIONS:\n"
        '["do not modify Roblox Studio", '
        '"do not modify terrain"]\n'
        "GLOBAL_RESTRICTIONS:\n"
        '["do not modify source", '
        '"do not modify Nexus"]\n'
        "EVIDENCE_REQUIRED:\n"
        + evidence
        + "\n"
        "COMPLETION_DEFINITION:\n"
        '["document architecture"]\n'
    )


def test_empty_compiled_evidence_is_authoritative():
    requirements = (
        preplanned_evidence_requirements(
            _task("[]")
        )
    )

    assert requirements is not None
    assert requirements.required_names() == ()


def test_restrictions_do_not_invent_evidence():
    requirements = (
        preplanned_evidence_requirements(
            _task("[]")
        )
    )

    assert requirements is not None
    assert requirements.required_names() == ()


def test_empty_external_evidence_requirement_passes_gate():
    requirements = (
        preplanned_evidence_requirements(
            _task("[]")
        )
    )

    assert requirements is not None

    decision = evaluate_completion_evidence(
        requirements=requirements,
        evidence="",
    )

    assert decision.complete
    assert decision.missing == ()


def test_explicit_test_evidence_is_preserved():
    requirements = (
        preplanned_evidence_requirements(
            _task(
                '["Unit test execution"]'
            )
        )
    )

    assert requirements is not None
    assert (
        requirements.required_names()
        == ("tests",)
    )


def test_normal_task_still_uses_generic_inference():
    task = (
        "Implement Roblox gameplay, "
        "run tests and playtest it."
    )

    assert (
        preplanned_evidence_requirements(
            task
        )
        is None
    )

    assert (
        infer_evidence_requirements(
            task=task
        ).required_names()
    )


def test_playtest_does_not_imply_test_evidence():
    requirements = (
        preplanned_evidence_requirements(
            _task(
                '["Runtime playtest", "Visual QA"]'
            )
        )
    )

    assert requirements is not None

    assert (
        requirements.required_names()
        == (
            "runtime",
            "visual",
        )
    )


def test_tests_and_playtest_remain_distinct():
    requirements = (
        preplanned_evidence_requirements(
            _task(
                '["Unit tests", "Runtime playtest"]'
            )
        )
    )

    assert requirements is not None

    assert (
        requirements.required_names()
        == (
            "tests",
            "runtime",
        )
    )
