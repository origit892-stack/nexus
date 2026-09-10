from nexus.runtime.planner import (
    reconcile_plan_authorization,
    validate_plan_semantics,
)


def understanding():
    return {
        "recommended_plan": [
            "Inspect evidence",
            "Compare candidates",
        ],
        "mutation_policy": "UNSURE",
    }


def empty_boundary_plan():
    return {
        "current_phase": "Review",
        "authorized_now": [],
        "forbidden_now": [],
        "deferred_actions": [
            "Publish final result",
        ],
        "approval_gates": [
            "User approval",
        ],
        "targets": [
            "Relevant material",
        ],
        "search_strategy": [
            "Inspect relevant evidence",
        ],
        "evidence_plan": [
            "Collect evidence",
        ],
        "evaluation_plan": [
            "Evaluate candidates",
        ],
        "selection_strategy": [
            "Compare evidence",
        ],
        "first_actions": [
            "Inspect evidence",
            "Compare candidates",
        ],
        "stop_conditions": [
            "Review package ready",
        ],
    }


def test_first_actions_become_current_authorization():
    result = reconcile_plan_authorization(
        understanding=understanding(),
        plan=empty_boundary_plan(),
    )

    assert result[
        "authorized_now"
    ] == [
        "Inspect evidence",
        "Compare candidates",
    ]


def test_deferred_gated_actions_get_current_boundary():
    result = reconcile_plan_authorization(
        understanding=understanding(),
        plan=empty_boundary_plan(),
    )

    assert result[
        "forbidden_now"
    ]

    assert (
        "Publish final result"
        in result[
            "forbidden_now"
        ][0]
    )


def test_reconciled_plan_passes_semantic_gate():
    result = reconcile_plan_authorization(
        understanding=understanding(),
        plan=empty_boundary_plan(),
    )

    errors = validate_plan_semantics(
        understanding=understanding(),
        plan=result,
    )

    assert errors == []


def test_does_not_require_asset_or_game_vocabulary():
    plan = empty_boundary_plan()

    plan[
        "first_actions"
    ] = [
        "Analyze accounting records",
    ]

    plan[
        "deferred_actions"
    ] = [
        "Submit report",
    ]

    result = reconcile_plan_authorization(
        understanding={
            "recommended_plan": [
                "Analyze accounting records",
            ],
            "mutation_policy": "UNSURE",
        },
        plan=plan,
    )

    assert result[
        "authorized_now"
    ] == [
        "Analyze accounting records"
    ]

    assert result[
        "forbidden_now"
    ]

    assert (
        validate_plan_semantics(
            understanding={
                "recommended_plan": [
                    "Analyze accounting records",
                ],
                "mutation_policy": "UNSURE",
            },
            plan=result,
        )
        == []
    )


def test_exact_authorized_action_removed_from_deferred():
    plan = empty_boundary_plan()

    plan[
        "authorized_now"
    ] = [
        "Inspect evidence",
    ]

    plan[
        "deferred_actions"
    ] = [
        "Inspect evidence",
        "Publish final result",
    ]

    result = reconcile_plan_authorization(
        understanding=understanding(),
        plan=plan,
    )

    assert (
        "Inspect evidence"
        not in result[
            "deferred_actions"
        ]
    )

    assert (
        "Publish final result"
        in result[
            "deferred_actions"
        ]
    )


def test_exact_deferred_action_removed_from_current_stop_conditions():
    plan = empty_boundary_plan()

    plan[
        "stop_conditions"
    ] = [
        "Publish final result",
        "Review package ready",
    ]

    result = reconcile_plan_authorization(
        understanding=understanding(),
        plan=plan,
    )

    assert (
        "Publish final result"
        not in result[
            "stop_conditions"
        ]
    )

    assert (
        "Review package ready"
        in result[
            "stop_conditions"
        ]
    )


def test_existing_valid_boundaries_are_preserved():
    plan = empty_boundary_plan()

    plan[
        "authorized_now"
    ] = [
        "Existing current action",
    ]

    plan[
        "forbidden_now"
    ] = [
        "Existing forbidden action",
    ]

    result = reconcile_plan_authorization(
        understanding=understanding(),
        plan=plan,
    )

    assert result[
        "authorized_now"
    ] == [
        "Existing current action"
    ]

    assert result[
        "forbidden_now"
    ] == [
        "Existing forbidden action"
    ]
