from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import json

from nexus.runtime.understanding import (
    UnderstandingError,
    _generate,
    _load_model_cached,
    extract_json_object,
    load_project_context,
    load_understanding_config,
)


class PlanningError(
    RuntimeError
):
    pass


PLAN_FIELDS = (
    "current_phase",
    "authorized_now",
    "forbidden_now",
    "deferred_actions",
    "approval_gates",
    "targets",
    "search_strategy",
    "evidence_plan",
    "evaluation_plan",
    "selection_strategy",
    "first_actions",
    "stop_conditions",
)


LIST_FIELDS = (
    "authorized_now",
    "forbidden_now",
    "deferred_actions",
    "approval_gates",
    "targets",
    "search_strategy",
    "evidence_plan",
    "evaluation_plan",
    "selection_strategy",
    "first_actions",
    "stop_conditions",
)


PLAN_LABELS = (
    (
        "P1",
        "Resolve the current authorized phase",
    ),
    (
        "P2",
        "Determine what is authorized now",
    ),
    (
        "P3",
        "Determine what is forbidden now",
    ),
    (
        "P4",
        "Identify deferred actions",
    ),
    (
        "P5",
        "Identify approval gates",
    ),
    (
        "P6",
        "Identify concrete task targets",
    ),
    (
        "P7",
        "Build the search strategy",
    ),
    (
        "P8",
        "Build the evidence plan",
    ),
    (
        "P9",
        "Build the evaluation plan",
    ),
    (
        "P10",
        "Build the selection strategy",
    ),
    (
        "P11",
        "Choose the first focused actions",
    ),
    (
        "P12",
        "Define stop conditions",
    ),
)


def _clean_understanding(
    understanding: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in understanding.items()
        if not key.startswith("_")
    }


def _plan_schema(
) -> dict[str, Any]:
    return {
        "current_phase": "string",
        "authorized_now": [
            "string"
        ],
        "forbidden_now": [
            "string"
        ],
        "deferred_actions": [
            "string"
        ],
        "approval_gates": [
            "string"
        ],
        "targets": [
            "string"
        ],
        "search_strategy": [
            "string"
        ],
        "evidence_plan": [
            "string"
        ],
        "evaluation_plan": [
            "string"
        ],
        "selection_strategy": [
            "string"
        ],
        "first_actions": [
            "string"
        ],
        "stop_conditions": [
            "string"
        ],
    }


def normalize_plan_structure(
    payload: dict[str, Any],
) -> dict[str, Any]:
    result = dict(
        payload
    )

    for field in LIST_FIELDS:
        if (
            field in result
            and isinstance(
                result[field],
                str,
            )
        ):
            result[field] = [
                result[field]
            ]

    return result


def validate_plan(
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for field in PLAN_FIELDS:
        if field not in payload:
            errors.append(
                f"missing field: {field}"
            )

    if (
        "current_phase"
        in payload
        and not isinstance(
            payload[
                "current_phase"
            ],
            str,
        )
    ):
        errors.append(
            "current_phase must be string"
        )

    for field in LIST_FIELDS:
        if (
            field in payload
            and not isinstance(
                payload[field],
                list,
            )
        ):
            errors.append(
                f"{field} must be list"
            )

    return errors


def _planner_system(
    context: str,
) -> str:
    return (
        "You are the Nexus Execution Planner.\n\n"
        "The Understanding Model has already interpreted "
        "the user's natural-language request.\n"
        "Your job is to convert that understanding into "
        "a focused, evidence-driven execution plan before "
        "the Director receives tools.\n\n"
        "You have NO tools.\n"
        "Do NOT execute anything.\n"
        "Do NOT invent filesystem paths or project facts.\n"
        "Do NOT assume later phases are currently authorized.\n"
        "Do NOT broaden the task merely because the project "
        "contains many systems.\n\n"
        "Your most important responsibilities are:\n"
        "- separate current authorization from future intent,\n"
        "- respect user review/approval gates,\n"
        "- identify concrete targets,\n"
        "- prevent broad directory wandering,\n"
        "- define the most useful evidence to gather,\n"
        "- plan technical/visual evaluation when appropriate,\n"
        "- define selection logic when the user asks to choose,\n"
        "- stop when the authorized phase is complete.\n\n"
        "For discovery tasks, prefer targeted search and "
        "evidence resolution over recursively walking every "
        "directory in the repository.\n\n"
        "For asset/mesh work, identify actual source/model/"
        "mesh/manifest/usage evidence before judging quality.\n\n"
        "If a family contains more than three viable variants "
        "and the user wants a selection, compare all viable "
        "candidates and propose the best three. Do not delete "
        "non-selected candidates unless separately authorized.\n\n"
        "After reasoning, return ONE JSON object using exactly "
        "this schema:\n"
        + json.dumps(
            _plan_schema(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "CANONICAL PROJECT CONTEXT:\n"
        + context
    )


def _repair_messages(
    *,
    system: str,
    understanding: dict[str, Any],
    invalid_output: str,
    errors: list[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                system
                + "\n\n"
                "PLAN SCHEMA REPAIR MODE.\n"
                "Do not redo broad reasoning.\n"
                "Do not invent project facts.\n"
                "Correct the structure only.\n"
                "Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                "UNDERSTANDING:\n"
                + json.dumps(
                    understanding,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n\nINVALID PLAN:\n"
                + invalid_output
                + "\n\nVALIDATION ERRORS:\n"
                + "\n".join(
                    "- " + error
                    for error in errors
                )
            ),
        },
    ]




def reconcile_plan_authorization(
    *,
    understanding: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Reconcile structural authorization boundaries.

    This function does NOT classify the task, infer domain
    semantics, or invent project actions.

    It only resolves contradictions using actions that the
    Understanding Model or Planner already produced.
    """
    result = normalize_plan_structure(
        plan
    )

    authorized = list(
        result.get(
            "authorized_now",
            [],
        )
    )

    forbidden = list(
        result.get(
            "forbidden_now",
            [],
        )
    )

    deferred = list(
        result.get(
            "deferred_actions",
            [],
        )
    )

    approval = list(
        result.get(
            "approval_gates",
            [],
        )
    )

    first_actions = list(
        result.get(
            "first_actions",
            [],
        )
    )

    recommended = understanding.get(
        "recommended_plan",
        [],
    )

    if isinstance(
        recommended,
        str,
    ):
        recommended = [
            recommended
        ]

    # If the Planner produced concrete first actions but left
    # current authorization empty, use those same Planner-
    # generated first actions as current work.
    #
    # No new domain action is invented here.
    if (
        not authorized
        and first_actions
    ):
        authorized = list(
            first_actions
        )

    # Fallback only when the Planner emitted no first_actions.
    # The Understanding Model's own recommended current work
    # can supply the existing semantic content.
    if (
        not authorized
        and recommended
    ):
        authorized = list(
            recommended
        )

    # A deferred action behind an approval gate cannot also
    # have an undefined current authorization boundary.
    #
    # Preserve the exact action text and add only a generic
    # temporal qualifier.
    if (
        deferred
        and approval
        and not forbidden
    ):
        forbidden = [
            (
                "Not authorized before the required "
                "approval gate: "
                + str(action)
            )
            for action in deferred
        ]

    # Remove exact contradictions where the same action appears
    # in both authorized_now and deferred_actions.
    authorized_keys = {
        str(item)
        .strip()
        .casefold()
        for item in authorized
        if str(item).strip()
    }

    deferred = [
        item
        for item in deferred
        if (
            str(item)
            .strip()
            .casefold()
            not in authorized_keys
        )
    ]

    # A deferred action cannot simultaneously be an exact stop
    # condition for the current phase.
    deferred_keys = {
        str(item)
        .strip()
        .casefold()
        for item in deferred
        if str(item).strip()
    }

    stop_conditions = [
        item
        for item in result.get(
            "stop_conditions",
            [],
        )
        if (
            str(item)
            .strip()
            .casefold()
            not in deferred_keys
        )
    ]

    result[
        "authorized_now"
    ] = authorized

    result[
        "forbidden_now"
    ] = forbidden

    result[
        "deferred_actions"
    ] = deferred

    result[
        "stop_conditions"
    ] = stop_conditions

    return result


def validate_plan_semantics(
    *,
    understanding: dict[str, Any],
    plan: dict[str, Any],
) -> list[str]:
    """
    Detect internal planning contradictions.

    This validator does not decide the user's domain intent
    and does not contain task-specific expected answers.
    """
    errors: list[str] = []

    recommended = understanding.get(
        "recommended_plan",
        [],
    )

    authorized = plan.get(
        "authorized_now",
        [],
    )

    forbidden = plan.get(
        "forbidden_now",
        [],
    )

    deferred = plan.get(
        "deferred_actions",
        [],
    )

    approval = plan.get(
        "approval_gates",
        [],
    )

    stop_conditions = plan.get(
        "stop_conditions",
        [],
    )

    current_phase = str(
        plan.get(
            "current_phase",
            ""
        )
    ).strip()

    if not current_phase:
        errors.append(
            "Planner current_phase is empty."
        )

    if (
        recommended
        and not authorized
    ):
        errors.append(
            "Planner authorized no current work even though "
            "the Understanding result contains a recommended "
            "current-phase plan."
        )

    if (
        authorized
        and deferred
        and authorized == deferred
    ):
        errors.append(
            "Planner copied the same work into authorized_now "
            "and deferred_actions."
        )

    mutation_policy = understanding.get(
        "mutation_policy",
        "UNSURE",
    )

    if (
        mutation_policy == "READ_ONLY"
        and not forbidden
    ):
        errors.append(
            "Understanding is READ_ONLY but Planner did not "
            "record any currently forbidden mutation."
        )

    # Generic temporal consistency rule:
    #
    # If the plan itself says some actions are deferred behind
    # approval gates, those actions are by definition not
    # authorized now. The plan must represent that boundary
    # explicitly instead of leaving forbidden_now empty.
    if (
        deferred
        and approval
        and not forbidden
    ):
        errors.append(
            "Planner has deferred actions behind approval gates "
            "but forbidden_now is empty. The current authorization "
            "boundary is therefore incomplete."
        )

    # The stop condition for the CURRENT phase must not simply
    # require completion of future/deferred work.
    #
    # Exact duplicates can be detected deterministically here.
    normalized_deferred = {
        str(item).strip().casefold()
        for item in deferred
        if str(item).strip()
    }

    normalized_stops = {
        str(item).strip().casefold()
        for item in stop_conditions
        if str(item).strip()
    }

    overlap = (
        normalized_deferred
        & normalized_stops
    )

    if overlap:
        errors.append(
            "Planner stop_conditions contain actions that are "
            "also deferred_actions: "
            + ", ".join(
                sorted(overlap)
            )
        )

    return errors


def _planner_critic_system(
    context: str,
) -> str:
    return (
        "You are the independent Nexus Planner Critic.\n\n"
        "You are NOT given a predetermined correct plan.\n"
        "Judge whether the proposed execution plan faithfully "
        "implements the user's request and the Understanding "
        "result.\n\n"
        "Pay special attention to temporal authorization:\n"
        "- work requested for NOW should not accidentally be "
        "moved into deferred_actions\n"
        "- future actions should not become authorized early\n"
        "- review or approval requirements must survive into "
        "approval_gates\n"
        "- READ_ONLY means current investigation/evaluation may "
        "still be authorized while mutation is forbidden\n"
        "- selecting or proposing candidates is not the same as "
        "deleting, placing, or mutating them\n\n"
        "Also check for:\n"
        "- invented project facts\n"
        "- empty authorized_now despite real current work\n"
        "- empty forbidden_now when current mutation is restricted\n"
        "- missing approval gates\n"
        "- search plans that are too broad or unrelated\n"
        "- plans that exceed the user's requested phase\n"
        "- plans that fail to reach the requested result\n"
        "- forbidden_now left empty even though the plan itself "
        "contains gated deferred actions\n"
        "- stop_conditions that require future/deferred work "
        "instead of completion of the current phase\n\n"
        "A valid plan must distinguish three different concepts:\n"
        "1. work authorized in the current phase\n"
        "2. work explicitly not authorized yet\n"
        "3. work deferred until a later phase or approval\n\n"
        "If deferred actions require approval, corrected_plan "
        "must express the current prohibition in forbidden_now.\n"
        "stop_conditions must describe when CURRENT authorized "
        "work is complete, not when the entire future workflow "
        "has eventually finished.\n\n"
        "Do not require specific wording, paths, tools, routes, "
        "or category names.\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "verdict": "PASS | FAIL",\n'
        '  "issues": ["string"],\n'
        '  "summary": "string",\n'
        '  "corrected_plan": null\n'
        "}\n\n"
        "If verdict is FAIL, corrected_plan must be a COMPLETE "
        "replacement plan using the same Planner schema. "
        "Do not leave current requested discovery/evaluation "
        "work empty merely because later mutation requires "
        "approval. Current non-mutating work can be authorized "
        "while deletion, placement, or other mutation remains "
        "forbidden or deferred. Preserve user review gates.\n\n"
        "CANONICAL PROJECT CONTEXT:\n"
        + context
    )


def critique_plan(
    *,
    user_request: str,
    understanding: dict[str, Any],
    plan: dict[str, Any],
    project_path: str | Path | None = None,
) -> dict[str, Any]:
    cfg = load_understanding_config()

    context = load_project_context(
        project_path
    )

    model, tokenizer, _ = (
        _load_model_cached(
            str(
                cfg["local_path"]
            )
        )
    )

    clean_understanding = (
        _clean_understanding(
            understanding
        )
    )

    clean_plan = {
        key: value
        for key, value in plan.items()
        if not key.startswith("_")
    }

    system = _planner_critic_system(
        context
    )

    user = (
        "ORIGINAL USER REQUEST:\n"
        + user_request
        + "\n\n"
        "UNDERSTANDING RESULT:\n"
        + json.dumps(
            clean_understanding,
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "PROPOSED EXECUTION PLAN:\n"
        + json.dumps(
            clean_plan,
            ensure_ascii=False,
            indent=2,
        )
    )

    raw, metrics = _generate(
        model=model,
        tokenizer=tokenizer,
        messages=[
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": user,
            },
        ],
        max_tokens=int(
            cfg.get(
                "critic_max_tokens",
                1024,
            )
        ),
        temperature=0.0,
        top_p=0.0,
    )

    try:
        result = extract_json_object(
            raw
        )
    except UnderstandingError as exc:
        raise PlanningError(
            "Planner critic did not return valid JSON: "
            + str(exc)
        ) from exc

    verdict = result.get(
        "verdict"
    )

    if verdict not in {
        "PASS",
        "FAIL",
    }:
        raise PlanningError(
            "Planner critic returned invalid verdict."
        )

    issues = result.get(
        "issues",
        [],
    )

    if isinstance(
        issues,
        str,
    ):
        issues = [
            issues
        ]

    if not isinstance(
        issues,
        list,
    ):
        raise PlanningError(
            "Planner critic issues must be a list."
        )

    result[
        "issues"
    ] = issues

    summary = result.get(
        "summary",
        "",
    )

    if not isinstance(
        summary,
        str,
    ):
        raise PlanningError(
            "Planner critic summary must be string."
        )

    result[
        "_metrics"
    ] = metrics

    return result


def approve_or_repair_plan(
    *,
    user_request: str,
    understanding: dict[str, Any],
    plan: dict[str, Any],
    project_path: str | Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Validate and, when necessary, iteratively repair a plan.

    No predetermined task answer is injected here.
    The repair model receives only:
    - the original request,
    - the Understanding result,
    - the current plan,
    - semantic validation errors,
    - and canonical project context.
    """

    current = reconcile_plan_authorization(
        understanding=understanding,
        plan=plan,
    )

    max_repairs = 2

    for attempt in range(
        0,
        max_repairs + 1,
    ):
        local_errors = validate_plan_semantics(
            understanding=understanding,
            plan=current,
        )

        if progress is not None:
            progress(
                "PLANNER: SEMANTIC CONSISTENCY CHECK"
            )

        critic = critique_plan(
            user_request=user_request,
            understanding=understanding,
            plan=current,
            project_path=project_path,
        )

        critic_failed = (
            critic[
                "verdict"
            ]
            == "FAIL"
        )

        if (
            not local_errors
            and not critic_failed
        ):
            current[
                "_nexus_planner_critic"
            ] = critic

            if progress is not None:
                progress(
                    "PLAN APPROVED"
                )

            return current

        if attempt >= max_repairs:
            raise PlanningError(
                "Planner semantic repair exhausted: "
                + json.dumps(
                    {
                        "local_errors": local_errors,
                        "critic_issues": critic.get(
                            "issues",
                            [],
                        ),
                        "current_plan": {
                            key: value
                            for key, value
                            in current.items()
                            if not key.startswith("_")
                        },
                    },
                    ensure_ascii=False,
                )
            )

        corrected = critic.get(
            "corrected_plan"
        )

        if not isinstance(
            corrected,
            dict,
        ):
            raise PlanningError(
                "Planner critic rejected the plan but "
                "did not provide a complete corrected_plan."
            )

        corrected = reconcile_plan_authorization(
            understanding=understanding,
            plan=corrected,
        )

        structural_errors = validate_plan(
            corrected
        )

        if structural_errors:
            raise PlanningError(
                "Corrected plan failed structural validation: "
                + "; ".join(
                    structural_errors
                )
            )

        current = corrected

        if progress is not None:
            progress(
                "PLANNER: "
                f"SEMANTIC REPAIR {attempt + 1}/{max_repairs}"
            )

    raise PlanningError(
        "Planner semantic repair terminated unexpectedly."
    )


def plan_task(
    *,
    user_request: str,
    understanding: dict[str, Any],
    project_path: str | Path | None = None,
    progress: Callable[[str], None]
    | None = None,
) -> dict[str, Any]:
    cfg = load_understanding_config()

    context = load_project_context(
        project_path
    )

    model, tokenizer, _ = (
        _load_model_cached(
            str(
                cfg["local_path"]
            )
        )
    )

    clean_understanding = (
        _clean_understanding(
            understanding
        )
    )

    system = _planner_system(
        context
    )

    messages = [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": (
                "ORIGINAL USER REQUEST:\n"
                + user_request
                + "\n\n"
                "UNDERSTANDING MODEL RESULT:\n"
                + json.dumps(
                    clean_understanding,
                    ensure_ascii=False,
                    indent=2,
                )
            ),
        },
    ]

    if progress is not None:
        progress(
            "PLANNER: REASONING"
        )

    raw, metrics = _generate(
        model=model,
        tokenizer=tokenizer,
        messages=messages,
        max_tokens=1536,
        temperature=0.0,
        top_p=0.0,
    )

    payload: dict[str, Any] | None = None

    try:
        payload = extract_json_object(
            raw
        )

        payload = (
            normalize_plan_structure(
                payload
            )
        )

        errors = validate_plan(
            payload
        )

    except UnderstandingError as exc:
        errors = [
            str(exc)
        ]

    repairs = 0

    while errors:
        if repairs >= 2:
            raise PlanningError(
                "Planner validation failed: "
                + "; ".join(errors)
            )

        repairs += 1

        if progress is not None:
            progress(
                "PLANNER: "
                f"SCHEMA REPAIR {repairs}"
            )

        repaired_raw, repair_metrics = (
            _generate(
                model=model,
                tokenizer=tokenizer,
                messages=_repair_messages(
                    system=system,
                    understanding=(
                        clean_understanding
                    ),
                    invalid_output=raw,
                    errors=errors,
                ),
                max_tokens=768,
                temperature=0.0,
                top_p=0.0,
            )
        )

        metrics[
            f"repair_{repairs}"
        ] = repair_metrics

        raw = repaired_raw

        try:
            payload = extract_json_object(
                raw
            )

            payload = (
                normalize_plan_structure(
                    payload
                )
            )

            errors = validate_plan(
                payload
            )

        except UnderstandingError as exc:
            errors = [
                str(exc)
            ]

    if payload is None:
        raise PlanningError(
            "Planner payload unavailable."
        )

    payload = approve_or_repair_plan(
        user_request=user_request,
        understanding=understanding,
        plan=payload,
        project_path=project_path,
        progress=progress,
    )

    payload[
        "_nexus_planner_meta"
    ] = {
        "model": cfg.get(
            "model_id"
        ),
        "repairs_used": repairs,
        "metrics": metrics,
    }

    if progress is not None:
        for index, (
            code,
            label,
        ) in enumerate(
            PLAN_LABELS,
            start=1,
        ):
            field = PLAN_FIELDS[
                index - 1
            ]

            value = payload.get(
                field
            )

            rendered = (
                value
                if isinstance(
                    value,
                    str,
                )
                else json.dumps(
                    value,
                    ensure_ascii=False,
                )
            )

            if len(rendered) > 120:
                rendered = (
                    rendered[:117]
                    + "..."
                )

            progress(
                "PLANNING "
                f"{code} "
                f"({index}/{len(PLAN_LABELS)}): "
                f"{label} -> {rendered}"
            )

        progress(
            "PLAN READY"
        )

    return payload


def render_plan_brief(
    payload: dict[str, Any],
) -> str:
    clean = {
        key: value
        for key, value in payload.items()
        if not key.startswith("_")
    }

    return (
        "\n\n"
        "NEXUS EXECUTION PLAN\n"
        "This plan was generated before tool execution. "
        "Follow its current-phase authorization, evidence "
        "strategy, approval gates, and stop conditions. "
        "Do not broaden the task without evidence or user "
        "authorization.\n"
        + json.dumps(
            clean,
            ensure_ascii=False,
            indent=2,
        )
        + "\nEND NEXUS EXECUTION PLAN\n"
    )
