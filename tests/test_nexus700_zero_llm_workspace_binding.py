from pathlib import Path
import ast

from nexus.agent import Agent


SOURCE = Path(
    "nexus/agent.py"
).read_text(
    encoding="utf-8"
)

TREE = ast.parse(
    SOURCE
)


def _workspace_argument():
    for node in ast.walk(
        TREE
    ):
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
            != "execute_fast_lookup"
        ):
            continue

        for keyword in node.keywords:
            if (
                keyword.arg
                == "workspace"
            ):
                return keyword.value

    raise AssertionError(
        "execute_fast_lookup "
        "workspace argument missing"
    )


def test_fast_lookup_workspace_is_self_workspace():
    value = _workspace_argument()

    assert isinstance(
        value,
        ast.Attribute,
    )

    assert isinstance(
        value.value,
        ast.Name,
    )

    assert (
        value.value.id
        == "self"
    )

    assert (
        value.attr
        == "workspace"
    )


def test_undefined_workspace_reference_removed():
    assert (
        "workspace=workspace"
        not in SOURCE
    )


def test_workspace_fix_marker_present():
    assert (
        "NEXUS700_ZERO_LLM_WORKSPACE_FIX"
        in SOURCE
    )


def test_agent_constructor_stores_workspace():
    init_source = (
        Path(
            "nexus/agent.py"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        "self.workspace = workspace"
        in init_source
    )
