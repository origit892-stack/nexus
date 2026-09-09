from __future__ import annotations

import json
from pathlib import Path

import yaml

from nexus.tools.mcp_dynamic import (
    mcp_list,
    mcp_call,
)


GLOBAL_CONFIG = (
    Path.home()
    / ".nexus"
    / "mcp.yaml"
)


def load_config():
    if not GLOBAL_CONFIG.exists():
        return {
            "servers": {}
        }

    with GLOBAL_CONFIG.open(
        "r",
        encoding="utf-8",
    ) as f:
        return (
            yaml.safe_load(f)
            or {
                "servers": {}
            }
        )


def save_config(cfg):
    GLOBAL_CONFIG.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with GLOBAL_CONFIG.open(
        "w",
        encoding="utf-8",
    ) as f:
        yaml.safe_dump(
            cfg,
            f,
            sort_keys=False,
        )


def add_server(
    name,
    command,
    args=None,
):
    cfg = load_config()

    cfg.setdefault(
        "servers",
        {},
    )[name] = {
        "command": command,
        "args": args or [],
        "enabled": True,
    }

    save_config(cfg)

    return cfg[
        "servers"
    ][name]


def remove_server(
    name,
):
    cfg = load_config()

    cfg.setdefault(
        "servers",
        {},
    ).pop(
        name,
        None,
    )

    save_config(cfg)


def list_servers():
    return load_config().get(
        "servers",
        {},
    )


def test_server(
    name,
):
    servers = list_servers()

    if name not in servers:
        return (
            f"MCP_SERVER_NOT_FOUND={name}"
        )

    server = servers[name]

    return mcp_list(
        server["command"],
        server.get(
            "args",
            [],
        ),
    )
