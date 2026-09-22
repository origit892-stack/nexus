from __future__ import annotations

import json
import os
import threading
import time
import uuid

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionEvent:
    event: str
    run_id: str
    ts: float
    payload: dict[str, Any]


class ExecutionEventBus:
    def __init__(
        self,
        path: str | Path | None = None,
        run_id: str | None = None,
    ):
        self.run_id = (
            run_id
            or uuid.uuid4().hex
        )

        self.path = (
            Path(path).expanduser()
            if path
            else None
        )

        self._lock = threading.Lock()

    def emit(
        self,
        event: str,
        **payload,
    ) -> ExecutionEvent:
        record = ExecutionEvent(
            event=event,
            run_id=self.run_id,
            ts=time.time(),
            payload=payload,
        )

        if self.path is not None:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            line = json.dumps(
                asdict(record),
                ensure_ascii=False,
                sort_keys=True,
            )

            with self._lock:
                with self.path.open(
                    "a",
                    encoding="utf-8",
                ) as handle:
                    handle.write(
                        line + "\n"
                    )
                    handle.flush()
                    os.fsync(
                        handle.fileno()
                    )

        return record


def default_event_bus(
    project_root: str | Path | None = None,
):
    root = (
        Path(project_root)
        if project_root
        else Path.cwd()
    )

    return ExecutionEventBus(
        root
        / ".nexus"
        / "execution_events.jsonl"
    )
