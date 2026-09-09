from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class ToolEvidence:
    tool: str
    args: dict
    output: str
    success: bool
    timestamp: float


class EvidenceLedger:
    def __init__(self):
        self.items = []

    def record(
        self,
        tool,
        args,
        output,
    ):
        text = str(
            output
        )

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

        success = not any(
            marker in text
            for marker
            in failure_markers
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
                }
                for item in self.items
            ],
        }
