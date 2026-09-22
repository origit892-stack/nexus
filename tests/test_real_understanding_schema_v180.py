from nexus.runtime.planner import (
    reconcile_plan_authorization,
)


def test_real_smoke_shape_self_heals_without_invention():
    understanding = {
        "user_goal": (
            "Find the versions and main titles of "
            "the requested files."
        ),
        "desired_end_state": (
            "Summarize the versions and main titles "
            "of the requested files."
        ),
        "current_requested_phase": "Initial",
        "explicit_requests": [
            (
                "Find the versions and main titles of "
                "the pyproject.toml and README.md files "
                "in the project."
            )
        ],
        "explicit_restrictions": [],
        "implicit_requirements": [],
        "relevant_game_context": [],
        "known_project_facts": [],
        "unknowns_requiring_discovery": [
            "Version of pyproject.toml",
            "Main title of README.md",
        ],
        "mutation_policy": "READ_ONLY",
        "evidence_needed": [],
        "recommended_plan": [],
        "completion_definition": [],
        "response_expected": (
            "The verified values will be summarized."
        ),
        "confidence": 0.6,
    }

    plan = {
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

    result = reconcile_plan_authorization(
        understanding=understanding,
        plan=plan,
    )

    assert result["authorized_now"]
    assert result["first_actions"]
    assert result["stop_conditions"]

    assert (
        result["authorized_now"][0]
        == understanding[
            "explicit_requests"
        ][0]
    )

    assert (
        result["stop_conditions"][0]
        == understanding[
            "desired_end_state"
        ]
    )
