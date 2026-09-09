from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import ClientSession
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client


def _plain(value: Any):
    """
    Convert Pydantic/dataclass/MCP objects into JSON-safe Python
    objects without stringifying input schemas.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(value, dict):
        return {
            str(k): _plain(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _plain(v)
            for v in value
        ]

    model_dump = getattr(
        value,
        "model_dump",
        None,
    )

    if callable(model_dump):
        return _plain(
            model_dump()
        )

    as_dict = getattr(
        value,
        "dict",
        None,
    )

    if callable(as_dict):
        try:
            return _plain(
                as_dict()
            )
        except Exception:
            pass

    if hasattr(
        value,
        "__dict__",
    ):
        return _plain(
            vars(value)
        )

    return str(value)


async def _list(
    command,
    args,
):
    server = StdioServerParameters(
        command=command,
        args=args,
    )

    async with stdio_client(
        server
    ) as (
        read,
        write,
    ):
        async with ClientSession(
            read,
            write,
        ) as session:
            await session.initialize()

            response = (
                await session.list_tools()
            )

            result = []

            for tool in response.tools:
                schema = getattr(
                    tool,
                    "inputSchema",
                    None,
                )

                if schema is None:
                    schema = getattr(
                        tool,
                        "input_schema",
                        None,
                    )

                schema = _plain(
                    schema
                )

                if not isinstance(
                    schema,
                    dict,
                ):
                    schema = {
                        "type": "object",
                        "properties": {},
                    }

                schema.setdefault(
                    "type",
                    "object",
                )

                result.append(
                    {
                        "name": str(
                            tool.name
                        ),
                        "description": str(
                            getattr(
                                tool,
                                "description",
                                "",
                            )
                            or ""
                        ),
                        "inputSchema": schema,
                    }
                )

            return result


async def _call(
    command,
    args,
    tool_name,
    arguments,
):
    server = StdioServerParameters(
        command=command,
        args=args,
    )

    async with stdio_client(
        server
    ) as (
        read,
        write,
    ):
        async with ClientSession(
            read,
            write,
        ) as session:
            await session.initialize()

            response = (
                await session.call_tool(
                    tool_name,
                    arguments,
                )
            )

            output = []

            for item in response.content:
                text = getattr(
                    item,
                    "text",
                    None,
                )

                if text is not None:
                    output.append(
                        text
                    )
                else:
                    output.append(
                        json.dumps(
                            _plain(item),
                            ensure_ascii=False,
                            default=str,
                        )
                    )

            return "\n".join(
                output
            )


def _run(coro):
    """
    CLI normally has no active asyncio loop. This wrapper also
    gives a clear failure if invoked from an unsupported nested loop.
    """

    try:
        asyncio.get_running_loop()

    except RuntimeError:
        return asyncio.run(
            coro
        )

    raise RuntimeError(
        "MCP_NESTED_EVENT_LOOP_UNSUPPORTED"
    )


def mcp_list(
    command,
    args=None,
):
    try:
        result = _run(
            _list(
                command,
                args or [],
            )
        )

        return json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return (
            "MCP_LIST_ERROR="
            f"{type(e).__name__}: {e}"
        )


def mcp_call(
    command,
    args,
    tool_name,
    arguments=None,
):
    try:
        return _run(
            _call(
                command,
                args or [],
                tool_name,
                arguments or {},
            )
        )

    except Exception as e:
        return (
            "MCP_CALL_ERROR="
            f"{type(e).__name__}: {e}"
        )
