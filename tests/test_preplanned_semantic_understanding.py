import ast
from pathlib import Path

import nexus.agent as agent_module

from nexus.runtime.prompt_milestones import (
    Milestone,
    MilestonePlan,
    master_prompt_hash,
    turn_checklist_execution_prompt,
    final_verification_execution_prompt,
    preplanned_understanding_prompt,
)


def _plan():
    master = "Perform a READ-ONLY audit."

    milestone = Milestone(
        id="M1",
        title="Architecture",
        objective="Inspect architecture.",
        requirements=(
            "Identify systems.",
        ),
        restrictions=(
            "Do not modify source.",
        ),
        dependencies=(),
        evidence_required=(
            "Filesystem evidence.",
        ),
        completion_definition=(
            "Architecture documented.",
        ),
    )

    return MilestonePlan(
        master_prompt_sha256=(
            master_prompt_hash(master)
        ),
        master_prompt=master,
        milestones=(milestone,),
        global_restrictions=(
            "READ_ONLY",
        ),
        final_completion_definition=(
            "Audit verified.",
        ),
    )


def test_milestone_semantic_view():
    canonical = (
        turn_checklist_execution_prompt(
            plan=_plan(),
            index=0,
        )
    )

    semantic = (
        preplanned_understanding_prompt(
            canonical
        )
    )

    assert (
        "EXECUTION_KIND=MILESTONE"
        in semantic
    )

    assert (
        "Inspect architecture."
        in semantic
    )

    assert "READ_ONLY" in semantic

    assert (
        "NEXUS_MILESTONE_EXECUTION_V1"
        not in semantic
    )

    assert (
        "Execute ONLY this milestone"
        not in semantic
    )


def test_final_semantic_view():
    canonical = (
        final_verification_execution_prompt(
            """
NEXUS_MILESTONE_FINAL_VERIFICATION_V1
Verify the completed master milestone plan.

MASTER PROMPT:
Perform a READ-ONLY audit.

FINAL COMPLETION DEFINITION:
- Audit verified.

Do not redo completed milestones. Verify whether the master request as a whole meets its final completion definition.
""".strip()
        )
    )

    semantic = (
        preplanned_understanding_prompt(
            canonical
        )
    )

    assert (
        "EXECUTION_KIND=FINAL_VERIFICATION"
        in semantic
    )

    assert (
        "Perform a READ-ONLY audit."
        in semantic
    )

    assert (
        "NEXUS_FINAL_VERIFICATION_V1"
        not in semantic
    )


def test_agent_uses_semantic_input_only_on_preplanned_path():
    source = Path(
        agent_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    cls = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "Agent"
        )
    )

    run = next(
        node
        for node in cls.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "run"
        )
    )

    branch = next(
        node
        for node in ast.walk(run)
        if (
            isinstance(node, ast.If)
            and (
                ast.get_source_segment(
                    source,
                    node.test,
                )
                or ""
            ).strip()
            == "_raw_preplanned_execution"
        )
    )

    direct_calls = []

    for statement in branch.body:
        for node in ast.walk(statement):
            if not isinstance(
                node,
                ast.Call,
            ):
                continue

            if not (
                isinstance(
                    node.func,
                    ast.Name,
                )
                and node.func.id
                == "understand_task"
            ):
                continue

            direct_calls.append(node)

    normal_calls = []

    for statement in branch.orelse:
        for node in ast.walk(statement):
            if not isinstance(
                node,
                ast.Call,
            ):
                continue

            if not (
                isinstance(
                    node.func,
                    ast.Name,
                )
                and node.func.id
                == "understand_task"
            ):
                continue

            normal_calls.append(node)

    assert len(direct_calls) == 1
    assert len(normal_calls) == 1

    direct_argument = (
        ast.get_source_segment(
            source,
            direct_calls[0].args[0],
        )
        or ""
    )

    normal_argument = (
        ast.get_source_segment(
            source,
            normal_calls[0].args[0],
        )
        or ""
    )

    assert (
        direct_argument
        == "_semantic_understanding_task"
    )

    assert normal_argument == "task"

    direct_text = "\n".join(
        ast.get_source_segment(
            source,
            statement,
        )
        or ""
        for statement in branch.body
    )

    normal_text = "\n".join(
        ast.get_source_segment(
            source,
            statement,
        )
        or ""
        for statement in branch.orelse
    )

    assert (
        "preplanned_understanding_prompt("
        in direct_text
    )

    assert (
        "_semantic_understanding_task"
        in direct_text
    )

    assert (
        "preplanned_understanding_prompt("
        not in normal_text
    )

