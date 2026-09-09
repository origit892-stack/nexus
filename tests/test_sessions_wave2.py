from __future__ import annotations

import json

from pathlib import Path

import pytest

from nexus.sessions.context import (
    COMPACTION_THRESHOLD,
    RECENT_HISTORY_WINDOW,
    build_agent_context,
)

from nexus.sessions.store import (
    SCHEMA_VERSION,
    SessionStore,
)


def make_store(
    tmp_path,
):
    return SessionStore(
        tmp_path
    )


def create_session(
    tmp_path,
):
    store = make_store(
        tmp_path
    )

    session = store.create(
        "Wave 2 objective",
        "Wave 2",
    )

    return store, session


def test_new_session_schema(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    assert (
        loaded.schema_version
        == SCHEMA_VERSION
    )

    assert (
        loaded.working_state[
            "objective"
        ]
        == "Wave 2 objective"
    )

    assert loaded.context_state[
        "durable_facts"
    ] == []

    assert loaded.resume_state[
        "interrupted"
    ] is False


def test_missing_wave2_fields_migrate(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    path = store._path(
        session.id
    )

    raw = json.loads(
        path.read_text()
    )

    for key in (
        "schema_version",
        "working_state",
        "context_state",
        "resume_state",
    ):
        raw.pop(
            key,
            None,
        )

    path.write_text(
        json.dumps(
            raw
        )
    )

    loaded = store.get(
        session.id
    )

    assert loaded.working_state
    assert loaded.context_state
    assert loaded.resume_state


@pytest.mark.parametrize(
    "field",
    [
        "working_state",
        "context_state",
        "resume_state",
    ],
)
def test_null_state_migration(
    tmp_path,
    field,
):
    store, session = create_session(
        tmp_path
    )

    path = store._path(
        session.id
    )

    raw = json.loads(
        path.read_text()
    )

    raw[field] = None

    path.write_text(
        json.dumps(
            raw
        )
    )

    loaded = store.get(
        session.id
    )

    assert getattr(
        loaded,
        field,
    ) is not None


def test_partial_nested_migration(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    path = store._path(
        session.id
    )

    raw = json.loads(
        path.read_text()
    )

    raw[
        "working_state"
    ] = {
        "objective": "x"
    }

    raw[
        "context_state"
    ] = {
        "summary": "y"
    }

    raw[
        "resume_state"
    ] = {
        "interrupted": True
    }

    path.write_text(
        json.dumps(
            raw
        )
    )

    loaded = store.get(
        session.id
    )

    assert "current_plan" in (
        loaded.working_state
    )

    assert "durable_facts" in (
        loaded.context_state
    )

    assert "continuation_point" in (
        loaded.resume_state
    )


def test_schema_version_normalization(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    path = store._path(
        session.id
    )

    raw = json.loads(
        path.read_text()
    )

    raw[
        "schema_version"
    ] = 1

    path.write_text(
        json.dumps(
            raw
        )
    )

    loaded = store.get(
        session.id
    )

    assert (
        loaded.schema_version
        == SCHEMA_VERSION
    )


def test_objective_update(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    store.set_objective(
        session.id,
        "New objective",
    )

    loaded = store.get(
        session.id
    )

    assert (
        loaded.objective
        == "New objective"
    )

    assert (
        loaded.working_state[
            "objective"
        ]
        == "New objective"
    )


def test_plan_replace(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    store.replace_plan(
        session.id,
        [
            "a",
            "b",
        ],
    )

    assert store.get(
        session.id
    ).working_state[
        "current_plan"
    ] == [
        "a",
        "b",
    ]


def test_completed_append_and_dedupe(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    store.append_completed(
        session.id,
        "done",
    )

    store.append_completed(
        session.id,
        "done",
    )

    assert store.get(
        session.id
    ).working_state[
        "completed_work"
    ] == [
        "done"
    ]


def test_pending_replace(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        [
            "one",
            "two",
        ],
    )

    assert store.get(
        session.id
    ).working_state[
        "pending_work"
    ] == [
        "one",
        "two",
    ]


def test_blocker_add_dedupe_clear(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    store.add_blocker(
        session.id,
        "blocked",
    )

    store.add_blocker(
        session.id,
        "blocked",
    )

    loaded = store.get(
        session.id
    )

    assert loaded.working_state[
        "blockers"
    ] == [
        "blocked"
    ]

    store.clear_blocker(
        session.id,
        "blocked",
    )

    assert store.get(
        session.id
    ).working_state[
        "blockers"
    ] == []


def test_checkpoint(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    store.set_checkpoint(
        session.id,
        "checkpoint-1",
    )

    assert store.get(
        session.id
    ).working_state[
        "last_checkpoint"
    ] == "checkpoint-1"


def test_fact_add_and_dedupe(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    store.add_durable_fact(
        session.id,
        "fact",
    )

    store.add_durable_fact(
        session.id,
        "fact",
    )

    assert store.get(
        session.id
    ).context_state[
        "durable_facts"
    ] == [
        "fact"
    ]


def test_no_compaction_below_threshold(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    while len(
        loaded.history
    ) < COMPACTION_THRESHOLD:
        loaded.history.append(
            {
                "type": "instruction",
                "text": (
                    f"entry-"
                    f"{len(loaded.history)}"
                ),
            }
        )

    ctx = build_agent_context(
        loaded
    )

    assert ctx[
        "summary"
    ] is None

    assert len(
        ctx[
            "recent_history"
        ]
    ) == len(
        loaded.history
    )


def test_compaction_above_threshold(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    for i in range(
        30
    ):
        loaded.history.append(
            {
                "type": (
                    "instruction"
                    if i % 2 == 0
                    else "result"
                ),
                "text": f"entry-{i}",
            }
        )

    before = list(
        loaded.history
    )

    ctx = build_agent_context(
        loaded
    )

    assert ctx[
        "summary"
    ]

    assert len(
        ctx[
            "recent_history"
        ]
    ) == RECENT_HISTORY_WINDOW

    assert (
        loaded.context_state[
            "compacted_through"
        ]
        == (
            len(
                before
            )
            - RECENT_HISTORY_WINDOW
        )
    )

    assert loaded.history == before


def test_summary_deterministic(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    for i in range(
        30
    ):
        loaded.history.append(
            {
                "type": "instruction",
                "text": f"entry-{i}",
            }
        )

    first = build_agent_context(
        loaded
    )[
        "summary"
    ]

    second = build_agent_context(
        loaded
    )[
        "summary"
    ]

    assert first == second


def test_agent_context_has_working_state(
    tmp_path,
):
    store, session = create_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    ctx = build_agent_context(
        loaded
    )

    assert "working_state" in ctx
    assert "recent_history" in ctx
