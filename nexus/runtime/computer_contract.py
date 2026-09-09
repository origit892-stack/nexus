from __future__ import annotations

from dataclasses import dataclass


ALLOWED_ACTIONS = {
    "screenshot",
    "move",
    "click",
    "double_click",
    "scroll",
    "type",
    "key",
}


@dataclass
class ComputerAction:
    action: str
    x: int | None = None
    y: int | None = None
    text: str | None = None
    key: str | None = None
    amount: int | None = None


class ComputerActionBudget:
    def __init__(
        self,
        max_actions=12,
        max_clicks=6,
        max_types=3,
    ):
        self.max_actions = int(
            max_actions
        )

        self.max_clicks = int(
            max_clicks
        )

        self.max_types = int(
            max_types
        )

        self.actions = 0
        self.clicks = 0
        self.types = 0

    def consume(
        self,
        action,
    ):
        if action not in ALLOWED_ACTIONS:
            raise PermissionError(
                "COMPUTER_ACTION_BLOCK="
                + str(action)
            )

        self.actions += 1

        if self.actions > self.max_actions:
            raise PermissionError(
                "COMPUTER_ACTION_BUDGET_EXCEEDED"
            )

        if action in {
            "click",
            "double_click",
        }:
            self.clicks += 1

            if (
                self.clicks
                > self.max_clicks
            ):
                raise PermissionError(
                    "COMPUTER_CLICK_BUDGET_EXCEEDED"
                )

        if action == "type":
            self.types += 1

            if (
                self.types
                > self.max_types
            ):
                raise PermissionError(
                    "COMPUTER_TYPE_BUDGET_EXCEEDED"
                )


def validate_action(
    action: ComputerAction,
):
    if (
        action.action
        not in ALLOWED_ACTIONS
    ):
        raise ValueError(
            "INVALID_COMPUTER_ACTION="
            + action.action
        )

    if action.action in {
        "click",
        "double_click",
        "move",
    }:
        if (
            action.x is None
            or action.y is None
        ):
            raise ValueError(
                "COMPUTER_COORDINATES_REQUIRED"
            )

    if action.action == "type":
        if action.text is None:
            raise ValueError(
                "COMPUTER_TEXT_REQUIRED"
            )

    if action.action == "key":
        if not action.key:
            raise ValueError(
                "COMPUTER_KEY_REQUIRED"
            )

    return True
