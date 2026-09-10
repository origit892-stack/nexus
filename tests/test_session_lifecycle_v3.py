from nexus.sessions.lifecycle import (
    ACTIVE,
    COMPLETED,
    INTERRUPTED,
    READY,
    SessionLifecycle,
    status_after_interrupt,
    status_after_turn,
    status_after_user_complete,
    status_after_user_continue,
)


def test_turn_complete_is_not_session_complete():
    assert (
        status_after_turn(ACTIVE)
        == READY
    )

    assert (
        status_after_turn(INTERRUPTED)
        == READY
    )


def test_only_user_complete_marks_completed():
    assert (
        status_after_user_complete()
        == COMPLETED
    )


def test_completed_session_can_continue():
    lifecycle = SessionLifecycle(
        COMPLETED
    )

    assert lifecycle.can_continue


def test_completed_session_can_go_back():
    lifecycle = SessionLifecycle(
        COMPLETED
    )

    assert lifecycle.can_go_back


def test_user_can_reopen_completed_session():
    assert (
        status_after_user_continue()
        == ACTIVE
    )


def test_interrupt_is_resumable():
    assert (
        status_after_interrupt()
        == INTERRUPTED
    )

    assert SessionLifecycle(
        INTERRUPTED
    ).can_continue
