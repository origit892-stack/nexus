from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nexus.runtime.execution_state import (
    ExecutionState,
)


class ExecutionCoreError(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class CompletionStatus:
    allowed: bool
    reason: str
    incomplete: tuple[str, ...]
    progress: float


@dataclass(frozen=True)
class FinalizationResult:
    final_text: str
    status: str
    execution: CompletionStatus


def inspect_completion(
    state: ExecutionState | None,
) -> CompletionStatus:
    """
    Deterministic completion decision.

    No model decides whether ExecutionState is complete.
    The state must contain every required item as DONE.
    """
    if state is None:
        return CompletionStatus(
            allowed=True,
            reason="NO_TASK_CONTRACT",
            incomplete=(),
            progress=1.0,
        )

    incomplete = state.incomplete()
    progress = state.progress_fraction()

    if incomplete:
        return CompletionStatus(
            allowed=False,
            reason="TASK_REQUIREMENTS_INCOMPLETE",
            incomplete=incomplete,
            progress=progress,
        )

    return CompletionStatus(
        allowed=True,
        reason="TASK_REQUIREMENTS_COMPLETE",
        incomplete=(),
        progress=1.0,
    )


def render_execution_progress(
    state: ExecutionState | None,
) -> str:
    if state is None:
        return (
            "TASK STATE\n"
            "No structured task contract is active."
        )

    snapshot = state.snapshot()

    lines = [
        "TASK STATE",
        (
            "Progress: "
            + f"{snapshot['progress'] * 100:.0f}%"
        ),
    ]

    for item in snapshot[
        "requirements"
    ]:
        lines.append(
            "- "
            + str(item["status"])
            + ": "
            + str(item["requirement"])
        )

    return "\n".join(lines)


def continuation_instruction(
    state: ExecutionState,
) -> str:
    incomplete = state.incomplete()

    if not incomplete:
        raise ExecutionCoreError(
            "Continuation requested for a "
            "completed execution state."
        )

    lines = [
        "NEXUS TASK STATE: CONTINUE",
        (
            "The current task contract is not "
            "complete."
        ),
        "",
        "REMAINING REQUIREMENTS:",
    ]

    lines.extend(
        "- " + item
        for item in incomplete
    )

    lines.extend(
        [
            "",
            (
                "Continue from existing evidence. "
                "Do not restart broad discovery."
            ),
            (
                "Focus on the remaining requirements "
                "and preserve all MUST_NOT_DO rules."
            ),
        ]
    )

    return "\n".join(lines)


def finalize_success(
    *,
    proposed_final: str,
    state: ExecutionState | None,
) -> FinalizationResult:
    """
    The only successful completion primitive for the
    Nexus 1.8 execution core.

    Callers may not report PASS while a structured task
    contains incomplete requirements.
    """
    completion = inspect_completion(
        state
    )

    if not completion.allowed:
        raise ExecutionCoreError(
            "SUCCESS_COMPLETION_BLOCKED: "
            + ", ".join(
                completion.incomplete
            )
        )

    text = str(
        proposed_final
    ).strip()

    if not text:
        raise ExecutionCoreError(
            "SUCCESS_COMPLETION_REQUIRES_FINAL_TEXT"
        )

    return FinalizationResult(
        final_text=text,
        status="PASS",
        execution=completion,
    )
