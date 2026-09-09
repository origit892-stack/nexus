from __future__ import annotations

from nexus.runtime.mcp_manager import (
    list_servers,
)
from nexus.tools.mcp_dynamic import (
    mcp_list,
    mcp_call,
)


def register_mcp_tools(
    registry,
):
    servers = list_servers()

    registered = []

    for server_name, server in servers.items():
        if not server.get(
            "enabled",
            True,
        ):
            continue

        command = server.get(
            "command"
        )

        args = server.get(
            "args",
            [],
        )

        raw = mcp_list(
            command,
            args,
        )

        try:
            import json
            definitions = json.loads(raw)

        except Exception:
            continue

        for tool in definitions:
            remote_name = tool["name"]

            local_name = (
                f"mcp_{server_name}_"
                f"{remote_name}"
            )

            schema = tool.get(
                "inputSchema",
                {
                    "type": "object",
                    "properties": {},
                },
            )

            description = (
                f"MCP {server_name}: "
                f"{tool.get('description') or remote_name}"
            )

            def make_handler(
                command=command,
                args=args,
                remote_name=remote_name,
            ):
                def handler(**kwargs):
                    return mcp_call(
                        command,
                        args,
                        remote_name,
                        kwargs,
                    )

                return handler

            try:
                registry.register(
                    local_name,
                    description,
                    schema,
                    make_handler(),
                    "network",
                    f"mcp:{server_name}",
                )

                registered.append(
                    local_name
                )

            except RuntimeError:
                pass

    return registered
