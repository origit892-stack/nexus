from pathlib import Path
import ast


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
                and child.name == "run"
            ):
                return child

    raise AssertionError(
        "Agent.run missing"
    )


def _first_definition(name):
    run = _run()

    lines = []

    for node in ast.walk(run):
        if not isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
            ),
        ):
            continue

        targets = (
            node.targets
            if isinstance(
                node,
                ast.Assign,
            )
            else [node.target]
        )

        for target in targets:
            if (
                isinstance(
                    target,
                    ast.Name,
                )
                and target.id == name
            ):
                lines.append(
                    node.lineno
                )

    assert lines

    return min(lines)


def _zero_line():
    for index, line in enumerate(
        SOURCE.splitlines(),
        1,
    ):
        if (
            "NEXUS700_ZERO_LLM_AFTER_RUN_INITIALIZATION"
            in line
        ):
            return index

    raise AssertionError(
        "zero-llm initialization marker missing"
    )


def test_rid_defined_before_zero_llm():
    assert (
        _first_definition("rid")
        < _zero_line()
    )


def test_run_state_defined_before_zero_llm():
    assert (
        _first_definition("run_state")
        < _zero_line()
    )


def test_fast_first_defined_before_zero_llm():
    assert (
        _first_definition("fast_first")
        < _zero_line()
    )


def test_zero_llm_still_uses_self_workspace():
    assert (
        "workspace=self.workspace"
        in SOURCE
    )


def test_zero_llm_block_not_duplicated():
    assert (
        SOURCE.count(
            "NEXUS700_ZERO_LLM_FAST_LOOKUP"
        )
        == 1
    )

    assert (
        SOURCE.count(
            "execute_fast_lookup("
        )
        == 1
    )
