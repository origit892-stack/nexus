import pytest

from nexus.runtime.task_contract import (
    TaskContract,
)

from nexus.runtime.execution_state import (
    ExecutionState,
)

from nexus.runtime.task_progress import (
    execute,
    tool_schema,
)


def state():
    contract = TaskContract(
        goal="audit",
        current_phase="audit",
        deliverables=("report",),
        must_do=("discover",),
        must_not_do=("do not mutate",),
        evidence_required=("technical QA",),
        done_when=("report ready",),
        mutation_policy="READ_ONLY",
    )

    return ExecutionState.create(
        contract
    )


def test_schema_is_strict():
    schema = tool_schema()

    params = schema[
        "function"
    ][
        "parameters"
    ]

    assert (
        params["additionalProperties"]
        is False
    )

    assert set(
        params["required"]
    ) == {
        "requirement",
        "status",
        "evidence",
    }


def test_tool_updates_existing_requirement():
    execution = state()

    result = execute(
        state=execution,
        arguments={
            "requirement": "discover",
            "status": "DONE",
            "evidence": "Inventory verified.",
        },
    )

    assert (
        "TASK_PROGRESS_UPDATED"
        in result
    )

    assert (
        "discover"
        not in execution.incomplete()
    )


def test_tool_rejects_invented_requirement():
    execution = state()

    with pytest.raises(KeyError):
        execute(
            state=execution,
            arguments={
                "requirement": "invented",
                "status": "DONE",
                "evidence": "fake",
            },
        )
