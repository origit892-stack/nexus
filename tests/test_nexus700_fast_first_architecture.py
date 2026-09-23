import ast
from pathlib import Path


SOURCE = Path(
    "nexus/agent.py"
).read_text(
    encoding="utf-8"
)

TREE = ast.parse(
    SOURCE
)


def _run():
    for node in TREE.body:
        if not isinstance(
            node,
            ast.ClassDef,
        ):
            continue

        if node.name != "Agent":
            continue

        for child in node.body:
            if (
                isinstance(
                    child,
                    ast.FunctionDef,
                )
                and child.name
                == "run"
            ):
                return child

    raise AssertionError(
        "Agent.run missing"
    )


def test_fast_first_import_is_top_level():
    imports = [
        node
        for node in TREE.body
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
            == "nexus.runtime.fast_first"
        )
    ]

    assert len(imports) == 1


def test_fast_decision_exists():
    assert (
        "NEXUS700_FAST_FIRST_DECISION"
        in SOURCE
    )


def test_reasoning_bypass_exists():
    assert (
        "NEXUS700_FAST_SKIP_REASONING"
        in SOURCE
    )


def test_understanding_and_planner_are_in_bypass():
    """
    Persisted Turn Checklist work is already master-planned.

    Both milestone execution and final verification are members
    of the preplanned execution path. They execute the canonical
    persisted contract directly and invoke neither Understanding
    nor Planner again.
    """
    run = _run()
    source = SOURCE

    segment = (
        ast.get_source_segment(
            source,
            run,
        )
        or ""
    )

    milestone_detector = segment.find(
        "is_turn_checklist_execution_prompt("
    )
    final_detector = segment.find(
        "is_final_verification_prompt("
    )
    master_preprocessor = segment.find(
        "_prepare_prompt_for_understanding("
    )

    assert milestone_detector >= 0
    assert final_detector >= 0
    assert master_preprocessor >= 0

    assert (
        milestone_detector
        < master_preprocessor
    )
    assert (
        final_detector
        < master_preprocessor
    )

    preplanned_branch = None

    for statement in ast.walk(run):
        if not isinstance(
            statement,
            ast.If,
        ):
            continue

        condition = (
            ast.get_source_segment(
                source,
                statement.test,
            )
            or ""
        )

        if (
            condition.strip()
            == "_raw_preplanned_execution"
        ):
            preplanned_branch = statement
            break

    assert preplanned_branch is not None

    direct_text = "\n".join(
        (
            ast.get_source_segment(
                source,
                statement,
            )
            or ""
        )
        for statement
        in preplanned_branch.body
    )

    normal_text = "\n".join(
        (
            ast.get_source_segment(
                source,
                statement,
            )
            or ""
        )
        for statement
        in preplanned_branch.orelse
    )

    assert "understand_task(" not in direct_text
    assert "plan_task(" not in direct_text
    assert (
        "preplanned_understanding_prompt("
        not in direct_text
    )

    assert (
        "self._preplanned_execution_brief("
        in direct_text
    )
    assert (
        "self._understanding = None"
        in direct_text
    )
    assert (
        "self._execution_plan = None"
        in direct_text
    )

    assert "understand_task(" in normal_text
    assert "plan_task(" in normal_text






def test_loader_contract_fixed():
    source = Path(
        "nexus/runtime/execution_completion.py"
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    assert (
        "NEXUS700_NORMALIZE_MODEL_LOADER_RESULT"
        in source
    )

    assert "_loaded_model" in source

    assert (
        "len(_loaded_model) == 2"
        in source
    )

    assert (
        "len(_loaded_model) >= 3"
        in source
    )

    assert (
        "_model_metadata = None"
        in source
    )

    assert (
        "_model_metadata = _loaded_model[2]"
        in source
    )

    loader_calls = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        name = None

        if isinstance(
            node.func,
            ast.Name,
        ):
            name = node.func.id

        elif isinstance(
            node.func,
            ast.Attribute,
        ):
            name = node.func.attr

        if (
            name
            == "_load_model_cached"
        ):
            loader_calls.append(node)

    assert loader_calls


def test_fast_module_exists():
    source = Path(
        "nexus/runtime/fast_first.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "class FastFirstDecision"
        in source
    )


def test_fast_memory_block_exists():
    assert (
        "NEXUS700_FAST_MEMORY_BLOCK"
        in SOURCE
    )


def test_fast_tool_budget_exists():
    assert (
        "NEXUS700_FAST_TOOL_COUNT"
        in SOURCE
    )


def test_fast_deterministic_completion_exists():
    assert (
        "NEXUS700_FAST_DETERMINISTIC_COMPLETION"
        in SOURCE
    )


def test_normal_completion_still_exists():
    assert (
        "evaluate_execution_completion("
        in SOURCE
    )
