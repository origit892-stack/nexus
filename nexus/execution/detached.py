from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path


def start_detached(
    workspace,
    objective,
):
    root = (
        Path(workspace)
        / ".nexus"
        / "detached"
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_id = (
        time.strftime(
            "%Y%m%d_%H%M%S"
        )
        + "_"
        + uuid.uuid4().hex[:8]
    )

    log = root / f"{run_id}.log"
    meta = root / f"{run_id}.json"

    out = log.open("w")

    proc = subprocess.Popen(
        [
            "nexus",
            "auto",
            "--workspace",
            str(workspace),
            objective,
        ],
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    meta.write_text(
        json.dumps(
            {
                "id": run_id,
                "pid": proc.pid,
                "objective": objective,
                "log": str(log),
                "started": time.time(),
            },
            indent=2,
        )
    )

    return {
        "id": run_id,
        "pid": proc.pid,
        "log": str(log),
    }
