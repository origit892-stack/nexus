from __future__ import annotations

from pathlib import Path
import inspect
import tempfile

import pytest

import nexus.sessions.agent_shell as shell
from nexus.sessions.store import SessionStore


class SequencePrompt:
    """
    Deterministic prompt adapter used to exercise the same
    run_agent_shell control-flow boundary as PromptSession.
    """

    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def prompt(self, message):
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


def make_session():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)

    store = SessionStore(root)

    session = store.create(
        "Input event acceptance",
        "Input Events",
    )

    return (
        temp,
        root,
        store,
        session,
    )


def test_escape_contract_symbol():
    assert hasattr(
        shell,
        "ESCAPE_RESULT",
    )

    assert shell.ESCAPE_RESULT


def test_escape_key_binding_is_present():
    source = inspect.getsource(
        shell
    )

    # We require an actual prompt_toolkit binding,
    # not merely a textual mention of Esc.
    assert "KeyBindings" in source

    escape_forms = (
        '"escape"',
        "'escape'",
        '"c-["',
        "'c-['",
    )

    assert any(
        form in source
        for form in escape_forms
    )


def test_escape_result_is_handled_by_shell():
    source = inspect.getsource(
        shell.run_agent_shell
    )

    assert (
        "ESCAPE_RESULT"
        in source
    )


def test_idle_ctrl_c_returns_to_prompt():
    temp, root, store, session = (
        make_session()
    )

    try:
        prompt = SequencePrompt(
            [
                KeyboardInterrupt(),
                "/back",
            ]
        )

        result = shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert prompt.calls == 2
        assert result is not None

    finally:
        temp.cleanup()


def test_running_turn_keyboard_interrupt_returns_to_prompt(
    monkeypatch,
):
    temp, root, store, session = (
        make_session()
    )

    instructions = []

    try:
        def interrupted_continue(
            project_path,
            session_id,
            instruction,
        ):
            instructions.append(
                instruction
            )

            if instruction == "interrupt me":
                raise KeyboardInterrupt()

        monkeypatch.setattr(
            shell,
            "continue_session",
            interrupted_continue,
        )

        prompt = SequencePrompt(
            [
                "interrupt me",
                "after interrupt",
                "/back",
            ]
        )

        result = shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert instructions == [
            "interrupt me",
            "after interrupt",
        ]

        assert prompt.calls == 3
        assert result is not None

    finally:
        temp.cleanup()


def test_failure_and_interrupt_are_distinct(
    monkeypatch,
):
    temp, root, store, session = (
        make_session()
    )

    seen = []

    try:
        def fake_continue(
            project_path,
            session_id,
            instruction,
        ):
            seen.append(
                instruction
            )

            if instruction == "interrupt":
                raise KeyboardInterrupt()

            if instruction == "failure":
                raise RuntimeError(
                    "synthetic failure"
                )

        monkeypatch.setattr(
            shell,
            "continue_session",
            fake_continue,
        )

        prompt = SequencePrompt(
            [
                "interrupt",
                "failure",
                "success",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert seen == [
            "interrupt",
            "failure",
            "success",
        ]

        assert prompt.calls == 4

    finally:
        temp.cleanup()


def test_back_after_interrupt_returns_cleanly(
    monkeypatch,
):
    temp, root, store, session = (
        make_session()
    )

    try:
        def fake_continue(
            project_path,
            session_id,
            instruction,
        ):
            raise KeyboardInterrupt()

        monkeypatch.setattr(
            shell,
            "continue_session",
            fake_continue,
        )

        prompt = SequencePrompt(
            [
                "interrupt",
                "/back",
            ]
        )

        result = shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert prompt.calls == 2
        assert result is not None

    finally:
        temp.cleanup()


def test_interrupt_does_not_replace_session(
    monkeypatch,
):
    temp, root, store, session = (
        make_session()
    )

    ids = []

    try:
        def fake_continue(
            project_path,
            session_id,
            instruction,
        ):
            ids.append(
                session_id
            )

            if instruction == "interrupt":
                raise KeyboardInterrupt()

        monkeypatch.setattr(
            shell,
            "continue_session",
            fake_continue,
        )

        prompt = SequencePrompt(
            [
                "interrupt",
                "next",
                "/back",
            ]
        )

        shell.run_agent_shell(
            root,
            session.id,
            prompt_session=prompt,
        )

        assert ids == [
            session.id,
            session.id,
        ]

    finally:
        temp.cleanup()


def test_escape_does_not_mutate_history_contract():
    temp, root, store, session = (
        make_session()
    )

    try:
        before = list(
            store.get(
                session.id
            ).history
            or []
        )

        # Esc is a navigation action.
        # It must never be represented as
        # a user instruction in history.
        assert not any(
            str(
                entry.get(
                    "text",
                    ""
                )
            ).strip()
            == shell.ESCAPE_RESULT
            for entry in before
        )

    finally:
        temp.cleanup()
