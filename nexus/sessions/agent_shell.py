from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from .runner import (
    continue_session,
    run_session,
)
from .store import SessionStore


ESCAPE_RESULT = "__NEXUS_AGENT_SHELL_ESCAPE__"


class PromptLike(Protocol):
    def prompt(
        self,
        message: str,
    ) -> str:
        ...


@dataclass
class AgentShellResult:
    project_path: str
    session_id: str
    turns: int
    reason: str


def _bindings() -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add(
        "escape",
        eager=True,
    )
    def escape(
        event,
    ):
        event.app.exit(
            result=ESCAPE_RESULT
        )

    return bindings


def _prompt_session() -> PromptSession:
    return PromptSession(
        key_bindings=_bindings(),
        style=Style.from_dict(
            {
                "prompt": (
                    "bold ansibrightcyan"
                ),
            }
        ),
    )


def _print_header(
    project_path,
    session_id,
):
    store = SessionStore(
        project_path
    )

    session = store.get(
        session_id
    )

    print()
    print(
        "NEXUS AGENT"
    )
    print(
        str(project_path)
    )

    if session is not None:
        print(
            f"Session: {session.title}"
        )
        print(
            f"Status: {session.status}"
        )

    print()
    print(
        "Esc  -> back to Nexus UI"
    )
    print(
        "Ctrl+C -> interrupt current turn"
    )
    print(
        "/back -> back to Nexus UI"
    )
    print()


def _execute_initial(
    project_path,
    session_id,
) -> bool:
    try:
        run_session(
            project_path,
            session_id,
        )

    except KeyboardInterrupt:
        print()
        print(
            "TURN INTERRUPTED"
        )
        return False

    except Exception as exc:
        print()
        print(
            "TURN FAILED"
        )
        print(
            str(exc)
        )
        return False

    else:
        print()
        print(
            "TURN COMPLETE"
        )
        return True


def _execute_continue(
    project_path,
    session_id,
    instruction,
) -> bool:
    try:
        continue_session(
            project_path,
            session_id,
            instruction,
        )

    except KeyboardInterrupt:
        print()
        print(
            "TURN INTERRUPTED"
        )
        return False

    except Exception as exc:
        print()
        print(
            "TURN FAILED"
        )
        print(
            str(exc)
        )
        return False

    else:
        print()
        print(
            "TURN COMPLETE"
        )
        return True


def run_agent_shell(
    project_path,
    session_id,
    *,
    initial_run=False,
    initial_instruction=None,
    prompt_session: PromptLike | None = None,
) -> AgentShellResult:
    """
    Run a persistent local Nexus Agent session.

    Agent output streams directly in the terminal. After every
    completed, interrupted, or failed turn, control returns to
    ``nexus_agent>``. Escape or /back returns to the Textual UI.
    """

    project_path = str(
        Path(project_path)
    )

    store = SessionStore(
        project_path
    )

    session = store.get(
        session_id
    )

    if session is None:
        raise KeyError(
            session_id
        )

    prompt_session = (
        prompt_session
        or _prompt_session()
    )

    turns = 0

    _print_header(
        project_path,
        session_id,
    )

    if initial_run:
        _execute_initial(
            project_path,
            session_id,
        )

        turns += 1

    if initial_instruction:
        instruction = str(
            initial_instruction
        ).strip()

        if instruction:
            _execute_continue(
                project_path,
                session_id,
                instruction,
            )

            turns += 1

    while True:
        print()

        try:
            instruction = (
                prompt_session.prompt(
                    "nexus_agent> "
                )
            )

        except KeyboardInterrupt:
            # Ctrl+C while idle clears the current input but
            # deliberately keeps the Agent Shell alive.
            print()
            continue

        except EOFError:
            return AgentShellResult(
                project_path=project_path,
                session_id=session_id,
                turns=turns,
                reason="EOF",
            )

        if instruction == ESCAPE_RESULT:
            return AgentShellResult(
                project_path=project_path,
                session_id=session_id,
                turns=turns,
                reason="ESC",
            )

        instruction = str(
            instruction
        ).strip()

        if not instruction:
            continue

        if instruction.lower() in {
            "/back",
            "/exit",
            "/ui",
        }:
            return AgentShellResult(
                project_path=project_path,
                session_id=session_id,
                turns=turns,
                reason="COMMAND",
            )

        if instruction.lower() == "/help":
            print(
                "Esc or /back : return to Nexus UI"
            )
            print(
                "Ctrl+C       : interrupt current turn"
            )
            continue

        _execute_continue(
            project_path,
            session_id,
            instruction,
        )

        turns += 1
