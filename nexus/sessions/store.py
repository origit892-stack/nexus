from __future__ import annotations

import json
import uuid

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path


SCHEMA_VERSION = 2


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def _normalize_list(value):
    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        str(item)
        for item in value
        if str(item).strip()
    ]


def _normalize_working_state(
    value,
    *,
    objective=None,
):
    value = (
        value
        if isinstance(
            value,
            dict,
        )
        else {}
    )

    checkpoint_serial = value.get(
        "checkpoint_serial",
        0,
    )

    try:
        checkpoint_serial = int(
            checkpoint_serial
        )
    except (
        TypeError,
        ValueError,
    ):
        checkpoint_serial = 0

    return {
        "objective": (
            value.get(
                "objective"
            )
            if value.get(
                "objective"
            )
            is not None
            else objective
        ),
        "current_plan": _normalize_list(
            value.get(
                "current_plan"
            )
        ),
        "completed_work": _normalize_list(
            value.get(
                "completed_work"
            )
        ),
        "pending_work": _normalize_list(
            value.get(
                "pending_work"
            )
        ),
        "blockers": _normalize_list(
            value.get(
                "blockers"
            )
        ),
        "last_checkpoint": value.get(
            "last_checkpoint"
        ),
        "active_item": value.get(
            "active_item"
        ),
        "last_completed_item": value.get(
            "last_completed_item"
        ),
        "checkpoint_serial": max(
            0,
            checkpoint_serial,
        ),
        "auto_checkpoint": bool(
            value.get(
                "auto_checkpoint",
                True,
            )
        ),
        "updated_at": value.get(
            "updated_at"
        ),
    }


def _normalize_context_state(
    value,
):
    value = (
        value
        if isinstance(
            value,
            dict,
        )
        else {}
    )

    compacted = value.get(
        "compacted_through",
        0,
    )

    recent_window = value.get(
        "recent_window",
        12,
    )

    try:
        compacted = int(
            compacted
        )
    except (
        TypeError,
        ValueError,
    ):
        compacted = 0

    try:
        recent_window = int(
            recent_window
        )
    except (
        TypeError,
        ValueError,
    ):
        recent_window = 12

    return {
        "summary": value.get(
            "summary"
        ),
        "durable_facts": _normalize_list(
            value.get(
                "durable_facts"
            )
        ),
        "compacted_through": max(
            0,
            compacted,
        ),
        "recent_window": max(
            1,
            recent_window,
        ),
        "updated_at": value.get(
            "updated_at"
        ),
    }


def _normalize_resume_state(
    value,
):
    value = (
        value
        if isinstance(
            value,
            dict,
        )
        else {}
    )

    return {
        "last_run_id": value.get(
            "last_run_id"
        ),
        "last_status": value.get(
            "last_status"
        ),
        "last_instruction": value.get(
            "last_instruction"
        ),
        "continuation_point": value.get(
            "continuation_point"
        ),
        "interrupted": bool(
            value.get(
                "interrupted",
                False,
            )
        ),
        "resume_requested_at": value.get(
            "resume_requested_at"
        ),
        "updated_at": value.get(
            "updated_at"
        ),
    }


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

    schema_version: int = SCHEMA_VERSION

    working_state: dict = field(
        default_factory=dict
    )

    context_state: dict = field(
        default_factory=dict
    )

    resume_state: dict = field(
        default_factory=dict
    )


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

    def _normalize_raw(
        self,
        raw,
    ):
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "SESSION_JSON_NOT_OBJECT"
            )

        history = raw.get(
            "history"
        )

        if not isinstance(
            history,
            list,
        ):
            history = []

            objective = raw.get(
                "objective"
            )

            if objective:
                history.append(
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
                history.append(
                    {
                        "type": "result",
                        "text": last_result,
                        "created_at": raw.get(
                            "updated_at"
                        ),
                    }
                )

        schema_version = raw.get(
            "schema_version",
            SCHEMA_VERSION,
        )

        try:
            schema_version = int(
                schema_version
            )
        except (
            TypeError,
            ValueError,
        ):
            schema_version = SCHEMA_VERSION

        if schema_version < SCHEMA_VERSION:
            schema_version = SCHEMA_VERSION

        raw = dict(raw)

        raw["history"] = history

        raw["schema_version"] = (
            schema_version
        )

        raw["working_state"] = (
            _normalize_working_state(
                raw.get(
                    "working_state"
                ),
                objective=raw.get(
                    "objective"
                ),
            )
        )

        raw["context_state"] = (
            _normalize_context_state(
                raw.get(
                    "context_state"
                )
            )
        )

        raw["resume_state"] = (
            _normalize_resume_state(
                raw.get(
                    "resume_state"
                )
            )
        )

        return raw

    def _normalize_session(
        self,
        session,
    ):
        session.schema_version = max(
            SCHEMA_VERSION,
            int(
                getattr(
                    session,
                    "schema_version",
                    SCHEMA_VERSION,
                )
                or SCHEMA_VERSION
            ),
        )

        session.working_state = (
            _normalize_working_state(
                getattr(
                    session,
                    "working_state",
                    None,
                ),
                objective=session.objective,
            )
        )

        session.context_state = (
            _normalize_context_state(
                getattr(
                    session,
                    "context_state",
                    None,
                )
            )
        )

        session.resume_state = (
            _normalize_resume_state(
                getattr(
                    session,
                    "resume_state",
                    None,
                )
            )
        )

        if not isinstance(
            session.history,
            list,
        ):
            session.history = []

        return session

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
            else objective[:72]
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
            schema_version=SCHEMA_VERSION,
            working_state=(
                _normalize_working_state(
                    None,
                    objective=objective,
                )
            ),
            context_state=(
                _normalize_context_state(
                    None
                )
            ),
            resume_state=(
                _normalize_resume_state(
                    None
                )
            ),
        )

        self.save(
            session
        )

        return session

    def save(
        self,
        session,
    ):
        session = (
            self._normalize_session(
                session
            )
        )

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
                asdict(
                    session
                ),
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

        raw = json.loads(
            path.read_text()
        )

        raw = self._normalize_raw(
            raw
        )

        return NexusSession(
            **raw
        )

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

                raw = self._normalize_raw(
                    raw
                )

                result.append(
                    NexusSession(
                        **raw
                    )
                )

            except (
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ):
                continue

        result.sort(
            key=lambda session: (
                session.updated_at
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

    def update_working_state(
        self,
        session_id,
        **changes,
    ):
        session = self.get(
            session_id
        )

        if session is None:
            raise KeyError(
                session_id
            )

        state = dict(
            session.working_state
        )

        for key, value in changes.items():
            if key not in state:
                continue

            if key in {
                "current_plan",
                "completed_work",
                "pending_work",
                "blockers",
            }:
                state[key] = (
                    _normalize_list(
                        value
                    )
                )
            else:
                state[key] = value

        state["updated_at"] = (
            utc_now()
        )

        session.working_state = state

        self.save(
            session
        )

        return session

    def set_objective(
        self,
        session_id,
        objective,
    ):
        objective = str(
            objective
        ).strip()

        session = self.get(
            session_id
        )

        if session is None:
            raise KeyError(
                session_id
            )

        session.objective = objective

        session.working_state[
            "objective"
        ] = objective

        session.working_state[
            "updated_at"
        ] = utc_now()

        self.save(
            session
        )

        return session

    def replace_plan(
        self,
        session_id,
        items,
    ):
        return self.update_working_state(
            session_id,
            current_plan=items,
        )

    def append_completed(
        self,
        session_id,
        text,
    ):
        session = self.get(
            session_id
        )

        if session is None:
            raise KeyError(
                session_id
            )

        text = str(
            text
        ).strip()

        items = list(
            session.working_state[
                "completed_work"
            ]
        )

        if text and text not in items:
            items.append(
                text
            )

        return self.update_working_state(
            session_id,
            completed_work=items,
        )

    def replace_pending(
        self,
        session_id,
        items,
    ):
        return self.update_working_state(
            session_id,
            pending_work=items,
        )

    def add_blocker(
        self,
        session_id,
        text,
    ):
        session = self.get(
            session_id
        )

        if session is None:
            raise KeyError(
                session_id
            )

        text = str(
            text
        ).strip()

        items = list(
            session.working_state[
                "blockers"
            ]
        )

        if text and text not in items:
            items.append(
                text
            )

        return self.update_working_state(
            session_id,
            blockers=items,
        )

    def clear_blocker(
        self,
        session_id,
        text,
    ):
        session = self.get(
            session_id
        )

        if session is None:
            raise KeyError(
                session_id
            )

        text = str(
            text
        ).strip()

        items = [
            item
            for item in session.working_state[
                "blockers"
            ]
            if item != text
        ]

        return self.update_working_state(
            session_id,
            blockers=items,
        )

    def set_checkpoint(
        self,
        session_id,
        text,
    ):
        return self.update_working_state(
            session_id,
            last_checkpoint=(
                str(text).strip()
            ),
        )

    def add_durable_fact(
        self,
        session_id,
        text,
    ):
        session = self.get(
            session_id
        )

        if session is None:
            raise KeyError(
                session_id
            )

        text = str(
            text
        ).strip()

        facts = list(
            session.context_state[
                "durable_facts"
            ]
        )

        if text and text not in facts:
            facts.append(
                text
            )

        session.context_state[
            "durable_facts"
        ] = facts

        session.context_state[
            "updated_at"
        ] = utc_now()

        self.save(
            session
        )

        return session


def _store_get_required(
    store,
    session_id,
):
    session = store.get(
        session_id
    )

    if session is None:
        raise KeyError(
            session_id
        )

    return session


def _clean_text(
    value,
):
    return str(
        value
    ).strip()


def _session_store_set_active_item(
    self,
    session_id,
    text,
):
    session = _store_get_required(
        self,
        session_id,
    )

    value = (
        None
        if text is None
        else _clean_text(
            text
        )
    )

    if value == "":
        value = None

    session.working_state[
        "active_item"
    ] = value

    session.working_state[
        "updated_at"
    ] = utc_now()

    self.save(
        session
    )

    return session


def _session_store_mark_done(
    self,
    session_id,
    text,
):
    text = _clean_text(
        text
    )

    if not text:
        raise ValueError(
            "SESSION_DONE_EMPTY"
        )

    session = _store_get_required(
        self,
        session_id,
    )

    completed = list(
        session.working_state[
            "completed_work"
        ]
    )

    if text not in completed:
        completed.append(
            text
        )

    pending = [
        item
        for item in session.working_state[
            "pending_work"
        ]
        if item != text
    ]

    session.working_state[
        "completed_work"
    ] = completed

    session.working_state[
        "pending_work"
    ] = pending

    if (
        session.working_state.get(
            "active_item"
        )
        == text
    ):
        session.working_state[
            "active_item"
        ] = None

    session.working_state[
        "last_completed_item"
    ] = text

    session.working_state[
        "updated_at"
    ] = utc_now()

    self.save(
        session
    )

    return session


def _session_store_select_next_pending(
    self,
    session_id,
):
    session = _store_get_required(
        self,
        session_id,
    )

    completed = set(
        session.working_state[
            "completed_work"
        ]
    )

    selected = None

    for item in session.working_state[
        "pending_work"
    ]:
        if item not in completed:
            selected = item
            break

    session.working_state[
        "active_item"
    ] = selected

    session.working_state[
        "updated_at"
    ] = utc_now()

    self.save(
        session
    )

    return selected


def _session_store_increment_checkpoint(
    self,
    session_id,
    text=None,
):
    session = _store_get_required(
        self,
        session_id,
    )

    serial = session.working_state.get(
        "checkpoint_serial",
        0,
    )

    try:
        serial = int(
            serial
        )
    except (
        TypeError,
        ValueError,
    ):
        serial = 0

    serial += 1

    session.working_state[
        "checkpoint_serial"
    ] = serial

    if text is not None:
        clean = _clean_text(
            text
        )

        session.working_state[
            "last_checkpoint"
        ] = (
            clean
            if clean
            else None
        )

    session.working_state[
        "updated_at"
    ] = utc_now()

    self.save(
        session
    )

    return session


def _session_store_set_auto_checkpoint(
    self,
    session_id,
    enabled,
):
    session = _store_get_required(
        self,
        session_id,
    )

    session.working_state[
        "auto_checkpoint"
    ] = bool(
        enabled
    )

    session.working_state[
        "updated_at"
    ] = utc_now()

    self.save(
        session
    )

    return session


SessionStore.set_active_item = (
    _session_store_set_active_item
)

SessionStore.mark_done = (
    _session_store_mark_done
)

SessionStore.select_next_pending = (
    _session_store_select_next_pending
)

SessionStore.increment_checkpoint = (
    _session_store_increment_checkpoint
)

SessionStore.set_auto_checkpoint = (
    _session_store_set_auto_checkpoint
)
