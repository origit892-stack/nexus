from __future__ import annotations

from pathlib import Path
import ast


SOURCE = Path(
    "nexus/agent.py"
).read_text(
    encoding="utf-8"
)

TREE = ast.parse(SOURCE)


def _run():
    agent = next(
        n for n in TREE.body
        if (
            isinstance(n, ast.ClassDef)
            and n.name == "Agent"
        )
    )

    return next(
        n for n in agent.body
        if (
            isinstance(
                n,
                ast.FunctionDef,
            )
            and n.name == "run"
        )
    )


def _call_lines(name):
    result = []

    for node in ast.walk(_run()):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        current = None

        if isinstance(
            node.func,
            ast.Name,
        ):
            current = node.func.id

        elif isinstance(
            node.func,
            ast.Attribute,
        ):
            current = node.func.attr

        if current == name:
            result.append(
                node.lineno
            )

    return sorted(result)


def test_master_prompt_intake_is_first_router():
    prepare = _call_lines(
        "_prepare_prompt_for_understanding"
    )

    assert len(prepare) == 1

    for name in (
        "classify_fast_first",
        "execute_fast_lookup",
        "understand_task",
    ):
        target = _call_lines(name)

        assert target
        assert prepare[0] < target[0]


def test_raw_intake_v2_marker_exists():
    assert (
        "NEXUS700_MASTER_PROMPT_INTAKE_V2_RAW"
        in SOURCE
    )
