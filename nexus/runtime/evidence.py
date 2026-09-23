from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
@dataclass
class ToolEvidence:
    tool: str
    args: dict
    output: str
    success: bool
    timestamp: float
    outcome: str = "EXECUTED_SUCCESSFULLY"


class EvidenceLedger:
    def __init__(self):
        self.items = []

    def record(
        self,
        tool,
        args,
        output,
        *,
        outcome=None,
    ):
        text = str(
            output
        )

        if outcome is None:
            failure_markers = (
                "UNKNOWN_TOOL=",
                "NEXUS_PERMISSION_BLOCK=",
                "TOOL_EXCEPTION=",
                "UNIVERSAL_TOOL_EXCEPTION=",
                "WEB_FETCH_ERROR=",
                "WEB_SEARCH_ERROR=",
                "MCP_LIST_ERROR=",
                "MCP_CALL_ERROR=",
            )

            if any(
                marker in text
                for marker
                in failure_markers
            ):
                outcome = (
                    "EXECUTION_FAILED"
                )
            else:
                outcome = (
                    "EXECUTED_SUCCESSFULLY"
                )

        outcome = str(
            outcome
        ).upper()

        valid_outcomes = {
            "EXECUTED_SUCCESSFULLY",
            "BLOCKED_BY_POLICY",
            "EXECUTION_FAILED",
        }

        if outcome not in valid_outcomes:
            raise ValueError(
                "INVALID_TOOL_EVIDENCE_OUTCOME="
                + outcome
            )

        success = (
            outcome
            == "EXECUTED_SUCCESSFULLY"
        )

        self.items.append(
            ToolEvidence(
                tool=str(tool),
                args=dict(
                    args or {}
                ),
                output=text,
                success=success,
                timestamp=time.time(),
                outcome=outcome,
            )
        )

    def successful(
        self,
        names=None,
    ):
        names = (
            set(names)
            if names is not None
            else None
        )

        return [
            item
            for item in self.items
            if (
                item.success
                and (
                    names is None
                    or item.tool in names
                )
            )
        ]

    def failures(self):
        return [
            item
            for item in self.items
            if not item.success
        ]

    def summary(self):
        return {
            "tool_calls": len(
                self.items
            ),
            "successful": len(
                self.successful()
            ),
            "failed": len(
                self.failures()
            ),
            "tools": [
                {
                    "tool": item.tool,
                    "success": item.success,
                    "outcome": item.outcome,
                }
                for item in self.items
            ],
        }
