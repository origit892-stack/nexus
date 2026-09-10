from pathlib import Path


def test_runner_never_marks_session_completed():
    source = Path(
        "nexus/sessions/runner.py"
    ).read_text()

    assert (
        'session.status = "COMPLETED"'
        not in source
    )


def test_ui_explicitly_marks_completed():
    source = Path(
        "nexus/ui/app.py"
    ).read_text()

    assert (
        'if action == "complete":'
        in source
    )

    assert (
        'session.status = "COMPLETED"'
        in source
    )


def test_runner_uses_ready_state():
    source = Path(
        "nexus/sessions/runner.py"
    ).read_text()

    assert (
        'session.status = "READY"'
        in source
    )
