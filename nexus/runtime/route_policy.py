from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


FAST_LOOKUP_ALLOWED = frozenset(
    {
        "list_files",
        "search_files",
        "read_file",
        "memory_search",
    }
)

FAST_LOOKUP_BLOCKED = frozenset(
    {
        "shell",
        "process_start",
        "write_file",
        "delegate_task",
        "memory_add",
    }
)

MUTATION_TOOL_NAMES = frozenset(
    {
        "write_file",
        "process_start",
        "delegate_task",
        "memory_add",
    }
)

PACKAGE_INSTALL_PATTERN = re.compile(
    r"""
    \b(
        pip(?:3)?\s+install
        |
        python(?:3)?\s+-m\s+pip\s+install
        |
        brew\s+install
        |
        npm\s+(?:install|i)
        |
        pnpm\s+(?:install|add)
        |
        yarn\s+add
        |
        gem\s+install
        |
        cargo\s+install
    )\b
    """,
    flags=(
        re.IGNORECASE
        | re.VERBOSE
    ),
)

BLENDER_PATTERN = re.compile(
    r"(?i)(?:^|[\s/])blender(?:\s|$)"
)

OPEN3D_PATTERN = re.compile(
    r"(?i)\b(?:open3d|o3d)\b"
)


@dataclass(frozen=True)
class RouteDecision:
    allow: bool
    reason: str | None = None


def _shell_command(
    arguments: Any,
) -> str:
    if not isinstance(
        arguments,
        dict,
    ):
        return ""

    return str(
        arguments.get(
            "command",
            "",
        )
    )


def evaluate_route_tool(
    *,
    route_name: str,
    tool_name: str,
    arguments: Any,
) -> RouteDecision:
    if route_name != "FAST_LOOKUP":
        return RouteDecision(
            allow=True
        )

    if tool_name in FAST_LOOKUP_ALLOWED:
        return RouteDecision(
            allow=True
        )

    if tool_name in FAST_LOOKUP_BLOCKED:
        if tool_name == "shell":
            command = _shell_command(
                arguments
            )

            if PACKAGE_INSTALL_PATTERN.search(
                command
            ):
                return RouteDecision(
                    False,
                    "FAST_LOOKUP_PACKAGE_INSTALL_BLOCKED",
                )

            if BLENDER_PATTERN.search(
                command
            ):
                return RouteDecision(
                    False,
                    "FAST_LOOKUP_BLENDER_BLOCKED",
                )

            if OPEN3D_PATTERN.search(
                command
            ):
                return RouteDecision(
                    False,
                    "FAST_LOOKUP_OPEN3D_BLOCKED",
                )

        return RouteDecision(
            False,
            (
                "FAST_LOOKUP_TOOL_BLOCKED:"
                + tool_name
            ),
        )

    # Strict allowlist:
    # unknown tools do not become accidental escape hatches.
    return RouteDecision(
        False,
        (
            "FAST_LOOKUP_NOT_ALLOWLISTED:"
            + tool_name
        ),
    )


def fast_lookup_hard_stop(
    *,
    route_name: str,
    iteration: int,
    max_iteration: int = 6,
) -> bool:
    return (
        route_name == "FAST_LOOKUP"
        and iteration > max_iteration
    )


def automatic_route_enforcement_enabled() -> bool:
    """
    Automatic legacy routing is disabled in normal Nexus
    operation.

    NEXUS_ROUTE_MODE=STRICT restores it for debugging and
    regression testing.
    """
    import os

    return (
        os.environ.get(
            "NEXUS_ROUTE_MODE",
            "OFF",
        )
        .strip()
        .upper()
        == "STRICT"
    )
