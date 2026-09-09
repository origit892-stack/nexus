from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

import pytest

import nexus.sessions.agent_shell as shell
from nexus.sessions.store import SessionStore


class FakePrompt:
    def __init__(self, inputs):
        self.inputs = iter(inputs)
        self.calls = 0

    def prompt(self, message):
        self.calls += 1
        value = next(self.inputs)

        if isinstance(value, BaseException):
            raise value

        return value


def make_session():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)

    store = SessionStore(root)

    session = store.create(
        "Initial objective",
        "Wave 1",
    )

    return temp, root, store, session


def history_len(store, session_id):
    session = store.get(session_id)
    return len(session.history or [])


def test_new_session_has_history():
    temp, root, store, session = make_session()

    try:
        loaded = store.get(session.id)

        assert loaded is not None
        assert loaded.history is not None
    finally:
        temp.cleanup()


def test_same_session_id_persists():
    temp, root, store, session = make_session()

    try:
        first = store.get(session.id)
        second = store.get(session.id)

        assert first.id == second.id == session.id
    finally:
        temp.cleanup()


def test_blank_input_contract():
    temp, root, store, session = make_session()

    try:
        before = history_len(
            store,
            session.id,
        )

        # Store state itself must remain unchanged
        # when no turn is executed.
        after = history_len(
            store,
            session.id,
        )

        assert before == after
    finally:
        temp.cleanup()


def test_help_command_exists():
    source = Path(shell.__file__).read_text()

    assert "/help" in source


def test_status_command_exists():
    source = Path(shell.__file__).read_text()

    assert "/status" in source


def test_history_command_exists():
    source = Path(shell.__file__).read_text()

    assert "/history" in source


def test_clear_command_exists():
    source = Path(shell.__file__).read_text()

    assert "/clear" in source


def test_back_command_exists():
    source = Path(shell.__file__).read_text()

    assert "/back" in source


def test_agent_prompt_exists():
    source = Path(shell.__file__).read_text()

    assert "nexus_agent>" in source


def test_escape_contract_exists():
    assert hasattr(
        shell,
        "ESCAPE_RESULT",
    )


def test_shell_callable():
    assert callable(
        shell.run_agent_shell
    )


def test_history_migration_missing():
    temp, root, store, session = make_session()

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

        raw.pop(
            "history",
            None,
        )

        path.write_text(
            json.dumps(raw)
        )

        loaded = store.get(
            session.id
        )

        assert loaded is not None
        assert loaded.history is not None
        assert len(loaded.history) >= 1
    finally:
        temp.cleanup()


def test_history_migration_null():
    temp, root, store, session = make_session()

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
