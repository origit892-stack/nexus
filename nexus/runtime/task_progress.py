from __future__ import annotations

from typing import Any

from nexus.runtime.execution_state import (
    ExecutionState,
)


TASK_PROGRESS_TOOL_NAME = "task_progress"


def tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": TASK_PROGRESS_TOOL_NAME,
            "description": (
                "Update Nexus task-state after evidence "
                "supports progress on an existing task "
                "requirement. This does not perform project "
                "work. Never invent requirement names. "
                "Use the exact requirement text shown in "
                "NEXUS TASK CONTRACT."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "requirement": {
                        "type": "string",
                    },
                    "status": {
                        "type": "string",
                        "enum": [
                            "IN_PROGRESS",
                            "DONE",
                        ],
                    },
                    "evidence": {
                        "type": "string",
                    },
                },
                "required": [
                    "requirement",
                    "status",
                    "evidence",
                ],
                "additionalProperties": False,
            },
        },
    }


def execute(
    *,
    state: ExecutionState,
    arguments: dict[str, Any],
) -> str:
    state.apply_progress_update(
        requirement=str(
            arguments.get(
                "requirement",
                "",
            )
        ),
        status=str(
            arguments.get(
                "status",
                "",
            )
        ),
        evidence=str(
            arguments.get(
                "evidence",
                "",
            )
        ),
    )

    snapshot = state.snapshot()

    return (
        "TASK_PROGRESS_UPDATED "
        + str(
            {
                "complete": snapshot[
                    "complete"
                ],
                "progress": snapshot[
                    "progress"
                ],
                "incomplete": snapshot[
                    "incomplete"
                ],
            }
        )
    )
