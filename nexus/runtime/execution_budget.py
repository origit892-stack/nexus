from __future__ import annotations

from dataclasses import dataclass


class ExecutionBudgetExceeded(RuntimeError):
    pass


@dataclass
class ExecutionBudget:
    max_iterations: int = 40
    max_tool_calls: int = 120
    max_consecutive_failures: int = 5
    max_same_action: int = 8

    iterations: int = 0
    tool_calls: int = 0
    consecutive_failures: int = 0

    def note_iteration(self):
        self.iterations += 1

        if (
            self.iterations
            > self.max_iterations
        ):
            raise ExecutionBudgetExceeded(
                "maximum agent iterations exceeded"
            )

    def note_tool_call(
        self,
        count: int = 1,
    ):
        self.tool_calls += count

        if (
            self.tool_calls
            > self.max_tool_calls
        ):
            raise ExecutionBudgetExceeded(
                "maximum tool-call budget exceeded"
            )

    def note_success(self):
        self.consecutive_failures = 0

    def note_failure(self):
        self.consecutive_failures += 1

        if (
            self.consecutive_failures
            > self.max_consecutive_failures
        ):
            raise ExecutionBudgetExceeded(
                "consecutive failure budget exceeded"
            )
