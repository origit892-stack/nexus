from pathlib import Path

from nexus.runtime.task_contract import TaskContract


def test_task_contract_uses_real_understanding_schema():
    contract = TaskContract.from_understanding_and_plan(
        understanding={
            "user_goal": "Inspect files",
            "desired_end_state": "Report findings",
            "current_requested_phase": "Inspection",
            "response_expected": "Verified report",
            "mutation_policy": "READ_ONLY",
        },
        plan={
            "current_phase": "Inspection",
            "authorized_now": [
                "Inspect files",
            ],
            "forbidden_now": [
                "Do not mutate files",
            ],
            "evidence_plan": [],
            "evaluation_plan": [],
            "stop_conditions": [
                "Report findings",
            ],
        },
    )

    assert contract.goal == "Inspect files"

    assert contract.deliverables == (
        "Report findings",
    )

    assert contract.current_phase == "Inspection"


def test_agent_has_one_completion_authority():
    source = Path(
        "nexus/agent.py"
    ).read_text()

    assert (
        "EXECUTION_COMPLETION_GATE_V173"
        in source
    )

    assert (
        "evaluate_execution_completion("
        in source
    )

    assert (
        "TASK_STATE_SUCCESS_GATE_V180"
        not in source
    )

    assert (
        "TASK_PROGRESS_DISPATCH_V180"
        not in source
    )

    assert (
        "task_progress_tool_schema()"
        not in source
    )


def test_manual_progress_is_not_required_by_agent():
    source = Path(
        "nexus/agent.py"
    ).read_text()

    assert "TASK_PROGRESS_TOOL_NAME" not in source
    assert "execute_task_progress" not in source
