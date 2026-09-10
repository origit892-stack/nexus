from nexus.runtime.planner import (
    validate_plan_semantics,
)


def understanding(
    mutation_policy="READ_ONLY",
):
    return {
        "recommended_plan": [
            "Inspect current evidence",
            "Compare candidates",
            "Prepare result for user review",
        ],
        "mutation_policy": (
            mutation_policy
        ),
    }


def plan():
    return {
        "current_phase": "Discovery",
        "authorized_now": [
            "Inspect current evidence",
            "Compare candidates",
        ],
        "forbidden_now": [
            "Modify project state",
        ],
        "deferred_actions": [
            "Future mutation",
        ],
        "approval_gates": [
            "User review before mutation",
        ],
    }


def test_consistent_read_only_plan():
    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=plan(),
    )

    assert errors == []


def test_empty_authorized_current_work_is_rejected():
    value = plan()

    value[
        "authorized_now"
    ] = []

    value[
        "deferred_actions"
    ] = [
        "Inspect current evidence",
        "Compare candidates",
    ]

    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=value,
    )

    assert errors


def test_read_only_with_no_forbidden_mutation_is_rejected():
    value = plan()

    value[
        "forbidden_now"
    ] = []

    errors = validate_plan_semantics(
        understanding=understanding(
            "READ_ONLY"
        ),
        plan=value,
    )

    assert errors


def test_empty_phase_is_rejected():
    value = plan()

    value[
        "current_phase"
    ] = ""

    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=value,
    )

    assert errors
