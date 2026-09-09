from __future__ import annotations

import json
import uuid

from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass
class NexusSession:
    id: str
    title: str
    project_path: str
    objective: str
    status: str
    created_at: str
    updated_at: str
    run_id: str | None = None
    last_result: str | None = None
    history: list[dict] | None = None


class SessionStore:
    def __init__(
        self,
        project_path,
    ):
        self.project_path = Path(
            project_path
        ).expanduser().resolve()

        self.root = (
            self.project_path
            / ".nexus"
            / "sessions"
        )

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _path(
        self,
        session_id,
    ):
        return (
            self.root
            / f"{session_id}.json"
        )

    def create(
        self,
        objective,
        title=None,
    ):
        objective = str(
            objective
        ).strip()

        if not objective:
            raise ValueError(
                "SESSION_OBJECTIVE_EMPTY"
            )

        session_id = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
            + "_"
            + uuid.uuid4().hex[:8]
        )

        clean_title = (
            str(title).strip()
            if title
            else objective[
                :72
            ]
        )

        now = utc_now()

        session = NexusSession(
            id=session_id,
            title=clean_title,
            project_path=str(
                self.project_path
            ),
            objective=objective,
            status="NEW",
            created_at=now,
            updated_at=now,
            history=[
                {
                    "type": "objective",
                    "text": objective,
                    "created_at": now,
                }
            ],
        )

        self.save(
            session
        )

        return session

    def save(
        self,
        session,
    ):
        session.updated_at = (
            utc_now()
        )

        path = self._path(
            session.id
        )

        temp = path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                asdict(session),
                ensure_ascii=False,
                indent=2,
            )
        )

        temp.replace(
            path
        )

    def get(
        self,
        session_id,
    ):
        path = self._path(
            session_id
        )

        if not path.exists():
            return None

        try:
            raw = json.loads(
                path.read_text()
            )

            if not isinstance(raw.get("history"), list):
                raw["history"] = []

                objective = raw.get(
                    "objective"
                )

                if objective:
                    raw["history"].append(
                        {
                            "type": "objective",
                            "text": objective,
                            "created_at": raw.get(
                                "created_at"
                            ),
                        }
                    )

                last_result = raw.get(
                    "last_result"
                )

                if last_result:
                    raw["history"].append(
                        {
                            "type": "result",
                            "text": last_result,
                            "created_at": raw.get(
                                "updated_at"
                            ),
                        }
                    )

            return NexusSession(
                **raw
            )

        except Exception:
            return None

    def list(
        self,
    ):
        result = []

        for path in self.root.glob(
            "*.json"
        ):
            try:
                raw = json.loads(
                    path.read_text()
                )

                if not isinstance(raw.get("history"), list):
                    raw["history"] = []

                    objective = raw.get(
                        "objective"
                    )

                    if objective:
                        raw["history"].append(
                            {
                                "type": "objective",
                                "text": objective,
                                "created_at": raw.get(
                                    "created_at"
                                ),
                            }
                        )

                    last_result = raw.get(
                        "last_result"
                    )

                    if last_result:
                        raw["history"].append(
                            {
                                "type": "result",
                                "text": last_result,
                                "created_at": raw.get(
                                    "updated_at"
                                ),
                            }
                        )

                result.append(
                    NexusSession(
                        **raw
                    )
                )

            except Exception:
                continue

        result.sort(
            key=lambda s: (
                s.updated_at
            ),
            reverse=True,
        )

        return result

    def delete(
        self,
        session_id,
    ):
        path = self._path(
            session_id
        )

        if not path.exists():
            return False

        path.unlink()

        return True
