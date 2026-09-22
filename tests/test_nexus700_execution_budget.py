import pytest

from nexus.runtime.execution_budget import (
    ExecutionBudget,
    ExecutionBudgetExceeded,
)


def test_iteration_budget():
    budget = ExecutionBudget(
        max_iterations=2
    )

    budget.note_iteration()
    budget.note_iteration()

    with pytest.raises(
        ExecutionBudgetExceeded
    ):
        budget.note_iteration()


def test_failure_budget_resets():
    budget = ExecutionBudget(
        max_consecutive_failures=2
    )

    budget.note_failure()
    budget.note_success()
    budget.note_failure()
    budget.note_failure()

    with pytest.raises(
        ExecutionBudgetExceeded
    ):
        budget.note_failure()
