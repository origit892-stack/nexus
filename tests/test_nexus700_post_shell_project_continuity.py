import ast
from pathlib import Path

import nexus.ui.app as app


def _launch_source():
    source = Path(
        app.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    fn = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "launch_home"
        )
    )

    return (
        ast.get_source_segment(
            source,
            fn,
        )
        or ""
    )


def test_launch_home_does_not_clear_project_hint():
    source = _launch_source()

    assert (
        "initial_project_path = None"
        not in source
    )


def test_selected_project_becomes_next_loop_hint():
    source = _launch_source()

    assert (
        "initial_project_path = str("
        in source
    )

    assert (
        "Path(project_path)"
        in source
    )


def test_project_continuity_is_set_before_shell_launch():
    source = _launch_source()

    selected = source.find(
        "project_path = result.get("
    )

    continuity = source.find(
        "initial_project_path = str(",
        selected,
    )

    shell = source.find(
        "run_agent_shell(",
        continuity,
    )

    assert selected >= 0
    assert continuity > selected
    assert shell > continuity


def test_continuity_does_not_persist_registry():
    source = _launch_source()

    assert "registry.add(" not in source
    assert "registry.use(" not in source
