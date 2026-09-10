from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    name: str
    discovery_budget: int
    action_iteration: int


FAST_LOOKUP = Route(
    name="FAST_LOOKUP",
    discovery_budget=8,
    action_iteration=5,
)

EDIT_AND_VERIFY = Route(
    name="EDIT_AND_VERIFY",
    discovery_budget=5,
    action_iteration=6,
)

COMPLEX = Route(
    name="COMPLEX",
    discovery_budget=8,
    action_iteration=10,
)


def explicit_route_name(
    task: str,
) -> str | None:
    """
    Return an explicitly requested Nexus route.

    Explicit route directives have precedence over
    heuristic task classification.
    """
    normalized = " ".join(
        str(task).upper().split()
    )

    directives = (
        (
            "FAST_LOOKUP",
            (
                "THIS IS A FAST_LOOKUP TASK",
                "ROUTE: FAST_LOOKUP",
                "NEXUS_ROUTE=FAST_LOOKUP",
                "NEXUS ROUTE: FAST_LOOKUP",
            ),
        ),
        (
            "EDIT_AND_VERIFY",
            (
                "THIS IS AN EDIT_AND_VERIFY TASK",
                "ROUTE: EDIT_AND_VERIFY",
                "NEXUS_ROUTE=EDIT_AND_VERIFY",
                "NEXUS ROUTE: EDIT_AND_VERIFY",
            ),
        ),
    )

    matches = [
        route_name
        for route_name, phrases in directives
        if any(
            phrase in normalized
            for phrase in phrases
        )
    ]

    # Conflicting explicit directives are not guessed.
    if len(set(matches)) > 1:
        return None

    if matches:
        return matches[0]

    return None


def route_source(
    instruction: str,
) -> str:
    if (
        explicit_route_name(
            instruction
        )
        is not None
    ):
        return "EXPLICIT"

    return "CLASSIFIER"


def classify_task(
    instruction: str,
) -> Route:
    explicit = explicit_route_name(instruction)

    if explicit == "FAST_LOOKUP":
        return FAST_LOOKUP

    if explicit == "EDIT_AND_VERIFY":
        return EDIT_AND_VERIFY

    text = instruction.lower()

    lookup_signals = (
        "find ",
        "list ",
        "show ",
        "locate ",
        "which files",
        "what files",
        "search ",
        "audit assets",
        "inventory",
    )

    edit_signals = (
        "fix ",
        "change ",
        "edit ",
        "update ",
        "create ",
        "implement ",
        "patch ",
    )

    complex_signals = (
        "architecture",
        "redesign",
        "investigate",
        "root cause",
        "comprehensive",
        "full game",
    )

    if any(
        signal in text
        for signal in complex_signals
    ):
        return COMPLEX

    if any(
        signal in text
        for signal in edit_signals
    ):
        return EDIT_AND_VERIFY

    if any(
        signal in text
        for signal in lookup_signals
    ):
        return FAST_LOOKUP

    return EDIT_AND_VERIFY
