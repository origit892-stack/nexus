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


def _show_status(
    project_path,
    session_id,
):
    """Display current session status information."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return

    history_count = len(session.history) if session.history else 0

    print()
    print("=" * 50)
    print(f"session_id: {session.id}")
    print(f"title: {session.title}")
    print(f"project_path: {session.project_path}")
    print(f"status: {session.status}")
    print(f"history_entries: {history_count}")

    run_id = getattr(session, "run_id", None)
    if run_id:
        print(f"run_id: {run_id}")

    print("=" * 50)
    print()


def _show_history(
    project_path,
    session_id,
):
    """Display conversation/session history in chronological order."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return

    if not session.history or len(session.history) == 0:
        print()
        print("No history entries available.")
        return

    print()
    print("=" * 50)
    print("SESSION HISTORY")
    print("=" * 50)
    print()

    for entry in session.history:
        entry_type = str(entry.get("type", "UNKNOWN")).upper()
        text = str(entry.get("text", "")).strip()

        # Map internal types to display labels
        if entry_type == "instruction":
            display_type = "INSTRUCTION"
        elif entry_type == "result":
            display_type = "RESULT"
        elif entry_type in ("failure", "error"):
            display_type = "FAILURE"
        elif entry_type == "interrupt":
            display_type = "INTERRUPT"
        else:
            display_type = entry_type

        # Only show entries with non-empty text for INSTRUCTION, RESULT types
        if entry_type in ("instruction", "result") and not text:
            continue

        print(f"{display_type}: {text}")

    print("=" * 50)
    print()


def _clear_display(
    project_path,
    session_id,
):
    """Clear terminal display but do NOT erase persisted session history."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        return

    # Clear the terminal by printing blank lines and a separator
    print()
    print("=" * 50)
    print("DISPLAY CLEARED")
    print("=" * 50)
    print()


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

        # Blank/whitespace input creates no history entry - just continue
        if not instruction:
            continue

        # Handle commands
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
                "Available commands:"
            )
            print("  /status    : Show current session status")
            print("  /history   : Display conversation history")
            print("  /clear     : Clear terminal display")
            print("  /back      : Return to Nexus UI")
            print("  /exit      : Exit agent shell")
            continue

        if instruction.lower() == "/status":
            _show_status(
                project_path,
                session_id,
            )
            continue

        if instruction.lower() == "/history":
            _show_history(
                project_path,
                session_id,
            )
            continue

        if instruction.lower() == "/clear":
            _clear_display(
                project_path,
                session_id,
            )
            continue

        # Execute the instruction/turn
        _execute_continue(
            project_path,
            session_id,
            instruction,
        )

        turns += 1
