from __future__ import annotations

import time
from pathlib import Path

from .store import JobStore
from .runner import JobRunner


class Scheduler:
    def __init__(
        self,
        workspace,
        poll_seconds=1.0,
    ):
        self.workspace = Path(
            workspace
        ).resolve()

        self.poll_seconds = float(
            poll_seconds
        )

    def run_once(
        self,
        job_id=None,
    ):
        store = JobStore(
            self.workspace
        )

        # Deterministic targeted execution.
        if job_id:
            job = store.get_job(
                job_id
            )

            if not job:
                return None

            if job[
                "cancel_requested"
            ]:
                store.set_job_status(
                    job_id,
                    "CANCELLED",
                )

                return job_id

            if job["status"] not in {
                "PENDING",
                "RUNNING",
            }:
                return None

            runner = JobRunner(
                self.workspace
            )

            runner.run_job(
                job_id
            )

            return job_id

        # Normal queue execution.
        jobs = store.list_jobs(
            limit=100
        )

        # list_jobs is newest-first.
        # Reverse so the queue is FIFO.
        for row in reversed(jobs):
            jid = row[0]
            status = row[3]

            if status not in {
                "PENDING",
                "RUNNING",
            }:
                continue

            job = store.get_job(
                jid
            )

            if not job:
                continue

            if job[
                "cancel_requested"
            ]:
                store.set_job_status(
                    jid,
                    "CANCELLED",
                )

                continue

            runner = JobRunner(
                self.workspace
            )

            runner.run_job(
                jid
            )

            return jid

        return None

    def run_forever(self):
        while True:
            self.run_once()

            time.sleep(
                self.poll_seconds
            )
