from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import inspect
import json


@dataclass
class ToolDefinition:
    name: str
    description: str
    schema: dict
    handler: Callable
    permission: str = "read"
    source: str = "core"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        schema: dict,
        handler: Callable,
        permission: str = "read",
        source: str = "core",
    ):
        if name in self._tools:
            raise RuntimeError(
                f"TOOL_ALREADY_REGISTERED={name}"
            )

        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            schema=schema,
            handler=handler,
            permission=permission,
            source=source,
        )

    def register_definition(
        self,
        definition: ToolDefinition,
    ):
        self.register(
            definition.name,
            definition.description,
            definition.schema,
            definition.handler,
            definition.permission,
            definition.source,
        )

    def has(self, name):
        return name in self._tools

    def get(self, name):
        return self._tools.get(name)

    def names(self):
        return sorted(self._tools)

    def definitions(self):
        return [
            self._tools[name]
            for name in self.names()
        ]

    def schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.schema,
                },
            }
            for tool in self.definitions()
        ]

    def execute(
        self,
        name: str,
        args: dict[str, Any],
    ):
        tool = self.get(name)

        if tool is None:
            return f"UNKNOWN_TOOL={name}"

        try:
            return tool.handler(**args)

        except Exception as e:
            return (
                "TOOL_EXCEPTION="
                f"{type(e).__name__}: {e}"
            )

    def subset(self, names):
        child = ToolRegistry()

        wanted = set(names)

        for name in self.names():
            if name not in wanted:
                continue

            definition = self.get(name)

            child.register_definition(
                definition
            )

        return child

    def describe(self):
        return [
            {
                "name": t.name,
                "description": t.description,
                "permission": t.permission,
                "source": t.source,
            }
            for t in self.definitions()
        ]
