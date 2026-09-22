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


def _definition(name):
    matches = []

    for node in ast.walk(
        _run()
    ):
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
                matches.append(
                    node.lineno
                )

    assert len(matches) == 1

    return matches[0]


def _call(name):
    matches = []

    for node in ast.walk(
        _run()
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        called = None

        if isinstance(
            node.func,
            ast.Name,
        ):
            called = node.func.id

        elif isinstance(
            node.func,
            ast.Attribute,
        ):
            called = node.func.attr

        if called == name:
            matches.append(
                node.lineno
            )

    assert matches

    return min(matches)


def test_state_router_understanding_order():
    rid = _definition("rid")

    state = _definition(
        "run_state"
    )

    router = _call(
        "execute_fast_lookup"
    )

    understanding = _call(
        "understand_task"
    )

    planner = _call(
        "plan_task"
    )

    assert rid < state
    assert state < router
    assert router < understanding
    assert understanding < planner


def test_state_hoist_marker():
    assert (
        "NEXUS700_FAST_ROUTER_V2_STATE_HOIST"
        in SOURCE
    )


def test_pre_understanding_marker():
    assert (
        "NEXUS700_FAST_ROUTER_V2_PRE_UNDERSTANDING"
        in SOURCE
    )


def test_router_unique():
    assert (
        SOURCE.count(
            "execute_fast_lookup("
        )
        == 1
    )


def test_rid_unique():
    assert (
        SOURCE.count(
            "rid = self.store.new_run("
        )
        == 1
    )


def test_run_state_unique():
    assert (
        SOURCE.count(
            "run_state = RunState("
        )
        == 1
    )
