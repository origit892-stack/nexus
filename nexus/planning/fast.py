from __future__ import annotations

import re


FAST_PLANNER_SYSTEM = """You plan Nexus tasks.

Return JSON only.

Legal roles:
architect,coder,qa,researcher,browser,computer,devops,security

Rules:
- one role per task
- 1-5 tasks
- dependencies are task IDs
- only one coder
- QA verifies independently
- preserve all concrete entities, URLs, requested facts and constraints
- no prose
- no markdown

Schema:
{"objective":"...","tasks":[{"id":"T1","role":"researcher","objective":"...","dependencies":[],"acceptance":["..."]}]}
"""


def compact_objective(
    objective,
    limit=2400,
):
    return re.sub(
        r"\s+",
        " ",
        str(objective),
    ).strip()[:limit]


def simple_web_research_plan(
    objective,
):
    original = compact_objective(
        objective
    )

    low = original.lower()

    web = any(
        token in low
        for token in (
            "website",
            "homepage",
            "http://",
            "https://",
            "web evidence",
            "official site",
            "official-site",
            "online",
            "internet",
        )
    )

    verify = any(
        token in low
        for token in (
            "verify",
            "verification",
            "independent qa",
            "independently",
            "independent",
        )
    )

    write = any(
        token in low
        for token in (
            "implement",
            "modify",
            "write code",
            "fix code",
            "edit file",
            "patch",
        )
    )

    if not web or write:
        return None

    researcher_objective = (
        "Execute this research request exactly as written. "
        "Preserve every named entity, website, requested fact, "
        "and constraint. Do not substitute another project, "
        "website, or topic.\n\n"
        "ORIGINAL REQUEST:\n"
        + original
    )

    researcher_acceptance = [
        (
            "Answer the concrete research target in the "
            "original request using successful authoritative "
            "web evidence"
        ),
        (
            "Preserve the named website/entity and requested "
            "fact from the original request"
        ),
    ]

    tasks = [
        {
            "id": "T1",
            "role": "researcher",
            "objective": researcher_objective,
            "dependencies": [],
            "acceptance": researcher_acceptance,
        }
    ]

    if verify:
        tasks.append(
            {
                "id": "T2",
                "role": "qa",
                "objective": (
                    "Independently verify the concrete finding "
                    "produced by T1 against the SAME named "
                    "authoritative source and SAME requested "
                    "fact from the original request. Use your "
                    "own source evidence. Do not invent or "
                    "substitute another website/topic.\n\n"
                    "ORIGINAL REQUEST:\n"
                    + original
                ),
                "dependencies": [
                    "T1"
                ],
                "acceptance": [
                    (
                        "T1 produced a concrete finding rather "
                        "than requesting clarification"
                    ),
                    (
                        "Independent evidence was gathered from "
                        "the same authoritative source/topic"
                    ),
                    (
                        "T1 finding was explicitly confirmed "
                        "or rejected"
                    ),
                ],
            }
        )

    return {
        "objective": original,
        "tasks": tasks,
    }
