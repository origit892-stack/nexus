from __future__ import annotations

from dataclasses import dataclass


ACTIVE = "ACTIVE"
READY = "READY"
INTERRUPTED = "INTERRUPTED"
COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class SessionLifecycle:
    status: str

    @property
    def can_continue(
        self,
    ) -> bool:
        return self.status in {
            ACTIVE,
            READY,
            INTERRUPTED,
            COMPLETED,
        }

    @property
    def can_go_back(
        self,
    ) -> bool:
        # Navigation must never be trapped by completion state.
        return True


def status_after_turn(
    current_status: str,
) -> str:
    # Agent finishing a turn is NOT user completion.
    if current_status == COMPLETED:
        return COMPLETED

    return READY


def status_after_interrupt() -> str:
    return INTERRUPTED


def status_after_user_complete() -> str:
    return COMPLETED


def status_after_user_continue() -> str:
    return ACTIVE
