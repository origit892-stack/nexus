from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from .store import JobStore


class JobRunner:
    def __init__(
        self,
        workspace,
        poll_interval=0.2,
    ):
        self.workspace = Path(
            workspace
        ).resolve()

        self.store = JobStore(
            self.workspace
        )

        self.poll_interval = float(
            poll_interval
        )

    def _dependency_passed(
        self,
        step,
        steps_by_id,
    ):
        for dep in step["dependencies"]:
            node = steps_by_id.get(dep)

            if not node:
                continue

            if node["status"] != "PASS":
                return False

        return True

    def run_job(
        self,
        jid,
    ):
        job = self.store.get_job(
            jid
        )

        if not job:
            raise RuntimeError(
                f"JOB_NOT_FOUND={jid}"
            )

        self.store.reset_interrupted(
            jid
        )

        job = self.store.get_job(
            jid
        )

        if job["cancel_requested"]:
            self.store.set_job_status(
                jid,
                "CANCELLED",
            )

            return "CANCELLED"

        self.store.increment_job_attempt(
            jid
        )

        self.store.set_job_status(
            jid,
            "RUNNING",
        )

        while True:
            job = self.store.get_job(
                jid
            )

            if job["cancel_requested"]:
                self.store.set_job_status(
                    jid,
                    "CANCELLED",
                )

                return "CANCELLED"

            steps = self.store.get_steps(
                jid
            )

            if all(
                s["status"] == "PASS"
                for s in steps
            ):
                self.store.set_job_status(
                    jid,
                    "PASS",
                )

                return "PASS"

            failed = [
                s
                for s in steps
                if s["status"] == "FAIL"
            ]

            if failed:
                self.store.set_job_status(
                    jid,
                    "FAIL",
                    failed[0]["stderr"],
                )

                return "FAIL"

            by_id = {
                s["id"]: s
                for s in steps
            }

            ready = [
                s
                for s in steps
                if (
                    s["status"]
                    == "PENDING"
                    and self._dependency_passed(
                        s,
                        by_id,
                    )
                )
            ]

            if not ready:
                time.sleep(
                    self.poll_interval
                )

                continue

            step = ready[0]

            self.store.set_step_running(
                step["id"]
            )

            job = self.store.get_job(
                jid
            )

            timeout = int(
                job[
                    "timeout_seconds"
                ]
            )

            attempts_allowed = int(
                job["max_retries"]
            ) + 1

            last_stdout = ""
            last_stderr = ""
            last_code = None

            success = False

            for _ in range(
                attempts_allowed
            ):
                try:
                    proc = subprocess.Popen(
                        step["command"],
                        shell=True,
                        cwd=str(
                            self.workspace
                        ),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        executable="/bin/bash",
                        start_new_session=True,
                    )

                    try:
                        stdout, stderr = (
                            proc.communicate(
                                timeout=timeout
                            )
                        )

                    except subprocess.TimeoutExpired:
                        os.killpg(
                            proc.pid,
                            signal.SIGTERM,
                        )

                        stdout, stderr = (
                            proc.communicate()
                        )

                        stderr += (
                            "\nNEXUS_STEP_TIMEOUT"
                        )

                        last_code = 124

                    else:
                        last_code = (
                            proc.returncode
                        )

                    last_stdout = stdout
                    last_stderr = stderr

                    if last_code == 0:
                        success = True
                        break

                except Exception as e:
                    last_code = 1

                    last_stderr = (
                        f"{type(e).__name__}: "
                        f"{e}"
                    )

                time.sleep(0.5)

            self.store.finish_step(
                step["id"],
                (
                    "PASS"
                    if success
                    else "FAIL"
                ),
                last_code,
                last_stdout,
                last_stderr,
            )

    def close(self):
        self.store.close()
