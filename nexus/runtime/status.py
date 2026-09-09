from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class NexusStatus:
    workspace: str
    current_objective: str | None
    active_agent: str | None
    current_step: str | None
    last_tool: str | None
    progress: str | None
    blockers: list[str]
    retries: int
    run_id: str | None
    run_status: str | None
    evidence_count: int
    jobs_running: int
    jobs_pending: int
    jobs_failed: int
    resumable_runs: int

    def as_dict(self):
        return asdict(
            self
        )


def _safe_json(
    value,
):
    if value is None:
        return {}

    if isinstance(
        value,
        dict,
    ):
        return value

    try:
        return json.loads(
            value
        )

    except Exception:
        return {}


def _find_db(
    workspace,
):
    root = Path(
        workspace
    ).resolve()

    candidates = [
        root / ".nexus" / "runs.db",
        root / ".nexus" / "jobs.db",
        Path.home() / ".nexus" / "runs.db",
        Path.home() / ".nexus" / "jobs.db",
    ]

    return [
        p
        for p in candidates
        if p.exists()
    ]


def _read_latest_run(
    workspace,
):
    root = Path(
        workspace
    ).resolve()

    run_state = (
        root
        / ".nexus"
        / "run_state"
    )

    if not run_state.exists():
        return {}

    files = sorted(
        run_state.glob(
            "*.json"
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for p in files:
        try:
            return json.loads(
                p.read_text()
            )

        except Exception:
            continue

    return {}


def _count_jobs(
    dbs,
):
    running = 0
    pending = 0
    failed = 0

    for db in dbs:
        try:
            conn = sqlite3.connect(
                str(db)
            )

            try:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "select name from sqlite_master "
                        "where type='table'"
                    )
                }

                for table in (
                    "jobs",
                    "job_runs",
                    "runs",
                ):
                    if table not in tables:
                        continue

                    try:
                        rows = conn.execute(
                            f"select status, count(*) "
                            f"from {table} "
                            f"group by status"
                        ).fetchall()

                    except Exception:
                        continue

                    for status, count in rows:
                        value = str(
                            status or ""
                        ).upper()

                        if value in {
                            "RUNNING",
                            "ACTIVE",
                        }:
                            running += int(
                                count
                            )

                        elif value in {
                            "PENDING",
                            "QUEUED",
                        }:
                            pending += int(
                                count
                            )

                        elif value in {
                            "FAILED",
                            "ERROR",
                        }:
                            failed += int(
                                count
                            )

            finally:
                conn.close()

        except Exception:
            continue

    return (
        running,
        pending,
        failed,
    )


def collect_status(
    workspace,
):
    state = _read_latest_run(
        workspace
    )

    results = state.get(
        "results",
        {}
    )

    plan = state.get(
        "plan",
        {}
    )

    tasks = plan.get(
        "tasks",
        [],
    )

    completed = 0
    active_agent = None
    current_step = None
    last_tool = None
    blockers = []
    evidence_count = 0
    retries = 0

    for task in tasks:
        tid = task.get(
            "id"
        )

        result = results.get(
            tid,
            {}
        )

        status = str(
            result.get(
                "status",
                ""
            )
        ).upper()

        if status == "PASS":
            completed += 1

        elif status in {
            "RUNNING",
            "ACTIVE",
        }:
            active_agent = task.get(
                "role"
            )

            current_step = task.get(
                "objective"
            )

        elif status in {
            "BLOCKED",
            "FAIL",
            "FAILED",
        }:
            blockers.append(
                f"{tid}:{status}"
            )

        evidence = result.get(
            "evidence",
            []
        )

        if isinstance(
            evidence,
            list,
        ):
            evidence_count += len(
                evidence
            )

        retries += int(
            result.get(
                "retries",
                0
            )
            or 0
        )

    event_log = state.get(
        "events",
        []
    )

    if isinstance(
        event_log,
        list,
    ):
        for event in reversed(
            event_log
        ):
            if (
                isinstance(
                    event,
                    dict,
                )
                and event.get(
                    "type"
                ) == "tool"
            ):
                payload = event.get(
                    "payload",
                    {}
                )

                last_tool = payload.get(
                    "name"
                )

                if last_tool:
                    break

    total = len(
        tasks
    )

    progress = (
        f"{completed}/{total} tasks"
        if total
        else None
    )

    dbs = _find_db(
        workspace
    )

    (
        jobs_running,
        jobs_pending,
        jobs_failed,
    ) = _count_jobs(
        dbs
    )

    resumable = 0

    if state:
        if str(
            state.get(
                "status",
                ""
            )
        ).upper() not in {
            "PASS",
            "FAILED",
            "FAIL",
        }:
            resumable = 1

    return NexusStatus(
        workspace=str(
            Path(
                workspace
            ).resolve()
        ),
        current_objective=state.get(
            "objective"
        ),
        active_agent=active_agent,
        current_step=current_step,
        last_tool=last_tool,
        progress=progress,
        blockers=blockers,
        retries=retries,
        run_id=state.get(
            "run_id"
        )
        or state.get(
            "id"
        ),
        run_status=state.get(
            "status"
        ),
        evidence_count=evidence_count,
        jobs_running=jobs_running,
        jobs_pending=jobs_pending,
        jobs_failed=jobs_failed,
        resumable_runs=resumable,
    )
