from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from rapidfuzz import fuzz


class MemoryStore:
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
            / "memory.sqlite3"
        )

        self.db = sqlite3.connect(
            self.path,
            check_same_thread=False,
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS memories(
                id TEXT PRIMARY KEY,
                created REAL,
                kind TEXT,
                content TEXT,
                metadata TEXT
            )
            """
        )

        self.db.commit()

    def add(
        self,
        content,
        kind="general",
        metadata=None,
    ):
        mid = uuid.uuid4().hex[:12]

        self.db.execute(
            """
            INSERT INTO memories
            VALUES(?,?,?,?,?)
            """,
            (
                mid,
                time.time(),
                kind,
                content,
                json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                ),
            ),
        )

        self.db.commit()

        return mid

    def search(
        self,
        query,
        limit=10,
    ):
        rows = self.db.execute(
            """
            SELECT
                id,
                kind,
                content,
                metadata
            FROM memories
            ORDER BY created DESC
            LIMIT 500
            """
        ).fetchall()

        scored = []

        for row in rows:
            score = fuzz.token_set_ratio(
                query,
                row[2],
            )

            scored.append(
                (
                    score,
                    row,
                )
            )

        scored.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        return [
            {
                "score": score,
                "id": row[0],
                "kind": row[1],
                "content": row[2],
                "metadata": json.loads(
                    row[3] or "{}"
                ),
            }
            for score, row in scored[:int(limit)]
        ]

    def list(
        self,
        limit=50,
    ):
        rows = self.db.execute(
            """
            SELECT
                id,
                datetime(
                    created,
                    'unixepoch',
                    'localtime'
                ),
                kind,
                content
            FROM memories
            ORDER BY created DESC
            LIMIT ?
            """,
            (
                int(limit),
            ),
        ).fetchall()

        return rows

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass

    def __del__(self):
        self.close()
