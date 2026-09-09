from __future__ import annotations

import json

import pytest

from nexus.sessions.store import (
    SessionStore,
)


def make_session(
    tmp_path,
):
    store = SessionStore(
        tmp_path
    )

    session = store.create(
        "Wave 3 objective",
        "Wave 3 Store",
    )

    return (
        store,
        session,
    )


def test_new_wave3_fields(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    loaded = store.get(
        session.id
    )

    state = loaded.working_state

    assert state[
        "active_item"
    ] is None

    assert state[
        "last_completed_item"
    ] is None

    assert state[
        "checkpoint_serial"
    ] == 0

    assert state[
        "auto_checkpoint"
    ] is True

    assert loaded.resume_state[
        "resume_requested_at"
    ] is None


def test_missing_wave3_fields_migrate(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    path = store._path(
        session.id
    )

    raw = json.loads(
        path.read_text()
    )

    for key in (
        "active_item",
        "last_completed_item",
        "checkpoint_serial",
        "auto_checkpoint",
    ):
        raw[
            "working_state"
        ].pop(
            key,
            None,
        )

    raw[
        "resume_state"
    ].pop(
        "resume_requested_at",
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

    assert loaded.working_state[
        "active_item"
    ] is None

    assert loaded.working_state[
        "checkpoint_serial"
    ] == 0

    assert loaded.working_state[
        "auto_checkpoint"
    ] is True

    assert loaded.resume_state[
        "resume_requested_at"
    ] is None


def test_null_wave3_values_migrate(
    tmp_path,
):
    store, session = make_session(
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
    ][
        "checkpoint_serial"
    ] = None

    raw[
        "working_state"
    ][
        "auto_checkpoint"
    ] = None

    path.write_text(
        json.dumps(
            raw
        )
    )

    loaded = store.get(
        session.id
    )

    assert loaded.working_state[
        "checkpoint_serial"
    ] == 0

    # Explicit null normalizes safely.
    assert isinstance(
        loaded.working_state[
            "auto_checkpoint"
        ],
        bool,
    )


def test_set_active_item(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.set_active_item(
        session.id,
        "active task",
    )

    assert store.get(
        session.id
    ).working_state[
        "active_item"
    ] == "active task"


def test_mark_done(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        [
            "one",
            "two",
        ],
    )

    store.set_active_item(
        session.id,
        "one",
    )

    store.mark_done(
        session.id,
        "one",
    )

    state = store.get(
        session.id
    ).working_state

    assert state[
        "completed_work"
    ] == [
        "one"
    ]

    assert state[
        "pending_work"
    ] == [
        "two"
    ]

    assert state[
        "active_item"
    ] is None

    assert state[
        "last_completed_item"
    ] == "one"


def test_mark_done_deduplicates(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.mark_done(
        session.id,
        "done",
    )

    store.mark_done(
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


def test_mark_done_rejects_blank(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    with pytest.raises(
        ValueError
    ):
        store.mark_done(
            session.id,
            "   ",
        )


def test_select_next_pending(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.replace_pending(
        session.id,
        [
            "done",
            "next",
            "later",
        ],
    )

    store.mark_done(
        session.id,
        "done",
    )

    selected = (
        store.select_next_pending(
            session.id
        )
    )

    assert selected == "next"

    assert store.get(
        session.id
    ).working_state[
        "active_item"
    ] == "next"


def test_select_next_pending_empty(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    assert (
        store.select_next_pending(
            session.id
        )
        is None
    )


def test_increment_checkpoint(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.increment_checkpoint(
        session.id,
        "checkpoint one",
    )

    first = store.get(
        session.id
    )

    assert first.working_state[
        "checkpoint_serial"
    ] == 1

    assert first.working_state[
        "last_checkpoint"
    ] == "checkpoint one"

    store.increment_checkpoint(
        session.id
    )

    second = store.get(
        session.id
    )

    assert second.working_state[
        "checkpoint_serial"
    ] == 2

    assert second.working_state[
        "last_checkpoint"
    ] == "checkpoint one"


def test_auto_checkpoint_toggle(
    tmp_path,
):
    store, session = make_session(
        tmp_path
    )

    store.set_auto_checkpoint(
        session.id,
        False,
    )

    assert store.get(
        session.id
    ).working_state[
        "auto_checkpoint"
    ] is False

    store.set_auto_checkpoint(
        session.id,
        True,
    )

    assert store.get(
        session.id
    ).working_state[
        "auto_checkpoint"
    ] is True
