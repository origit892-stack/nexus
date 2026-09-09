import json
import sqlite3
import time
import uuid
from pathlib import Path


class Store:
    def __init__(
        self,
        workspace,
    ):
        self.root = (
            Path(workspace)
            / ".nexus"
        )

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path = (
            self.root
            / "runs.sqlite3"
        )

        self.db = sqlite3.connect(
            self.path,
            check_same_thread=False,
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS runs(
                id TEXT PRIMARY KEY,
                started REAL,
                finished REAL,
                role TEXT,
                task TEXT,
                status TEXT,
                result TEXT
            )
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                ts REAL,
                kind TEXT,
                payload TEXT
            )
            """
        )

        self.db.commit()

    def new_run(
        self,
        role,
        task,
    ):
        rid = (
            time.strftime(
                "%Y%m%d_%H%M%S"
            )
            + "_"
            + uuid.uuid4().hex[:8]
        )

        self.db.execute(
            """
            INSERT INTO runs
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                rid,
                time.time(),
                None,
                role,
                task,
                "RUNNING",
                "",
            ),
        )

        self.db.commit()

        return rid

    def event(
        self,
        rid,
        kind,
        payload,
    ):
        if not isinstance(
            payload,
            str,
        ):
            payload = json.dumps(
                payload,
                ensure_ascii=False,
                default=str,
            )

        self.db.execute(
            """
            INSERT INTO events(
                run_id,
                ts,
                kind,
                payload
            )
            VALUES(?,?,?,?)
            """,
            (
                rid,
                time.time(),
                kind,
                payload,
            ),
        )

        self.db.commit()

    def finish(
        self,
        rid,
        status,
        result,
    ):
        self.db.execute(
            """
            UPDATE runs
            SET
                finished=?,
                status=?,
                result=?
            WHERE id=?
            """,
            (
                time.time(),
                status,
                result,
                rid,
            ),
        )

        self.db.commit()

    def recent(
        self,
        limit=20,
    ):
        return self.db.execute(
            """
            SELECT
                id,
                role,
                status,
                substr(task,1,90)
            FROM runs
            ORDER BY started DESC
            LIMIT ?
            """,
            (
                int(limit),
            ),
        ).fetchall()



    def get_run(self, run_id):
        row = self.db.execute(
            """
            SELECT
                id,
                started,
                finished,
                role,
                task,
                status,
                result
            FROM runs
            WHERE id=?
            """,
            (run_id,),
        ).fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "started": row[1],
            "finished": row[2],
            "role": row[3],
            "task": row[4],
            "status": row[5],
            "result": row[6],
        }

    def events_for_run(self, run_id):
        return self.db.execute(
            """
            SELECT
                id,
                ts,
                kind,
                payload
            FROM events
            WHERE run_id=?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
