from __future__ import annotations

import pytest

import nexus.sessions.runner as runner

from nexus.sessions.state_update import (
    state_update_protocol_prompt,
)

from nexus.sessions.store import (
    SessionStore,
)


class StringAgent:
    def __init__(
        self,
        value,
    ):
        self.value = value

    def run(
        self,
        prompt,
    ):
        return self.value


def make_session(
    tmp_path,
):
    store = SessionStore(
        tmp_path
    )

    session = store.create(
        "Wave 5 recovery objective",
        "Wave 5 Recovery",
    )

    return store, session


@pytest.mark.parametrize(
    "result",
    [
        "AGENT_EXCEPTION=InternalServerError: synthetic",
        "MAX_ITERATIONS_REACHED",
        "NEXUS_TOOL_BUDGET_EXCEEDED=4",
    ],
)
def test_agent_failure_sentinel_marks_session_failed(
    tmp_path,
    monkeypatch,
    result,
):
    store, session = make_session(
        tmp_path
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: (
            StringAgent(
                result
            )
        ),
    )

    with pytest.raises(
        RuntimeError
    ):
        runner.continue_session(
            tmp_path,
            session.id,
            "perform work",
        )

    loaded = store.get(
        session.id
    )

    assert loaded.status == "FAILED"

    assert loaded.resume_state[
        "last_status"
    ] == "FAILED"

    assert loaded.working_state[
        "checkpoint_serial"
    ] == 0

    assert not any(
        entry.get(
            "type"
        ) == "result"
        and entry.get(
            "text"
        ) == result
        for entry in (
            loaded.history
            or []
        )
    )


def test_agent_exception_does_not_apply_state(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        [
            "task one",
        ],
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: (
            StringAgent(
                "AGENT_EXCEPTION=InternalServerError: synthetic"
            )
        ),
    )

    with pytest.raises(
        RuntimeError
    ):
        runner.continue_session(
            tmp_path,
            session.id,
            "task one",
        )

    loaded = store.get(
        session.id
    )

    assert loaded.working_state[
        "completed_work"
    ] == []

    assert loaded.working_state[
        "pending_work"
    ] == [
        "task one"
    ]


def test_protocol_requires_final_response():
    prompt = state_update_protocol_prompt()

    lower = prompt.lower()

    assert (
        "final assistant response"
        in lower
    )

    assert (
        "never send the block through memory_add"
        in lower
    )

    assert (
        "never store the block as memory"
        in lower
    )

    assert (
        "must contain the block"
        in lower
    )


def test_protocol_requires_last_content():
    prompt = (
        state_update_protocol_prompt()
        .lower()
    )

    assert (
        "last content in the final response"
        in prompt
    )
