from __future__ import annotations

from pathlib import Path

import pytest

import nexus.sessions.runner as runner

from nexus.sessions.resume import (
    build_resume_instruction,
    reconcile_session_state,
)

from nexus.sessions.store import (
    SessionStore,
)


class FakeResult:
    run_id = "wave3-run"

    def __str__(
        self,
    ):
        return "wave3-result"


class SuccessAgent:
    def run(
        self,
        prompt,
    ):
        return FakeResult()


class FailureAgent:
    def run(
        self,
        prompt,
    ):
        raise RuntimeError(
            "wave3 failure"
        )


class InterruptAgent:
    def run(
        self,
        prompt,
    ):
        raise KeyboardInterrupt()


def make_session(
    tmp_path,
):
    store = SessionStore(
        tmp_path
    )

    session = store.create(
        "Wave 3 objective",
        "Wave 3 Resume",
    )

    return store, session


def test_resume_instruction_contains_state(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_plan(
        session.id,
        [
            "plan one",
            "plan two",
        ],
    )

    store.replace_pending(
        session.id,
        [
            "pending one",
        ],
    )

    store.append_completed(
        session.id,
        "completed one",
    )

    store.add_blocker(
        session.id,
        "blocker one",
    )

    store.set_active_item(
        session.id,
        "active one",
    )

    store.set_checkpoint(
        session.id,
        "checkpoint one",
    )

    store.add_durable_fact(
        session.id,
        "fact one",
    )

    loaded = store.get(
        session.id
    )

    instruction = (
        build_resume_instruction(
            loaded,
            tmp_path,
        )
    )

    required = [
        "Wave 3 objective",
        "active one",
        "plan one",
        "completed one",
        "pending one",
        "blocker one",
        "checkpoint one",
        "fact one",
        "inspect the current project state",
        "do not restart",
    ]

    lower = instruction.lower()

    for value in required:
        assert (
            value.lower()
            in lower
        )


def test_reconciliation(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        [
            "one",
            "two",
        ],
    )

    store.append_completed(
        session.id,
        "done",
    )

    store.add_blocker(
        session.id,
        "blocked",
    )

    loaded = store.get(
        session.id
    )

    result = (
        reconcile_session_state(
            loaded,
            tmp_path,
        )
    )

    assert result[
        "project_exists"
    ] is True

    assert result[
        "nexus_workspace_exists"
    ] is True

    assert result[
        "pending_count"
    ] == 2

    assert result[
        "completed_count"
    ] == 1

    assert result[
        "blocker_count"
    ] == 1

    assert "git_branch" in result

    assert (
        "git_tracked_dirty_count"
        in result
    )


def test_success_auto_checkpoint(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: (
            SuccessAgent()
        ),
    )

    runner.continue_session(
        tmp_path,
        session.id,
        "continue task",
    )

    loaded = store.get(
        session.id
    )

    assert loaded.working_state[
        "checkpoint_serial"
    ] == 1

    assert (
        "continue task"
        in loaded.working_state[
            "last_checkpoint"
        ]
    )


def test_success_checkpoint_increments_once(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: (
            SuccessAgent()
        ),
    )

    runner.continue_session(
        tmp_path,
        session.id,
        "one",
    )

    first = store.get(
        session.id
    ).working_state[
        "checkpoint_serial"
    ]

    runner.continue_session(
        tmp_path,
        session.id,
        "two",
    )

    second = store.get(
        session.id
    ).working_state[
        "checkpoint_serial"
    ]

    assert first == 1
    assert second == 2


def test_failure_does_not_checkpoint(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: (
            FailureAgent()
        ),
    )

    with pytest.raises(
        RuntimeError
    ):
        runner.continue_session(
            tmp_path,
            session.id,
            "fail",
        )

    assert store.get(
        session.id
    ).working_state[
        "checkpoint_serial"
    ] == 0


def test_interrupt_does_not_checkpoint(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: (
            InterruptAgent()
        ),
    )

    with pytest.raises(
        KeyboardInterrupt
    ):
        runner.continue_session(
            tmp_path,
            session.id,
            "interrupt",
        )

    assert store.get(
        session.id
    ).working_state[
        "checkpoint_serial"
    ] == 0


def test_auto_checkpoint_off(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    store.set_auto_checkpoint(
        session.id,
        False,
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: (
            SuccessAgent()
        ),
    )

    runner.continue_session(
        tmp_path,
        session.id,
        "no checkpoint",
    )

    assert store.get(
        session.id
    ).working_state[
        "checkpoint_serial"
    ] == 0
