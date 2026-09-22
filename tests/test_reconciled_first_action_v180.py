from nexus.runtime.planner import (
    reconcile_plan_authorization,
)


def test_first_action_follows_reconciled_authority():
    understanding = {
        "mutation_policy": "READ_ONLY",
        "recommended_plan": [
            "read requested files",
        ],
    }

    plan = {
        "current_phase": "read files",
        "authorized_now": [],
        "forbidden_now": [
            "do not modify files",
        ],
        "deferred_actions": [],
        "approval_gates": [],
        "targets": [],
        "search_strategy": [],
        "evidence_plan": [],
        "evaluation_plan": [],
        "selection_strategy": [],
        "first_actions": [],
        "stop_conditions": [
            "facts reported",
        ],
    }

    result = reconcile_plan_authorization(
        understanding=understanding,
        plan=plan,
    )

    assert result[
        "authorized_now"
    ] == [
        "read requested files"
    ]

    assert result[
        "first_actions"
    ] == [
        "read requested files"
    ]
