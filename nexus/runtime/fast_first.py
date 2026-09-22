from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Iterable


@dataclass(frozen=True)
class FastFirstDecision:
    eligible: bool
    route: str
    reason: str
    read_only: bool
    deterministic_completion: bool
    skip_understanding_model: bool
    skip_planner_model: bool
    skip_completion_model: bool
    max_tool_calls: int
    max_iterations: int


_MUTATION_TERMS = (
    "create",
    "write",
    "edit",
    "modify",
    "delete",
    "remove",
    "rename",
    "move",
    "install",
    "upgrade",
    "commit",
    "push",
    "publish",
    "deploy",
    "build",
    "generate",
    "fix",
    "patch",
    "change",
    "replace",
)

_COMPLEX_TERMS = (
    "architect",
    "architecture",
    "design a system",
    "refactor",
    "implement",
    "debug",
    "investigate why",
    "root cause",
    "optimize",
    "benchmark",
    "compare approaches",
    "research",
    "plan",
    "strategy",
    "migrate",
)

_LOOKUP_TERMS = (
    "find",
    "locate",
    "search",
    "read",
    "inspect",
    "check",
    "verify",
    "list",
    "show",
    "report",
    "what",
    "which",
    "where",
    "does",
    "is there",
    "exists",
)

_READ_ONLY_MARKERS = (
    "read-only",
    "read only",
    "do not modify",
    "don't modify",
    "do not change",
    "don't change",
    "do not edit",
    "don't edit",
    "do not create",
)


def _normalized(text: str) -> str:
    return " ".join(
        str(text or "")
        .strip()
        .lower()
        .split()
    )


def classify_fast_first(
    task: str,
) -> FastFirstDecision:
    text = _normalized(task)

    if not text:
        return FastFirstDecision(
            eligible=False,
            route="NORMAL",
            reason="empty_task",
            read_only=False,
            deterministic_completion=False,
            skip_understanding_model=False,
            skip_planner_model=False,
            skip_completion_model=False,
            max_tool_calls=0,
            max_iterations=0,
        )

    explicit_read_only = any(
        marker in text
        for marker in _READ_ONLY_MARKERS
    )

    mutation_requested = any(
        re.search(
            r"\b"
            + re.escape(term)
            + r"\b",
            text,
        )
        for term in _MUTATION_TERMS
    )

    if explicit_read_only:
        mutation_requested = False

    complex_requested = any(
        term in text
        for term in _COMPLEX_TERMS
    )

    lookup_requested = any(
        re.search(
            r"\b"
            + re.escape(term)
            + r"\b",
            text,
        )
        for term in _LOOKUP_TERMS
    )

    filesystem_signal = any(
        token in text
        for token in (
            ".md",
            ".toml",
            ".json",
            ".yaml",
            ".yml",
            ".py",
            ".lua",
            ".luau",
            "file",
            "folder",
            "directory",
            "workspace",
            "heading",
            "version",
            "path",
        )
    )

    eligible = (
        lookup_requested
        and filesystem_signal
        and not mutation_requested
        and not complex_requested
    )

    if not eligible:
        return FastFirstDecision(
            eligible=False,
            route="NORMAL",
            reason="requires_normal_reasoning",
            read_only=explicit_read_only,
            deterministic_completion=False,
            skip_understanding_model=False,
            skip_planner_model=False,
            skip_completion_model=False,
            max_tool_calls=0,
            max_iterations=0,
        )

    return FastFirstDecision(
        eligible=True,
        route="FAST_LOOKUP",
        reason="simple_read_only_filesystem_lookup",
        read_only=True,
        deterministic_completion=True,
        skip_understanding_model=True,
        skip_planner_model=True,
        skip_completion_model=True,
        max_tool_calls=4,
        max_iterations=5,
    )


def fast_lookup_contract(
    task: str,
) -> dict:
    decision = classify_fast_first(
        task
    )

    return {
        "route":
            decision.route,

        "authorized_now":
            [
                "Perform focused read-only filesystem discovery.",
                "Read only the minimum files required to answer.",
            ],

        "forbidden_now":
            [
                "Create project files.",
                "Modify project files.",
                "Delete project files.",
                "Use memory as task evidence.",
            ],

        "deferred_actions":
            [],

        "approval_gates":
            [],

        "targets":
            [],

        "search_strategy":
            [
                "Use direct filesystem tools against the requested workspace.",
                "Prefer exact-name search before broad listing.",
                "Stop discovery when every requested fact has direct evidence.",
            ],

        "evidence_plan":
            [
                "Tool output is evidence.",
                "A successful exhaustive exact-name search with zero matches is valid negative evidence.",
                "File contents read directly from the workspace are positive evidence.",
            ],

        "evaluation_plan":
            [
                "Verify every requested fact has direct tool evidence.",
            ],

        "selection_strategy":
            [
                "Use the narrowest sufficient evidence.",
            ],

        "first_actions":
            [
                "Perform the most direct filesystem lookup required by the request.",
            ],

        "stop_conditions":
            [
                "Every requested fact has direct filesystem evidence.",
            ],
    }


def deterministic_fast_completion(
    *,
    task: str,
    evidence_entries: Iterable,
) -> tuple[bool, str]:
    entries = list(
        evidence_entries
        or []
    )

    if not entries:
        return (
            False,
            "no_evidence",
        )

    verified = []

    for entry in entries:
        if isinstance(
            entry,
            dict,
        ):
            if entry.get(
                "verified",
                True,
            ):
                verified.append(
                    entry
                )
            continue

        if getattr(
            entry,
            "verified",
            True,
        ):
            verified.append(
                entry
            )

    if not verified:
        return (
            False,
            "no_verified_evidence",
        )

    return (
        True,
        "verified_fast_lookup_evidence",
    )
