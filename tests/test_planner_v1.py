from nexus.runtime.planner import (
    PLAN_FIELDS,
    normalize_plan_structure,
    render_plan_brief,
    validate_plan,
)


def valid_plan():
    return {
        "current_phase": "Discovery",
        "authorized_now": [
            "Inspect evidence",
        ],
        "forbidden_now": [
            "Unapproved mutation",
        ],
        "deferred_actions": [
            "Later work",
        ],
        "approval_gates": [
            "User review",
        ],
        "targets": [
            "Relevant project content",
        ],
        "search_strategy": [
            "Use focused evidence discovery",
        ],
        "evidence_plan": [
            "Resolve direct evidence",
        ],
        "evaluation_plan": [
            "Evaluate relevant candidates",
        ],
        "selection_strategy": [
            "Compare viable candidates",
        ],
        "first_actions": [
            "Locate primary evidence",
        ],
        "stop_conditions": [
            "Current phase complete",
        ],
    }


def test_valid_plan():
    assert (
        validate_plan(
            valid_plan()
        )
        == []
    )


def test_all_fields_present():
    value = valid_plan()

    for field in PLAN_FIELDS:
        assert field in value


def test_string_list_normalization():
    value = valid_plan()

    value[
        "targets"
    ] = "One target"

    normalized = (
        normalize_plan_structure(
            value
        )
    )

    assert normalized[
        "targets"
    ] == [
        "One target"
    ]


def test_missing_field_fails():
    value = valid_plan()

    del value[
        "approval_gates"
    ]

    errors = validate_plan(
        value
    )

    assert any(
        "approval_gates"
        in error
        for error in errors
    )


def test_render_plan_drops_meta():
    value = valid_plan()

    value[
        "_nexus_planner_meta"
    ] = {
        "x": 1
    }

    rendered = (
        render_plan_brief(
            value
        )
    )

    assert (
        "_nexus_planner_meta"
        not in rendered
    )

    assert (
        "NEXUS EXECUTION PLAN"
        in rendered
    )
