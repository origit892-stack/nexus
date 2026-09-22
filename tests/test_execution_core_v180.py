import pytest

from nexus.runtime.task_contract import (
    TaskContract,
)

from nexus.runtime.execution_state import (
    ExecutionState,
)

from nexus.runtime.execution_core import (
    ExecutionCoreError,
    continuation_instruction,
    finalize_success,
    inspect_completion,
    render_execution_progress,
)


def contract():
    return TaskContract(
        goal="audit assets",
        current_phase="audit",
        deliverables=(
            "categorized report",
        ),
        must_do=(
            "discover",
            "categorize",
        ),
        must_not_do=(
            "do not mutate",
        ),
        evidence_required=(
            "technical QA",
        ),
        done_when=(
            "report ready",
        ),
        mutation_policy="READ_ONLY",
    )


def test_incomplete_state_cannot_complete():
    state = ExecutionState.create(
        contract()
    )

    result = inspect_completion(
        state
    )

    assert result.allowed is False
    assert result.incomplete
    assert result.progress == 0.0


def test_partial_progress_still_cannot_complete():
    state = ExecutionState.create(
        contract()
    )

    state.mark_done(
        "discover",
        "inventory collected",
    )

    result = inspect_completion(
        state
    )

    assert result.allowed is False

    assert (
        "categorize"
        in result.incomplete
    )


def test_success_requires_every_requirement_done():
    state = ExecutionState.create(
        contract()
    )

    for requirement in tuple(
        state.incomplete()
    ):
        state.mark_done(
            requirement,
            "verified",
        )

    result = inspect_completion(
        state
    )

    assert result.allowed is True
    assert result.progress == 1.0

    final = finalize_success(
        proposed_final="Audit complete.",
        state=state,
    )

    assert final.status == "PASS"
    assert (
        final.final_text
        == "Audit complete."
    )


def test_finalize_success_rejects_incomplete_state():
    state = ExecutionState.create(
        contract()
    )

    with pytest.raises(
        ExecutionCoreError,
        match="SUCCESS_COMPLETION_BLOCKED",
    ):
        finalize_success(
            proposed_final="Done",
            state=state,
        )


def test_finalize_success_requires_user_facing_text():
    state = ExecutionState.create(
        contract()
    )

    for requirement in tuple(
        state.incomplete()
    ):
        state.mark_done(
            requirement
        )

    with pytest.raises(
        ExecutionCoreError,
        match=(
            "SUCCESS_COMPLETION_REQUIRES_FINAL_TEXT"
        ),
    ):
        finalize_success(
            proposed_final="   ",
            state=state,
        )


def test_continuation_lists_remaining_requirements():
    state = ExecutionState.create(
        contract()
    )

    state.mark_done(
        "discover",
        "done",
    )

    text = continuation_instruction(
        state
    )

    assert "categorize" in text
    assert "technical QA" in text
    assert "report ready" in text

    assert (
        "Do not restart broad discovery"
        in text
    )


def test_progress_renderer_is_human_readable():
    state = ExecutionState.create(
        contract()
    )

    state.mark_done(
        "discover",
        "done",
    )

    text = render_execution_progress(
        state
    )

    assert "TASK STATE" in text
    assert "DONE: discover" in text
    assert "PENDING: categorize" in text


def test_legacy_no_contract_can_finalize():
    result = finalize_success(
        proposed_final="Simple answer.",
        state=None,
    )

    assert result.status == "PASS"
    assert (
        result.execution.reason
        == "NO_TASK_CONTRACT"
    )
