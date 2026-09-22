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
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "Agent"
        ):
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


def _engine_call():
    run = _run()

    calls = []

    for node in ast.walk(run):
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
            == "execute_fast_lookup"
        ):
            calls.append(
                node
            )

    assert len(calls) == 1

    return calls[0]


def test_v2_primary_gate_marker_exists():
    assert (
        "NEXUS700_FAST_ROUTER_V2_PRIMARY_GATE"
        in SOURCE
    )


def test_engine_not_nested_under_fast_first_eligible():
    run = _run()
    call = _engine_call()

    for node in ast.walk(run):
        if not isinstance(
            node,
            ast.If,
        ):
            continue

        condition = (
            ast.get_source_segment(
                SOURCE,
                node.test,
            )
            or ""
        )

        if (
            "fast_first.eligible"
            not in condition
        ):
            continue

        assert not (
            node.lineno
            <= call.lineno
            <= node.end_lineno
        )


def test_engine_still_uses_self_workspace():
    call = _engine_call()

    workspace = next(
        keyword.value
        for keyword
        in call.keywords
        if keyword.arg
        == "workspace"
    )

    assert isinstance(
        workspace,
        ast.Attribute,
    )

    assert isinstance(
        workspace.value,
        ast.Name,
    )

    assert (
        workspace.value.id
        == "self"
    )

    assert (
        workspace.attr
        == "workspace"
    )


def test_handled_gate_still_exists():
    assert (
        "if _zero_llm_result.handled:"
        in SOURCE
    )


def test_normal_understanding_path_still_exists():
    assert (
        "understand_task("
        in SOURCE
    )


def test_normal_planner_path_still_exists():
    assert (
        "plan_task("
        in SOURCE
    )
