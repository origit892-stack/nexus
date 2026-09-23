import ast
from pathlib import Path

import nexus.agent as agent_module


def _source_and_run():
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

    return source, run


def _preplanned_branch():
    source, run = _source_and_run()

    matches = []

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
            matches.append(node)

    assert len(matches) == 1

    return source, matches[0]


def _statements(
    source,
    statements,
):
    return "\n".join(
        ast.get_source_segment(
            source,
            statement,
        )
        or ""
        for statement in statements
    )


def test_raw_milestone_marker_precedes_master_preprocessor():
    source, run = _source_and_run()

    segment = (
        ast.get_source_segment(
            source,
            run,
        )
        or ""
    )

    milestone = segment.find(
        "is_turn_checklist_execution_prompt("
    )

    prepare = segment.find(
        "_prepare_prompt_for_understanding("
    )

    assert milestone >= 0
    assert prepare >= 0
    assert milestone < prepare


def test_raw_final_marker_precedes_master_preprocessor():
    source, run = _source_and_run()

    segment = (
        ast.get_source_segment(
            source,
            run,
        )
        or ""
    )

    final = segment.find(
        "is_final_verification_prompt("
    )

    prepare = segment.find(
        "_prepare_prompt_for_understanding("
    )

    assert final >= 0
    assert prepare >= 0
    assert final < prepare


def test_preplanned_union_contains_milestone_and_final():
    source, run = _source_and_run()

    segment = (
        ast.get_source_segment(
            source,
            run,
        )
        or ""
    )

    assignment = (
        "_raw_preplanned_execution = ("
    )

    start = segment.find(
        assignment
    )

    assert start >= 0

    end = segment.find(
        "\n\n",
        start,
    )

    assert end >= 0

    union = segment[
        start:end
    ]

    assert (
        "_raw_milestone_execution"
        in union
    )

    assert (
        "_raw_final_verification"
        in union
    )


def test_preplanned_true_branch_uses_direct_brief_no_models():
    source, branch = _preplanned_branch()

    body = _statements(
        source,
        branch.body,
    )

    assert "understand_task(" not in body
    assert "plan_task(" not in body
    assert (
        "preplanned_understanding_prompt("
        not in body
    )
    assert (
        "self._understanding = None"
        in body
    )
    assert (
        "self._preplanned_execution_brief("
        in body
    )
    assert (
        "self._execution_plan = None"
        in body
    )



def test_normal_else_branch_preserves_planner():
    source, branch = _preplanned_branch()

    orelse = _statements(
        source,
        branch.orelse,
    )

    assert "plan_task(" in orelse


def test_preplanned_branch_clears_execution_plan():
    source, branch = _preplanned_branch()

    body = _statements(
        source,
        branch.body,
    )

    assert (
        "self._execution_plan = None"
        in body
    )

    assert (
        'self._execution_plan_prompt = ""'
        in body
    )


def test_master_preprocessor_only_runs_for_non_preplanned_requests():
    source, run = _source_and_run()

    matches = []

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
            == "not _raw_preplanned_execution"
        ):
            matches.append(node)

    assert len(matches) == 1

    body = _statements(
        source,
        matches[0].body,
    )

    assert (
        "_prepare_prompt_for_understanding("
        in body
    )
