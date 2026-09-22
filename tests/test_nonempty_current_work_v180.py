from nexus.runtime.planner import (
    reconcile_plan_authorization,
    understanding_requires_current_work,
    validate_execution_ready_plan,
    validate_plan_semantics,
)


def understanding():
    return {
        "user_goal": "Find requested information.",
        "desired_end_state": "Report verified information.",
        "current_requested_phase": "Initial",
        "explicit_requests": [
            "Find and inspect requested files.",
        ],
        "explicit_restrictions": [],
        "implicit_requirements": [],
        "relevant_game_context": [],
        "known_project_facts": [],
        "unknowns_requiring_discovery": [
            "Requested values",
        ],
        "mutation_policy": "READ_ONLY",
        "evidence_needed": [],
        "recommended_plan": [],
        "completion_definition": [],
        "response_expected": "Verified summary.",
        "confidence": 0.8,
    }


def plan():
    return {
        "current_phase": "Initial",
        "authorized_now": [],
        "forbidden_now": [
            "Project mutation is not authorized "
            "during the current READ_ONLY phase."
        ],
        "deferred_actions": [],
        "approval_gates": [],
        "targets": [],
        "search_strategy": [],
        "evidence_plan": [],
        "evaluation_plan": [],
        "selection_strategy": [],
        "first_actions": [],
        "stop_conditions": [],
    }


def test_real_understanding_requires_work():
    assert understanding_requires_current_work(
        understanding()
    )


def test_semantic_validation_requires_authority_only():
    value = plan()

    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=value,
    )

    joined = "\\n".join(errors)

    assert "authorized_now is empty" in joined
    assert "first_actions is empty" not in joined
    assert "stop_conditions is empty" not in joined


def test_execution_readiness_requires_execution_fields():
    value = plan()

    value["authorized_now"] = [
        "Find requested information.",
    ]

    errors = validate_execution_ready_plan(
        understanding=understanding(),
        plan=value,
    )

    joined = "\\n".join(errors)

    assert "first_actions" in joined
    assert "stop_conditions" in joined


def test_reconciliation_makes_simple_read_only_plan_ready():
    value = reconcile_plan_authorization(
        understanding=understanding(),
        plan=plan(),
    )

    assert validate_plan_semantics(
        understanding=understanding(),
        plan=value,
    ) == []

    assert validate_execution_ready_plan(
        understanding=understanding(),
        plan=value,
    ) == []

    assert value["authorized_now"]
    assert value["first_actions"]
    assert value["stop_conditions"]
