from __future__ import annotations

import json
import threading


SAFE_CACHE_TOOLS = {
    "web_fetch",
    "web_search",
    "browser_run",
    "read_file",
    "list_files",
    "search_files",
    "cli_which",
    "cli_version",
    "acceptance_verify",
}


class ToolCallCache:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def key(
        self,
        name,
        args,
    ):
        return (
            str(name),
            json.dumps(
                args or {},
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ),
        )

    def cacheable(
        self,
        name,
    ):
        return (
            name in SAFE_CACHE_TOOLS
        )

    def get(
        self,
        name,
        args,
    ):
        if not self.cacheable(
            name
        ):
            return None

        key = self.key(
            name,
            args,
        )

        with self.lock:
            return self.data.get(
                key
            )

    def put(
        self,
        name,
        args,
        output,
    ):
        if not self.cacheable(
            name
        ):
            return

        key = self.key(
            name,
            args,
        )

        with self.lock:
            self.data[key] = str(
                output
            )
