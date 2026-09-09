from __future__ import annotations

from nexus.agent import Agent
from nexus.config import effective_config
from nexus.sessions.store import (
    SessionStore,
    utc_now,
)


def run_session(
    project_path,
    session_id,
):
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

    session.status = "RUNNING"

    store.save(
        session
    )

    try:
        workspace = str(
            project_path
        )

        cfg = effective_config(
            project_path
        )

        result = Agent(
            cfg,
            workspace,
            role="director",
            live=True,
        ).run(
            session.objective
        )

        session.status = "COMPLETED"
        session.last_result = str(
            result
        )

        run_id = getattr(
            result,
            "run_id",
            None,
        )

        if run_id:
            session.run_id = str(
                run_id
            )

        store.save(
            session
        )

        return result

    except KeyboardInterrupt:
        session.status = "INTERRUPTED"
        session.last_result = (
            "Session interrupted by user."
        )

        store.save(
            session
        )

        raise

    except Exception as exc:
        session.status = "FAILED"
        session.last_result = str(
            exc
        )

        store.save(
            session
        )

        raise

def continue_session(
    project_path,
    session_id,
    instruction,
):
    """
    Continue an existing Nexus session using the same
    session identity and accumulated session history.
    """

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

    instruction = str(
        instruction
    ).strip()

    if not instruction:
        raise ValueError(
            "CONTINUATION_EMPTY"
        )

    if session.history is None:
        session.history = []

    session.history.append(
        {
            "type": "instruction",
            "text": instruction,
            "created_at": utc_now(),
        }
    )

    session.status = "RUNNING"

    store.save(
        session
    )

    workspace = str(
        project_path
    )

    cfg = effective_config(
        project_path
    )

    history_lines = []

    for item in session.history:
        item_type = str(
            item.get(
                "type",
                "event",
            )
        )

        text = str(
            item.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        history_lines.append(
            f"{item_type.upper()}: {text}"
        )

    prompt = (
        "Continue the existing Nexus session.\n\n"
        "SESSION HISTORY:\n"
        + "\n\n".join(
            history_lines
        )
        + "\n\n"
        "Continue from the current real project state. "
        "Do not redo completed work unnecessarily. "
        "Treat the latest INSTRUCTION as the current request."
    )

    try:
        result = Agent(
            cfg,
            workspace,
            role="director",
            live=True,
        ).run(
            prompt
        )

        session.status = "COMPLETED"
        session.last_result = str(
            result
        )

        session.history.append(
            {
                "type": "result",
                "text": str(
                    result
                ),
                "created_at": utc_now(),
            }
        )

        run_id = getattr(
            result,
            "run_id",
            None,
        )

        if run_id:
            session.run_id = str(
                run_id
            )

        store.save(
            session
        )

        return result

    except KeyboardInterrupt:
        session.status = "INTERRUPTED"
        session.last_result = (
            "Session interrupted by user."
        )

        session.history.append(
            {
                "type": "interrupt",
                "text": (
                    "Session interrupted by user."
                ),
                "created_at": utc_now(),
            }
        )

        store.save(
            session
        )

        raise

    except Exception as exc:
        session.status = "FAILED"
        session.last_result = str(
            exc
        )

        session.history.append(
            {
                "type": "error",
                "text": str(
                    exc
                ),
                "created_at": utc_now(),
            }
        )

        store.save(
            session
        )

        raise

