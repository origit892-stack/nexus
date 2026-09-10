from nexus.runtime.planner import (
    validate_plan_semantics,
)


def understanding():
    return {
        "recommended_plan": [
            "Inspect evidence",
            "Evaluate candidates",
        ],
        "mutation_policy": "UNSURE",
    }


def base_plan():
    return {
        "current_phase": "Review",
        "authorized_now": [
            "Inspect evidence",
            "Evaluate candidates",
        ],
        "forbidden_now": [
            "Perform gated future action",
        ],
        "deferred_actions": [
            "Perform gated future action",
        ],
        "approval_gates": [
            "User approval",
        ],
        "stop_conditions": [
            "Current review result is ready",
        ],
    }


def test_consistent_gated_plan_passes():
    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=base_plan(),
    )

    assert errors == []


def test_gated_deferred_work_requires_forbidden_boundary():
    value = base_plan()

    value[
        "forbidden_now"
    ] = []

    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=value,
    )

    assert any(
        "approval gates"
        in error
        for error in errors
    )


def test_deferred_action_cannot_be_exact_stop_condition():
    value = base_plan()

    value[
        "stop_conditions"
    ] = [
        "Perform gated future action",
    ]

    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=value,
    )

    assert any(
        "deferred_actions"
        in error
        for error in errors
    )


def test_no_hardcoded_asset_semantics_required():
    value = {
        "current_phase": "Analysis",
        "authorized_now": [
            "Analyze records",
        ],
        "forbidden_now": [
            "Publish result",
        ],
        "deferred_actions": [
            "Publish result",
        ],
        "approval_gates": [
            "Approval",
        ],
        "stop_conditions": [
            "Analysis report ready",
        ],
    }

    generic_understanding = {
        "recommended_plan": [
            "Analyze records",
        ],
        "mutation_policy": "UNSURE",
    }

    assert (
        validate_plan_semantics(
            understanding=generic_understanding,
            plan=value,
        )
        == []
    )
