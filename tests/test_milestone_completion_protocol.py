from nexus.sessions.runner import (
    _milestone_result_failure,
)


def test_verification_pending_blocks_pass():
    result = (
        "VERIFICATION_PENDING\n"
        "MISSING_EVIDENCE=artifact,tests\n"
        "IMPLEMENTATION_RESULT:\n"
        "Incomplete."
    )

    assert (
        _milestone_result_failure(
            result
        )
        == result
    )


def test_agent_exception_blocks_pass():
    result = (
        "AGENT_EXCEPTION="
        "RuntimeError: boom"
    )

    assert (
        _milestone_result_failure(
            result
        )
        == result
    )


def test_plain_success_not_failure():
    assert (
        _milestone_result_failure(
            "Implementation completed."
        )
        is None
    )



def test_acceptance_override_fail_cannot_become_milestone_pass():
    result = (
        "NEXUS_ACCEPTANCE_OVERRIDE=FAIL\n"
        "MODEL_PASS_REJECTED=YES\n"
        "REASON=PASS report contains incompatible evidence"
    )

    assert (
        _milestone_result_failure(
            result
        )
        == result
    )


def test_acceptance_override_text_inside_normal_prose_is_not_failure():
    result = (
        "Audit note: the literal marker "
        "NEXUS_ACCEPTANCE_OVERRIDE=FAIL "
        "is documented here, not emitted as status."
    )

    assert (
        _milestone_result_failure(
            result
        )
        is None
    )
