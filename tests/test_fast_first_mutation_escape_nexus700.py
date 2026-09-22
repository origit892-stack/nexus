from __future__ import annotations

from nexus.runtime.fast_first import (
    classify_fast_first,
)


MUTATING_TASKS = (
    "Create a file named hello.txt.",
    "Modify nexus/agent.py.",
    "Delete obsolete files.",
    "Fix the bug in this Python source.",
    "Move Roblox MeshParts into a straight line in Studio.",
    "Create a bunker door in Roblox Studio.",
    "Change Workspace terrain around spawn.",
    "Implement a stamina system in the Roblox game.",
    "Add a ProximityPrompt to the bunker door.",
    "Reposition all meshes 10 studs apart.",
    "Generate and place 19 MeshParts in Workspace.",
)


def test_mutating_tasks_are_not_fast_first_eligible():
    escaped = []

    for task in MUTATING_TASKS:
        decision = classify_fast_first(
            task
        )

        if bool(
            getattr(
                decision,
                "eligible",
                False,
            )
        ):
            escaped.append(task)

    assert escaped == []
