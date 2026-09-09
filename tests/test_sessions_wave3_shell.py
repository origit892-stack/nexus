from __future__ import annotations

import nexus.sessions.agent_shell as shell

from nexus.sessions.store import (
    SessionStore,
)


class FakePrompt:
    def __init__(self, values):
        self.values = iter(values)

    def prompt(self, message):
        value = next(self.values)

        if isinstance(
            value,
            BaseException,
        ):
            raise value

        return value


def make_session(tmp_path):
    store = SessionStore(tmp_path)

    session = store.create(
        "Wave 3 shell objective",
        "Wave 3 Shell",
    )

    return store, session


def test_done_is_local(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        ["task"],
    )

    store.set_active_item(
        session.id,
        "task",
    )

    calls = []

    monkeypatch.setattr(
        shell,
        "continue_session",
        lambda *args, **kwargs: (
            calls.append(args)
        ),
    )

    shell.run_agent_shell(
        tmp_path,
        session.id,
        prompt_session=FakePrompt(
            [
                "/done task",
                "/back",
            ]
        ),
    )

    state = store.get(
        session.id
    ).working_state

    assert calls == []
    assert state[
        "completed_work"
    ] == ["task"]

    assert state[
        "pending_work"
    ] == []

    assert state[
        "active_item"
    ] is None


def test_next_is_local(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        ["first", "second"],
    )

    calls = []

    monkeypatch.setattr(
        shell,
        "continue_session",
        lambda *args, **kwargs: (
            calls.append(args)
        ),
    )

    shell.run_agent_shell(
        tmp_path,
        session.id,
        prompt_session=FakePrompt(
            [
                "/next",
                "/back",
            ]
        ),
    )

    assert calls == []

    assert store.get(
        session.id
    ).working_state[
        "active_item"
    ] == "first"


def test_autocheckpoint_toggle_is_local(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    calls = []

    monkeypatch.setattr(
        shell,
        "continue_session",
        lambda *args, **kwargs: (
            calls.append(args)
        ),
    )

    shell.run_agent_shell(
        tmp_path,
        session.id,
        prompt_session=FakePrompt(
            [
                "/autocheckpoint off",
                "/autocheckpoint on",
                "/back",
            ]
        ),
    )

    assert calls == []

    assert store.get(
        session.id
    ).working_state[
        "auto_checkpoint"
    ] is True


def test_resume_same_session_once(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        ["resume item"],
    )

    seen = []

    def fake_continue(
        project_path,
        session_id,
        instruction,
    ):
        seen.append(
            (
                session_id,
                instruction,
            )
        )

    monkeypatch.setattr(
        shell,
        "continue_session",
        fake_continue,
    )

    result = shell.run_agent_shell(
        tmp_path,
        session.id,
        prompt_session=FakePrompt(
            [
                "/resume",
                "/back",
            ]
        ),
    )

    assert len(seen) == 1
    assert seen[0][0] == session.id
    assert "resume item" in seen[0][1]

    assert result.turns == 1

    loaded = store.get(
        session.id
    )

    assert loaded.resume_state[
        "resume_requested_at"
    ] is not None


def test_local_commands_do_not_add_history(
    tmp_path,
    monkeypatch,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        ["one"],
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
        lambda *args, **kwargs: None,
    )

    shell.run_agent_shell(
        tmp_path,
        session.id,
        prompt_session=FakePrompt(
            [
                "/next",
                "/done one",
                "/autocheckpoint off",
                "/back",
            ]
        ),
    )

    after = list(
        store.get(
            session.id
        ).history
        or []
    )

    assert before == after
