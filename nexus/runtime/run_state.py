from __future__ import annotations

import json
import time
from pathlib import Path


class RunState:
    def __init__(self, workspace, run_id):
        self.workspace = Path(workspace).resolve()
        self.run_id = run_id
        self.root = self.workspace / ".nexus" / "run_state"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / f"{run_id}.json"

    def save(self, data):
        payload = {
            "run_id": self.run_id,
            "updated": time.time(),
            **data,
        }

        tmp = self.path.with_suffix(".tmp")

        tmp.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

        tmp.replace(self.path)

    def load(self):
        if not self.path.exists():
            return None

        return json.loads(
            self.path.read_text()
        )

    def exists(self):
        return self.path.exists()
