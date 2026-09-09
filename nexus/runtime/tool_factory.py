from __future__ import annotations

from nexus.runtime.registry import (
    ToolRegistry,
)
from nexus.runtime.permissions import (
    PermissionEngine,
)
from nexus.tools import Tools
from nexus.tools.universal import (
    UniversalTools,
    universal_schemas,
)
from nexus.memory import MemoryStore
from nexus.browser import run_browser
from nexus.plugins import register_plugins
from nexus.runtime.mcp_registry import register_mcp_tools


def _schema_map(
    schemas,
):
    return {
        x["function"]["name"]: x[
            "function"
        ]
        for x in schemas
    }


def build_registry(
    workspace,
    role,
    run_id,
    workspace_config=None,
    task_grants=None,
    include_mcp=False,
):
    registry = ToolRegistry()

    permissions = PermissionEngine(
        role,
        workspace_config,
        task_grants=task_grants,
    )

    core = Tools(
        workspace,
        role,
        run_id,
    )

    universal = UniversalTools(
        workspace,
        role,
    )

    # -----------------------------------------
    # Core tools
    # -----------------------------------------

    for spec in core.schemas():
        fn = spec["function"]

        name = fn["name"]

        handler = getattr(
            core,
            name,
        )

        permission = (
            "write"
            if name in {
                "write_file",
                "replace_text",
            }
            else "read"
        )

        registry.register(
            name,
            fn["description"],
            fn["parameters"],
            handler,
            permission,
            "core",
        )

    # -----------------------------------------
    # Universal tools
    # -----------------------------------------

    permission_map = {
        "web_search": "network",
        "web_fetch": "network",
        "browser_open": "network",
        "screenshot": "computer",
        "computer_type": "computer",
        "computer_key": "computer",
        "process_start": "process",
        "process_status": "read",
        "process_stop": "process",
        "ssh_run": "remote",
        "cli_which": "read",
        "cli_version": "read",
    }

    for spec in universal_schemas():
        fn = spec["function"]
        name = fn["name"]

        handler = getattr(
            universal,
            name,
        )

        registry.register(
            name,
            fn["description"],
            fn["parameters"],
            handler,
            permission_map.get(
                name,
                "read",
            ),
            "universal",
        )

    # -----------------------------------------
    # Memory tools
    # -----------------------------------------

    memory = MemoryStore(
        workspace
    )

    registry.register(
        "memory_add",
        "Store durable workspace memory.",
        {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string"
                },
                "kind": {
                    "type": "string"
                },
            },
            "required": [
                "content"
            ],
        },
        memory.add,
        "write",
        "memory",
    )

    registry.register(
        "memory_search",
        "Search durable workspace memory.",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string"
                },
                "limit": {
                    "type": "integer"
                },
            },
            "required": [
                "query"
            ],
        },
        memory.search,
        "read",
        "memory",
    )

    # -----------------------------------------
    # Playwright browser
    # -----------------------------------------

    registry.register(
        "browser_run",
        (
            "Use headless Chromium to load a page, "
            "read text/title, click, fill or screenshot."
        ),
        {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string"
                },
                "action": {
                    "type": "string",
                    "enum": [
                        "text",
                        "title",
                        "click",
                        "fill",
                        "screenshot",
                    ],
                },
                "selector": {
                    "type": "string"
                },
                "text": {
                    "type": "string"
                },
                "screenshot": {
                    "type": "string"
                },
            },
            "required": [
                "url"
            ],
        },
        run_browser,
        "network",
        "browser",
    )

    context = {
        "workspace": workspace,
        "role": role,
        "run_id": run_id,
    }

    register_plugins(
        registry,
        context,
    )

    if include_mcp:
        register_mcp_tools(
            registry,
        )

    return (
        registry,
        permissions,
    )
