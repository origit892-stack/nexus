import ast
from pathlib import Path

import nexus.agent as agent_module
import nexus.sessions.runner as runner_module

from nexus.runtime.prompt_milestones import (
    final_verification_execution_prompt,
    is_final_verification_prompt,
    is_turn_checklist_execution_prompt,
)


def test_final_protocol_is_distinct():
    prompt = final_verification_execution_prompt(
        "Verify final completion."
    )

    assert is_final_verification_prompt(
        prompt
    )

    assert not is_turn_checklist_execution_prompt(
        prompt
    )


def test_final_detector_precedes_master_preprocessor():
    source = Path(
        agent_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef)
        and n.name == "Agent"
    )

    run = next(
        n for n in cls.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "run"
    )

    segment = (
        ast.get_source_segment(
            source,
            run,
        )
        or ""
    )

    final_detector = segment.find(
        "is_final_verification_prompt("
    )

    preprocessor = segment.find(
        "_prepare_prompt_for_understanding("
    )

    assert final_detector >= 0
    assert preprocessor >= 0
    assert final_detector < preprocessor


def test_preplanned_execution_bypasses_understanding_and_planning():
    source = Path(
        agent_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef)
        and n.name == "Agent"
    )

    run = next(
        n for n in cls.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "run"
    )

    branches = []

    for node in ast.walk(run):
        if not isinstance(
            node,
            ast.If,
        ):
            continue

        condition = (
            ast.get_source_segment(
                source,
                node.test,
            )
            or ""
        )

        if (
            condition.strip()
            == "_raw_preplanned_execution"
        ):
            branches.append(node)

    assert len(branches) == 1

    branch = branches[0]

    body = "\n".join(
        ast.get_source_segment(
            source,
            statement,
        )
        or ""
        for statement in branch.body
    )

    orelse = "\n".join(
        ast.get_source_segment(
            source,
            statement,
        )
        or ""
        for statement in branch.orelse
    )

    assert "understand_task(" not in body
    assert "plan_task(" not in body
    assert (
        "preplanned_understanding_prompt("
        not in body
    )

    assert (
        "self._preplanned_execution_brief("
        in body
    )
    assert (
        "self._understanding = None"
        in body
    )
    assert (
        "self._execution_plan = None"
        in body
    )

    assert "understand_task(" in orelse
    assert "plan_task(" in orelse



def test_runner_wraps_final_verification():
    source = Path(
        runner_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "final_verification_execution_prompt("
        in source
    )

    assert (
        "_final_verification_prompt("
        in source
    )
