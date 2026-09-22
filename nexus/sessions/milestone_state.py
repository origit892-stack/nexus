from __future__ import annotations

from copy import deepcopy
from typing import Any


MILESTONE_STATE_VERSION = 1

PENDING = "PENDING"
RUNNING = "RUNNING"
PASS = "PASS"
FAIL = "FAIL"

FINAL_PENDING = "PENDING"
FINAL_RUNNING = "RUNNING"
FINAL_PASS = "PASS"
FINAL_FAIL = "FAIL"

_VALID_STATUS = {
    PENDING,
    RUNNING,
    PASS,
    FAIL,
}


def empty_milestone_state() -> dict[str, Any]:
    return {
        "version": MILESTONE_STATE_VERSION,
        "active": False,
        "master_prompt_sha256": None,
        "master_prompt": None,
        "plan": None,
        "current_milestone_index": None,
        "milestones": [],
        "final_verification": {
            "status": FINAL_PENDING,
            "run_id": None,
            "result": None,
            "evidence": [],
        },
        "master_status": PENDING,
        "master_result": None,
    }


def normalize_milestone_state(
    value: Any,
) -> dict[str, Any]:
    base = empty_milestone_state()

    if not isinstance(value, dict):
        return base

    result = deepcopy(base)

    for key in (
        "active",
        "master_prompt_sha256",
        "master_prompt",
        "plan",
        "current_milestone_index",
        "master_status",
        "master_result",
    ):
        if key in value:
            result[key] = deepcopy(value[key])

    result["active"] = bool(
        result["active"]
    )

    milestones = value.get("milestones")

    if isinstance(milestones, list):
        normalized = []

        for index, item in enumerate(milestones):
            if not isinstance(item, dict):
                continue

            status = str(
                item.get("status", PENDING)
            ).upper()

            if status not in _VALID_STATUS:
                status = PENDING

            normalized.append({
                "index": index,
                "id": item.get("id"),
                "title": item.get("title"),
                "source_requirements": list(
                    item.get(
                        "source_requirements",
                        [],
                    )
                    if isinstance(
                        item.get(
                            "source_requirements",
                            [],
                        ),
                        (list, tuple),
                    )
                    else []
                ),
                "status": status,
                "run_id": item.get("run_id"),
                "result": item.get("result"),
                "evidence": list(
                    item.get("evidence", [])
                    if isinstance(
                        item.get("evidence", []),
                        list,
                    )
                    else []
                ),
            })

        result["milestones"] = normalized

    final = value.get("final_verification")

    if isinstance(final, dict):
        final_status = str(
            final.get(
                "status",
                FINAL_PENDING,
            )
        ).upper()

        if final_status not in _VALID_STATUS:
            final_status = FINAL_PENDING

        result["final_verification"] = {
            "status": final_status,
            "run_id": final.get("run_id"),
            "result": final.get("result"),
            "evidence": list(
                final.get("evidence", [])
                if isinstance(
                    final.get("evidence", []),
                    list,
                )
                else []
            ),
        }

    master_status = str(
        result.get(
            "master_status",
            PENDING,
        )
    ).upper()

    if master_status not in _VALID_STATUS:
        master_status = PENDING

    result["master_status"] = master_status

    index = result.get(
        "current_milestone_index"
    )

    if index is not None:
        try:
            index = int(index)
        except (TypeError, ValueError):
            index = None

    if (
        index is not None
        and (
            index < 0
            or index >= len(
                result["milestones"]
            )
        )
    ):
        index = None

    result[
        "current_milestone_index"
    ] = index

    return result


def state_from_plan(
    plan,
) -> dict[str, Any]:
    payload = plan.to_dict()

    milestones = []

    for index, item in enumerate(
        payload["milestones"]
    ):
        milestones.append({
            "index": index,
            "id": item["id"],
            "title": item["title"],
            "source_requirements": list(
                item.get(
                    "source_requirements",
                    [],
                )
            ),
            "status": PENDING,
            "run_id": None,
            "result": None,
            "evidence": [],
        })

    state = empty_milestone_state()

    state.update({
        "active": True,
        "master_prompt_sha256":
            payload["master_prompt_sha256"],
        "master_prompt":
            payload["master_prompt"],
        "plan": payload,
        "current_milestone_index":
            0 if milestones else None,
        "milestones": milestones,
        "master_status":
            RUNNING if milestones else PENDING,
    })

    return normalize_milestone_state(
        state
    )


def current_milestone(
    state: dict[str, Any],
):
    state = normalize_milestone_state(
        state
    )

    index = state[
        "current_milestone_index"
    ]

    if index is None:
        return None

    return deepcopy(
        state["milestones"][index]
    )


def mark_current_running(
    state: dict[str, Any],
) -> dict[str, Any]:
    state = normalize_milestone_state(
        state
    )

    index = state[
        "current_milestone_index"
    ]

    if index is None:
        raise ValueError(
            "NO_CURRENT_MILESTONE"
        )

    current = state[
        "milestones"
    ][index]

    if current["status"] == PASS:
        raise ValueError(
            "CURRENT_MILESTONE_ALREADY_PASS"
        )

    current["status"] = RUNNING
    state["active"] = True
    state["master_status"] = RUNNING

    return state


def mark_current_pass(
    state: dict[str, Any],
    *,
    run_id=None,
    result=None,
    evidence=None,
) -> dict[str, Any]:
    state = normalize_milestone_state(
        state
    )

    index = state[
        "current_milestone_index"
    ]

    if index is None:
        raise ValueError(
            "NO_CURRENT_MILESTONE"
        )

    current = state[
        "milestones"
    ][index]

    current["status"] = PASS
    current["run_id"] = run_id
    current["result"] = result
    current["evidence"] = list(
        evidence or []
    )

    next_index = index + 1

    if next_index < len(
        state["milestones"]
    ):
        state[
            "current_milestone_index"
        ] = next_index
    else:
        state[
            "current_milestone_index"
        ] = None

    # IMPORTANT:
    # Finishing the final user milestone does NOT mean
    # the master request is complete. FinalVerification
    # remains pending.
    state["master_status"] = RUNNING
    state["active"] = True

    return state


def mark_current_fail(
    state: dict[str, Any],
    *,
    run_id=None,
    result=None,
    evidence=None,
) -> dict[str, Any]:
    state = normalize_milestone_state(
        state
    )

    index = state[
        "current_milestone_index"
    ]

    if index is None:
        raise ValueError(
            "NO_CURRENT_MILESTONE"
        )

    current = state[
        "milestones"
    ][index]

    current["status"] = FAIL
    current["run_id"] = run_id
    current["result"] = result
    current["evidence"] = list(
        evidence or []
    )

    state["master_status"] = FAIL
    state["active"] = True

    return state


def user_milestones_complete(
    state: dict[str, Any],
) -> bool:
    state = normalize_milestone_state(
        state
    )

    milestones = state[
        "milestones"
    ]

    return bool(milestones) and all(
        item["status"] == PASS
        for item in milestones
    )


def begin_final_verification(
    state: dict[str, Any],
) -> dict[str, Any]:
    state = normalize_milestone_state(
        state
    )

    if not user_milestones_complete(
        state
    ):
        raise ValueError(
            "USER_MILESTONES_INCOMPLETE"
        )

    state[
        "final_verification"
    ]["status"] = FINAL_RUNNING

    state["master_status"] = RUNNING
    state["active"] = True

    return state


def mark_final_pass(
    state: dict[str, Any],
    *,
    run_id=None,
    result=None,
    evidence=None,
) -> dict[str, Any]:
    state = normalize_milestone_state(
        state
    )

    if not user_milestones_complete(
        state
    ):
        raise ValueError(
            "USER_MILESTONES_INCOMPLETE"
        )

    final = state[
        "final_verification"
    ]

    final["status"] = FINAL_PASS
    final["run_id"] = run_id
    final["result"] = result
    final["evidence"] = list(
        evidence or []
    )

    state["master_status"] = PASS
    state["master_result"] = result
    state["active"] = False

    return state


def mark_final_fail(
    state: dict[str, Any],
    *,
    run_id=None,
    result=None,
    evidence=None,
) -> dict[str, Any]:
    state = normalize_milestone_state(
        state
    )

    final = state[
        "final_verification"
    ]

    final["status"] = FINAL_FAIL
    final["run_id"] = run_id
    final["result"] = result
    final["evidence"] = list(
        evidence or []
    )

    state["master_status"] = FAIL
    state["active"] = True

    return state


def resume_index(
    state: dict[str, Any],
):
    state = normalize_milestone_state(
        state
    )

    for index, item in enumerate(
        state["milestones"]
    ):
        if item["status"] != PASS:
            return index

    return None
