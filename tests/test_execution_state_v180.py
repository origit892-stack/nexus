import pytest

from nexus.runtime.task_contract import (
    TaskContract,
)

from nexus.runtime.execution_state import (
    ExecutionState,
    STATUS_DONE,
)


def make_contract():
    return TaskContract(
        goal="audit",
        current_phase="inspection",
        deliverables=("report",),
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


def test_new_state_is_not_complete():
    state = ExecutionState.create(
        make_contract()
    )

    assert state.complete() is False

    assert set(
        state.incomplete()
    ) == {
        "discover",
        "categorize",
        "technical QA",
        "report ready",
    }


def test_progress_does_not_equal_completion():
    state = ExecutionState.create(
        make_contract()
    )

    state.record_progress(
        "discover",
        "listed files",
    )

    assert state.complete() is False

    item = state.requirements[
        "discover"
    ]

    assert item.evidence == [
        "listed files"
    ]

    assert (
        item.status
        != STATUS_DONE
    )


def test_completion_requires_every_requirement():
    state = ExecutionState.create(
        make_contract()
    )

    for requirement in tuple(
        state.incomplete()
    ):
        state.mark_done(
            requirement,
            "verified",
        )

    assert state.complete() is True
    assert state.incomplete() == ()
    assert (
        state.progress_fraction()
        == 1.0
    )


def test_unknown_requirement_is_rejected():
    state = ExecutionState.create(
        make_contract()
    )

    with pytest.raises(KeyError):
        state.mark_done(
            "invented work"
        )


def test_progress_update_requires_known_requirement():
    state = ExecutionState.create(
        make_contract()
    )

    with pytest.raises(KeyError):
        state.apply_progress_update(
            requirement="invented",
            status="DONE",
            evidence="fake",
        )


def test_progress_update_requires_evidence():
    state = ExecutionState.create(
        make_contract()
    )

    with pytest.raises(
        ValueError,
        match="requires evidence",
    ):
        state.apply_progress_update(
            requirement="discover",
            status="DONE",
            evidence="",
        )


def test_progress_update_can_mark_requirement_done():
    state = ExecutionState.create(
        make_contract()
    )

    state.apply_progress_update(
        requirement="discover",
        status="DONE",
        evidence="Inventory command returned all candidate files.",
    )

    assert (
        state.requirements[
            "discover"
        ].status
        == STATUS_DONE
    )
