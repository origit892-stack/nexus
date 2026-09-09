from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

import nexus.sessions.agent_shell as shell
import nexus.sessions.runner as runner
from nexus.sessions.store import SessionStore


class FakePrompt:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def prompt(self, message):
        self.calls += 1
        value = next(self.values)

        if isinstance(value, BaseException):
            raise value

        return value


def make_store():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    store = SessionStore(root)
    session = store.create(
        "Initial objective",
        "Behavioral",
    )
    return temp, root, store, session


def test_three_turns_same_session(monkeypatch):
    temp, root, store, session = make_store()

    seen = []

    try:
        def fake_continue(project_path, session_id, instruction):
            seen.append(
                (
                    session_id,
                    instruction,
                )
            )

            loaded = store.get(session_id)
            loaded.history.append(
                {
                    "type": "instruction",
                    "text": instruction,
                    "created_at": loaded.updated_at,
                }
            )
            loaded.history.append(
                {
                    "type": "result",
                    "text": f"result:{instruction}",
                    "created_at": loaded.updated_at,
                }
            )
            store.save(loaded)

        monkeypatch.setattr(
            shell,
            "continue_session",
            fake_continue,
        )

        prompt = FakePrompt(
            [
                "turn one",
                "turn two",
                "turn three",
                "/back",
            ]
        )

        result = shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert result is not None
        assert [x[0] for x in seen] == [
            session.id,
            session.id,
            session.id,
        ]
        assert [x[1] for x in seen] == [
            "turn one",
            "turn two",
            "turn three",
        ]

        loaded = store.get(session.id)
        assert loaded is not None

        texts = [
            item.get("text")
            for item in loaded.history
            if item.get("type")
            in {
                "instruction",
                "result",
            }
        ]

        assert "turn one" in texts
        assert "turn two" in texts
        assert "turn three" in texts
    finally:
        temp.cleanup()


def test_blank_input_creates_no_turn(monkeypatch):
    temp, root, store, session = make_store()

    calls = []

    try:
        monkeypatch.setattr(
            shell,
            "continue_session",
            lambda *args, **kwargs: calls.append(
                (args, kwargs)
            ),
        )

        before = len(
            store.get(session.id).history or []
        )

        prompt = FakePrompt(
            [
                "",
                "   ",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        after = len(
            store.get(session.id).history or []
        )

        assert calls == []
        assert before == after
    finally:
        temp.cleanup()


def test_failure_returns_to_prompt(monkeypatch):
    temp, root, store, session = make_store()

    calls = []

    try:
        def fake_continue(project_path, session_id, instruction):
            calls.append(instruction)

            if instruction == "fail":
                raise RuntimeError(
                    "synthetic failure"
                )

        monkeypatch.setattr(
            shell,
            "continue_session",
            fake_continue,
        )

        prompt = FakePrompt(
            [
                "fail",
                "after failure",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert calls == [
            "fail",
            "after failure",
        ]
        assert prompt.calls >= 3
    finally:
        temp.cleanup()


def test_idle_ctrl_c_returns_to_prompt(monkeypatch):
    temp, root, store, session = make_store()

    try:
        prompt = FakePrompt(
            [
                KeyboardInterrupt(),
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert prompt.calls == 2
    finally:
        temp.cleanup()


def test_back_exits_shell(monkeypatch):
    temp, root, store, session = make_store()

    try:
        prompt = FakePrompt(
            [
                "/back",
            ]
        )

        result = shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert result is not None
    finally:
        temp.cleanup()


def test_help_returns_to_prompt(monkeypatch):
    temp, root, store, session = make_store()

    try:
        prompt = FakePrompt(
            [
                "/help",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert prompt.calls == 2
    finally:
        temp.cleanup()


def test_status_returns_to_prompt(monkeypatch):
    temp, root, store, session = make_store()

    try:
        prompt = FakePrompt(
            [
                "/status",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert prompt.calls == 2
    finally:
        temp.cleanup()


def test_history_returns_to_prompt(monkeypatch):
    temp, root, store, session = make_store()

    try:
        prompt = FakePrompt(
            [
                "/history",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert prompt.calls == 2
    finally:
        temp.cleanup()


def test_clear_does_not_erase_history(monkeypatch):
    temp, root, store, session = make_store()

    try:
        before = list(
            store.get(session.id).history or []
        )

        prompt = FakePrompt(
            [
                "/clear",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        after = list(
            store.get(session.id).history or []
        )

        assert after == before
    finally:
        temp.cleanup()


def test_continue_session_blank_instruction_is_noop():
    temp, root, store, session = make_store()

    try:
        before = list(
            store.get(session.id).history or []
        )

        result = runner.continue_session(
            root,
            session.id,
            "   ",
        )

        after = list(
            store.get(session.id).history or []
        )

        assert result is None
        assert after == before
    finally:
        temp.cleanup()


def test_legacy_missing_history_still_loads():
    temp, root, store, session = make_store()

    try:
        path = (
            root
            / ".nexus"
            / "sessions"
            / f"{session.id}.json"
        )

        import json

        raw = json.loads(
            path.read_text()
        )

        raw.pop("history", None)

        path.write_text(
            json.dumps(raw)
        )

        loaded = store.get(
            session.id
        )

        assert loaded is not None
        assert loaded.history is not None
    finally:
        temp.cleanup()


def test_legacy_null_history_still_loads():
    temp, root, store, session = make_store()

    try:
        path = (
            root
            / ".nexus"
            / "sessions"
            / f"{session.id}.json"
        )

        import json

        raw = json.loads(
            path.read_text()
        )

        raw["history"] = None

        path.write_text(
            json.dumps(raw)
        )

        loaded = store.get(
            session.id
        )

        assert loaded is not None
        assert loaded.history is not None
    finally:
        temp.cleanup()


def test_shell_prompt_contract():
    source = Path(
        shell.__file__
    ).read_text()

    assert "nexus_agent>" in source
    assert "/help" in source
    assert "/status" in source
    assert "/history" in source
    assert "/clear" in source
    assert "/back" in source


def test_escape_symbol_contract():
    assert hasattr(
        shell,
        "ESCAPE_RESULT",
    )


def test_runner_same_session_api():
    assert callable(
        runner.continue_session
    )
    assert callable(
        runner.run_session
    )
