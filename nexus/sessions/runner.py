from __future__ import annotations
from nexus.runtime.prompt_milestones import milestone_plan_from_payload
from nexus.runtime.prompt_milestones import turn_checklist_execution_prompt
from nexus.sessions.milestone_state import begin_final_verification
from nexus.sessions.milestone_state import current_milestone
from nexus.sessions.milestone_state import mark_current_fail
from nexus.sessions.milestone_state import mark_current_pass
from nexus.sessions.milestone_state import mark_current_running
from nexus.sessions.milestone_state import mark_final_fail
from nexus.sessions.milestone_state import mark_final_pass
from nexus.sessions.milestone_state import normalize_milestone_state
from nexus.sessions.milestone_state import user_milestones_complete

from nexus.agent import Agent
from nexus.config import effective_config

from nexus.sessions.context import (
    render_agent_context,
)

from nexus.sessions.state_update import (
    apply_state_update,
    extract_state_update,
    state_update_protocol_prompt,
    strip_state_update,
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
    *,
    capability_policy="NORMAL",
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
        capability_policy=capability_policy,
    )


def run_session(
    project_path,
    session_id,
):
    # NEXUS700_TURN_CHECKLIST_ENTRY_ROUTE_V1
    _turn_result = _run_turn_checklist_session(
        project_path,
        session_id,
        progress=print,
    )
    if _turn_result is not None:
        return _turn_result
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

        session.status = "READY"

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
            status="READY",
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
    # NEXUS700_TURN_CHECKLIST_ENTRY_ROUTE_V1
    _turn_result = _run_turn_checklist_session(
        project_path,
        session_id,
        progress=print,
    )
    if _turn_result is not None:
        return _turn_result
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

    prompt = (
        render_agent_context(
            session,
            current_instruction=instruction,
        )
        + "\n\n"
        + state_update_protocol_prompt()
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

        raw_result_text = str(
            result
        )

        failure_sentinels = (
            "AGENT_EXCEPTION=",
            "MAX_ITERATIONS_REACHED",
            "NEXUS_TOOL_BUDGET_EXCEEDED=",
        )

        if raw_result_text.startswith(
            failure_sentinels
        ):
            raise RuntimeError(
                raw_result_text
            )

        state_update = None
        state_update_error = None
        visible_result_text = raw_result_text

        try:
            state_update = extract_state_update(
                raw_result_text
            )

            if state_update is not None:
                visible_result_text = strip_state_update(
                    raw_result_text
                )

        except Exception as exc:
            state_update_error = (
                f"{type(exc).__name__}: {exc}"
            )

        session.status = "READY"

        session.last_result = visible_result_text

        history.append(
            {
                "type": "result",
                "text": visible_result_text,
                "created_at": utc_now(),
            }
        )

        if run_id:
            session.run_id = run_id

        _update_resume_state(
            session,
            status="READY",
            instruction=instruction,
            run_id=run_id,
            interrupted=False,
            continuation_point="ready-for-next-turn",
        )

        if state_update_error is not None:
            history.append(
                {
                    "type": "state_update_rejected",
                    "text": state_update_error,
                    "created_at": utc_now(),
                }
            )

        store.save(
            session
        )

        explicit_checkpoint = False

        if state_update is not None:
            try:
                updated = apply_state_update(
                    store,
                    session_id,
                    state_update,
                )

                explicit_checkpoint = (
                    state_update.checkpoint
                    is not None
                )

            except Exception as exc:
                refreshed_rejection = store.get(
                    session_id
                )

                if refreshed_rejection is not None:
                    rejection_history = _ensure_history(
                        refreshed_rejection
                    )

                    rejection_history.append(
                        {
                            "type": "state_update_rejected",
                            "text": (
                                f"{type(exc).__name__}: {exc}"
                            ),
                            "created_at": utc_now(),
                        }
                    )

                    store.save(
                        refreshed_rejection
                    )

        refreshed = store.get(
            session_id
        )

        if (
            refreshed is not None
            and refreshed.working_state.get(
                "auto_checkpoint",
                True,
            )
            and not explicit_checkpoint
        ):
            next_serial = (
                int(
                    refreshed.working_state.get(
                        "checkpoint_serial",
                        0,
                    )
                    or 0
                )
                + 1
            )

            clean_instruction = (
                str(
                    instruction
                )
                .strip()
                .replace(
                    "\n",
                    " ",
                )
            )

            if len(
                clean_instruction
            ) > 160:
                clean_instruction = (
                    clean_instruction[:160]
                    + "..."
                )

            checkpoint = (
                f"Turn {next_serial} completed: "
                f"{clean_instruction}"
            )

            store.increment_checkpoint(
                session_id,
                checkpoint,
            )

        if visible_result_text != raw_result_text:
            return visible_result_text

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


def _load_persisted_milestone_plan(
    state,
):
    from nexus.runtime.prompt_milestones import (
        milestone_plan_from_payload,
    )

    payload = state.get("plan")

    if not isinstance(payload, dict):
        raise ValueError(
            "MILESTONE_PLAN_NOT_PERSISTED"
        )

    prompt = state.get(
        "master_prompt"
    )

    if not isinstance(prompt, str):
        raise ValueError(
            "MASTER_PROMPT_NOT_PERSISTED"
        )

    return milestone_plan_from_payload(
        prompt=prompt,
        payload=payload,
    )


def _final_verification_prompt(
    plan,
) -> str:
    definitions = "\n".join(
        "- " + str(value)
        for value in plan.final_completion_definition
    )

    return (
        "NEXUS_MILESTONE_FINAL_VERIFICATION_V1\n"
        "Verify the completed master milestone plan.\n\n"
        "MASTER PROMPT:\n"
        + plan.master_prompt
        + "\n\nFINAL COMPLETION DEFINITION:\n"
        + definitions
        + "\n\n"
        "Do not redo completed milestones. "
        "Verify whether the master request as a whole "
        "meets its final completion definition."
    )


def _run_milestone_state_machine(
    project_path,
    session_id,
    *,
    agent_factory=None,
    progress=None,
):
    from nexus.sessions.store import (
        SessionStore,
    )

    from nexus.sessions.milestone_state import (
        normalize_milestone_state,
        current_milestone,
        mark_current_running,
        mark_current_pass,
        mark_current_fail,
        user_milestones_complete,
        begin_final_verification,
        mark_final_pass,
        mark_final_fail,
    )

    from nexus.runtime.prompt_milestones import (
        milestone_execution_prompt,
        final_verification_execution_prompt,
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

    state = normalize_milestone_state(
        session.working_state.get(
            "milestone_state"
        )
    )

    if not state["active"]:
        raise ValueError(
            "MILESTONE_STATE_NOT_ACTIVE"
        )

    plan = _load_persisted_milestone_plan(
        state
    )

    if agent_factory is None:
        agent_factory = _agent

    # NEXUS700_ORCHESTRATOR_POLICY_PROPAGATION_V1
    def _make_agent(policy):
        try:
            return agent_factory(
                project_path,
                capability_policy=policy,
            )
        except TypeError as exc:
            # Test factories and legacy factories may accept
            # only project_path. Never silently downgrade the
            # real factory from READ_ONLY to NORMAL.
            if agent_factory is _agent:
                raise
            return agent_factory(
                project_path
            )

    while True:
        item = current_milestone(
            state
        )

        if item is None:
            break

        index = state[
            "current_milestone_index"
        ]

        if progress is not None:
            progress(
                "MILESTONE "
                + str(item["id"])
                + ": RUNNING"
            )

        state = mark_current_running(
            state
        )

        store.update_working_state(
            session_id,
            milestone_state=state,
            active_item=item["id"],
            current_plan=(
                "Execute "
                + str(item["id"])
                + ": "
                + str(item["title"])
            ),
        )

        instruction = (
            turn_checklist_execution_prompt(
                plan=plan,
                index=index,
            )
        )

        capability_policy = (
            _milestone_capability_policy(
                plan,
                milestone_index=index,
            )
        )

        if progress is not None:
            progress(
                "MILESTONE "
                + str(item["id"])
                + ": CAPABILITY="
                + capability_policy
            )

        agent = _make_agent(
            capability_policy
        )

        try:
            result = agent.run(
                instruction
            )

        except BaseException as exc:
            state = mark_current_fail(
                state,
                result=(
                    type(exc).__name__
                    + ": "
                    + str(exc)
                ),
                evidence=[
                    {
                        "type":
                            "agent_exception",
                        "milestone_id":
                            item["id"],
                    }
                ],
            )

            store.update_working_state(
                session_id,
                milestone_state=state,
                blockers=[
                    (
                        str(item["id"])
                        + " failed: "
                        + type(exc).__name__
                        + ": "
                        + str(exc)
                    )
                ],
            )

            if progress is not None:
                progress(
                    "MILESTONE "
                    + str(item["id"])
                    + ": FAIL"
                )

            raise

        returned_failure = (
            _milestone_result_failure(
                result
            )
        )

        if returned_failure is not None:
            state = mark_current_fail(
                state,
                result=returned_failure,
                evidence=[
                    {
                        "type":
                            "agent_reported_failure",
                        "milestone_id":
                            item["id"],
                    }
                ],
            )

            store.update_working_state(
                session_id,
                milestone_state=state,
                blockers=[
                    (
                        str(item["id"])
                        + " failed: "
                        + returned_failure
                    )
                ],
            )

            if progress is not None:
                progress(
                    "MILESTONE "
                    + str(item["id"])
                    + ": FAIL"
                )

            raise RuntimeError(
                "MILESTONE_AGENT_REPORTED_FAILURE:"
                + str(item["id"])
                + ":"
                + returned_failure
            )

        state = mark_current_pass(
            state,
            result=result,
            evidence=[
                {
                    "type":
                        "verified_agent_completion",
                    "milestone_id":
                        item["id"],
                }
            ],
        )

        store.update_working_state(
            session_id,
            milestone_state=state,
            last_completed_item=item["id"],
            blockers=[],
        )

        if progress is not None:
            progress(
                "MILESTONE "
                + str(item["id"])
                + ": PASS"
            )

    if not user_milestones_complete(
        state
    ):
        raise RuntimeError(
            "MILESTONE_SEQUENCE_ENDED_INCOMPLETE"
        )

    final_status = state[
        "final_verification"
    ]["status"]

    if final_status == "PASS":
        return state.get(
            "master_result"
        )

    state = begin_final_verification(
        state
    )

    store.update_working_state(
        session_id,
        milestone_state=state,
        active_item="FinalVerification",
        current_plan=(
            "Verify master completion"
        ),
    )

    if progress is not None:
        progress(
            "FINAL VERIFICATION: RUNNING"
        )

    final_capability_policy = (
        _milestone_capability_policy(
            plan,
            milestone_index=None,
        )
    )

    if progress is not None:
        progress(
            "FINAL VERIFICATION: CAPABILITY="
            + final_capability_policy
        )

    final_agent = _make_agent(
        final_capability_policy
    )

    try:
        final_result = final_agent.run(
            final_verification_execution_prompt(
                _final_verification_prompt(
                    plan
                ),
                mutation_policy=final_capability_policy,
                restrictions=plan.global_restrictions,
            )
        )

    except BaseException as exc:
        state = mark_final_fail(
            state,
            result=(
                type(exc).__name__
                + ": "
                + str(exc)
            ),
            evidence=[
                {
                    "type":
                        "final_verification_exception",
                }
            ],
        )

        store.update_working_state(
            session_id,
            milestone_state=state,
            blockers=[
                (
                    "FinalVerification failed: "
                    + type(exc).__name__
                    + ": "
                    + str(exc)
                )
            ],
        )

        if progress is not None:
            progress(
                "FINAL VERIFICATION: FAIL"
            )

        raise

    state = mark_final_pass(
        state,
        result=final_result,
        evidence=[
            {
                "type":
                    "verified_agent_completion",
                "milestone_id":
                    "FinalVerification",
            }
        ],
    )

    store.update_working_state(
        session_id,
        milestone_state=state,
        active_item=None,
        current_plan=None,
        blockers=[],
    )

    if progress is not None:
        progress(
            "FINAL VERIFICATION: PASS"
        )
        progress(
            "MASTER COMPLETE"
        )

    return final_result


def _milestone_result_failure(
    result,
):
    """
    Detect authoritative non-completion returned as ordinary
    Agent text.

    VERIFICATION_PENDING is emitted by the Agent completion
    evidence layer and cannot be converted into milestone PASS.
    """
    text = str(
        result or ""
    ).strip()

    failure_prefixes = (
        "AGENT_EXCEPTION=",
        "NEXUS_MILESTONE_UNDERSTANDING_FAILED:",
        "NEXUS_UNDERSTANDING_FAILED:",
        "NEXUS_PLANNING_FAILED:",
        "VERIFICATION_PENDING",
        "NEXUS_ACCEPTANCE_OVERRIDE=FAIL",
    )

    for prefix in failure_prefixes:
        if text.startswith(
            prefix
        ):
            return text

    return None

def _milestone_capability_policy(
    plan,
    *,
    milestone_index=None,
) -> str:
    """
    Runtime authorization comes only from the persisted
    compiled milestone mutation_policy.

    Free-form restrictions are boundaries, not authorization.
    Missing, malformed, and UNSURE policy fail closed.
    """
    if milestone_index is None:
        policies = tuple(
            str(
                getattr(
                    milestone,
                    "mutation_policy",
                    "UNSURE",
                )
                or "UNSURE"
            ).strip().upper()
            for milestone in plan.milestones
        )

        if "MUTATING" in policies:
            return "NORMAL"

        return "READ_ONLY"

    index = int(
        milestone_index
    )

    if (
        index < 0
        or index >= len(
            plan.milestones
        )
    ):
        raise IndexError(
            "MILESTONE_INDEX_OUT_OF_RANGE"
        )

    policy = str(
        getattr(
            plan.milestones[index],
            "mutation_policy",
            "UNSURE",
        )
        or "UNSURE"
    ).strip().upper()

    if policy == "MUTATING":
        return "NORMAL"

    return "READ_ONLY"


# NEXUS700_TURN_CHECKLIST_PRODUCT_ROUTE_V1

def _prepare_turn_checklist_session(
    project_path,
    session_id,
    *,
    progress=None,
):
    from nexus.runtime.prompt_milestones import (
        analyze_prompt_complexity,
        should_activate_turn_checklist,
    )
    from nexus.runtime.understanding import (
        compile_master_prompt,
    )
    from nexus.sessions.milestone_state import (
        normalize_milestone_state,
        state_from_plan,
    )

    store = SessionStore(project_path)

    session = store.get(session_id)

    if session is None:
        raise KeyError(session_id)

    existing = normalize_milestone_state(
        session.working_state.get(
            "milestone_state"
        )
    )

    # A persisted checklist is authoritative.
    # Resume must never recompile the master prompt.
    if (
        existing["active"]
        and existing.get("plan")
    ):
        if progress is not None:
            progress(
                "MASTER PROMPT: RESUMING CHECKLIST"
            )
        return existing

    master_prompt = str(
        session.objective or ""
    )

    complexity = analyze_prompt_complexity(
        master_prompt
    )

    if not should_activate_turn_checklist(
        master_prompt
    ):
        return None

    if progress is not None:
        progress(
            "MASTER PROMPT: MILESTONE MODE"
        )
        progress(
            "MASTER PROMPT: complexity="
            + str(complexity.score)
        )

    plan, metrics = compile_master_prompt(
        master_prompt,
        progress=progress,
    )

    state = state_from_plan(plan)

    store.update_working_state(
        session_id,
        milestone_state=state,
    )

    if progress is not None:
        progress(
            "MASTER PROMPT: "
            + str(len(plan.milestones))
            + " MILESTONES"
        )

        for milestone in plan.milestones:
            progress(
                "[ ] "
                + str(milestone.id)
                + ": "
                + str(milestone.title)
            )

    return state


def _run_turn_checklist_session(
    project_path,
    session_id,
    *,
    progress=None,
    agent_factory=None,
):
    state = _prepare_turn_checklist_session(
        project_path,
        session_id,
        progress=progress,
    )

    if state is None:
        return None

    return _run_milestone_state_machine(
        project_path,
        session_id,
        progress=progress,
        agent_factory=agent_factory,
    )

