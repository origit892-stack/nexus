from nexus.runtime.route_policy import (
    evaluate_route_tool,
    fast_lookup_hard_stop,
)


def decision(
    name,
    args=None,
):
    return evaluate_route_tool(
        route_name="FAST_LOOKUP",
        tool_name=name,
        arguments=args or {},
    )


def test_fast_lookup_allowlist():
    for name in (
        "list_files",
        "search_files",
        "read_file",
        "memory_search",
    ):
        assert decision(name).allow


def test_fast_lookup_blocks_shell():
    result = decision(
        "shell",
        {
            "command": "find . -name '*tree*'",
        },
    )

    assert not result.allow


def test_fast_lookup_blocks_package_install():
    result = decision(
        "shell",
        {
            "command": (
                "python3 -m pip install "
                "fast-simplification"
            ),
        },
    )

    assert not result.allow

    assert (
        result.reason
        == "FAST_LOOKUP_PACKAGE_INSTALL_BLOCKED"
    )


def test_fast_lookup_blocks_mutation():
    for name in (
        "write_file",
        "process_start",
        "memory_add",
        "delegate_task",
    ):
        assert not decision(name).allow


def test_fast_lookup_blocks_unknown_tool():
    assert not decision(
        "some_future_mutation_tool"
    ).allow


def test_fast_lookup_hard_stop():
    assert not fast_lookup_hard_stop(
        route_name="FAST_LOOKUP",
        iteration=6,
    )

    assert fast_lookup_hard_stop(
        route_name="FAST_LOOKUP",
        iteration=7,
    )
