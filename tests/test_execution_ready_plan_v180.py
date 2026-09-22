from nexus.runtime.planner import (
    validate_execution_ready_plan,
)


def test_no_current_work_requires_no_execution_state():
    understanding = {
        "user_goal": "",
        "desired_end_state": "",
        "explicit_requests": [],
        "unknowns_requiring_discovery": [],
        "evidence_needed": [],
        "recommended_plan": [],
        "completion_definition": [],
    }

    assert validate_execution_ready_plan(
        understanding=understanding,
        plan={},
    ) == []


def test_actionable_work_requires_three_execution_fields():
    understanding = {
        "user_goal": "Inspect files",
        "desired_end_state": "Report findings",
        "explicit_requests": [
            "Inspect files",
        ],
        "unknowns_requiring_discovery": [
            "Requested values",
        ],
        "evidence_needed": [],
        "recommended_plan": [],
        "completion_definition": [],
    }

    errors = validate_execution_ready_plan(
        understanding=understanding,
        plan={
            "authorized_now": [],
            "first_actions": [],
            "stop_conditions": [],
        },
    )

    text = "\\n".join(errors)

    assert "authorized_now" in text
    assert "first_actions" in text
    assert "stop_conditions" in text
