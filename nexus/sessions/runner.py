from __future__ import annotations

from nexus.agent import Agent
from nexus.config import effective_config

from nexus.sessions.context import (
    render_agent_context,
)

from nexus.sessions.store import (
    SessionStore,
    utc_now,
)


def _ensure_history(
    session,
):
    if not isinstance(
        session.history,
        list,
    ):
        session.history = []

    return session.history


def _resume_state(
    session,
):
    state = getattr(
        session,
        "resume_state",
        None,
    )

    if not isinstance(
        state,
        dict,
    ):
        state = {}

    defaults = {
        "last_run_id": None,
        "last_status": None,
        "last_instruction": None,
        "continuation_point": None,
        "interrupted": False,
        "updated_at": None,
    }

    defaults.update(
        state
    )

    session.resume_state = defaults

    return defaults


def _update_resume_state(
    session,
    *,
    status,
    instruction=None,
    run_id=None,
    interrupted=False,
    continuation_point=None,
):
    state = _resume_state(
        session
    )

    if instruction is not None:
        state[
            "last_instruction"
        ] = str(
            instruction
        )

    if run_id is not None:
        state[
            "last_run_id"
        ] = str(
            run_id
        )

    state[
        "last_status"
    ] = str(
        status
    )

    state[
        "interrupted"
    ] = bool(
        interrupted
    )

    state[
        "continuation_point"
    ] = continuation_point

    state[
        "updated_at"
    ] = utc_now()

    session.resume_state = state


def _result_run_id(
    result,
):
    value = getattr(
        result,
        "run_id",
        None,
    )

    if value is None:
        return None

    return str(
        value
    )


def _agent(
    project_path,
):
    workspace = str(
        project_path
    )

    cfg = effective_config(
        project_path
    )

    return Agent(
        cfg,
        workspace,
        role="director",
        live=True,
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

    history = _ensure_history(
        session
    )

    session.status = "RUNNING"

    _update_resume_state(
        session,
        status="RUNNING",
        instruction=session.objective,
        interrupted=False,
        continuation_point="initial-turn-running",
    )

    store.save(
        session
    )

    try:
        result = _agent(
            project_path
        ).run(
            session.objective
        )

        run_id = _result_run_id(
            result
        )

        session.status = "COMPLETED"

        session.last_result = str(
            result
        )

        if run_id:
            session.run_id = run_id

        history.append(
            {
                "type": "result",
                "text": str(
                    result
                ),
                "created_at": utc_now(),
            }
        )

        _update_resume_state(
            session,
            status="COMPLETED",
            instruction=session.objective,
            run_id=run_id,
            interrupted=False,
            continuation_point="ready-for-next-turn",
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

        history.append(
            {
                "type": "interrupt",
                "text": (
                    "Session interrupted by user."
                ),
                "created_at": utc_now(),
            }
        )

        _update_resume_state(
            session,
            status="INTERRUPTED",
            instruction=session.objective,
            run_id=session.run_id,
            interrupted=True,
            continuation_point="initial-turn-interrupted",
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

        history.append(
            {
                "type": "failure",
                "text": str(
                    exc
                ),
                "created_at": utc_now(),
            }
        )

        _update_resume_state(
            session,
            status="FAILED",
            instruction=session.objective,
            run_id=session.run_id,
            interrupted=False,
            continuation_point="failed-turn-recovery",
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
    Continue an existing Nexus session while preserving
    the same durable session identity.
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
        return None

    history = _ensure_history(
        session
    )

    history.append(
        {
            "type": "instruction",
            "text": instruction,
            "created_at": utc_now(),
        }
    )

    session.status = "RUNNING"

    _update_resume_state(
        session,
        status="RUNNING",
        instruction=instruction,
        run_id=session.run_id,
        interrupted=False,
        continuation_point="turn-running",
    )

    store.save(
        session
    )

    prompt = render_agent_context(
        session,
        current_instruction=instruction,
    )

    # build_agent_context/render_agent_context may update
    # derived context_state, so persist it before inference.
    store.save(
        session
    )

    try:
        result = _agent(
            project_path
        ).run(
            prompt
        )

        run_id = _result_run_id(
            result
        )

        session.status = "COMPLETED"

        session.last_result = str(
            result
        )

        history.append(
            {
                "type": "result",
                "text": str(
                    result
                ),
                "created_at": utc_now(),
            }
        )

        if run_id:
            session.run_id = run_id

        _update_resume_state(
            session,
            status="COMPLETED",
            instruction=instruction,
            run_id=run_id,
            interrupted=False,
            continuation_point="ready-for-next-turn",
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

        history.append(
            {
                "type": "interrupt",
                "text": (
                    "Session interrupted by user."
                ),
                "created_at": utc_now(),
            }
        )

        _update_resume_state(
            session,
            status="INTERRUPTED",
            instruction=instruction,
            run_id=session.run_id,
            interrupted=True,
            continuation_point="interrupted-turn",
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

        history.append(
            {
                "type": "failure",
                "text": str(
                    exc
                ),
                "created_at": utc_now(),
            }
        )

        _update_resume_state(
            session,
            status="FAILED",
            instruction=instruction,
            run_id=session.run_id,
            interrupted=False,
            continuation_point="failed-turn-recovery",
        )

        store.save(
            session
        )

        raise
