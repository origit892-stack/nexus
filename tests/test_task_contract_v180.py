from nexus.runtime.task_contract import (
    TaskContract,
)


def test_contract_comes_from_semantic_outputs():
    understanding = {
        "actual_goal": "Audit project assets",
        "desired_result": (
            "A categorized recommendation"
        ),
        "mutation_policy": "READ_ONLY",
    }

    plan = {
        "current_phase": "inspection",
        "authorized_now": [
            "discover assets",
            "categorize assets",
        ],
        "forbidden_now": [
            "do not delete assets",
        ],
        "evidence_plan": [
            "usage evidence",
        ],
        "evaluation_plan": [
            "technical quality",
            "visual quality",
        ],
        "stop_conditions": [
            "selection complete",
            "report ready",
        ],
    }

    contract = (
        TaskContract
        .from_understanding_and_plan(
            understanding=understanding,
            plan=plan,
        )
    )

    assert (
        contract.goal
        == "Audit project assets"
    )

    assert (
        contract.mutation_policy
        == "READ_ONLY"
    )

    assert (
        "discover assets"
        in contract.must_do
    )

    assert (
        "do not delete assets"
        in contract.must_not_do
    )

    assert (
        "technical quality"
        in contract.evidence_required
    )

    assert (
        "report ready"
        in contract.done_when
    )
