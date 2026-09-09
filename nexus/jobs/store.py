from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path


class JobStore:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace / ".nexus"
        self.root.mkdir(parents=True, exist_ok=True)

        self.path = self.root / "jobs.sqlite3"

        self.db = sqlite3.connect(
            self.path,
            timeout=30,
            check_same_thread=False,
        )

        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY,
                created REAL,
                updated REAL,
                name TEXT,
                status TEXT,
                max_retries INTEGER,
                attempt INTEGER,
                timeout_seconds INTEGER,
                cancel_requested INTEGER,
                error TEXT,
                metadata TEXT
            )
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS steps(
                id TEXT PRIMARY KEY,
                job_id TEXT,
                step_index INTEGER,
                name TEXT,
                command TEXT,
                dependencies TEXT,
                status TEXT,
                attempt INTEGER,
                started REAL,
                finished REAL,
                exit_code INTEGER,
                stdout TEXT,
                stderr TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_steps_job
            ON steps(job_id, step_index)
            """
        )

        self.db.commit()

    def create_job(
        self,
        name,
        steps,
        max_retries=2,
        timeout_seconds=900,
        metadata=None,
    ):
        jid = (
            time.strftime("%Y%m%d_%H%M%S")
            + "_"
            + uuid.uuid4().hex[:8]
        )

        now = time.time()

        self.db.execute(
            """
            INSERT INTO jobs
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                jid,
                now,
                now,
                name,
                "PENDING",
                int(max_retries),
                0,
                int(timeout_seconds),
                0,
                "",
                json.dumps(metadata or {}),
            ),
        )

        previous_id = None

        for index, raw in enumerate(steps):
            sid = (
                jid
                + "_"
                + str(index).zfill(3)
            )

            deps = raw.get("dependencies")

            if deps is None:
                deps = (
                    [previous_id]
                    if previous_id
                    else []
                )

            self.db.execute(
                """
                INSERT INTO steps
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    jid,
                    index,
                    raw.get(
                        "name",
                        f"step-{index}"
                    ),
                    raw["command"],
                    json.dumps(deps),
                    "PENDING",
                    0,
                    None,
                    None,
                    None,
                    "",
                    "",
                ),
            )

            previous_id = sid

        self.db.commit()

        return jid

    def get_job(self, jid):
        row = self.db.execute(
            """
            SELECT
                id,
                created,
                updated,
                name,
                status,
                max_retries,
                attempt,
                timeout_seconds,
                cancel_requested,
                error,
                metadata
            FROM jobs
            WHERE id=?
            """,
            (jid,),
        ).fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "created": row[1],
            "updated": row[2],
            "name": row[3],
            "status": row[4],
            "max_retries": row[5],
            "attempt": row[6],
            "timeout_seconds": row[7],
            "cancel_requested": bool(row[8]),
            "error": row[9],
            "metadata": json.loads(
                row[10] or "{}"
            ),
        }

    def get_steps(self, jid):
        rows = self.db.execute(
            """
            SELECT
                id,
                step_index,
                name,
                command,
                dependencies,
                status,
                attempt,
                started,
                finished,
                exit_code,
                stdout,
                stderr
            FROM steps
            WHERE job_id=?
            ORDER BY step_index
            """,
            (jid,),
        ).fetchall()

        return [
            {
                "id": r[0],
                "index": r[1],
                "name": r[2],
                "command": r[3],
                "dependencies": json.loads(
                    r[4] or "[]"
                ),
                "status": r[5],
                "attempt": r[6],
                "started": r[7],
                "finished": r[8],
                "exit_code": r[9],
                "stdout": r[10],
                "stderr": r[11],
            }
            for r in rows
        ]

    def list_jobs(self, limit=50):
        return self.db.execute(
            """
            SELECT
                id,
                datetime(
                    created,
                    'unixepoch',
                    'localtime'
                ),
                name,
                status,
                attempt,
                error
            FROM jobs
            ORDER BY created DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    def set_job_status(
        self,
        jid,
        status,
        error="",
    ):
        self.db.execute(
            """
            UPDATE jobs
            SET
                status=?,
                error=?,
                updated=?
            WHERE id=?
            """,
            (
                status,
                error,
                time.time(),
                jid,
            ),
        )

        self.db.commit()

    def increment_job_attempt(self, jid):
        self.db.execute(
            """
            UPDATE jobs
            SET
                attempt=attempt+1,
                updated=?
            WHERE id=?
            """,
            (
                time.time(),
                jid,
            ),
        )

        self.db.commit()

    def set_step_running(
        self,
        sid,
    ):
        self.db.execute(
            """
            UPDATE steps
            SET
                status='RUNNING',
                attempt=attempt+1,
                started=?,
                finished=NULL
            WHERE id=?
            """,
            (
                time.time(),
                sid,
            ),
        )

        self.db.commit()

    def finish_step(
        self,
        sid,
        status,
        exit_code,
        stdout,
        stderr,
    ):
        self.db.execute(
            """
            UPDATE steps
            SET
                status=?,
                finished=?,
                exit_code=?,
                stdout=?,
                stderr=?
            WHERE id=?
            """,
            (
                status,
                time.time(),
                exit_code,
                stdout[-50000:],
                stderr[-50000:],
                sid,
            ),
        )

        self.db.commit()

    def reset_interrupted(self, jid):
        self.db.execute(
            """
            UPDATE steps
            SET status='PENDING'
            WHERE
                job_id=?
                AND status='RUNNING'
            """,
            (jid,),
        )

        self.db.execute(
            """
            UPDATE jobs
            SET
                status='PENDING',
                updated=?
            WHERE
                id=?
                AND status='RUNNING'
            """,
            (
                time.time(),
                jid,
            ),
        )

        self.db.commit()

    def request_cancel(self, jid):
        self.db.execute(
            """
            UPDATE jobs
            SET
                cancel_requested=1,
                updated=?
            WHERE id=?
            """,
            (
                time.time(),
                jid,
            ),
        )

        self.db.commit()

    def clear_cancel(self, jid):
        self.db.execute(
            """
            UPDATE jobs
            SET
                cancel_requested=0,
                updated=?
            WHERE id=?
            """,
            (
                time.time(),
                jid,
            ),
        )

        self.db.commit()

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass

    def __del__(self):
        self.close()
