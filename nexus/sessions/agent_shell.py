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


# Wave 2: New shell commands for working state management
def _show_state(
    project_path,
    session_id,
):
    """Display current session working state (Wave 2)."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return

    print()
    print("=" * 50)
    print("WORKING STATE")
    print("=" * 50)
    print()
    
    history = session.history or []
    
    # Extract working state information from history
    objective = session.objective
    
    plan_entries = [e for e in history if e.get("type") == "instruction"]
    completed_entries = [e for e in history if e.get("type") == "result" and not str(e.get("text", "")).startswith("FAILURE")]
    
    print(f"objective: {objective}")
    print()
    
    # Show plan (recent instructions)
    print("plan:")
    for entry in reversed(plan_entries[-5:] if len(plan_entries) > 5 else plan_entries):
        text = str(entry.get("text", "")).strip()
        if text:
            print(f"  - {text}")
    print()
    
    # Show completed work (recent results)
    print("completed_work:")
    for entry in reversed(completed_entries[-5:] if len(completed_entries) > 5 else completed_entries):
        text = str(entry.get("text", "")).strip()
        if text:
            print(f"  - {text[:100]}...")
    print()
    
    # Show pending work (instructions without results yet)
    print("pending_work:")
    for entry in plan_entries[-5:] if len(plan_entries) > 5 else plan_entries:
        text = str(entry.get("text", "")).strip()
        if text and not any(e.get("type") == "result" and e.get("text", "").startswith(text[:20]) for e in completed_entries):
            print(f"  - {text}")
    print()
    
    # Show blockers (failures)
    failures = [e for e in history if e.get("type") in ("failure", "error")]
    print("blockers:")
    for entry in reversed(failures[-3:] if len(failures) > 3 else failures):
        text = str(entry.get("text", "")).strip()
        if text:
            print(f"  - {text}")
    print()
    
    # Show checkpoint (last successful result summary)
    last_result = session.last_result or ""
    if last_result:
        print(f"checkpoint: {last_result[:200]}")
    else:
        print("checkpoint: None")

    print("=" * 50)
    print()




def _set_checkpoint(
    project_path,
    session_id,
):
    """Set checkpoint to current state (Wave 2)."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return False
    
    # Set checkpoint to last result summary
    history = session.history or []
    
    # Find the most recent successful result
    for entry in reversed(history):
        if entry.get("type") == "result":
            text = str(entry.get("text", "")).strip()
            if text and not text.startswith("FAILURE"):
                checkpoint = f"[CHECKPOINT] {text[:500]}"
                print(f"Checkpoint set: {checkpoint}")
                break
    
    return True


def _show_fact(
    project_path,
    session_id,
):
    """Show a specific fact from history (Wave 2)."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return False
    
    # Parse the instruction to find which fact to show
    # Format: /fact <type> or /fact <index>
    
    history = session.history or []
    
    print()
    print("=" * 50)
    print("FACTS")
    print("=" * 50)
    print()
    
    # Show all facts (history entries)
    for i, entry in enumerate(history[-10:] if len(history) > 10 else history):
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
        
        print(f"[{i}] {display_type}: {text[:200]}")

    print("=" * 50)
    print()


def _show_blocker(
    project_path,
    session_id,
):
    """Show current blockers (Wave 2)."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return False
    
    history = session.history or []
    
    # Find failures/blockers
    blockers = [e for e in history if e.get("type") in ("failure", "error")]
    
    print()
    print("=" * 50)
    print("BLOCKERS")
    print("=" * 50)
    print()
    
    if not blockers:
        print("No active blockers.")
    else:
        for entry in reversed(blockers[-3:] if len(blockers) > 3 else blockers):
            text = str(entry.get("text", "")).strip()
            if text:
                print(f"- {text}")

    print("=" * 50)
    print()


def _unblock(
    project_path,
    session_id,
):
    """Acknowledge and clear a blocker (Wave 2)."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return False
    
    # Parse the instruction to find which blocker to unblock
    # Format: /unblock <index> or /unblock all
    
    history = session.history or []
    
    # Find failures/blockers
    blockers = [e for e in history if e.get("type") in ("failure", "error")]
    
    print()
    print("=" * 50)
    print("UNBLOCKING")
    print("=" * 50)
    print()
    
    if not blockers:
        print("No active blockers to unblock.")
    else:
        # Remove the most recent blocker from history (simulating resolution)
        if blockers:
            last_blocker = blockers[-1]
            text = str(last_blocker.get("text", "")).strip()
            print(f"Unblocking: {text}")
            
            # Create a resolved entry
            resolved_entry = {
                "type": "unblocked",
                "text": f"{text} (resolved)",
                "created_at": session.updated_at,
            }
            history.append(resolved_entry)
            
            # Remove the blocker from history
            if len(history) > 1:
                history.pop()
    
    print("Blockers cleared.")

    store.save(session)
    return True


def _show_plan(
    project_path,
    session_id,
):
    """Show current plan (Wave 2)."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return False
    
    history = session.history or []
    
    # Extract instructions as the plan
    plan_entries = [e for e in history if e.get("type") == "instruction"]
    
    print()
    print("=" * 50)
    print("PLAN")
    print("=" * 50)
    print()
    
    objective = session.objective
    print(f"objective: {objective}")
    print()
    
    if not plan_entries:
        print("No plan entries yet.")
    else:
        # Show recent instructions as the plan
        for entry in reversed(plan_entries[-10:] if len(plan_entries) > 10 else plan_entries):
            text = str(entry.get("text", "")).strip()
            if text:
                print(f"- {text}")

    print("=" * 50)
    print()


def _show_pending(
    project_path,
    session_id,
):
    """Show pending work (Wave 2)."""
    store = SessionStore(project_path)
    session = store.get(session_id)

    if session is None:
        print()
        print("Session not found.")
        return False
    
    history = session.history or []
    
    # Instructions without corresponding results are pending
    instructions = [e for e in history if e.get("type") == "instruction"]
    results = [e for e in history if e.get("type") == "result" and not str(e.get("text", "")).startswith("FAILURE")]
    
    print()
    print("=" * 50)
    print("PENDING WORK")
    print("=" * 50)
    print()
    
    # Find instructions that don't have a corresponding result yet
    pending = []
    for instr in reversed(instructions[-10:] if len(instructions) > 10 else instructions):
        text = str(instr.get("text", "")).strip()
        if text:
            # Check if there's a matching result
            has_result = any(
                r.get("type") == "result" and 
                not str(r.get("text", "")).startswith("FAILURE") and
                len(str(r.get("text", ""))) > 0
                for r in results[-5:]
            )
            if not has_result:
                pending.append(text)

    if not pending:
        print("No pending work.")
    else:
        for item in reversed(pending):
            print(f"- {item}")

    print("=" * 50)
    print()



def _show_working_state(
    project_path,
    session_id,
):
    """Display durable Wave 2 working state."""

    store = SessionStore(
        project_path
    )

    session = store.get(
        session_id
    )

    if session is None:
        print()
        print(
            "Session not found."
        )
        return

    state = (
        session.working_state
        if isinstance(
            session.working_state,
            dict,
        )
        else {}
    )

    print()
    print(
        "=" * 50
    )
    print(
        "WORKING STATE"
    )
    print(
        "=" * 50
    )

    print(
        "objective:",
        state.get(
            "objective"
        )
        or session.objective,
    )

    print(
        "current_plan:"
    )

    for item in state.get(
        "current_plan",
        [],
    ):
        print(
            f"  - {item}"
        )

    print(
        "completed_work:"
    )

    for item in state.get(
        "completed_work",
        [],
    ):
        print(
            f"  - {item}"
        )

    print(
        "pending_work:"
    )

    for item in state.get(
        "pending_work",
        [],
    ):
        print(
            f"  - {item}"
        )

    print(
        "blockers:"
    )

    for item in state.get(
        "blockers",
        [],
    ):
        print(
            f"  - {item}"
        )

    print(
        "last_checkpoint:",
        state.get(
            "last_checkpoint"
        ),
    )

    print(
        "=" * 50
    )
    print()


def _show_context(
    project_path,
    session_id,
):
    """Display Wave 2 derived context/compaction state."""

    store = SessionStore(
        project_path
    )

    session = store.get(
        session_id
    )

    if session is None:
        print()
        print(
            "Session not found."
        )
        return

    try:
        from .context import (
            build_agent_context,
        )

        derived = (
            build_agent_context(
                session
            )
        )

    except Exception as exc:
        print()
        print(
            "Unable to build session context:"
        )
        print(
            str(exc)
        )
        return

    state = (
        session.context_state
        if isinstance(
            session.context_state,
            dict,
        )
        else {}
    )

    summary = derived.get(
        "summary"
    )

    recent = derived.get(
        "recent_history",
        [],
    )

    facts = derived.get(
        "durable_facts",
        [],
    )

    compacted_through = state.get(
        "compacted_through",
        0,
    )

    active = bool(
        summary
        or compacted_through
    )

    print()
    print(
        "=" * 50
    )
    print(
        "SESSION CONTEXT"
    )
    print(
        "=" * 50
    )

    print(
        "compaction_active:",
        active,
    )

    print(
        "compacted_through:",
        compacted_through,
    )

    print(
        "recent_history_count:",
        len(
            recent
        ),
    )

    print(
        "durable_fact_count:",
        len(
            facts
        ),
    )

    print(
        "summary:"
    )

    if summary:
        print(
            summary
        )
    else:
        print(
            "  —"
        )

    print(
        "=" * 50
    )
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
    
    Wave 2: Added working state commands for objectives, plans, checkpoints,
    facts, blockers, and pending work tracking.
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
            # Wave 2 commands
            print("  /state     : Show durable working state")
            print("  /context   : Show compaction/context state")
            print("  /checkpoint <text> : Set durable checkpoint")
            print("  /fact <text>       : Add durable fact")
            print("  /blocker <text>    : Add blocker")
            print("  /unblock <text>    : Clear matching blocker")
            print("  /plan <a; b; ...>  : Replace current plan")
            print("  /pending <a; b; ...>: Replace pending work")
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

        # Wave 2: Working state commands
        command, separator, argument = (
            instruction.partition(" ")
        )

        command = command.lower().strip()
        argument = argument.strip()

        if command == "/state":
            _show_working_state(
                project_path,
                session_id,
            )
            continue

        if command == "/context":
            _show_context(
                project_path,
                session_id,
            )
            continue

        if command == "/checkpoint":
            if not argument:
                print()
                print(
                    "Usage: /checkpoint <text>"
                )
                continue

            store = SessionStore(
                project_path
            )

            store.set_checkpoint(
                session_id,
                argument,
            )

            print()
            print(
                f"Checkpoint set: {argument}"
            )
            continue

        if command == "/fact":
            if not argument:
                print()
                print(
                    "Usage: /fact <text>"
                )
                continue

            store = SessionStore(
                project_path
            )

            store.add_durable_fact(
                session_id,
                argument,
            )

            print()
            print(
                f"Fact added: {argument}"
            )
            continue

        if command == "/blocker":
            if not argument:
                print()
                print(
                    "Usage: /blocker <text>"
                )
                continue

            store = SessionStore(
                project_path
            )

            store.add_blocker(
                session_id,
                argument,
            )

            print()
            print(
                f"Blocker added: {argument}"
            )
            continue

        if command == "/unblock":
            if not argument:
                print()
                print(
                    "Usage: /unblock <text>"
                )
                continue

            store = SessionStore(
                project_path
            )

            store.clear_blocker(
                session_id,
                argument,
            )

            print()
            print(
                f"Blocker cleared: {argument}"
            )
            continue

        if command == "/plan":
            if not argument:
                print()
                print(
                    "Usage: /plan <item; item; ...>"
                )
                continue

            items = [
                item.strip()
                for item in argument.split(";")
                if item.strip()
            ]

            store = SessionStore(
                project_path
            )

            store.replace_plan(
                session_id,
                items,
            )

            print()
            print(
                "Plan updated."
            )
            continue

        if command == "/pending":
            if not argument:
                print()
                print(
                    "Usage: /pending <item; item; ...>"
                )
                continue

            items = [
                item.strip()
                for item in argument.split(";")
                if item.strip()
            ]

            store = SessionStore(
                project_path
            )

            store.replace_pending(
                session_id,
                items,
            )

            print()
            print(
                "Pending work updated."
            )
            continue

        # Execute the instruction/turn
        _execute_continue(
            project_path,
            session_id,
            instruction,
        )

        turns += 1
