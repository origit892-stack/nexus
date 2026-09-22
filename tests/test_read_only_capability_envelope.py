import pytest

from nexus.agent import Agent
from nexus.runtime.capability_envelope import (
    evaluate_capability,
)


def test_read_only_policy_is_fail_closed():
    allowed = {
        "list_files",
        "read_file",
        "search_files",
        "memory_search",
    }

    candidates = allowed | {
        "write_file",
        "shell",
        "process_start",
        "delegate_task",
        "delegate_batch",
        "browser_open",
        "computer_type",
        "memory_add",
        "mcp_roblox_write",
        "future_unknown_tool",
    }

    actual = {
        name
        for name in candidates
        if evaluate_capability(
            policy="READ_ONLY",
            tool_name=name,
        ).allow
    }

    assert actual == allowed


def test_agent_central_guard():
    agent = object.__new__(Agent)
    agent.capability_policy = "READ_ONLY"

    agent._enforce_capability_tool(
        "read_file"
    )

    for name in (
        "write_file",
        "delegate_task",
        "browser_open",
        "mcp_roblox_write",
        "future_unknown_tool",
    ):
        with pytest.raises(PermissionError):
            agent._enforce_capability_tool(
                name
            )


def test_normal_policy_preserved():
    agent = object.__new__(Agent)
    agent.capability_policy = "NORMAL"

    for name in (
        "write_file",
        "delegate_task",
        "browser_open",
    ):
        agent._enforce_capability_tool(
            name
        )
