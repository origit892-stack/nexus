from __future__ import annotations

import re


ROLE_BASE = {
    "architect": {
        "read_file",
        "list_files",
        "search_files",
        "memory_search",
    },

    "coder": {
        "read_file",
        "list_files",
        "search_files",
        "shell",
        "write_file",
        "replace_text",
        "acceptance_verify",
        "memory_search",
    },

    "qa": {
        "read_file",
        "list_files",
        "search_files",
        "acceptance_verify",
        "memory_search",
    },

    "researcher": {
        "web_search",
        "web_fetch",
    },

    "browser": {
        "web_search",
        "web_fetch",
        "browser_run",
        "browser_open",
    },

    "computer": {
        "screenshot",
        "computer_type",
        "computer_key",
    },

    "devops": {
        "shell",
        "process_start",
        "process_status",
        "process_stop",
        "cli_which",
        "cli_version",
        "ssh_run",
    },

    "security": {
        "read_file",
        "list_files",
        "search_files",
        "web_search",
        "web_fetch",
    },
}


WEB_WORDS = re.compile(
    r"\b("
    r"web|website|url|http|https|online|internet|"
    r"page|homepage|source|research|fetch|search"
    r")\b",
    re.I,
)

BROWSER_WORDS = re.compile(
    r"\b("
    r"click|fill|form|login|navigate|browser|tab|"
    r"button|selector"
    r")\b",
    re.I,
)

FILE_WORDS = re.compile(
    r"\b("
    r"file|code|repository|repo|source|filesystem|"
    r"project|script|module|diff|git"
    r")\b",
    re.I,
)

MCP_WORDS = re.compile(
    r"\b("
    r"mcp|roblox|studio|robridge"
    r")\b",
    re.I,
)


def resolve_capabilities(
    role,
    objective,
    acceptance=None,
    available=None,
):
    role = str(role)
    objective = str(objective or "")

    acceptance_text = "\n".join(
        str(x)
        for x in (acceptance or [])
    )

    text = (
        objective
        + "\n"
        + acceptance_text
    )

    allowed = set(
        ROLE_BASE.get(
            role,
            set(),
        )
    )

    # QA is task-sensitive. A web QA task should verify via web,
    # not wander through the local repository.
    if role == "qa":
        if WEB_WORDS.search(text):
            allowed = {
                "web_search",
                "web_fetch",
                "acceptance_verify",
            }

            if BROWSER_WORDS.search(text):
                allowed.add(
                    "browser_run"
                )

        elif FILE_WORDS.search(text):
            allowed = {
                "read_file",
                "list_files",
                "search_files",
                "acceptance_verify",
            }

    if role == "researcher":
        if BROWSER_WORDS.search(text):
            allowed.add(
                "browser_run"
            )

    # MCP is never granted merely because it exists.
    # The task must explicitly require MCP/Roblox/Studio/RoBridge.
    if MCP_WORDS.search(text):
        if role in {
            "qa",
            "architect",
            "devops",
        }:
            if available:
                for name in available:
                    if name.startswith(
                        "mcp_"
                    ):
                        allowed.add(name)

    if available is not None:
        allowed &= set(
            available
        )

    return allowed


def tool_budget(
    role,
    objective,
):
    role = str(role)

    if role in {
        "researcher",
        "browser",
        "qa",
    }:
        return 8

    if role in {
        "architect",
        "security",
    }:
        return 12

    if role == "coder":
        return 30

    if role in {
        "computer",
        "devops",
    }:
        return 20

    return 12
