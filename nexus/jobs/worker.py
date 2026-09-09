from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .scheduler import Scheduler


def worker_state_path(
    workspace,
):
    return (
        Path(workspace)
        / ".nexus"
        / "worker_state.json"
    )


def write_state(
    workspace,
    state,
):
    path = worker_state_path(
        workspace
    )

    payload = {
        "pid": os.getpid(),
        "updated": time.time(),
        **state,
    }

    tmp = path.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
        )
    )

    tmp.replace(path)


def run_worker(
    workspace,
    once=False,
    job_id=None,
):
    scheduler = Scheduler(
        workspace
    )

    write_state(
        workspace,
        {
            "status": "RUNNING",
            "target_job": job_id,
        },
    )

    if once:
        jid = scheduler.run_once(
            job_id=job_id
        )

        write_state(
            workspace,
            {
                "status": "IDLE",
                "last_job": jid,
                "target_job": job_id,
            },
        )

        return jid

    while True:
        jid = scheduler.run_once()

        write_state(
            workspace,
            {
                "status": "RUNNING",
                "last_job": jid,
            },
        )

        time.sleep(1)
