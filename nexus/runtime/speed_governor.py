from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any
import os


def smart_mode_enabled() -> bool:
    """
    SMART mode preserves caching, telemetry and route
    capabilities while disabling aggressive speed pressure.
    """
    value = os.environ.get(
        "NEXUS_SPEED_MODE",
        "SMART",
    )

    return value.strip().upper() == "SMART"


READ_ONLY_TOOLS = {
    "list_files",
    "read_file",
    "search_files",
    "memory_search",
}

PROGRESS_TOOLS = {
    "write_file",
    "shell",
    "process_start",
    "delegate_task",
    "acceptance_verify",
}


def canonical_tool_signature(
    name: str,
    arguments: Any,
) -> str:
    payload = json.dumps(
        {
            "name": name,
            "arguments": arguments,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


@dataclass
class SpeedGovernor:
    discovery_budget: int = 6
    repeated_call_limit: int = 1
    action_required_iteration: int = 8

    discovery_calls: int = 0
    successful_discovery_calls: int = 0
    targeted_discovery_calls: int = 0
    cache_hits: int = 0
    suppressed_calls: int = 0
    progress_events: int = 0

    turn_started_at: float = field(
        default_factory=time.monotonic
    )

    seen_calls: dict[str, int] = field(
        default_factory=dict
    )

    tool_timings: list[dict[str, Any]] = field(
        default_factory=list
    )

    def before_tool(
        self,
        *,
        iteration: int,
        name: str,
        arguments: Any,
    ) -> dict[str, Any]:
        signature = canonical_tool_signature(
            name,
            arguments,
        )

        seen = self.seen_calls.get(
            signature,
            0,
        )

        if (
            name in READ_ONLY_TOOLS
            and seen >= self.repeated_call_limit
        ):
            self.suppressed_calls += 1

            return {
                "allow": False,
                "reason": (
                    "DUPLICATE_READ_ONLY_CALL"
                ),
                "signature": signature,
            }

        if name in READ_ONLY_TOOLS:
            self.discovery_calls += 1

        if (
            not smart_mode_enabled()
            and self.discovery_calls
            > self.discovery_budget
            and self.progress_events == 0
            and name in READ_ONLY_TOOLS
        ):
            return {
                "allow": False,
                "reason": (
                    "DISCOVERY_BUDGET_EXCEEDED"
                ),
                "signature": signature,
            }

        if (
            not smart_mode_enabled()
            and iteration
            >= self.action_required_iteration
            and self.progress_events == 0
            and name in READ_ONLY_TOOLS
        ):
            return {
                "allow": False,
                "reason": (
                    "ACTION_REQUIRED"
                ),
                "signature": signature,
            }

        self.seen_calls[
            signature
        ] = seen + 1

        return {
            "allow": True,
            "reason": None,
            "signature": signature,
        }

    def record_discovery_success(
        self,
        *,
        tool_name: str,
    ) -> None:
        if tool_name not in READ_ONLY_TOOLS:
            return

        self.successful_discovery_calls += 1

        if tool_name in {
            "search_files",
            "read_file",
            "memory_search",
        }:
            self.targeted_discovery_calls += 1

    def completion_allowed(
        self,
        *,
        route_name: str,
    ) -> tuple[bool, str | None]:
        if smart_mode_enabled():
            return True, None

        if route_name != "FAST_LOOKUP":
            return True, None

        if self.successful_discovery_calls < 2:
            return (
                False,
                "INSUFFICIENT_DISCOVERY_EVIDENCE",
            )

        if self.targeted_discovery_calls < 1:
            return (
                False,
                "NO_TARGETED_DISCOVERY_EVIDENCE",
            )

        return True, None

    def record_progress(
        self,
        tool_name: str,
    ) -> None:
        if tool_name in PROGRESS_TOOLS:
            self.progress_events += 1

    def record_tool_timing(
        self,
        *,
        name: str,
        duration: float,
        cached: bool = False,
    ) -> None:
        if cached:
            self.cache_hits += 1

        self.tool_timings.append(
            {
                "name": name,
                "duration": duration,
                "cached": cached,
            }
        )

    def guidance(
        self,
        reason: str,
    ) -> str:
        if reason == "DUPLICATE_READ_ONLY_CALL":
            return (
                "SPEED_GOVERNOR: This exact read-only "
                "tool call was already performed. Reuse "
                "the existing result. Do not call it again."
            )

        if reason == "DISCOVERY_BUDGET_EXCEEDED":
            return (
                "SPEED_GOVERNOR: Discovery budget exhausted. "
                "Use the evidence already collected. Perform "
                "the next concrete action, delegate a focused "
                "task, or return the result if sufficient."
            )

        if reason == "ACTION_REQUIRED":
            return (
                "SPEED_GOVERNOR: Too many iterations occurred "
                "without concrete progress. Stop broad discovery "
                "and take the next goal-directed action now."
            )

        return (
            "SPEED_GOVERNOR: Avoid unnecessary tool calls."
        )

    def report(
        self,
    ) -> dict[str, Any]:
        elapsed = (
            time.monotonic()
            - self.turn_started_at
        )

        total_tool_time = sum(
            item["duration"]
            for item in self.tool_timings
        )

        return {
            "elapsed_seconds": elapsed,
            "tool_seconds": total_tool_time,
            "discovery_calls": self.discovery_calls,
            "successful_discovery_calls": (
                self.successful_discovery_calls
            ),
            "targeted_discovery_calls": (
                self.targeted_discovery_calls
            ),
            "cache_hits": self.cache_hits,
            "suppressed_calls": self.suppressed_calls,
            "progress_events": self.progress_events,
            "tool_calls": len(
                self.tool_timings
            ),
        }
