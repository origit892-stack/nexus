from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


VALID_ROLES = {
    "architect",
    "coder",
    "qa",
    "researcher",
    "browser",
    "computer",
    "devops",
    "security",
}


ROLE_ALIASES = {
    "research": "researcher",
    "research agent": "researcher",
    "web": "researcher",
    "web research": "researcher",
    "web researcher": "researcher",

    "browser agent": "browser",

    "quality assurance": "qa",
    "quality-assurance": "qa",
    "tester": "qa",
    "test": "qa",

    "developer": "coder",
    "coding": "coder",
    "implementation": "coder",
    "implementer": "coder",

    "architecture": "architect",

    "computer agent": "computer",
    "gui": "computer",

    "devops agent": "devops",
    "ops": "devops",

    "security reviewer": "security",
}


@dataclass
class PlannedTask:
    id: str
    role: str
    objective: str
    dependencies: list[str] = field(
        default_factory=list
    )
    acceptance: list[str] = field(
        default_factory=list
    )


@dataclass
class Plan:
    objective: str
    tasks: list[PlannedTask]


PLANNER_SYSTEM = """
You are the Nexus execution planner.

Convert the user's objective into a SMALL dependency DAG.

Every task MUST have exactly ONE role.

LEGAL ROLES:

architect
coder
qa
researcher
browser
computer
devops
security

NEVER output combined roles such as:

browser/researcher
architect+qa
coder/devops

ROLE OWNERSHIP:

researcher:
public web research, web_search, web_fetch,
source discovery and evidence gathering.

browser:
interactive browser navigation, clicking,
forms and browser automation.

architect:
read-only architecture and code analysis.

coder:
the single implementation writer.

qa:
independent verification.

computer:
GUI/computer interaction.

devops:
CLI infrastructure, processes, servers and SSH.

security:
security and permission review.

RULES:

- Use specialists.
- Independent read-only investigations may run in parallel.
- Only one Coder may own overlapping implementation scope.
- QA must be independent from Coder.
- Implementation tasks require concrete acceptance criteria.
- Stub/mock/placeholder cannot satisfy real implementation acceptance.
- Do not claim execution occurred.
- Usually use 2-6 tasks.
- Dependencies must reference task IDs exactly.
- Return JSON ONLY.
- No Markdown.
- No explanation.

SCHEMA:

{
  "objective": "string",
  "tasks": [
    {
      "id": "T1",
      "role": "researcher",
      "objective": "string",
      "dependencies": [],
      "acceptance": ["string"]
    }
  ]
}
"""


def normalize_role(role, objective=""):
    raw = str(role or "").strip().lower()

    raw = re.sub(
        r"\s+",
        " ",
        raw,
    )

    if raw in VALID_ROLES:
        return raw

    if raw in ROLE_ALIASES:
        return ROLE_ALIASES[raw]

    pieces = [
        x.strip()
        for x in re.split(
            r"[/+,&|]|\band\b",
            raw,
        )
        if x.strip()
    ]

    normalized = []

    for piece in pieces:
        if piece in VALID_ROLES:
            normalized.append(piece)

        elif piece in ROLE_ALIASES:
            normalized.append(
                ROLE_ALIASES[piece]
            )

    normalized = list(
        dict.fromkeys(normalized)
    )

    if len(normalized) == 1:
        return normalized[0]

    if len(normalized) > 1:
        objective_lower = str(
            objective
        ).lower()

        interactive_words = (
            "click",
            "fill",
            "navigate",
            "interactive",
            "browser automation",
            "form",
            "login",
            "tab",
        )

        research_words = (
            "research",
            "search",
            "fetch",
            "source",
            "evidence",
            "website",
            "web",
        )

        if (
            "browser" in normalized
            and any(
                word in objective_lower
                for word in interactive_words
            )
        ):
            return "browser"

        if (
            "researcher" in normalized
            and any(
                word in objective_lower
                for word in research_words
            )
        ):
            return "researcher"

        priority = (
            "computer",
            "devops",
            "browser",
            "researcher",
            "architect",
            "qa",
            "security",
            "coder",
        )

        for candidate in priority:
            if candidate in normalized:
                return candidate

    raise ValueError(
        f"INVALID_ROLE={role}"
    )


def extract_json(text):
    text = str(
        text or ""
    ).strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(
            lines
        ).strip()

    try:
        return json.loads(text)

    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        return json.loads(
            text[start:end + 1]
        )

    raise ValueError(
        "PLAN_JSON_NOT_FOUND"
    )


def check_cycles(tasks):
    graph = {
        task.id: list(
            task.dependencies
        )
        for task in tasks
    }

    visiting = set()
    visited = set()

    def visit(node):
        if node in visited:
            return

        if node in visiting:
            raise ValueError(
                f"DAG_CYCLE={node}"
            )

        visiting.add(node)

        for dep in graph.get(
            node,
            [],
        ):
            visit(dep)

        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def validate_plan(raw):
    if not isinstance(raw, dict):
        raise ValueError(
            "PLAN_NOT_OBJECT"
        )

    tasks = raw.get("tasks")

    if (
        not isinstance(tasks, list)
        or not tasks
    ):
        raise ValueError(
            "PLAN_HAS_NO_TASKS"
        )

    ids = set()
    result = []
    coder_count = 0

    for index, item in enumerate(tasks):
        if not isinstance(item, dict):
            raise ValueError(
                f"INVALID_TASK={index}"
            )

        tid = str(
            item.get(
                "id",
                f"T{index + 1}",
            )
        ).strip()

        if not tid:
            tid = f"T{index + 1}"

        if tid in ids:
            raise ValueError(
                f"DUPLICATE_TASK_ID={tid}"
            )

        ids.add(tid)

        objective = str(
            item.get(
                "objective",
                "",
            )
        ).strip()

        if not objective:
            raise ValueError(
                f"TASK_OBJECTIVE_MISSING={tid}"
            )

        role = normalize_role(
            item.get(
                "role",
                "",
            ),
            objective,
        )

        if role == "coder":
            coder_count += 1

        dependencies = item.get(
            "dependencies",
            [],
        )

        if dependencies is None:
            dependencies = []

        if not isinstance(
            dependencies,
            list,
        ):
            dependencies = [
                dependencies
            ]

        dependencies = [
            str(x).strip()
            for x in dependencies
            if str(x).strip()
        ]

        acceptance = item.get(
            "acceptance",
            [],
        )

        if acceptance is None:
            acceptance = []

        if isinstance(
            acceptance,
            str,
        ):
            acceptance = [
                acceptance
            ]

        result.append(
            PlannedTask(
                id=tid,
                role=role,
                objective=objective,
                dependencies=dependencies,
                acceptance=[
                    str(x)
                    for x in acceptance
                ],
            )
        )

    if coder_count > 1:
        raise ValueError(
            "MULTIPLE_CODERS_BLOCKED"
        )

    for task in result:
        for dep in task.dependencies:
            if dep not in ids:
                raise ValueError(
                    f"UNKNOWN_DEPENDENCY={dep}"
                )

            if dep == task.id:
                raise ValueError(
                    f"SELF_DEPENDENCY={task.id}"
                )

    check_cycles(result)

    return Plan(
        objective=str(
            raw.get(
                "objective",
                "",
            )
        ),
        tasks=result,
    )


def parse_plan(text):
    return validate_plan(
        extract_json(text)
    )
