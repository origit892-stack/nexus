from __future__ import annotations

from typing import Any

from .execution_events import ExecutionEventBus


def emit_completion_gate(
    bus: ExecutionEventBus,
    *,
    iteration: int,
    decision: Any,
    proposed_final: str,
    evidence_count: int,
):
    allow = bool(
        getattr(
            decision,
            "allow",
            False,
        )
    )

    verdict = getattr(
        decision,
        "verdict",
        "PASS" if allow else "CONTINUE",
    )

    summary = getattr(
        decision,
        "summary",
        "",
    )

    unmet = getattr(
        decision,
        "unmet_conditions",
        [],
    )

    next_focus = getattr(
        decision,
        "next_focus",
        "",
    )

    return bus.emit(
        "execution_completion_gate",
        iteration=iteration,
        verdict=verdict,
        allow=allow,
        summary=summary,
        unmet_conditions=list(
            unmet or []
        ),
        next_focus=next_focus,
        proposed_final_length=len(
            proposed_final or ""
        ),
        evidence_count=int(
            evidence_count
        ),
    )


def emit_success_return(
    bus: ExecutionEventBus,
    *,
    iteration: int,
    proposed_final: str,
):
    return bus.emit(
        "execution_success_return",
        iteration=iteration,
        proposed_final_length=len(
            proposed_final or ""
        ),
    )
