from __future__ import annotations

import json
import time

from pathlib import Path

import pytest

import nexus.sessions.agent_shell as shell
import nexus.sessions.runner as runner

from nexus.sessions.context import (
    COMPACTION_THRESHOLD,
    RECENT_HISTORY_WINDOW,
    build_agent_context,
    render_agent_context,
)

from nexus.sessions.store import (
    SCHEMA_VERSION,
    SessionStore,
)


class FakePrompt:
    def __init__(
        self,
        values,
    ):
        self.values = iter(
            values
        )

        self.calls = 0

    def prompt(
        self,
        message,
    ):
        self.calls += 1

        value = next(
            self.values
        )

        if isinstance(
            value,
            BaseException,
        ):
            raise value

        return value


class FakeResult:
    def __init__(
        self,
        text="result",
        run_id="run-test",
    ):
        self.text = text
        self.run_id = run_id

    def __str__(
        self,
    ):
        return self.text


class SuccessfulAgent:
    def __init__(
        self,
        result=None,
    ):
        self.result = (
            result
            or FakeResult()
        )

        self.prompts = []

    def run(
        self,
        prompt,
    ):
        self.prompts.append(
            prompt
        )

        return self.result


class FailingAgent:
    def run(
        self,
        prompt,
    ):
        raise RuntimeError(
            "synthetic failure"
        )


class InterruptingAgent:
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
        "Wave 2 behavioral objective",
        "Wave 2 Behavioral",
    )

    return (
        store,
        session,
    )


def test_reading_legacy_session_does_not_rewrite_file(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    path = store._path(
        session.id
    )

    raw = json.loads(
        path.read_text()
    )

    raw.pop(
        "schema_version",
        None,
    )

    raw.pop(
        "working_state",
        None,
    )

    raw.pop(
        "context_state",
        None,
    )

    raw.pop(
        "resume_state",
        None,
    )

    path.write_text(
        json.dumps(
            raw,
            indent=2,
        )
    )

    before = (
        path.read_bytes()
    )

    loaded = store.get(
        session.id
    )

    after = (
        path.read_bytes()
    )

    assert loaded is not None
    assert before == after

    assert (
        loaded.schema_version
        == SCHEMA_VERSION
    )

    assert isinstance(
        loaded.working_state,
        dict,
    )

    assert isinstance(
        loaded.context_state,
        dict,
    )

    assert isinstance(
        loaded.resume_state,
        dict,
    )


def test_corrupt_json_is_not_silently_converted_to_none(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    path = store._path(
        session.id
    )

    path.write_text(
        "{ invalid json"
    )

    with pytest.raises(
        json.JSONDecodeError
    ):
        store.get(
            session.id
        )


def test_shell_wave2_commands_modify_state_without_agent_turn(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    agent_calls = []

    def forbidden_continue(
        *args,
        **kwargs,
    ):
        agent_calls.append(
            (
                args,
                kwargs,
            )
        )

        raise AssertionError(
            "Wave 2 shell command "
            "must not invoke agent"
        )

    monkeypatch.setattr(
        shell,
        "continue_session",
        forbidden_continue,
    )

    prompt = FakePrompt(
        [
            "/checkpoint checkpoint one",
            "/fact durable fact one",
            "/fact durable fact one",
            "/blocker blocked by one",
            "/blocker blocked by one",
            "/plan step one; step two",
            "/pending pending one; pending two",
            "/unblock blocked by one",
            "/state",
            "/context",
            "/back",
        ]
    )

    before_history = list(
        store.get(
            session.id
        ).history
        or []
    )

    result = shell.run_agent_shell(
        tmp_path,
        session.id,
        prompt_session=prompt,
    )

    assert result is not None

    assert agent_calls == []

    loaded = store.get(
        session.id
    )

    assert (
        loaded.working_state[
            "last_checkpoint"
        ]
        == "checkpoint one"
    )

    assert (
        loaded.context_state[
            "durable_facts"
        ]
        == [
            "durable fact one"
        ]
    )

    assert (
        loaded.working_state[
            "blockers"
        ]
        == []
    )

    assert (
        loaded.working_state[
            "current_plan"
        ]
        == [
            "step one",
            "step two",
        ]
    )

    assert (
        loaded.working_state[
            "pending_work"
        ]
        == [
            "pending one",
            "pending two",
        ]
    )

    assert (
        loaded.history
        == before_history
    )


def test_state_and_context_commands_do_not_mutate_history(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    before = list(
        store.get(
            session.id
        ).history
        or []
    )

    monkeypatch.setattr(
        shell,
        "continue_session",
        lambda *args, **kwargs: (
            pytest.fail(
                "Agent invoked"
            )
        ),
    )

    prompt = FakePrompt(
        [
            "/state",
            "/context",
            "/back",
        ]
    )

    shell.run_agent_shell(
        tmp_path,
        session.id,
        prompt_session=prompt,
    )

    after = list(
        store.get(
            session.id
        ).history
        or []
    )

    assert before == after


def test_success_resume_state(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    agent = SuccessfulAgent(
        FakeResult(
            "successful result",
            "run-success",
        )
    )

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: agent,
    )

    result = runner.continue_session(
        tmp_path,
        session.id,
        "continue work",
    )

    assert str(
        result
    ) == "successful result"

    loaded = store.get(
        session.id
    )

    assert (
        loaded.status
        == "COMPLETED"
    )

    assert (
        loaded.resume_state[
            "last_instruction"
        ]
        == "continue work"
    )

    assert (
        loaded.resume_state[
            "last_run_id"
        ]
        == "run-success"
    )

    assert (
        loaded.resume_state[
            "last_status"
        ]
        == "COMPLETED"
    )

    assert (
        loaded.resume_state[
            "interrupted"
        ]
        is False
    )

    assert (
        loaded.resume_state[
            "continuation_point"
        ]
        == "ready-for-next-turn"
    )


def test_failure_resume_state(
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
            FailingAgent()
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic failure",
    ):
        runner.continue_session(
            tmp_path,
            session.id,
            "failing turn",
        )

    loaded = store.get(
        session.id
    )

    assert (
        loaded.status
        == "FAILED"
    )

    assert (
        loaded.resume_state[
            "last_instruction"
        ]
        == "failing turn"
    )

    assert (
        loaded.resume_state[
            "last_status"
        ]
        == "FAILED"
    )

    assert (
        loaded.resume_state[
            "interrupted"
        ]
        is False
    )

    assert (
        loaded.resume_state[
            "continuation_point"
        ]
        == "failed-turn-recovery"
    )

    assert (
        loaded.history[-1][
            "type"
        ]
        == "failure"
    )


def test_interrupt_resume_state(
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
            InterruptingAgent()
        ),
    )

    with pytest.raises(
        KeyboardInterrupt
    ):
        runner.continue_session(
            tmp_path,
            session.id,
            "interrupt turn",
        )

    loaded = store.get(
        session.id
    )

    assert (
        loaded.status
        == "INTERRUPTED"
    )

    assert (
        loaded.resume_state[
            "last_instruction"
        ]
        == "interrupt turn"
    )

    assert (
        loaded.resume_state[
            "last_status"
        ]
        == "INTERRUPTED"
    )

    assert (
        loaded.resume_state[
            "interrupted"
        ]
        is True
    )

    assert (
        loaded.resume_state[
            "continuation_point"
        ]
        == "interrupted-turn"
    )

    assert (
        loaded.history[-1][
            "type"
        ]
        == "interrupt"
    )


def test_runner_uses_compacted_context_for_long_session(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    for i in range(
        30
    ):
        loaded.history.append(
            {
                "type": (
                    "instruction"
                    if i % 2 == 0
                    else "result"
                ),
                "text": (
                    f"historic entry {i}"
                ),
            }
        )

    store.save(
        loaded
    )

    agent = SuccessfulAgent()

    monkeypatch.setattr(
        runner,
        "_agent",
        lambda project_path: agent,
    )

    runner.continue_session(
        tmp_path,
        session.id,
        "latest request",
    )

    assert len(
        agent.prompts
    ) == 1

    prompt = agent.prompts[0]

    assert (
        "COMPACTED CONTEXT:"
        in prompt
    )

    assert (
        "RECENT HISTORY:"
        in prompt
    )

    assert (
        "CURRENT INSTRUCTION:"
        in prompt
    )

    assert (
        "latest request"
        in prompt
    )


def test_compaction_does_not_delete_full_history(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    for i in range(
        40
    ):
        loaded.history.append(
            {
                "type": "instruction",
                "text": f"entry-{i}",
            }
        )

    before = list(
        loaded.history
    )

    context = build_agent_context(
        loaded
    )

    assert (
        len(
            context[
                "recent_history"
            ]
        )
        == RECENT_HISTORY_WINDOW
    )

    assert context[
        "summary"
    ]

    assert loaded.history == before


def test_compaction_threshold_boundary(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    while len(
        loaded.history
    ) < COMPACTION_THRESHOLD:
        loaded.history.append(
            {
                "type": "instruction",
                "text": "boundary",
            }
        )

    at_threshold = (
        build_agent_context(
            loaded
        )
    )

    assert (
        at_threshold[
            "summary"
        ]
        is None
    )

    loaded.history.append(
        {
            "type": "instruction",
            "text": "over threshold",
        }
    )

    above_threshold = (
        build_agent_context(
            loaded
        )
    )

    assert (
        above_threshold[
            "summary"
        ]
    )


def test_context_summary_is_deterministic_across_fresh_loads(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    for i in range(
        35
    ):
        loaded.history.append(
            {
                "type": "instruction",
                "text": f"item-{i}",
            }
        )

    store.save(
        loaded
    )

    first_session = store.get(
        session.id
    )

    second_session = store.get(
        session.id
    )

    first = build_agent_context(
        first_session
    )[
        "summary"
    ]

    second = build_agent_context(
        second_session
    )[
        "summary"
    ]

    assert first == second
