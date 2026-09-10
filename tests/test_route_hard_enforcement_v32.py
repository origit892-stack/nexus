from pathlib import Path

from nexus.runtime.route_policy import (
    evaluate_route_tool,
)


def evaluate(name, arguments=None):
    return evaluate_route_tool(
        route_name="FAST_LOOKUP",
        tool_name=name,
        arguments=arguments or {},
    )


def test_only_four_tools_are_allowed():
    allowed = {
        "list_files",
        "search_files",
        "read_file",
        "memory_search",
    }

    candidates = {
        "list_files",
        "search_files",
        "read_file",
        "memory_search",
        "shell",
        "process_start",
        "write_file",
        "delegate_task",
        "memory_add",
        "blender",
        "open3d",
        "future_tool",
    }

    actual = {
        name
        for name in candidates
        if evaluate(name).allow
    }

    assert actual == allowed


def test_shell_cat_is_blocked():
    result = evaluate(
        "shell",
        {
            "command": (
                "cat docs/director/"
                "CURRENT-TASK.md"
            )
        },
    )

    assert not result.allow


def test_shell_find_is_blocked():
    result = evaluate(
        "shell",
        {
            "command": (
                "find . -iname '*tree*'"
            )
        },
    )

    assert not result.allow


def test_package_install_is_blocked():
    result = evaluate(
        "shell",
        {
            "command": (
                "python3 -m pip install foo"
            )
        },
    )

    assert not result.allow


def test_unknown_tool_is_blocked():
    assert not evaluate(
        "some_new_tool"
    ).allow


def test_agent_has_hard_route_gate():
    source = Path(
        "nexus/agent.py"
    ).read_text()

    assert (
        "def _enforce_route_tool("
        in source
    )

    assert (
        "NEXUS ROUTE POLICY BLOCK:"
        in source
    )

    route = source.index(
        "route_block = ("
    )

    speed = source.index(
        "speed_decision = (",
        route,
    )

    assert route < speed
