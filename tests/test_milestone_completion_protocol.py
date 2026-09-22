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
