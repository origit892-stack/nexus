from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


READ_ONLY = "READ_ONLY"
NORMAL = "NORMAL"


READ_ONLY_ALLOWLIST = frozenset({
    "list_files",
    "read_file",
    "search_files",
    "memory_search",
})


@dataclass(frozen=True)
class CapabilityDecision:
    allow: bool
    reason: str


def normalize_policy(
    value,
) -> str:
    text = str(
        value or NORMAL
    ).strip().upper()

    if text == READ_ONLY:
        return READ_ONLY

    return NORMAL


def evaluate_capability(
    *,
    policy,
    tool_name,
) -> CapabilityDecision:
    policy = normalize_policy(
        policy
    )

    name = str(
        tool_name or ""
    ).strip()

    if policy != READ_ONLY:
        return CapabilityDecision(
            True,
            "NORMAL_POLICY",
        )

    if name in READ_ONLY_ALLOWLIST:
        return CapabilityDecision(
            True,
            "READ_ONLY_ALLOWLIST",
        )

    return CapabilityDecision(
        False,
        (
            "READ_ONLY_TOOL_BLOCKED:"
            + name
        ),
    )


def allowed_tools_for_policy(
    *,
    policy,
    available_tools: Iterable[str],
) -> set[str]:
    policy = normalize_policy(
        policy
    )

    names = {
        str(name)
        for name in available_tools
    }

    if policy != READ_ONLY:
        return names

    return names.intersection(
        READ_ONLY_ALLOWLIST
    )
